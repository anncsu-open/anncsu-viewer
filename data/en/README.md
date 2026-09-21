# ANNCSU addresses

The certified addresses of Italian comuni, from the National Archive of House
Numbers and Urban Streets (ANNCSU), converted to cloud-native formats and
published as a STAC catalog following the Portolan profile.

Updated to the 15 September 2026 release, with 20,731,065 addresses.
Browse the catalog in the [Portolan Browser](https://browser.portolan-sdi.org/#/external/pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/catalog.json) and see the data on
a map in the [web viewer](https://anncsu-open.github.io/anncsu-viewer/).

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

| Statistic | Value |
|---|---|
| Total addresses | 20,731,065 |
| Outside the comune boundary, beyond 110 m | 51,423 (0.25%) |
| Without a comune boundary to compare against | 0 |
| Comuni with at least one address | 5,493 |
| Method 1, field survey with instruments, accuracy below 5 m | 1,714,163 (8.27%) |
| Method 2, field survey with instruments, accuracy of 5 m or more | 290,652 (1.40%) |
| Method 3, indirect derivation from a spatial database, estimated accuracy below 5 m | 7,125,819 (34.37%) |
| Method 4, indirect derivation from a spatial database, estimated accuracy of 5 m or more | 10,894,269 (52.55%) |
| Method 5, indirect derivation through the functions of the Portale per i Comuni | 706,162 (3.41%) |

## Licence

The data is published under the [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/) licence, SPDX identifier `CC-BY-4.0`. The official ANNCSU pages cite EU implementing regulation 2023/138 on high-value datasets, which mandates this licence for the address series, but do not state it in full. Anyone who needs certainty for a commercial reuse should ask the Agenzia delle Entrate.

## Provenance

The data comes from the [ANNCSU open data portal](https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/), where it is
published monthly as CSV. The archive is owned by the Agenzia delle Entrate and
Istat; comuni are responsible for keeping it up to date.

The conversion to GeoParquet, PMTiles and H3 tiles is done by the pipeline in
[https://github.com/anncsu-open/anncsu-viewer](https://github.com/anncsu-open/anncsu-viewer) and does not alter the values: it adds the comune name
by joining on the Istat code, a point geometry built from the coordinates, a
bounding box per row, and two columns flagging addresses that fall outside the
boundary of their own comune.

This catalog is a derived copy, not the original source. For the authoritative
data refer to the ANNCSU portal.

## Generated automatically

Do not edit these files by hand: they are rewritten at every data update. The
sources live in `scripts/catalog/` in the repository.
