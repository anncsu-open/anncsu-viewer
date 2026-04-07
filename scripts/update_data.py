# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "geoparquet-io>=1.0.0b2",
#     "gpio-pmtiles",
#     "duckdb>=1.2.0",
#     "httpx",
#     "typer",
# ]
# ///
"""Download ANNCSU Italian address dataset and convert to GeoParquet.

Usage:
    uv run scripts/update_data.py
    uv run scripts/update_data.py --force   # skip freshness check

The script downloads the full Italian address CSV from the ANNCSU open data
portal, loads it into DuckDB, creates point geometries from coordinates,
and exports the result as a spatially-sorted GeoParquet file.

It checks whether the remote dataset is newer than the last update by
comparing the date embedded in the CSV filename inside the zip archive
with the last commit date of the existing GeoParquet file.
"""

import io
import re
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import httpx
import typer

ANNCSU_URL = (
    "https://anncsu.open.agenziaentrate.gov.it"
    "/age-inspire/opendata/anncsu/getds.php?INDIR_ITA"
)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "anncsu-indirizzi.parquet"
PMTILES_FILE = OUTPUT_DIR / "anncsu-indirizzi.pmtiles"
TILES_DIR = OUTPUT_DIR / "tiles"
COMUNI_FILE = OUTPUT_DIR / "comuni.json"
COMUNI_H3_FILE = OUTPUT_DIR / "comuni-h3.json"
BOUNDARIES_FILE = OUTPUT_DIR / "istat-boundaries.parquet"
MARKER_FILE = OUTPUT_DIR / ".last_remote_date"
H3_RESOLUTION = 5
TAIL_SIZE = 65536
DOWNLOAD_TIMEOUT = 600
MAX_RETRIES = 3
RETRY_WAIT = 30


def _check_server_available() -> None:
    """Raise early if the ANNCSU server is not reachable or returns an error.

    Uses a single-byte GET range request instead of HEAD because the
    Akamai CDN in front of the ANNCSU portal blocks HEAD requests with 403.
    """
    print("Checking ANNCSU server availability ...")
    try:
        response = httpx.get(
            ANNCSU_URL,
            headers={"Range": "bytes=0-0"},
            follow_redirects=True,
            timeout=30,
        )
    except httpx.TransportError as exc:
        raise SystemExit(f"ANNCSU server unreachable: {exc}") from exc
    if response.status_code == 403:
        raise SystemExit(
            f"ANNCSU server returned 403 Forbidden — the service may be "
            f"temporarily unavailable. Retry later."
        )
    if response.status_code >= 400:
        raise SystemExit(
            f"ANNCSU server returned HTTP {response.status_code}. Retry later."
        )
    print("Server is available")


