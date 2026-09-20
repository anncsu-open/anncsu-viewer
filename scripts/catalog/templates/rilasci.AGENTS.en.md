# Instructions for agents

Collection `rilasci` of the ANNCSU catalog: the archive of monthly downloads,
conforming to the [Portolan](https://github.com/portolan-sdi/portolan-spec)
profile v0.2.0. It is a tabular collection: items have no geometry and the
files have no geometry column; coordinates are text in `COORD_X_COMUNE` and
`COORD_Y_COMUNE`, with a decimal comma.

## Structure

One item per release, with `id` and `version` equal to the release date and
`datetime` at midnight UTC of that day. Items are chained with
`predecessor-version` and `successor-version`; the collection points at the
newest with `latest-version`. The `indirizzi` and `indirizzi-h3` collections
point at the release they derive from with `derived_from` and at this
collection with `version-history`.

## Assets

Every item has two assets with absolute hrefs on R2: `data`, the lossless
Parquet of the CSV, and `source`, the original or reconstructed ZIP.
`file:size` and `file:checksum` are in multihash form. The item description
states whether the release is original or reconstructed.

## What not to do

Do not infer the current state from this collection: the current release is
in the `indirizzi` and `indirizzi-h3` collections, which hold georeferenced
addresses only. Do not treat the catalog as the authoritative source: it is a
copy of the ANNCSU portal, indicated by the `via` link.
