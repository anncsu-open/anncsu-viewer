# Instructions for agents

The `stradario` collection of the ANNCSU catalog: the archive of the national
street register, conforming to the
[Portolan](https://github.com/portolan-sdi/portolan-spec) profile
$portolan_version. It is a tabular collection: items have no geometry and the
files have no geometry column. All nine columns are text.

## Structure

One item per release, with `id` and `version` equal to the release date and
`datetime` at midnight UTC of that day. Items are chained with
`predecessor-version` and `successor-version`; the collection points to the
latest with `latest-version`. The item of a release whose house numbers are
also in `rilasci` points to them with a `related` link, and the other way
round.

## Assets

Every item has the `data` asset, the Parquet of the CSV, lossless for the
original releases, and usually the `source` asset, the portal's original
ZIP. An item without a `source`
asset has no ZIP: its origin is `third-party`, a Parquet converted by others,
and its description says so. Hrefs are absolute on R2; `file:size` and
`file:checksum` use the multihash format.

## What not to do

Do not assume every month has a release: the archive has gaps, described in
the README. Do not rebuild the street register of a missing month by grouping
house numbers without saying that streets with no accesses are missing. Do not
treat the catalog as authoritative: it is a copy of the ANNCSU portal, given
by the `via` link.
