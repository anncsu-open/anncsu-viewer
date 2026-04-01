# Data Pipeline Design

## Overview

Automated pipeline to download, convert, partition, and host the ANNCSU Italian address dataset (~14M addresses) as GeoParquet, PMTiles, and H3 tiles. Data is served from Cloudflare R2 and consumed entirely in the browser via DuckDB WASM and MapLibre GL.

## Data Source

- **URL**: `https://anncsu.open.agenziaentrate.gov.it/age-inspire/opendata/anncsu/getds.php?INDIR_ITA`
- **Format**: ZIP archive containing a single CSV file
- **CSV naming convention**: `INDIR_ITA_YYYYMMDD.csv` (date embedded in filename)
- **Size**: ~274 MB (compressed zip), ~14M rows, ~18 columns per row
- **Schema**: Defined at `https://www.anncsu.gov.it/.allegati/metadata_indirizzario.json`
- **Coordinate system**: ETRF2000 (lon/lat in decimal degrees)
- **Key coordinate fields**: `COORD_X_COMUNE` (longitude), `COORD_Y_COMUNE` (latitude)
- **Note**: coordinates use comma as decimal separator (Italian locale)

## Architecture

### Deployment modes

The application supports two modes configured via `VITE_APP_MODE`:

| | Nazionale | Comunale |
|---|---|---|
| **Map visualization** | PMTiles (vector tiles, range requests) | DuckDB WASM → GeoJSON → MapLibre |
| **Address search** | H3 tiles loaded on demand per comune | Single GeoParquet loaded entirely |
| **Search UX** | Unified field: comune + address | Direct address search |
| **Data size** | ~14M addresses, ~1.5 GB total | Small (single comune) |

### Data hosting — Cloudflare R2

All data files are hosted on a public Cloudflare R2 bucket.

**Why R2** (after trying alternatives):
- **GitHub Pages**: doesn't serve Git LFS files (returns pointer bytes instead of content)
- **GitHub Releases**: double-redirect (302→302→200) with signed temporary URLs breaks PMTiles range requests (each request gets a different URL)
- **raw.githubusercontent.com**: works but has rate limits
- **Cloudflare R2**: stable URLs, CORS support, range requests, free egress, no rate limits

**Configuration:**
- Bucket: `anncsu-data`
- Public URL: `https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev`
- CORS: allows `https://anncsu-open.github.io` + `http://localhost:5173`, `Range` header required
- Upload: `rclone` with `--transfers=32` for parallel uploads

### Files on R2

| File | Size | Purpose |
|---|---|---|
| `anncsu-indirizzi.parquet` | ~679 MB | Full GeoParquet (comunale mode, pipeline source) |
| `anncsu-indirizzi.pmtiles` | ~214 MB | PMTiles vector tiles (nazionale map visualization) |
| `comuni.json` | ~small | ISTAT municipality lookup (codice_istat → nome_comune) |
| `comuni-h3.json` | ~479 KB | Municipality → H3 cells mapping (nazionale search) |
| `tiles/h3_cell=<id>/<id>.parquet` | ~500 KB each | ~1400 H3 tile parquets (nazionale search) |

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
ZIP (remote)
  → CSV (extracted)
    → DuckDB (in-memory, JOIN with comuni.json)
      → GeoParquet (bbox + Hilbert sorting)
        → PMTiles (via gpio-pmtiles)
        → H3 tiles (via geoparquet-io partition_by_h3)
          → Cloudflare R2 (via rclone)
```

### Steps

1. **Download** full zip archive via HTTP GET
2. **Extract** CSV to temporary file in `data/`
3. **Load into DuckDB** with `read_csv`, filtering rows with valid coordinates
4. **JOIN with `comuni.json`** to add `NOME_COMUNE` column
5. **Create point geometries** using `ST_Point(longitude, latitude)` via DuckDB spatial extension
6. **Export as Parquet** with ZSTD compression
7. **Enhance with geoparquet-io**: add bbox metadata and Hilbert spatial sorting
8. **Convert to PMTiles** via `gpio-pmtiles` for map visualization
9. **Partition into H3 tiles** via `geoparquet-io` `partition_by_h3()` at resolution 5
10. **Clean up** temporary CSV

### DuckDB schema

All original columns are preserved, plus:
- `NOME_COMUNE` (VARCHAR) — from JOIN with `comuni.json`
- `longitude` (DOUBLE) — cast from `COORD_X_COMUNE` (comma → dot decimal separator)
- `latitude` (DOUBLE) — cast from `COORD_Y_COMUNE` (comma → dot decimal separator)
- `geometry` (GEOMETRY) — point created from lon/lat
- `oob_distance_m` (DOUBLE) — distance in meters from the declared municipality boundary (`NULL` if inside)
- `out_of_bounds` (BOOLEAN) — `true` if `oob_distance_m > 110m`

Rows without coordinates are excluded (`WHERE COORD_X_COMUNE IS NOT NULL AND COORD_Y_COMUNE IS NOT NULL`).

## H3 Tiling Strategy

### Purpose

DuckDB WASM in the browser cannot load the full 679 MB parquet file (malloc fails at ~2 GB). H3 tiles partition the data into ~1400 small files (~500 KB each) that can be loaded on demand.

### How it works

1. `geoparquet-io` partitions the GeoParquet by H3 cell at resolution 5 (~250 km² hexagons)
2. `comuni-h3.json` maps each `CODICE_ISTAT` to its H3 cells
3. When a user selects a comune, the frontend downloads only the relevant tiles (typically 1-3 tiles)
4. DuckDB WASM loads the tiles as buffers and queries them with `CODICE_ISTAT` filter

### Frontend flow (nazionale mode)

```
User types "Vacone" → selects from autocomplete
  → frontend reads comuni-h3.json → finds H3 cells for Vacone
    → fetches tile parquets from R2
      → registers as DuckDB buffers
        → SQL query with CODICE_ISTAT filter
          → address list for autocomplete
