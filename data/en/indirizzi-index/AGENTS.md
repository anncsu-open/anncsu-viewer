# Instructions for agents

The `indirizzi-index` collection of the ANNCSU catalog, conforming to the
[Portolan](https://github.com/portolan-sdi/portolan-spec) profile
v0.3.0. It declares the [draft address-index
extension](https://github.com/anncsu-open/anncsu-viewer/blob/main/geocoding/address-index/v0.1.0/README.md), which for now lives only in this repository.
It is a tabular collection, with no geometry column.

## Where the data is

Two Parquet assets: the one whose roles include `address-streets` is
`vie.parquet`, the streets; the one with `address-points` is `civici.parquet`,
the access points. Each carries `address_index:sort`, the columns its rows are
sorted by, and `address_index:row_groups`, `address_index:row_group_rows` and
`address_index:footer_metadata_bytes` for planning HTTP range requests, along
with `file:size`, `file:checksum` in multihash format and `table:columns`. On
the collection, `address_index:normalization` is `anncsu-odonimo/1` and
`address_index:place_column` is `codice_istat`. `version` is the date of the
ANNCSU release the files are built from.

## How to search

Take the rows of a comune with the statistics of `codice_istat`, normalize the
street name with `anncsu-odonimo/1` and compare it with `name_norm`. For house
numbers, filter `civici.parquet` on `codice_istat` and `street_id`. The order
is byte-wise on UTF-8, with nulls last.

The comune's code is the `feature_id` of the `gazetteer` collection, given by
the `related` link.

## What not to do

Do not normalize the query with the gazetteer's function: `anncsu-odonimo/1`
turns apostrophes into spaces, `nfd-strip-marks-lower/1` keeps them. Do not
count rows whose `alt_of` is set as separate streets: they are other names for
the same street. Do not assume every access point has a number: `number` is
null where the source has none. Do not treat the collection as authoritative:
it derives from ANNCSU, the archive of the Agenzia delle Entrate and Istat
given by the `via` link.
