# How the stradario is archived

Status: phase 1 implemented (branch stradario-archive, 2026-11-24). Phase 2 not started.

## Goal

Keep every release of the ANNCSU street register (`getds.php?STRAD_ITA`, the
"stradario"), publish it on R2 as the portal's ZIP plus a lossless Parquet
copy, and describe the history in the Portolan catalog, the same way the
civici are handled in [how-releases-are-handled.md](how-releases-are-handled.md).
The 2025-01-28 release survives only as ondata's Parquet: it has no ZIP, and
its completeness against the original CSV cannot be verified.

Nobody archives the stradario regularly. ondata/archivio_anncsu holds one
release (2025-01-28), the Wayback Machine one capture (2026-01-14), and
mfortini/diff_ANNCSU holds only civici
(checked again on 2026-11-24: no stradario file, no street-only rows in the
consolidated Parquet). The portal serves only the latest release, so every
release the pipeline does not keep is lost. The September 2026 one already is.

The register is worth keeping for the 163,592 streets with no civici on
2026-11-02 (13.4% of 1,221,302). The civici cannot represent them: a street
appears in the civici only through its accesses.

## Decisions

| Question | Decision |
|---|---|
| Releases published | Originals only. Months without an original stradario get no item. |
| Months without an original | The collection README gives the query that derives the part with civici from `rilasci`. |
| Catalog shape | A fourth collection, `stradario`, tabular, one item per release, chained with the version extension. |
| Where the pipeline runs | Phase 1 inside `scripts/update_data.py`; phase 2 in its own script and workflow. The catalog and the bucket are identical in both phases. |
| Failure isolation | The stradario is saved before the civici start, so a civici failure cannot lose it. A stradario failure does not stop the civici. |
| Catalog after a stradario failure | Published anyway when the civici part succeeds; the run turns red afterwards. |
| Version identifier | The date in the CSV name, `STRAD_ITA_<ymd>.csv`, as for the civici. |
| Cloud-native copy | Parquet with the 9 columns as text, every row, no geometry. |

## What derives from the civici

For every street with at least one access, grouping the raw civici by street
reproduces the stradario row exactly, as text, in all nine columns:

```sql
SELECT CODICE_COMUNE, CODICE_ISTAT, PROGRESSIVO_NAZIONALE, CODICE_COMUNALE,
       ODONIMO, "LOCALITA'", count(*)::VARCHAR AS TOTALE_ACCESSI,
       DIZIONE_LINGUA1, DIZIONE_LINGUA2
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/<date>/INDIR_ITA_<ymd>.parquet')
GROUP BY ALL;
```

Measured on 2026-11-02 against the original: 1,057,710 streets, 0 rows
different in either direction. On 2026-01-14 one street differs: the original
civici CSV lists street 622113 three times (2,091 rows, 697 distinct), and the
civici archive, rebuilt from mfortini's deduplicated Parquet, keeps 697. The
query is therefore exact only where the civici release is exact.

This is why derived releases are not published: each would miss exactly the
streets that make the stradario worth keeping, and the rest is already in
`rilasci`. The README states this and gives the query.

## Releases available today

| Date | Source | Origin | ZIP |
|---|---|---|---|
| 2025-01-28 | `output/STRAD_ITA_20250128.parquet` in ondata/archivio_anncsu, a typed Parquet with `column9` | `third-party` | none |
| 2025-08-04 | a local copy of the portal's ZIP, saved in August 2025 | `original` | yes |
| 2026-01-14 | Wayback Machine capture of 2026-01-18 | `original` | yes |
| 2026-11-02 | the portal, downloaded on 2026-11-24 | `original` | yes |

Copies of all four are in `~/Downloads/anncsu_backup/`:
`STRAD_ITA_20250128_ondata.parquet`, `stradarioItalia_20250804.zip`,
`stradarioItalia_20260114_wayback.zip`, `stradarioItalia_20261102.zip`. The
2026-11-02 release is safe even if the portal moves on before phase 1 ships.