```

### Pre-fetch optimization

When the user types a combined query ("Vacone, Via Roma"), the frontend:
1. Detects the comma separator and recognizes the comune
2. Starts downloading H3 tiles **in background** while the user types the address
3. Shows an address preview under the suggestion once tiles are loaded
4. On click, the address list is ready immediately

## Out-of-Bounds Detection

### Problem

Some ANNCSU addresses have coordinates that fall outside their declared municipality boundaries. For example, an address with `CODICE_ISTAT` of Roccafiorita appearing at coordinates in Frascati (hundreds of km away). See [issue #1](https://github.com/anncsu-open/anncsu-viewer/issues/1).

### Approach — ISTAT boundary validation

During ingestion, each address is validated against the official ISTAT municipality boundary polygons:

1. Load ISTAT boundaries from `data/istat-boundaries.parquet` (generated by `scripts/generate_boundaries.py`)
2. For each address, LEFT JOIN with the boundary polygon of its declared `CODICE_ISTAT`
3. Check `ST_Contains(boundary, point)`:
   - **Inside** → `oob_distance_m = NULL`, `out_of_bounds = false`
   - **Outside** → `oob_distance_m` = distance in meters from the boundary
   - `out_of_bounds = true` only if `oob_distance_m > 110` (geocoding tolerance threshold matching the max ISTAT boundary gap of ~110m)
   - Addresses within 110m of the boundary are not flagged, accounting for coordinate imprecision in both the ANNCSU geocoding and ISTAT boundary vertices

### Boundary data source

ISTAT publishes non-generalized administrative boundary shapefiles annually:
- **URL**: `https://www.istat.it/storage/cartografia/confini_amministrativi/non_generalizzati/2025/Limiti01012025.zip`
- **Format**: Shapefile (EPSG:32632 UTM32N), converted to GeoParquet (WGS84) by `generate_boundaries.py`
- **Coverage**: ~7,900 municipalities with precise polygon boundaries

### Boundary topology fix

The raw ISTAT boundaries have two topological defects ([issue #2](https://github.com/anncsu-open/anncsu-viewer/issues/2)):

1. **5 invalid polygons** (Acquaviva delle Fonti, Rutigliano, Sannicandro di Bari, Santa Ninfa, Bronte)
2. **6 genuine gaps** between adjacent municipalities (up to ~110m), where no other municipality covers the space between them

`generate_boundaries.py` applies two post-processing steps after CRS transformation:

1. **`shapely.make_valid()`** on all invalid polygons
2. **`shapely.snap()`** on each gap pair with `tolerance = gap * 1.5`, then `make_valid()` again

One marine gap (Arzachena–La Maddalena, 154m) is excluded as it represents sea between islands.

The diagnostic query in `scripts/find_gaps.sql` can be used to verify gap closure.

### Previous approach considered

An H3-based approach was initially considered (checking if the address's H3 cell at resolution 5 was in the expected cell list for the municipality). However, this failed because `comuni-h3.json` is derived from the same potentially-incorrect address data, so misplaced addresses pollute the cell list. ISTAT boundaries are an independent authoritative source.

### Output

Flagged addresses get an `out_of_bounds` boolean column in the parquet. The frontend can:
- Display them with a different color/icon on the map
- Filter them out of search results
- Show a warning in the popup

## Output Files

| File | Format | Purpose |
|---|---|---|
| `anncsu-indirizzi.parquet` | GeoParquet (ZSTD, bbox, Hilbert sorted) | Full dataset, comunale mode source |
| `anncsu-indirizzi.pmtiles` | PMTiles (vector tiles) | Nazionale map visualization |
| `istat-boundaries.parquet` | GeoParquet | ISTAT municipality boundary polygons |
| `comuni.json` | JSON array | ISTAT municipality lookup |
| `comuni-h3.json` | JSON array | Municipality → H3 cell mapping |
| `tiles/h3_cell=<id>/<id>.parquet` | GeoParquet | H3 partitioned tiles for search |

## Versioning Strategy

Data files are hosted on Cloudflare R2 (not in git). Only metadata files (`comuni.json`, `comuni-h3.json`) and the LFS-tracked parquet/PMTiles are in the repository.

### GitHub Action flow

1. Run `update_data.py`
2. If data changed, upload all files to R2 via `rclone --transfers=32`
3. No git commit needed for data (R2 is the source of truth)

## Script Execution

Scripts use PEP 723 inline metadata for self-contained dependencies, runnable via `uv`:

```shell
uv run scripts/update_data.py        # Full pipeline: download → convert → partition
uv run scripts/generate_comuni.py    # Generate ISTAT municipality lookup
uv run scripts/generate_comuni_h3.py # Map municipalities to H3 cells
```

Dependencies resolved automatically by `uv`:
- `duckdb` — CSV loading, spatial extension, parquet export
- `geoparquet-io` — bbox metadata, spatial sorting, H3 partitioning
- `gpio-pmtiles` — GeoParquet to PMTiles conversion
- `httpx` — HTTP client with range request support

## GitHub Action Schedule

```yaml
schedule:
  - cron: '0 6 * * 1'  # Every Monday at 06:00 UTC
```

The freshness check downloads only ~64 KB (zip tail) to detect changes. The full download (~274 MB) and conversion only happens when the dataset has been updated. Weekly schedule balances freshness with resource usage.

### Required secrets

| Secret | Purpose |
|---|---|
| `R2_ACCESS_KEY_ID` | Cloudflare R2 API access |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 API secret |
| `CLOUDFLARE_ACCOUNT_ID` | R2 endpoint URL |
