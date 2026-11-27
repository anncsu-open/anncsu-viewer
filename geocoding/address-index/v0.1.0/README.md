# Address Index Extension

- **Title:** Address Index
- **Identifier:** <https://raw.githubusercontent.com/anncsu-open/anncsu-viewer/main/geocoding/address-index/v0.1.0/schema.json>
- **Field Name Prefix:** address_index
- **Scope:** Collection
- **Extension [Maturity Classification](https://github.com/radiantearth/stac-spec/tree/master/extensions/README.md#extension-maturity):** Proposal (draft, not yet published or proposed)
- **Owner:** anncsu-open

An **address index** lets a client find a street, then a house number on it,
inside a place it already knows, with no server: two sorted Parquet files read
over HTTP range requests.

It is the level below a [gazetteer](https://github.com/cholmes/stac-gazetteer).
A gazetteer turns "vacone" into a place and its bounding box; an address index
turns "via san giovanni 1" inside that place into an access point. The two
meet on one value: the address index's place column holds the gazetteer's
`feature_id`. For the Italian ANNCSU data, that value is the six-digit codice
ISTAT of the comune.

A client can use either one alone. An application that always works in one
comune, such as a municipality's own site, needs only the address index and
the comune's code.

- [JSON Schema](schema.json)
- [Example Collection](examples/collection.json)
- The normalization test vectors: [normalization-vectors.json](../../normalization-vectors.json)

## What this schema cannot check

The schema sees only the STAC JSON. A Collection can pass it and still be
unusable, because what a client relies on is inside the Parquet files:

- the rows ascend by the columns in `address_index:sort`, the first compared
  byte-wise on UTF-8, never by locale collation;
- the footer declares that order in `sorting_columns`;
- every row group has exact, untruncated min/max statistics on the columns a
  client searches (the place column, and `name_norm` or `street_id`);
- `name_norm` was produced by the normalization the Collection names.

A separate checker that opens the files is needed for that.
[`scripts/check_geocoding_index.py`](../../../scripts/check_geocoding_index.py)
is the one this repository runs.

## Fields

### Collection fields

| Field Name | Type | Description |
| --- | --- | --- |
| address_index:normalization | string | **REQUIRED.** The normalization that produced the streets' `name_norm`, e.g. `anncsu-odonimo/1`. |
| address_index:place_column | string | The column holding the place id, equal to a gazetteer's `feature_id`. Defaults to `codice_istat`. |

### Asset fields

They apply to the assets whose roles include `address-streets` or
`address-points`. A Collection declaring this extension needs one asset of
each. Each also carries the role `data`.

| Field Name | Type | Description |
| --- | --- | --- |
| address_index:sort | [string] | **REQUIRED.** The columns the rows ascend by, in order. |
| address_index:row_groups | integer | **REQUIRED.** The number of row groups, for planning range reads. |
| address_index:row_group_rows | integer | Rows per row group, when uniform. |
| address_index:footer_metadata_bytes | integer | The size of the Parquet thrift footer alone, so a client can fetch it with one exact range request. |

`file:size`, `file:checksum` and `table:row_count` come from the
[file](https://github.com/stac-extensions/file) and
[table](https://github.com/stac-extensions/table) extensions and belong on the
same assets.

## The two files

### Streets (`address-streets`)

One row per street, plus one row per other-language name of a street.

| Column | Type | Notes |
| --- | --- | --- |
| `codice_istat` | string | **Required.** The place column. |
| `comune` | string | The place's name, so a result needs no gazetteer to show it. |
| `street_id` | int64 | **Required.** The street's stable id (ANNCSU `PROGRESSIVO_NAZIONALE`). |
| `name` | string | **Required.** The name to show. |
| `name_norm` | string | **Required.** `name` by the declared normalization. |
| `name_lang` | string | ISO 639-3, on an other-language row when known. |
| `alt_of` | int64 | Null on the main row; the `street_id` on an other-language row. |
| `numbers` | int32 | **Required.** The street's access points. |
| `number_min`, `number_max` | int32 | The range of house numbers, which tells apart streets with the same name. |
| `bbox` | struct of four doubles | **Required.** `xmin, ymin, xmax, ymax`, from access points placed inside the place. |

Sorted by `codice_istat, name_norm, street_id`. A client reads the contiguous
run of one place by binary search on the statistics of `codice_istat`, then
matches the streets in memory.

### Access points (`address-points`)

One row per access point of the source, which can mean several rows for one
house number.

| Column | Type | Notes |
| --- | --- | --- |
| `codice_istat` | string | **Required.** The place column. |
| `street_id` | int64 | **Required.** The street. |
| `id` | int64 | **Required.** The access point's stable id (ANNCSU `PROGRESSIVO_ACCESSO`). |
| `number` | int32 | The house number, null where the source has none. |
| `suffix` | string | ANNCSU `ESPONENTE`: `A`, `B`, `BIS`, `1`… |
| `specificita` | string | ANNCSU `SPECIFICITA`, which holds the red/black numbering of Genova, Firenze and Savona. |
| `metrico` | string | ANNCSU `METRICO`, the kilometre marker of an access point with no number. |
| `out_of_bounds` | boolean | The source places the point outside its comune. |
| `lon`, `lat` | double | **Required.** The access point, EPSG:4326. |

Sorted by `codice_istat, street_id, number, suffix, specificita, id`, nulls
last. A client finds one street's access points by binary search on the
statistics of the first two columns. A row group that spans two streets is read
whole, which is correct.

## Normalization `anncsu-odonimo/1`

```
NFD -> drop combining marks (\p{M}) -> lowercase
    -> every character that is not a letter, digit, space or hyphen becomes a space
    -> collapse whitespace -> trim
```

ANNCSU writes accented letters as a trailing apostrophe ("VIA DELLA LIBERTA'")
and elides with one ("VIA D'ANNUNZIO"). Turning every apostrophe into a space
makes "LIBERTA'" and a typed "libertà" both "liberta", and "D'ANNUNZIO"
"d annunzio". The same goes for dots, so "G.MARCONI" is found by typing
"marconi".

It differs from the gazetteer's `nfd-strip-marks-lower/1`, which keeps
apostrophes and drops other punctuation. A client must fold a query with the
normalization of the file it searches. The test vectors file has cases for
both.

## Relation types

A Collection using this extension should link its gazetteer with
`rel: related`, so a client can find the places whose ids the place column
holds.
