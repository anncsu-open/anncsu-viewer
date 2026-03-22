# Data Pipeline Design

## Overview

Automated pipeline to download, convert, and version the ANNCSU Italian address dataset as GeoParquet.

## Data Source

- **URL**: `https://anncsu.open.agenziaentrate.gov.it/age-inspire/opendata/anncsu/getds.php?INDIR_ITA`
- **Format**: ZIP archive containing a single CSV file
- **CSV naming convention**: `INDIR_ITA_YYYYMMDD.csv` (date embedded in filename)
- **Size**: ~274 MB (compressed zip - March 2026), ~18 columns per row
- **Schema**: Defined at `https://www.anncsu.gov.it/.allegati/metadata_indirizzario.json`
- **Coordinate system**: ETRF2000 (lon/lat in decimal degrees)
- **Key coordinate fields**: `COORD_X_COMUNE` (longitude), `COORD_Y_COMUNE` (latitude)

## Freshness Detection Strategy

The ANNCSU server does not provide a `Last-Modified` header, and `HEAD` requests return 403 (Akamai CDN). The date of the dataset is embedded in the CSV filename inside the zip archive.

### Approach

1. **Download only the tail of the zip** (~64 KB range request) to read the zip central directory
2. **Extract the CSV filename** and parse the date from `INDIR_ITA_YYYYMMDD.csv`
3. **Compare with the last git commit date** of `data/anncsu-indirizzi.parquet`
4. **Skip download** if the remote date is not newer than the local commit date

### Why this works

- ZIP files store the central directory (file listing) at the end of the archive
- A range request for the last 64 KB is sufficient to read all filenames
- This avoids downloading the full ~274 MB file just to check if it changed
- The git commit date serves as a reliable timestamp of when the data was last updated

### Edge cases

| Scenario | Behavior |
|---|---|
| No existing parquet file | Always download |
| Cannot parse date from zip | Always download |
| Range request fails | Fall back to full download |
| Remote date == local date | Skip (already up to date) |

## Conversion Pipeline

```
ZIP (remote) → CSV (extracted) → DuckDB (in-memory) → Parquet → GeoParquet
```

### Steps

1. **Download** full zip archive via HTTP GET
2. **Extract** CSV to temporary file in `data/`
3. **Load into DuckDB** with `read_csv`, filtering rows with valid coordinates
4. **Create point geometries** using `ST_Point(longitude, latitude)` via DuckDB spatial extension
5. **Export as Parquet** with ZSTD compression
6. **Enhance with geoparquet-io**: add bbox metadata and Hilbert spatial sorting
7. **Clean up** temporary CSV

### DuckDB schema

All original columns are preserved, plus:
- `longitude` (DOUBLE) — cast from `COORD_X_COMUNE`
- `latitude` (DOUBLE) — cast from `COORD_Y_COMUNE`
- `geometry` (GEOMETRY) — point created from lon/lat

Rows without coordinates are excluded (`WHERE COORD_X_COMUNE IS NOT NULL AND COORD_Y_COMUNE IS NOT NULL`).

## Output

- **File**: `data/anncsu-indirizzi.parquet`
- **Format**: GeoParquet with bbox metadata and Hilbert curve spatial sorting
- **Compression**: ZSTD

## Versioning Strategy

The GeoParquet file is committed directly to the git repository in the `data/` directory.

### Git commit flow (GitHub Action)

1. Run the update script
2. If the file changed, stage `data/anncsu-indirizzi.parquet`
3. Commit with message: `data: update ANNCSU dataset (YYYY-MM-DD)` where the date comes from the CSV filename
4. Push to the repository

### Considerations

- **File size**: The parquet file with ZSTD compression should be significantly smaller than the raw CSV (~274 MB zip). If it exceeds GitHub's 100 MB limit, Git LFS should be configured for `data/*.parquet`.
- **History growth**: Each update replaces the file, so git history will grow. Periodic shallow clones or LFS mitigate this.
- **Branch**: Commits go to `main` directly (data-only change, no code impact).

## Script Execution

The script uses PEP 723 inline metadata for self-contained dependencies:

```shell
uv run scripts/update_data.py
```

Dependencies are resolved automatically by `uv`:
- `duckdb` — CSV loading, spatial extension, parquet export
- `geoparquet-io` — bbox metadata and spatial sorting
- `httpx` — HTTP client with range request support

## GitHub Action Schedule

```yaml
schedule:
  - cron: '0 6 * * *'  # Every day at 06:00 UTC
```

The freshness check only downloads ~64 KB (zip tail) to detect changes. The full download (~274 MB) only happens when the dataset has actually been updated. This makes a daily schedule lightweight and ensures the data is kept as fresh as possible.
