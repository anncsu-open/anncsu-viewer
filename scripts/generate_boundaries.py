# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.2.0",
#     "geoparquet-io>=1.0.0b2",
#     "httpx",
#     "shapely>=2.0",
# ]
# ///
"""Download ISTAT municipality boundaries and convert to GeoParquet.

Usage:
    uv run scripts/generate_boundaries.py

Downloads the ISTAT administrative boundaries shapefile (comuni),
loads it into DuckDB with the spatial extension, and exports as
GeoParquet for use in out-of-bounds validation.
"""

import io
import zipfile
from pathlib import Path

import duckdb
import httpx

# ISTAT administrative boundaries - comuni (non-generalized for precision)
ISTAT_URL = (
    "https://www.istat.it/storage/cartografia/confini_amministrativi"
    "/non_generalizzati/2025/Limiti01012025.zip"
)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "istat-boundaries.parquet"


def download_and_extract_shapefile() -> Path:
    """Download ISTAT boundaries zip and extract the comuni shapefile."""
    print(f"Downloading ISTAT boundaries from {ISTAT_URL} ...")
    response = httpx.get(ISTAT_URL, follow_redirects=True, timeout=120)
    response.raise_for_status()
    print(f"Downloaded {len(response.content) / (1024 * 1024):.1f} MB")

    extract_dir = OUTPUT_DIR / "istat_tmp"
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        # Find the comuni shapefile (Com01012025_g directory)
        shp_files = [n for n in zf.namelist() if "Com" in n and n.endswith(".shp")]
        if not shp_files:
            raise RuntimeError(f"No comuni shapefile found. Contents: {zf.namelist()[:20]}")

        # Extract all files related to the shapefile
        shp_name = shp_files[0]
        base = shp_name.rsplit(".", 1)[0]
        for name in zf.namelist():
            if name.startswith(base.rsplit("/", 1)[0] if "/" in base else base[:10]):
                zf.extract(name, extract_dir)

        return extract_dir / shp_name


def shapefile_to_parquet(shp_path: Path) -> Path:
    """Load shapefile into DuckDB and export as GeoParquet."""
    print(f"Loading shapefile {shp_path.name} into DuckDB ...")
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    con.execute(f"""
        CREATE TABLE boundaries AS
        SELECT
            CAST(PRO_COM_T AS VARCHAR) AS codice_istat,
            COMUNE AS nome_comune,
            ST_FlipCoordinates(ST_Transform(geom, 'EPSG:32632', 'EPSG:4326')) AS geometry
        FROM ST_Read('{shp_path}')
    """)

    row_count = con.execute("SELECT COUNT(*) FROM boundaries").fetchone()[0]
    print(f"Loaded {row_count:,} municipality boundaries")

    fix_invalid_polygons(con)
    fix_topological_gaps(con)

    print(f"Writing GeoParquet to {OUTPUT_FILE} ...")
    con.execute(f"""
        COPY boundaries TO '{OUTPUT_FILE}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    con.close()
    return OUTPUT_FILE


def fix_invalid_polygons(con: duckdb.DuckDBPyConnection) -> None:
    """Fix geometrically invalid polygons using shapely.make_valid."""
    from shapely import from_wkb, make_valid, to_wkb

    invalid_rows = con.execute("""
        SELECT codice_istat, nome_comune, ST_AsWKB(geometry) AS wkb
        FROM boundaries
        WHERE NOT ST_IsValid(geometry)
    """).fetchall()

    if not invalid_rows:
        print("All polygons are valid")
        return

    print(f"Fixing {len(invalid_rows)} invalid polygons ...")
    for codice, nome, wkb in invalid_rows:
        geom = make_valid(from_wkb(wkb))
        fixed_wkb = to_wkb(geom)
        con.execute(
            "UPDATE boundaries SET geometry = ST_GeomFromWKB(?)"
            " WHERE codice_istat = ?",
            [fixed_wkb, codice],
        )
        print(f"  Fixed: {codice} {nome}")


# Marine gaps (islands separated by sea) — not real topology errors.
EXCLUDED_MARINE_GAPS = frozenset({
    ("090006", "090035"),  # Arzachena - La Maddalena
})


def fix_topological_gaps(con: duckdb.DuckDBPyConnection) -> None:
    """Close genuine topological gaps between adjacent municipalities.

    Finds pairs of municipalities that are close but don't touch and
    where no other municipality covers the space between them, then
    snaps one polygon to the other to close the gap.
    """
    from shapely import from_wkb, make_valid, snap, to_wkb

    gap_pairs = con.execute("""
        WITH candidates AS (
            SELECT
                a.codice_istat AS istat_a,
                b.codice_istat AS istat_b,
                ST_Distance(a.geometry, b.geometry)::DOUBLE AS gap_deg,
                ST_Centroid(ST_ShortestLine(a.geometry, b.geometry)) AS midpoint
            FROM boundaries a, boundaries b
            WHERE a.codice_istat < b.codice_istat
              AND ST_DWithin(a.geometry, b.geometry, 0.002)
              AND ST_Distance(a.geometry, b.geometry) > 0.000001
              AND NOT ST_Touches(a.geometry, b.geometry)
              AND NOT ST_Overlaps(a.geometry, b.geometry)
              AND NOT ST_Intersects(a.geometry, b.geometry)
        )
        SELECT c.istat_a, c.istat_b, c.gap_deg
        FROM candidates c
        WHERE NOT EXISTS (
            SELECT 1
            FROM boundaries o
            WHERE o.codice_istat != c.istat_a
              AND o.codice_istat != c.istat_b
              AND ST_Contains(o.geometry, c.midpoint)
        )
    """).fetchall()

    if not gap_pairs:
        print("No topological gaps found")
        return

    gaps_to_fix = [
        (ia, ib, gap)
        for ia, ib, gap in gap_pairs
        if (ia, ib) not in EXCLUDED_MARINE_GAPS
    ]

    if not gaps_to_fix:
        print("All gaps are excluded marine gaps")
        return

    print(f"Closing {len(gaps_to_fix)} topological gaps ...")
    for istat_a, istat_b, gap_deg in gaps_to_fix:
        wkb_a = con.execute(
            "SELECT ST_AsWKB(geometry) FROM boundaries WHERE codice_istat = ?",
            [istat_a],
        ).fetchone()[0]
        wkb_b = con.execute(
            "SELECT ST_AsWKB(geometry) FROM boundaries WHERE codice_istat = ?",
            [istat_b],
        ).fetchone()[0]

        geom_a = from_wkb(wkb_a)
        geom_b = from_wkb(wkb_b)

        tolerance = gap_deg * 1.5
        geom_b_snapped = make_valid(snap(geom_b, geom_a, tolerance))

        con.execute(
            "UPDATE boundaries SET geometry = ST_GeomFromWKB(?)"
            " WHERE codice_istat = ?",
            [to_wkb(geom_b_snapped), istat_b],
        )

        gap_m = gap_deg * 111000
        print(f"  Closed: {istat_a} <-> {istat_b} ({gap_m:.1f}m)")


def cleanup(extract_dir: Path) -> None:
    """Remove temporary extraction directory."""
    import shutil
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
        print("Cleaned up temporary files")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    extract_dir = OUTPUT_DIR / "istat_tmp"
    try:
        shp_path = download_and_extract_shapefile()
        parquet_path = shapefile_to_parquet(shp_path)

        size_mb = parquet_path.stat().st_size / (1024 * 1024)
        print(f"Done! {parquet_path} ({size_mb:.1f} MB)")
    finally:
        cleanup(extract_dir)


if __name__ == "__main__":
    main()
