# Instructions for agents

The `gazetteer` collection of the ANNCSU catalog, conforming to the
[Portolan](https://github.com/portolan-sdi/portolan-spec) profile
$portolan_version. It declares the [gazetteer]($gazetteer_spec) extension: it
is the index of comuni names, meant to be read without a server. It is a
tabular collection, with no geometry column.

## Where the data is

The asset whose roles include `gazetteer-index` is the Parquet file. On the
asset, `gazetteer:row_groups`, `gazetteer:row_group_rows` and
`gazetteer:footer_metadata_bytes` are for planning HTTP range requests;
`file:size` tells whether the file changed and `file:checksum` uses the
multihash format. On the collection, `gazetteer:levels` is `[3]`, the level of
comuni, `gazetteer:normalization` is `nfd-strip-marks-lower/1` and
`gazetteer:sort` is `name_norm`. `version` is the date of the ANNCSU release
the file is built from.

## How to search

Normalize the query with `nfd-strip-marks-lower/1` before comparing it with
`name_norm`. Comparison and order are byte-wise on UTF-8, never a language's
collation. Two comuni can share a `name_norm`: `parent_name`, the province,
tells them apart.

The `feature_id` is the comune's Istat code. To get to its streets, look it up
in the `codice_istat` column of the `indirizzi-index` collection, given by the
`related` link.

## What not to do

Do not treat rows whose `alt_of` is set as separate comuni: they are other
names for the same comune, with the same `feature_id`. Do not use `bbox` as the
comune boundary: it covers the comune's access points, not its territory. Do
not treat the collection as authoritative: it derives from ANNCSU, given by
the `via` link, and from the Istat list of comuni.
