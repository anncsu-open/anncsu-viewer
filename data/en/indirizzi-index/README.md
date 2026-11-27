# ANNCSU address index

The streets and access points of ANNCSU in two Parquet files sorted by comune. A client reads the rows of one comune with HTTP range requests and no server, and looks up first the street, then the house number. The format is described by a [draft STAC extension](https://github.com/anncsu-open/anncsu-viewer/blob/main/geocoding/address-index/v0.1.0/README.md) kept in this repository.

The `codice_istat` column holds the `feature_id` of the `gazetteer` collection: the gazetteer finds the comune, this index finds the address. An application that always works inside a single comune can use this index alone, with the comune's code. The data comes from the ANNCSU release of 2 November 2026.

## Files

| File | Rows | Row groups | Size |
|---|---|---|---|
| [`vie.parquet`](../../indirizzi-index/2026-11-02/vie.parquet) | 786,969 | 193 × 4,096 rows | 42.7 MB |
| [`civici.parquet`](../../indirizzi-index/2026-11-02/civici.parquet) | 20,728,959 | 633 × 32,768 rows | 425.3 MB |

The files have no geometry column. The position of a street is the `bbox` of
its access points; the position of an access point is its `lon`, `lat` pair.

## How to read it

Finding an address takes two steps, both with HTTP range requests.

1. The street. The client reads the footer of `vie.parquet`, picks from the
   min/max statistics of `codice_istat` the row groups of the comune and
   downloads only those: the rows of a comune are contiguous, about 15,000 for
   Rome, the largest comune. It then normalizes the typed name with
   `anncsu-odonimo/1` and compares it in memory with `name_norm`.
2. The house number. Once the street is found, the client picks in
   `civici.parquet` the row groups that hold the `codice_istat`, `street_id`
   pair, again from the statistics, and looks for the number and suffix among
   those rows.

`anncsu-odonimo/1` applies NFD decomposition, removes diacritics, lowercases,
replaces with a space every character other than letters, digits, spaces and
hyphens, and collapses repeated spaces. So "LIBERTA'", as ANNCSU writes it, and
a typed "libertà" both give "liberta". The gazetteer uses another function,
which keeps apostrophes: a query is normalized with the function of the file
being searched. The test cases of both functions are in
[`geocoding/normalization-vectors.json`](https://github.com/anncsu-open/anncsu-viewer/blob/main/geocoding/normalization-vectors.json).

The [draft address-index extension](https://github.com/anncsu-open/anncsu-viewer/blob/main/geocoding/address-index/v0.1.0/README.md) defines the file
format and the `address_index:*` fields, and comes with a JSON schema and an
example collection.

With DuckDB, the streets of Vacone (Istat code 057072) named San Giovanni, then
the house numbers of one of them:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT street_id, name, numbers, number_min, number_max
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/indirizzi-index/2026-11-02/vie.parquet')
WHERE codice_istat = '057072' AND name_norm LIKE '%san giovanni%';

SELECT number, suffix, lon, lat
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/indirizzi-index/2026-11-02/civici.parquet')
WHERE codice_istat = '057072' AND street_id = 468312
ORDER BY number;
```

## The link to the gazetteer

The `codice_istat` column holds the comune's Istat code, which is the
`feature_id` of the [`gazetteer`](../gazetteer/) collection. An application
finds the comune in the gazetteer, then the address here. An application that
always works in the same comune already knows the code and reads only these
two files.

In `vie.parquet`, rows whose `alt_of` is set are the names of a street in
another language, from the ANNCSU `DIZIONE_LINGUA1` and `DIZIONE_LINGUA2`
columns: they keep the street's `street_id`, so they lead to the same house
numbers. To count streets, keep the rows where `alt_of` is null.

## Schema

### Streets (`vie.parquet`)

| Column | Type | Description |
|---|---|---|
| `codice_istat` | varchar | Istat code of the comune, six digits as text: the feature_id of the gazetteer. First sort column. |
| `comune` | varchar | Name of the comune from the Istat list, to display a result without reading the gazetteer. |
| `street_id` | bigint | Stable identifier of the street, the PROGRESSIVO_NAZIONALE of ANNCSU. |
| `name` | varchar | The street name to display: the ODONIMO as published, or the name in another language on an alternate row. |
| `name_norm` | varchar | The name normalized by anncsu-odonimo/1: NFD decomposition, diacritics removed, lowercase, every character other than letters, digits, spaces and hyphens replaced by a space, repeated spaces collapsed. So LIBERTA' and libertà both give liberta. |
| `name_lang` | varchar | ISO 639-3 language of the name on rows in another language, when it is known. Null on the main row. |
| `alt_of` | bigint | Null on the main row. On a row in another language, the street_id of the street. |
| `numbers` | integer | Number of access points on the street. |
| `number_min` | integer | The lowest house number on the street. Null if no access point has a number. |
| `number_max` | integer | The highest house number on the street. With number_min it tells apart streets with the same name. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Bounding box of the street's access points in WGS84 degrees, leaving out those outside the comune boundary; if all of them are, it covers all of them. |

### Access points (`civici.parquet`)

| Column | Type | Description |
|---|---|---|
| `codice_istat` | varchar | Istat code of the comune, six digits as text: the feature_id of the gazetteer. First sort column. |
| `street_id` | bigint | The street of the access point: the street_id of the streets file, the PROGRESSIVO_NAZIONALE of ANNCSU. |
| `id` | bigint | Stable identifier of the access point, the PROGRESSIVO_ACCESSO of ANNCSU. |
| `number` | integer | The house number, the CIVICO of ANNCSU. Null where the source has none. |
| `suffix` | varchar | The ESPONENTE of ANNCSU, the letter part of the house number: A, B, BIS, 1. |
| `specificita` | varchar | The SPECIFICITA of ANNCSU, which holds among other things the red and black numbering of Genova, Firenze and Savona. |
| `metrico` | varchar | The METRICO of ANNCSU: the house number in metres, in comuni that use metric numbering. Text, as in the source. |
| `out_of_bounds` | boolean | True when the access point falls more than 110 metres outside the boundary of its comune, according to Istat boundaries. Null when the comune has no matching boundary. |
| `lon` | double | Longitude of the access point in degrees, WGS84 (EPSG:4326). |
| `lat` | double | Latitude of the access point in degrees, WGS84 (EPSG:4326). |

## Provenance

The two files are built by `scripts/build_geocoding_index.py`, in the
[https://github.com/anncsu-open/anncsu-viewer](https://github.com/anncsu-open/anncsu-viewer) repository, from the georeferenced access points of the
[`indirizzi`](../indirizzi/) collection. The comune name in the `comune`
column comes from the [Istat list of Italian comuni](https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv). The
original source of the streets and access points is the [ANNCSU open data
portal](https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/), held by the Agenzia delle Entrate and Istat. This
catalog is a copy derived from it.

## Licence

The data is published under the [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/) licence, SPDX identifier `CC-BY-4.0`. The official ANNCSU pages cite EU implementing regulation 2023/138 on high-value datasets, which mandates this licence for the address series, but do not state it in full. Anyone who needs certainty for a commercial reuse should ask the Agenzia delle Entrate.

The Istat list of comuni is also published under CC BY 4.0. A reuse of the
files must credit both ANNCSU and Istat.

## Generated automatically

Do not edit this file by hand: it is rewritten every time the catalog is
generated. The sources live in `scripts/catalog/` in the repository; the facts
about the files are in `indirizzi-index/index.json`, written by
`scripts/build_geocoding_index.py`.
