# How releases are handled

Status: implemented (branch `release-archive`, 2026-09-21)

## Goal

Keep every monthly ANNCSU release, publish it on R2 as the original ZIP plus a
lossless Parquet copy, and describe the whole history in the Portolan catalog
with the STAC version extension, so that a consumer can fetch any past release
and, later, a DuckLake table can offer time-travel queries over it.

The ANNCSU portal serves only the latest release. Twelve past releases exist
only as a reconstruction from the consolidated parquet of
[mfortini/diff_ANNCSU](https://github.com/mfortini/diff_ANNCSU); the September
2026 release is an original download.

## Decisions

| Question | Decision |
|---|---|
| Version identifier | The release date in the upstream CSV name, `YYYY-MM-DD`. Never a git commit SHA. |
| Cloud-native copy per release | A lossless Parquet of the raw CSV: every row, the 19 original columns as text, no geometry. |
| Historical enriched GeoParquet | Not published. It stays in git LFS as an internal artifact. |
| Releases in scope | Thirteen, from 2025-09-03 to 2026-09-15. The July 2025 CSV found locally is left out for provenance homogeneity. |
| Where the big files live | R2 only, under `rilasci/<date>/`. The repository holds item JSON and an index, never ZIPs or raw Parquet. |
| Where the reconstruction tool lives | `scripts/rebuild_archive.py` in this repository, run locally once, kept out of commits for now. |
| Catalog shape | A third, tabular collection `rilasci` with one item per release, linked with the version extension. |

### Why the release date and not a commit SHA

A SHA is opaque where the date is self-describing, it exists for seven
releases only, it identifies the lossy derived GeoParquet rather than the
release, and git LFS is not a publication channel: its URLs need
authentication and redirects that a DuckDB client cannot follow. Rebases
rewrite SHAs too. Commit SHAs remain provenance, recorded where useful, and
the LFS object id of the enriched parquet is its sha256, the same number the
catalog already exposes as `file:checksum`.

### Why a lossless Parquet and not the enriched GeoParquet

The enriched GeoParquet keeps only rows with coordinates: 20,731,065 of
27,415,954 in September 2026, so 6,684,889 addresses, almost a quarter, are
dropped, and columns are added that the original does not have. It cannot
represent a release. The raw Parquet keeps every row and is the input a
future DuckLake table needs: one snapshot per release, built by diffing
consecutive raw Parquets on `PROGRESSIVO_ACCESSO`, which is unique across all
27,415,954 rows of the September release.

## Reconstruction fidelity

Verified on 2026-09-15, the one release with an original in hand.

The consolidated parquet filtered on `d_2026_09_15` yields 27,415,954 rows with
27,415,954 distinct `PROGRESSIVO_ACCESSO`, the same count as the original CSV.
The first reconstruction differed from the original by 1,673 bytes across
exactly 5,700 rows, all paired by `PROGRESSIVO_ACCESSO`, for two reasons:

- `QUOTA`: the portal never uses exponent notation and drops the zero before
  the decimal comma when the integer part is zero, writing `,0000717` and
  `-,055`. DuckDB's `CAST(double AS VARCHAR)` wrote `7,17e-05` for 3,986 rows
  and kept the leading zero for 1,713 more. The fix formats to seven fixed
  decimals, the maximum observed, trims trailing zeros and the separator, and
  removes a leading zero only when followed by the decimal mark.
- `SPECIFICITA`: one record, present in every release, carries `true` where
  the original has `T`, a boolean cast that happened when the consolidated
  parquet was built. The fix maps `true` back to `T` and `false` to `F`. No
  other text column in the 50 million rows carries such values.

After both fixes the reconstructed CSV has the original's exact size,
2,206,082,816 bytes, the same header, and the same md5 of the sorted content,
`bdc0f55e34c193bb729a8721fab557ac`. Only the row order differs, which the
portal does not define. The same method applies to the twelve earlier
releases, whose originals no longer exist anywhere; they are published as
reconstructions and labelled so.

## Published layout

```
r2:anncsu-data/                            = https://pub-…r2.dev/
├── catalog.json, indirizzi/, indirizzi-h3/, en/     as today
└── rilasci/
    ├── collection.json, README.md, AGENTS.md
    ├── releases.json                                the index, also in git
    ├── 2025-09-03/
    │   ├── 2025-09-03.json                          item, also in git
    │   ├── indirizzarioItalia_20250903.zip          R2 only
    │   └── INDIR_ITA_20250903.parquet               R2 only
    ├── …
    └── 2026-09-15/
        ├── 2026-09-15.json
        ├── indirizzarioItalia_20260915.zip
        └── INDIR_ITA_20260915.parquet
```

The repository mirrors the tree without the two large files per release.
`.gitignore` blocks `data/rilasci/**/*.zip` and `data/rilasci/**/*.parquet`;
the LFS rules in `.gitattributes` do not reach subdirectories, so without the
ignore a raw Parquet would land in git as a plain blob.

Item assets use **absolute https hrefs** to R2, which the spec allows
(`PORTO-CORE-023`). Every other href in the catalog stays relative. In the
workflow `rashid` runs with `--data-scope local`, so it verifies the bytes of
the assets present in the checkout and leaves the archive unread; a full
checksum pass over the archive is a deliberate, occasional run.

## The index

`data/rilasci/releases.json` is the single source of facts about the archive.
The generator builds items from it and never lists the bucket.

```json
{
  "releases": [
    {
      "date": "2026-09-15",
      "origin": "original",
      "note": "Download from the ANNCSU portal on 2026-09-19.",
      "zip": {"name": "indirizzarioItalia_20260915.zip", "size": 336123456, "sha256": "…"},
      "parquet": {"name": "INDIR_ITA_20260915.parquet", "size": 0, "sha256": "…", "rows": 27415954},
      "archived": "2026-09-20T10:00:00Z"
    }
  ]
}
```

`origin` is `original` or `reconstructed`. `archived` is written once, when
the entry is created, and never recomputed, so the generator stays
deterministic. The monthly workflow appends one entry; the backfill writes
thirteen.

## Catalog modelling

### The `rilasci` collection

Tabular, in the spec's sense: `rashid` classifies a collection as geospatial
when an item has a geometry, an asset has a spatial media type, or
`table:columns` names a geometry column. None applies here, so no thumbnail
and no style are required (verified with a probe catalog: 0 errors).

- `id: rilasci`, titles and descriptions in both languages, licence, providers
  and `via` as the other collections, `updated` as the other collections.
- `extent.spatial.bbox` is the area of interest, Italy, as `PORTO-FMT-036`
  prescribes for tabular collections; `extent.temporal` runs from the first
  release, open-ended.
- `table:columns`: the 19 original columns, all `varchar`, with descriptions
  taken from `columns.yaml`, which gains `LOCALITA'`, `COORD_X_COMUNE` and
  `COORD_Y_COMUNE` flagged `raw_only`.
- Links: `root`, `parent`, one `item` per release with a title,
  `latest-version` to the newest item, `via`, `license`, `agents`,
  `describedby`, the language alternates, the viewer.
- Extensions: Portolan, file, table, version, language.

### The release items

`rilasci/<date>/<date>.json`, one per release:

- `id` and `properties.version` equal to the date; `properties.datetime` at
  midnight UTC of the release date.
- `geometry: null` and no `bbox` key: STAC forbids a bbox on a null geometry,
  and this is what keeps the collection tabular.
- `properties.table:columns` and `table:row_count` from the index.
- `properties.description` states the origin: original download, or
  reconstruction from diff_ANNCSU with the verified method.
- Assets: `data`, the raw Parquet, `application/vnd.apache.parquet`, roles
  `["data"]`; `source`, the ZIP, `application/zip`, roles `["source"]`. Both
  with `file:size` and multihash `file:checksum` from the index.
- Links: `root`, `parent`, `collection`, `via`, `predecessor-version` and
  `successor-version` to the neighbouring releases where they exist, the
  language alternate.

### The live collections

`indirizzi` and `indirizzi-h3` gain `version` equal to the current release
date, a `derived_from` link to the item of that release, and a
`version-history` link to the `rilasci` collection. Their descriptions state
that they hold the georeferenced addresses only, with both counts.

## Pipeline changes

`scripts/update_data.py`, after the download:

1. Write the ZIP it already holds in memory to
   `data/rilasci/<date>/indirizzarioItalia_<ymd>.zip`.
2. Convert the extracted CSV to `INDIR_ITA_<ymd>.parquet` with DuckDB:
   `read_csv` with `;` delimiter, header, no quoting, every column as
   `VARCHAR`, empty field as NULL; rows ordered by `CODICE_ISTAT`,
   `PROGRESSIVO_NAZIONALE`, `PROGRESSIVO_ACCESSO` so the output is
   deterministic whatever the CSV order; ZSTD compression.
3. Compute sizes, sha256 and row count, and append the entry to
   `releases.json` with `origin: original`.

The new step runs before the enrichment, on the CSV that is already on disk,
and adds roughly one minute and 650 MB of scratch space to the run.

`.github/workflows/update-data.yml` uploads `data/rilasci/<date>/` to R2 with
`rclone copy` and commits `releases.json` with the data. The catalog workflow
then runs as today, builds the items from the index, and publishes
`rilasci/**/*.json` with `rclone copy`, never `sync`: a sync from a checkout
that lacks the ZIPs would delete them from the bucket.

## Backfill

A one-off, run locally, with `scripts/rebuild_archive.py`: the reconstruction
script moved from `~/Downloads/anncsu_backup/` with the two fidelity fixes,
extended to produce the raw Parquet and the index entries with the same code
the pipeline uses.

1. For each of the twelve reconstructed releases: rebuild the ZIP from the
   consolidated parquet, convert to raw Parquet, compute facts, append to the
   index with `origin: reconstructed`.
2. For 2026-09-15: use the original ZIP, `origin: original`.
3. Upload `data/rilasci/` files to R2 with `rclone copy`, about 8.5 GB.
4. Commit `releases.json` and let the catalog workflow generate the items.

The consolidated parquet, 250 MB, stays an external input and does not enter
the repository. The script stays uncommitted for now, by decision.

## Tests

- Index parsing and validation: dates ordered, unique, origin in the allowed
  set, checksums multihash-ready.
- Raw conversion on a fixture CSV: row count preserved, every column
  `VARCHAR`, empty fields null, deterministic bytes across two runs.
- Item builder: null geometry and no bbox, version fields, predecessor and
  successor links only where a neighbour exists, absolute asset hrefs, facts
  copied from the index.
- Collection builder: tabular signals only, `latest-version` to the newest
  item, one `item` link per release.
- Live collections: `version`, `derived_from`, `version-history`.
- Conformance: `rashid check --schema --data-scope local` over the fixture
  tree with two releases, in both languages, no errors and no warnings.
- Determinism of the whole build, as today.

## Out of scope

- DuckLake time travel. It is the reason the raw Parquet is lossless, but the
  table itself is a later milestone.
- The July 2025 original CSV.
- Publishing historical enriched GeoParquets.

## Credits

The twelve reconstructed releases exist thanks to
[mfortini/diff_ANNCSU](https://github.com/mfortini/diff_ANNCSU), which
consolidated every monthly download since September 2025 into one parquet
with a presence flag per release. The catalog names it as the source of the
reconstructions in every reconstructed item and in the collection README.
