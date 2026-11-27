# ANNCSU comuni gazetteer

The comuni that have at least one address in ANNCSU, in one Parquet file in the index format of the STAC [gazetteer](https://github.com/cholmes/stac-gazetteer/blob/main/gazetteer/v1.0.0/README.md) extension. Each comune has its name, its province, its Istat code as `feature_id` and the bounding box of its access points. Names in another language, and spellings with a space in place of the apostrophe, are extra rows. Rows are sorted by `name_norm`, so a client finds a comune by name with a few HTTP range requests and no server; [`@cngeo/geocoder-core`](https://github.com/cholmes/cng-map-widgets/tree/main/packages/geocoder-core) reads this collection as it is.

The `feature_id` is the key the `indirizzi-index` collection uses to look up the streets of a comune. The data comes from the ANNCSU release of 2 November 2026.

## Files

| File | Rows | Row groups | Size |
|---|---|---|---|
| [`comuni.parquet`](../../gazetteer/2026-11-02/comuni.parquet) | 5,821 | 2 × 4,096 rows | 0.4 MB |

The file has no geometry column. The position of a comune is its `bbox`,
computed from its access points: it is narrower than the comune's territory,
but enough to bring the map to the comune.

## How to read it

A client normalizes the typed text with `nfd-strip-marks-lower/1`, the same
function that produced `name_norm`: NFD decomposition, diacritics removed,
lowercase, characters other than letters, digits, spaces, apostrophes and
hyphens removed, repeated spaces collapsed. It then reads the Parquet footer,
picks from the min/max statistics of `name_norm` the row groups that can hold
the prefix it looks for, and downloads only those with HTTP range requests.
The file is small, so a client can also read it whole.

[`@cngeo/geocoder-core`](https://github.com/cholmes/cng-map-widgets/tree/main/packages/geocoder-core), from the cng-map-widgets project,
takes the asset whose roles include `gazetteer-index` and plans its reads with
the `gazetteer:*` fields. The
[gazetteer extension](https://github.com/cholmes/stac-gazetteer/blob/main/gazetteer/v1.0.0/README.md) defines the file format and those
fields.

With DuckDB, the two comuni named Castro, told apart by their province:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT name, parent_name, feature_id, bbox
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/gazetteer/2026-11-02/comuni.parquet')
WHERE name_norm = 'castro';
```

## Alternate names and the address index

A row whose `alt_of` is set is another name for the same comune: its name in
another language from the Istat list, with the language in `name_lang` (Bozen
for Bolzano), or its name written with a space in place of the apostrophe, so
that typing "sant ambrogio" finds Sant'Ambrogio di Torino. To count comuni or
join them to other data, keep the rows where `alt_of` is null.

The `feature_id` is the comune's Istat code, six digits as text. The
[`indirizzi-index`](../indirizzi-index/) collection holds the same value in its
`codice_istat` column, so a comune found here leads to its streets.

## Schema

| Column | Type | Description |
|---|---|---|
| `name` | varchar | The name to display, from the Istat list of comuni. On an alternate row it is the name in another language, or the same name when the row only changes name_norm. |
| `name_norm` | varchar | The name normalized by nfd-strip-marks-lower/1: NFD decomposition, diacritics removed, lowercase, characters other than letters, digits, spaces, apostrophes and hyphens removed, repeated spaces collapsed. It is the sort column, compared byte by byte. |
| `level` | integer | Administrative level, always 3: the level of comuni in geoBoundaries (ADM3) and in Who's On First (localadmin). |
| `country` | varchar | ISO 3166-1 alpha-3 country code, always ITA. |
| `feature_id` | varchar | Istat code of the comune, six digits as text. Alternate rows repeat the code of their comune. It is the value of the codice_istat column in the address index. |
| `country_name` | varchar | Country name, always Italia. |
| `parent_name` | varchar | Name of the province, the supra-municipal territorial unit of Istat. It tells apart comuni with the same name. |
| `parent_id` | varchar | Istat code of the supra-municipal territorial unit. |
| `name_lang` | varchar | ISO 639-3 language of the name, for example deu or slv, on rows in another language. Null on the other rows. |
| `alt_of` | varchar | Null on the main row. On an alternate row, the feature_id of the comune the row is another name of. |
| `source` | varchar | Source of the row, always anncsu. |
| `addresses` | integer | Number of georeferenced access points of the comune in the release, including those ANNCSU places outside the comune boundary. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Bounding box of the comune's access points in WGS84 degrees, leaving out those outside the comune boundary; if all of them are, it covers all of them. It is narrower than the comune's territory. |

## Provenance

The file is built by `scripts/build_geocoding_index.py`, in the
[https://github.com/anncsu-open/anncsu-viewer](https://github.com/anncsu-open/anncsu-viewer) repository, from the georeferenced access points of the
[`indirizzi`](../indirizzi/) collection and from the [Istat list of Italian
comuni](https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv), which gives the names, the provinces and the names in
other languages. The original source of the addresses is the [ANNCSU open data
portal](https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/), held by the Agenzia delle Entrate and Istat. This
catalog is a copy derived from it.

## Licence

The data is published under the [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/) licence, SPDX identifier `CC-BY-4.0`. The official ANNCSU pages cite EU implementing regulation 2023/138 on high-value datasets, which mandates this licence for the address series, but do not state it in full. Anyone who needs certainty for a commercial reuse should ask the Agenzia delle Entrate.

The Istat list of comuni is also published under CC BY 4.0. A reuse of the
file must credit both ANNCSU and Istat.

## Generated automatically

Do not edit this file by hand: it is rewritten every time the catalog is
generated. The sources live in `scripts/catalog/` in the repository; the facts
about the files are in `gazetteer/index.json`, written by
`scripts/build_geocoding_index.py`.