`third-party` is a new origin value: the ZIP is gone and the Parquet comes from
someone else's conversion of the CSV. ondata typed `PROGRESSIVO_NAZIONALE` and
`TOTALE_ACCESSI` as BIGINT. Casting them back to text is faithful only if the
originals always write these two columns as canonical integers (no leading
zeros, signs or spaces). The builder checks that on the three originals and
records the result in the item's note.

## The CSV defect

The January 2026 files of both datasets contain a record whose ODONIMO ends
with a line feed, written without quotes:

```
B242;065017;1345847;;STRADA PROV.LE DUECENTOSESSANTOTTO BIS
;;39;;;
```

Street 1345847 breaks one stradario record and its 39 civici records, 78 lines
in the civici CSV. DuckDB's strict `read_csv`, which `csv_to_raw_parquet` uses
today, stops on such a file. A release with this defect would fail the weekly
civici run as it stands, so the fix belongs to both datasets.

The shared reader rejoins a physical line that has too few fields with the
following ones, keeping the line feed inside the value. It is lossless and
deterministic, and it stops with an error when a record cannot be rebuilt
(too many fields, or the file ends mid-record). On a file without the defect
its output is byte-identical to today's raw Parquet. The enrichment path
(`csv_to_parquet`) must survive the same file without losing rows; whether it
reads through the shared reader is left to the builder.

## Published layout

```
r2:anncsu-data/
└── stradario/
    ├── collection.json, README.md, AGENTS.md
    ├── releases.json                          the index, also in git
    ├── 2025-01-28/
    │   ├── 2025-01-28.json                    item, also in git
    │   └── STRAD_ITA_20250128.parquet         R2 only
    └── 2026-11-02/
        ├── 2026-11-02.json
        ├── stradarioItalia_20261102.zip       R2 only
        └── STRAD_ITA_20261102.parquet         R2 only
```

The English tree gets `en/stradario/` with the same metadata. `.gitignore`
blocks `data/stradario/**/*.{zip,parquet,csv}`. Uploads of `stradario/` use
`rclone copy` with filters, never `sync`, for the reason given for `rilasci`.

## The index

`data/stradario/releases.json`, the same shape as `rilasci/releases.json`,
with two differences: `origin` may be `third-party`, and `zip` is `null` when
there is no ZIP. Validation accepts a null `zip` only for `third-party`.

The Parquet is written with DuckDB: `read_csv` through the shared reader, `;`
delimiter, header, no quoting, every column `VARCHAR`, empty field as NULL.
The tenth column produced by the trailing `;` (`column9`) is dropped after
checking it is empty on every row; a non-empty value stops the conversion.
Rows are ordered by `CODICE_ISTAT` and `TRY_CAST(PROGRESSIVO_NAZIONALE AS
BIGINT)`, ZSTD compression.

## Catalog modelling

The `stradario` collection follows `rilasci`:

- tabular: no geometry, no thumbnail, no style; `extent.spatial` is Italy,
  `extent.temporal` starts at the first release, open-ended;
- `table:columns` from `columns.yaml`, which gains `TOTALE_ACCESSI` in both
  languages; the description says it is computed from the civici of the same
  release (checked on 2026-09-15: equal on every street);
- one `item` link per release, `latest-version`, the language alternates,
  `via`, `license`, `agents`, `describedby`, the viewer;
- `updated` comes from the stradario index (the latest `archived`), so it does
  not depend on which workflow ran.

Each item mirrors a `rilasci` item: `geometry: null`, no `bbox`, `version` and
`datetime` from the date, `data` asset for the Parquet, `source` asset for the
ZIP when there is one, both with title and description in each language,
`predecessor-version` and `successor-version`. When a civici release has the
same date, the item links to it with `rel: related`, and the civici item links
back.

The root catalog gains a `child` link and a line in its description. The
`stradario` README lists the releases with their origin, names the known
gaps (2026-09-15 lost; no original for the months between the four releases
above), and gives the derivation query.

## Two phases

### Phase 1: inside the weekly run

Deadline: merged before the portal's next release, expected in early December
2026. The weekly run is on Mondays.

