# ANNCSU Viewer

A web viewer for street addresses and house numbers from the Italian National Archive of Street Numbers and Urban Roads (ANNCSU). Data is processed directly in the browser using [DuckDB WASM](https://duckdb.org/).

## Quick start

```shell
npm install
npm run dev
```

## Configuration

The application is configurable via Vite environment variables.

### Environment variables

| Variable | Description | Default |
|---|---|---|
| `VITE_COMUNE_NAME` | Municipality name displayed in the header and info panel | `del territorio nazionale` |
| `VITE_DATA_BASE_URL` | Base URL for parquet data files in production | `https://anncsu-open.github.io/anncsu-viewer` |
| `VITE_APP_MODE` | Deployment mode: `nazionale` (PMTiles + GeoParquet) or `comunale` (GeoParquet only) | `nazionale` |

Create a `.env` file in the project root:

```shell
VITE_COMUNE_NAME=del Comune di Vacone
```

Or pass the variable at build time:

```shell
VITE_COMUNE_NAME="del Comune di Vacone" npm run build
```

## Test

```shell
npx vitest run
```

## Credits

This project is derived from [overture-duckdb-wasm](https://github.com/fgravin/overture-duckdb-wasm) by Florent Gravin, released under the MIT license.
