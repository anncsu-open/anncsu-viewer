# ANNCSU Viewer

A web viewer for Italian street addresses and house numbers from the [ANNCSU](https://www.anncsu.gov.it/) (Archivio Nazionale dei Numeri Civici e delle Strade Urbane). Built with Vue 3, MapLibre GL, and DuckDB WASM — all data processing happens directly in the browser with no backend required.

**Live demo:** [anncsu-open.github.io/anncsu-viewer](https://anncsu-open.github.io/anncsu-viewer/)

## Architecture

The application supports two deployment modes:

### Nazionale mode (default)

Designed to serve the entire Italian address dataset (~25M addresses).

- **Map visualization** — [PMTiles](https://protomaps.com/docs/pmtiles) vector tiles served from Cloudflare R2, loaded progressively via HTTP range requests
- **Address search** — Data partitioned into [H3](https://h3geo.org/) hexagonal tiles (~1400 files, ~500KB each). Only the tiles covering the selected municipality are downloaded on demand
- **Smart geocoding** — Single search field with automatic detection of municipality names, addresses, and combined queries (e.g. "Roma, Via Appia 1")
- **Search ranking** — Jaccard similarity with multi-term matching and LRU cache

### Comunale mode

Designed for a single municipality deployment with a small dataset.

- **Map + search** — Single GeoParquet file loaded entirely via DuckDB WASM
- **Simpler UX** — Direct address search without municipality selection

## Data pipeline

The dataset is downloaded from the [ANNCSU open data portal](https://anncsu.open.agenziaentrate.gov.it/) and converted through a Python pipeline:

```
CSV (zip) → DuckDB → GeoParquet → PMTiles + H3 tiles
```

Scripts are self-contained with [PEP 723](https://peps.python.org/pep-0723/) inline dependencies, runnable via [uv](https://docs.astral.sh/uv/):

```shell
uv run scripts/update_data.py        # Download, convert, and partition data
uv run scripts/generate_comuni.py    # Generate ISTAT municipality lookup
uv run scripts/generate_comuni_h3.py # Map municipalities to H3 cells
```

Data files are hosted on **Cloudflare R2** for public access with CORS and range request support. A [GitHub Action](.github/workflows/update-data.yml) runs weekly to check for updates and upload new data.

See [`scripts/DESIGN.md`](scripts/DESIGN.md) for detailed pipeline documentation.

## Quick start

```shell
npm install
npm run dev
```

## Configuration

The application is configurable via Vite environment variables in a `.env` file:

| Variable | Description | Default |
|---|---|---|
| `VITE_COMUNE_NAME` | Municipality name displayed in header and info panel | `del territorio nazionale` |
| `VITE_DATA_BASE_URL` | Base URL for data files (R2 bucket or local) | `https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev` |
| `VITE_APP_MODE` | `nazionale` (PMTiles + H3 tiles) or `comunale` (GeoParquet only) | `nazionale` |

Example for a municipal deployment:

```shell
VITE_COMUNE_NAME=del Comune di Vacone
VITE_DATA_BASE_URL=https://your-r2-bucket.r2.dev
VITE_APP_MODE=comunale
```

## Tech stack

- **Frontend** — [Vue 3](https://vuejs.org/) + [Pinia](https://pinia.vuejs.org/) + [Tailwind CSS](https://tailwindcss.com/)
- **Map** — [MapLibre GL JS](https://maplibre.org/) + [PMTiles](https://protomaps.com/docs/pmtiles)
- **Data** — [DuckDB WASM](https://duckdb.org/) + [GeoParquet](https://geoparquet.org/) + [H3](https://h3geo.org/)
- **Data pipeline** — Python + [geoparquet-io](https://github.com/geoparquet/geoparquet-io) + [gpio-pmtiles](https://github.com/geoparquet/gpio-pmtiles)
- **Hosting** — GitHub Pages (app) + Cloudflare R2 (data)
- **Design** — [Design System Italia](https://designers.italia.it/) (colors, Titillium Web font)

## Tests

```shell
npx vitest run
```

## License

MIT — see [LICENSE](LICENSE).

## Credits

This project is derived from [overture-duckdb-wasm](https://github.com/fgravin/overture-duckdb-wasm) by Florent Gravin, released under the MIT license.

Developed by [Geobeyond Srl](https://geobeyond.it/) within the PNRR Misura 1.3.1 programme for ANNCSU digitalization.
