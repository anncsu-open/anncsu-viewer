# Data catalog

The ANNCSU data served from Cloudflare R2 comes with a catalog: a small set of
JSON and Markdown files that describe what the data is, where each file lives,
what the columns mean, and how to draw it on a map. It follows
[Portolan](https://github.com/portolan-sdi/portolan-spec), a profile of the STAC standard for cloud-native geospatial data.

You do not need to know STAC to use the data. The catalog is there so that
tools, and people who arrive without context, can find their way without
reading this repository first.

The catalog is generated from the data by a script, not written by hand. The
design decisions behind it, and the Portolan requirements they satisfy, are in
[docs/how-to-portolan.md](docs/how-to-portolan.md).

## Using the data

Everything is served from `https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev`.
Start at `catalog.json` and follow the links, or go straight to a file if you
already know what you want.

List what the catalog holds:

```shell
curl -s https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/catalog.json \
  | jq -r '.links[] | select(.rel == "child") | "\(.title) — \(.href)"'
```

Query the whole dataset with DuckDB, straight over HTTP. Rows are spatially
sorted, so a filter on an area or a municipality reads only the parts of the
file it needs:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT ODONIMO, CIVICO, ESPONENTE, NOME_COMUNE
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/anncsu-indirizzi.parquet')
WHERE CODICE_ISTAT = '058091'
LIMIT 10;
```

For a single municipality the H3 tiles are far smaller than the full file,
around 0.66 MB each against 1 GB. `comuni-h3.json` maps each municipality to the cells that contain its addresses, which is how the viewer avoids downloading everything:

```shell
curl -s https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/comuni-h3.json \
  | jq -r '.[] | select(.nome_comune == "Roma") | .h3_cells[]'
```

```sql
SELECT count(*)
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/tiles/h3_cell=851fb467fffffff/851fb467fffffff.parquet')
WHERE CODICE_ISTAT = '058091';
```

To draw the data, use the PMTiles archive with the MapLibre style the catalog
publishes. The style is a complete, self-contained JSON that MapLibre GL JS
loads directly, so nothing has to be assembled by hand.

What the columns mean is in `table:columns` inside each `collection.json`, and
in the schema table of each collection README. Both come from the same source,
so they cannot disagree.

## Working on the catalog

Regenerate it from whatever is currently in `data/`:

```shell
uv run scripts/build_catalog.py
```

Validate it with the Portolan validator. This is the same check the workflow
runs as a gate, so a clean run here means CI will pass:

```shell
uv run --with 'rashid>=0.1.8,<0.2.0' rashid check data/ --schema
```

Run the generator's tests:

```shell
uv run scripts/test_build_catalog.py
```

Check the published copy against the live bucket. This verifies range requests
and CORS on the server rather than the metadata:

```shell
uv run --with 'rashid>=0.1.8,<0.2.0' rashid check data/ --live \
  --live-base-url https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev
```

## Where the files are

`data/` is a 1:1 image of the bucket root, so the catalog is generated there and published by the existing rclone sync alongside the data.

```
data/                                  = the public bucket root
├── catalog.json                       generated
├── README.md, AGENTS.md               generated
├── anncsu-indirizzi.parquet           from the pipeline
├── anncsu-indirizzi.pmtiles           from the pipeline
├── comuni.json, comuni-h3.json        from the pipeline
├── tiles/h3_cell=*/*.parquet          from the pipeline
├── indirizzi/                         collection: the whole dataset as one file
│   ├── collection.json
│   ├── README.md, AGENTS.md
│   ├── thumbnail.png
│   └── styles/indirizzi.json
└── indirizzi-h3/                      collection: the same data, split into tiles
    └── ...                            same shape
```

Data files stay where they are, so the frontend, the sync, and every published
URL keep working. Everything the catalog points at is a relative path climbing
one level, such as `../anncsu-indirizzi.parquet`.

The hand-written sources live outside `data/`, in `scripts/catalog/`:

| File | What it holds |
|---|---|
| `columns.yaml` | Type and Italian description for every column |
| `*.md.tmpl` | README and AGENTS templates |
| `styles/*.json` | MapLibre GL style files, copied verbatim when published |

## Making changes

**Edit the source, never the generated output.** Everything the generator writes
under `data/` is overwritten on the next run.

To change a column description, edit `columns.yaml`. The same text feeds the
JSON and the README schema table, so it is written once.

To change how the data looks on a map, edit the MapLibre style in
`scripts/catalog/styles/`.

To add a collection, give it a directory with `collection.json`, `README.md`,
and `AGENTS.md`, which Portolan requires together, then add a link to it from
the root catalog. Validate before committing: the check catches a link pointing
at a directory that does not exist yet.

When the upstream schema changes, the generator stops instead of guessing. It
compares `columns.yaml` against the real parquet schema and fails when a column
has no description, or when the file describes a column that is gone.

## How it gets published

A workflow runs after "Update ANNCSU Data" finishes, and can also be started by
hand. It generates the catalog, validates it, commits when something changed,
uploads only the catalog files, then checks the result against the live bucket.

Validation is the gate: on failure nothing is committed and nothing is uploaded.

The generator is deterministic, so a run over unchanged data produces identical
files and the workflow commits nothing. Re-running it is always safe.

## Two things to know

**Do not expect the partition glob to expand over HTTPS.** The catalog publishes a glob pattern over the tiles, but plain HTTPS gives no directory listing, so a reader cannot discover the files from the pattern alone. Use `comuni-h3.json` to find the cells you need, or the S3 endpoint if you hold credentials.

**The licence is stated but not confirmed at the source.** The catalog declares
`CC-BY-4.0`. The official ANNCSU pages cite EU implementing regulation 2023/138
on high-value datasets, which mandates that licence for address data, but they
do not write it out. If you need certainty for a commercial reuse, check with
the Agenzia delle Entrate.
