# Geocoding index: measurements

What a browser downloads to search the geocoding index, measured on the
2026-11-02 ANNCSU release (20,728,959 access points, 781,923 streets, 5,502
comuni). The numbers come from the Parquet footers, as a range-reading client
plans its requests:

```bash
uv run scripts/measure_geocoding_index.py data/gazetteer/2026-11-02/comuni.parquet \
  data/indirizzi-index/2026-11-02/vie.parquet data/indirizzi-index/2026-11-02/civici.parquet
```

For each comune, the script takes the row groups of its streets (by the
statistics of `codice_istat`), then its longest street and the row groups of
that street's access points (by the statistics of `codice_istat` and
`street_id`). Adjacent row groups count as one request. "First address" adds
everything a client with an empty cache fetches: the whole gazetteer, the
footer of each file, the streets of the comune and the access points of the
street.

## Files

| File | Rows | Row groups | Footer | Size |
|---|---|---|---|---|
| `gazetteer/2026-11-02/comuni.parquet` | 5,821 (5,502 comuni and 319 alternate spellings) | 2 of 4096 | 5 KiB | 341 KiB |
| `indirizzi-index/2026-11-02/vie.parquet` | 786,969 (781,923 streets and 5,046 other-language names) | 193 of 4096 | 325 KiB | 41 MiB |
| `indirizzi-index/2026-11-02/civici.parquet` | 20,728,959 | 633 of 32768 | 757 KiB | 406 MiB |

The build takes about 20 seconds and 2.7 GB of memory on a laptop.

## Choosing the row-group sizes

A smaller row group means less to read for one street, but a longer footer,
which a client reads before its first search. The first build used 8192 rows
per group for the access points, and its footer was 2,990 KiB, three quarters
of the cost of a first search. Six combinations were measured:

| Streets / access points per group | Footers | Vacone, first address | Median comune (018121) | Roma |
|---|---|---|---|---|
| 4096 / 8192 | 325 + 2,990 KiB | 4,032 KiB | 4,035 KiB | 5,306 KiB |
| 4096 / 16384 | 325 + 1,503 KiB | 2,720 KiB | 2,728 KiB | 4,361 KiB |
| **4096 / 32768** | 325 + 757 KiB | **2,316 KiB** | **2,343 KiB** | 4,699 KiB |
| 4096 / 65536 | 325 + 385 KiB | 2,627 KiB | 2,627 KiB | 6,312 KiB |
| 16384 / 16384 | 86 + 1,503 KiB | 3,136 KiB | 3,121 KiB | 4,800 KiB |
| 16384 / 32768 | 86 + 757 KiB | 2,732 KiB | 2,736 KiB | 5,138 KiB |

The index uses 4096 rows per street group and 32768 per access-point group.
It is the cheapest for a typical comune; Rome costs 338 KiB more than with
16384. Larger street groups shrink the street footer but make every comune
read 850 KiB of streets instead of 215 KiB.

## The chosen layout

| Comune | Streets: groups / requests / bytes | Longest street (access points) | Its access points: groups / requests / bytes | First address |
|---|---|---|---|---|
| Vacone (057072) | 1 / 1 / 215 KiB | 468306 (79) | 1 / 1 / 678 KiB | 2,316 KiB |
| Median comune (018121) | 1 / 1 / 215 KiB | 729628 (305) | 1 / 1 / 704 KiB | 2,343 KiB |
| Roma (058091) | 5 / 1 / 1,132 KiB | 909003 (1,938) | 3 / 3 / 2,143 KiB | 4,699 KiB |

After the first search, the footers and the comune's streets are in the
client's cache: another street of the same comune costs one access-point
group, under 700 KiB.

### Against the targets of the design

- The gazetteer is under 500 KiB: met, 341 KiB, loaded whole.
- A comune's streets in at most two requests: met, one request even for Rome.
- One street's access points in one row group: met for Vacone and the median
  comune, not for Rome's longest street, which takes three groups in three
  requests. The street's rows span at most two adjacent groups. The third is a
  group that straddles the boundary between two comuni: per-column statistics
  can only bound a (comune, street) pair loosely, so a client reads it to be
  safe. The streets file could carry the index of the access-point row groups
  each street occupies, as the gazetteer contract's `geometry_ref` does for
  boundaries, and a client would then fetch exactly those groups. That is a
  decision for the package (phase 2).

## Today's search, for comparison

The viewer today downloads `comuni-h3.json` (591 KiB) and every H3 tile of
the chosen comune:

| Comune | Today | The index, first address |
|---|---|---|
| Vacone | 898 KiB (one tile, 307 KiB) | 2,316 KiB |
| Roma | 38,402 KiB (13 tiles, 37,811 KiB) | 4,699 KiB |

The index costs more for a small comune's first search and much less for a
large one, because it never downloads the addresses of streets the user is
not looking for. Later searches in the same comune cost one access-point
group at most, where today they cost nothing once the tiles are loaded.

## Interoperability with @cngeo/geocoder-core

`@cngeo/geocoder-core` 0.3.1, from `cholmes/cng-map-widgets` at commit
`56dac2e82839e491ac70f5a744221256ea76cd27` (2026-11-25), loaded our gazetteer
from its STAC Collection, `gazetteer/collection.json`, served over HTTP with
range requests, with hyparquet 1.33.0 injected through `setHyparquetModules`.

| Query | First result |
|---|---|
| `vacone` | `057072` Vacone, Rieti, bbox 12.6375, 42.3718, 12.6597, 42.3931 |
| `aldein` | `021001` Aldein, Bolzano/Bozen (the German alternate of Aldino) |
| `sant ambrogio` | `001255` Sant'Ambrogio di Torino, found through the spelling with a space |
| `castro` | `016065` Castro, Bergamo, with `moreCount: 1` |

geocoder-core collapses places with the same name, country and level into one
result (`dedupeByNameCountryLevel`): Castro in the province of Lecce
(`075096`) is in that result's `collapsed` list, without its province. Our
package keeps the two apart, with their provinces, as the design asks.