- A new module in `scripts/` holds what both phases share: the remote date
  from the ZIP tail, the download, the shared reader, the raw Parquet writer
  for both datasets, the index entry. It depends on `duckdb` and `httpx` only,
  so the phase 2 script stays light. `update_data.py` archives the civici
  through it.
- The stradario runs as its own invocation, in its own step at the start of
  `update-data.yml`, and uploads `data/stradario/` to R2 and commits
  `data/stradario/releases.json` before the civici start. A civici failure in
  the same run, an exception or a runner killed during enrichment, leaves the
  stradario release safe. The step compares the remote date with the latest
  date in the stradario index and does nothing when they match.
- A stradario failure does not stop the civici. The civici steps run, upload
  and commit as today.
- The catalog is built and published whenever the civici part succeeds,
  including a run where the civici are already up to date, whatever happened
  to the stradario. `update-data.yml` calls `build-catalog.yml` with
  `workflow_call` instead of the `workflow_run` trigger, so a green run does
  not build the catalog twice. When the civici part fails, the catalog is not
  built, as today: the gate exists so that a failed data update does not
  publish metadata describing stale data. A stradario release saved in that
  run reaches the catalog at the next build.
- After the catalog, the run turns red if the stradario step failed, with the
  stradario error in the log. A stradario failure is never silent and never
  holds back the civici catalog.
- `build-catalog.yml` publishes the stradario metadata and commits
  `data/stradario` with the rest of the catalog. It keeps `workflow_dispatch`.

### Phase 2: its own script and workflow

- `scripts/update_stradario.py`, a PEP 723 script on the shared module, and
  `.github/workflows/update-stradario.yml`, weekly, without the LFS checkout.
  It carries over the phase 1 step unchanged: archive, upload, commit, then
  build the catalog.
- The stradario step leaves `update-data.yml` and `update_data.py`.
- Both data workflows commit to `main` and can start the catalog build. The
  data workflows and `build-catalog.yml` get concurrency groups so that two
  pushes or two catalog builds never run at once (builder's call: groups, not a
  schedule offset, because a manual dispatch ignores the schedule).

The invariant: from the same index, both phases produce the same catalog bytes
and the same objects under `stradario/` on R2. Phase 2 changes no path, name,
index field or catalog text.

## Backfill

Run once, locally, through the shared module, with the four files above:
convert, compute facts, append to the index with the right origin and a note
naming the source, upload `data/stradario/` to R2 with `rclone copy`. About
90 MB in total. Then commit the index and let the catalog workflow build the
items.

## Tests

- Shared reader: the January record as a fixture, for both datasets; a clean
  file gives the same bytes as today; a record with too many fields and a file
  ending mid-record both fail.
- Stradario conversion: `column9` dropped, a non-empty `column9` fails, row
  count kept, deterministic bytes over two runs.
- Index: `third-party` accepted with a null `zip`, rejected with a null `zip`
  for any other origin.
- Pipeline: a stradario failure leaves the civici processed and the run red;
  an up-to-date stradario is skipped while the civici still run.
- Workflow, checked once by hand with `workflow_dispatch` and an input that
  forces the stradario step to fail: the civici upload, the catalog is
  published, and the run ends red. A forced civici failure leaves the
  stradario on R2 and in git, and the catalog unbuilt.
- Catalog: collection and items pass rashid 0.4.0 with no errors or warnings;
  `related` links resolve in both directions; an item without ZIP has no
  `source` asset; the phase 1 and phase 2 builds are byte-identical from the
  same index.

## Out of scope

- Derived stradario releases (decided above).
- A live "current stradario" collection: `latest-version` points at it.
- Using the stradario in the viewer.
- Replacing the reconstructed civici release of 2026-01-14 with the original
  from the Wayback Machine. Worth doing, as separate work: the original has
  1,394 duplicate rows and the line-feed record that the reconstruction lacks.
- Regional `STRAD_<REG>` files and DuckLake.

## Left to the builder

The module's name and API, the backfill command line, how the stradario
invocation is selected (a flag or a separate entry point), how the workflow
carries the stradario outcome to the final step, the reader's implementation,
ordering tie-breaks, the `.gitignore` lines, and the exact catalog texts.
