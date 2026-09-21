# ANNCSU addresses

The certified addresses of Italian comuni, from the National Archive of House
Numbers and Urban Streets (ANNCSU), converted to cloud-native formats and
published as a STAC catalog following the Portolan profile.

Updated to the $dataset_date_human release, with $row_count_human addresses.
Browse the catalog in the [Portolan Browser]($browser_url) and see the data on
a map in the [web viewer]($viewer_url).

## What it contains

| Collection | What it is for |
|---|---|
| [ANNCSU addresses, single file](./indirizzi/) | Analysis over the whole country |
| [ANNCSU addresses, partitioned by H3 cell](./indirizzi-h3/) | Reading one comune without downloading everything |
| [ANNCSU monthly releases](./rilasci/) | Fetching a past download, or comparing two releases |

The first two describe the same data in two access shapes, and hold only the
georeferenced addresses of the current release. The third keeps every monthly
download whole, rows without coordinates included. This is the English
translation of the catalog; the Italian source tree is one level up, at
[`../`](../).

## Statistics

$statistics_table

## Licence

$license_paragraph

## Provenance

The data comes from the [ANNCSU open data portal]($source_portal), where it is
published monthly as CSV. The archive is owned by the Agenzia delle Entrate and
Istat; comuni are responsible for keeping it up to date.

The conversion to GeoParquet, PMTiles and H3 tiles is done by the pipeline in
[$repo_url]($repo_url) and does not alter the values: it adds the comune name
by joining on the Istat code, a point geometry built from the coordinates, a
bounding box per row, and two columns flagging addresses that fall outside the
boundary of their own comune.

This catalog is a derived copy, not the original source. For the authoritative
data refer to the ANNCSU portal.

## Generated automatically

Do not edit these files by hand: they are rewritten at every data update. The
sources live in `scripts/catalog/` in the repository.
