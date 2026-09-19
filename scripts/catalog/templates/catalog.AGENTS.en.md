# Instructions for agents

This is a STAC 1.1.0 catalog conforming to the
[Portolan](https://github.com/portolan-sdi/portolan-spec) profile v0.2.0. It
is the English tree of a catalog whose source language is Italian; the Italian
root is the `alternate` link with `hreflang: it`.

## How to read it

Start from `catalog.json` and follow the `child` links. Every collection
declares its assets with relative `href`s, resolved against the location of
its `collection.json`. The data files, styles and thumbnails live in the
Italian tree, so from here every asset href climbs two levels. The `self` link
on the root carries the public base, so a relative href resolves to an
absolute URL even from a local copy.

## What to know before querying the data

There are two collections over the same addresses. `indirizzi` exposes one
GeoParquet of about a gigabyte, spatially sorted: use it for national
aggregations. `indirizzi-h3` exposes the same data partitioned into files
under a megabyte each: use it for a single comune or a single area.

The `partition:glob` field of `indirizzi-h3` cannot be expanded over HTTPS,
because the protocol offers no directory listing. To know which cells you
need, read the `cell-index` asset, `comuni-h3.json`, which maps every comune
to the cells that contain its addresses.

Column descriptions are in `table:columns` on every collection.

## What not to do

Do not infer temporal coverage from file names. The release date is in
`extent.temporal` and the moment of the last sync in the `updated` field.

Do not treat this catalog as the authoritative source: it is a copy of the
ANNCSU portal, indicated by the `via` link.