def get_remote_date() -> datetime | None:
    """Fetch the zip tail to extract the CSV date from its filename."""
    print("Checking remote dataset date ...")
    try:
        response = httpx.get(
            ANNCSU_URL,
            headers={"Range": f"bytes=-{TAIL_SIZE}"},
            follow_redirects=True,
            timeout=60,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        print(f"Warning: could not fetch remote date (HTTP {exc.response.status_code})")
        return None
    except httpx.TransportError as exc:
        print(f"Warning: could not fetch remote date ({exc})")
        return None

    matches = re.findall(rb"INDIR_ITA_(\d{8})\.csv", response.content)
    if not matches:
        print("Could not determine remote date, will proceed with download")
        return None

    date_str = matches[-1].decode()
    remote_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
    print(f"Remote dataset date: {remote_date.date()}")
    return remote_date


def get_local_date() -> datetime | None:
    """Read the last downloaded dataset date from the marker file."""
    if not MARKER_FILE.exists():
        return None

    try:
        date_str = MARKER_FILE.read_text().strip()
        local_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
        print(f"Last downloaded dataset date: {local_date.date()}")
        return local_date
    except (ValueError, OSError):
        return None


def save_remote_date(remote_date: datetime) -> None:
    """Persist the remote dataset date to the marker file after a successful download."""
    MARKER_FILE.write_text(remote_date.strftime("%Y%m%d"))


def is_update_needed(remote_date: datetime | None = None) -> bool:
    """Check if the remote dataset is newer than the local one."""
    if remote_date is None:
        remote_date = get_remote_date()
    if remote_date is None:
        return True

    local_date = get_local_date()
    if local_date is None:
        print("No marker file found, will download")
        return True

    if remote_date > local_date:
        print("Remote dataset is newer, will download")
        return True

    print("Local data is up to date, skipping download")
    return False


def download_and_extract() -> Path:
    """Download the ANNCSU zip and extract the CSV."""
    print(f"Downloading from {ANNCSU_URL} ...")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            data = io.BytesIO()
            with httpx.stream(
                "GET", ANNCSU_URL, follow_redirects=True, timeout=DOWNLOAD_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                    data.write(chunk)
                    downloaded += len(chunk)
                    mb = downloaded / (1024 * 1024)
                    if total:
                        pct = downloaded * 100 / total
                        print(f"  {mb:.0f} MB / {total / (1024 * 1024):.0f} MB ({pct:.0f}%)")
                    else:
                        print(f"  {mb:.0f} MB downloaded ...")
            break
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            if attempt == MAX_RETRIES:
                raise SystemExit(f"Download failed after {MAX_RETRIES} attempts: {exc}") from exc
            print(f"Attempt {attempt}/{MAX_RETRIES} failed ({exc}), retrying in {RETRY_WAIT}s ...")
            time.sleep(RETRY_WAIT)
    print(f"Downloaded {downloaded / (1024 * 1024):.1f} MB")

    data.seek(0)
    with zipfile.ZipFile(data) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise RuntimeError(f"No CSV found in zip. Contents: {zf.namelist()}")
        csv_name = csv_names[0]
        print(f"Extracting {csv_name} ...")
        zf.extract(csv_name, OUTPUT_DIR)
        return OUTPUT_DIR / csv_name


def csv_to_parquet(csv_path: Path) -> Path:
    """Load CSV into DuckDB, join with comuni, create geometries, and export as Parquet."""
    if not COMUNI_FILE.exists():
        raise RuntimeError(
            f"{COMUNI_FILE} not found. Run generate_comuni.py first: "
            "uv run scripts/generate_comuni.py"
        )

    print("Loading CSV into DuckDB ...")
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("INSTALL h3 FROM community; LOAD h3;")

    # Load comuni lookup table from JSON array
    con.execute(f"""
        CREATE TABLE comuni AS
        SELECT codice_istat, nome_comune
        FROM read_json('{COMUNI_FILE}')
    """)

    comuni_count = con.execute("SELECT COUNT(*) FROM comuni").fetchone()[0]
    print(f"Loaded {comuni_count:,} comuni from lookup table")

    con.execute(f"""
        CREATE TABLE addresses AS
        SELECT
            a.CODICE_COMUNE,
            a.CODICE_ISTAT,
            c.nome_comune AS NOME_COMUNE,
            a.PROGRESSIVO_NAZIONALE,
            a.CODICE_COMUNALE,
            a.ODONIMO,
            a.DIZIONE_LINGUA1,
            a.DIZIONE_LINGUA2,
            a.PROGRESSIVO_ACCESSO,
            a.CODICE_COMUNALE_ACCESSO,
            a.CIVICO,
            a.ESPONENTE,
            a.SPECIFICITA,
            a.METRICO,
            a.PROGRESSIVO_SNC,
            CAST(REPLACE(a.COORD_X_COMUNE, ',', '.') AS DOUBLE) AS longitude,
            CAST(REPLACE(a.COORD_Y_COMUNE, ',', '.') AS DOUBLE) AS latitude,
            a.QUOTA,
            a.METODO,
            ST_Point(
                CAST(REPLACE(a.COORD_X_COMUNE, ',', '.') AS DOUBLE),
                CAST(REPLACE(a.COORD_Y_COMUNE, ',', '.') AS DOUBLE)
            ) AS geometry
        FROM read_csv(
            '{csv_path}',
            header=true,
            auto_detect=true,
            ignore_errors=true
        ) a
        LEFT JOIN comuni c ON a.CODICE_ISTAT = c.codice_istat
        WHERE a.COORD_X_COMUNE IS NOT NULL
          AND a.COORD_Y_COMUNE IS NOT NULL
    """)

    row_count = con.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
    print(f"Loaded {row_count:,} addresses with coordinates")

    # Flag out-of-bounds addresses using ISTAT municipal boundaries
    if BOUNDARIES_FILE.exists():
        print("Flagging out-of-bounds addresses using ISTAT boundaries ...")
        con.execute(f"""
            CREATE TABLE boundaries AS
            SELECT codice_istat, geometry
            FROM read_parquet('{BOUNDARIES_FILE}')
        """)

        # Threshold in meters: addresses outside their boundary but within
        # this distance are not flagged as out-of-bounds (geocoding tolerance).
        oob_threshold_m = 110

        con.execute(f"""
            CREATE TABLE addresses_validated AS
            SELECT
                a.*,
                CASE
                    WHEN b.geometry IS NULL THEN NULL
                    WHEN ST_Contains(b.geometry, a.geometry) THEN NULL
                    ELSE ROUND(ST_Distance(b.geometry, a.geometry)::DOUBLE * 111000, 2)
                END AS oob_distance_m,
                CASE
                    WHEN b.geometry IS NULL THEN NULL
                    WHEN ST_Contains(b.geometry, a.geometry) THEN false
                    WHEN ST_Distance(b.geometry, a.geometry)::DOUBLE * 111000 > {oob_threshold_m} THEN true
                    ELSE false
                END AS out_of_bounds
            FROM addresses a
            LEFT JOIN boundaries b ON a.CODICE_ISTAT = b.codice_istat
        """)

        con.execute("DROP TABLE addresses")
        con.execute("ALTER TABLE addresses_validated RENAME TO addresses")

        oob_count = con.execute(
            "SELECT COUNT(*) FROM addresses WHERE out_of_bounds = true"
        ).fetchone()[0]
        total = con.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
        print(f"Flagged {oob_count:,} out-of-bounds addresses out of {total:,}")
    else:
        print(f"Warning: {BOUNDARIES_FILE} not found, skipping out-of-bounds detection")

    print(f"Writing Parquet to {OUTPUT_FILE} ...")
    con.execute(f"""
        COPY addresses TO '{OUTPUT_FILE}'
        (FORMAT PARQUET, COMPRESSION ZSTD)
    """)

    con.close()
    return OUTPUT_FILE


def enhance_with_geoparquet(parquet_path: Path) -> None:
    """Add bbox and spatial sorting using geoparquet-io.

    Uses two passes with a disk flush in between to keep peak memory
    under ~5.5 GB (single-pass peaks at ~11 GB on 18M rows, which
    exceeds the 7 GB available on GitHub Actions runners).
    """
    import gc

    import geoparquet_io as gpio

    print("Adding bbox ...")
    gpio.read(str(parquet_path)).add_bbox().write(str(parquet_path))
    gc.collect()

    print("Spatial sorting (Hilbert) ...")
    gpio.read(str(parquet_path)).sort_hilbert().write(str(parquet_path))
    gc.collect()

    print("GeoParquet enhancement complete")


def partition_h3_tiles(parquet_path: Path) -> Path:
    """Partition GeoParquet into H3 tiles for nazionale search."""
    import geoparquet_io as gpio

    print(f"Partitioning into H3 tiles (resolution {H3_RESOLUTION}) ...")
    gpio.read(str(parquet_path)) \
        .add_h3(resolution=H3_RESOLUTION) \
        .partition_by_h3(str(TILES_DIR), resolution=H3_RESOLUTION)

    tile_count = len(list(TILES_DIR.glob("**/*.parquet")))
    print(f"Created {tile_count} H3 tiles in {TILES_DIR}")
    return TILES_DIR


def convert_to_pmtiles(parquet_path: Path) -> Path:
    """Convert GeoParquet to PMTiles for map visualization."""
    from gpio_pmtiles import create_pmtiles_from_geoparquet

    print(f"Converting to PMTiles: {PMTILES_FILE} ...")
    if PMTILES_FILE.exists():
        PMTILES_FILE.unlink()
    create_pmtiles_from_geoparquet(
        str(parquet_path),
        str(PMTILES_FILE),
        layer="addresses",
        include_cols="ODONIMO,CIVICO,ESPONENTE,CODICE_ISTAT,NOME_COMUNE,oob_distance_m,out_of_bounds",
        verbose=True,
    )
    size_mb = PMTILES_FILE.stat().st_size / (1024 * 1024)
    print(f"PMTiles conversion complete ({size_mb:.1f} MB)")
    return PMTILES_FILE


def main(
    force: bool = typer.Option(False, "--force", help="Skip freshness check and force re-download"),
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _check_server_available()

    remote_date = get_remote_date()

    if not force and not is_update_needed(remote_date):
        return

    csv_path = download_and_extract()

    try:
        parquet_path = csv_to_parquet(csv_path)
        enhance_with_geoparquet(parquet_path)
        convert_to_pmtiles(parquet_path)
        partition_h3_tiles(parquet_path)
    finally:
        if csv_path.exists():
            csv_path.unlink()
            print("Cleaned up temporary CSV")

    if remote_date is not None:
        save_remote_date(remote_date)
        print(f"Saved dataset date marker: {remote_date.date()}")

    size_mb = parquet_path.stat().st_size / (1024 * 1024)
    print(f"Done! GeoParquet: {parquet_path} ({size_mb:.1f} MB)")
    if PMTILES_FILE.exists():
        pm_size_mb = PMTILES_FILE.stat().st_size / (1024 * 1024)
        print(f"Done! PMTiles: {PMTILES_FILE} ({pm_size_mb:.1f} MB)")


if __name__ == "__main__":
    typer.run(main)
