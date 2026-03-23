# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.2.0",
#     "geoparquet-io>=1.0.0b2",
#     "httpx",
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

    print(f"Writing GeoParquet to {OUTPUT_FILE} ...")
    con.execute(f"""
        COPY boundaries TO '{OUTPUT_FILE}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    con.close()
    return OUTPUT_FILE


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
