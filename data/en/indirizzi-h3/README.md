# ANNCSU addresses, partitioned by H3 cell

The same addresses as the indirizzi collection, split into 1,348 files by the resolution 5 H3 cell that contains them, in Hive layout tiles/h3_cell=<cell>/<cell>.parquet. Every file is under a megabyte, so a client can read one comune without downloading the national file. The bulk-access glob is https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/tiles/h3_cell=*/*.parquet, but HTTPS offers no listing: to know which cells you need, use the comuni-h3.json index, registered as a metadata asset. Of 20,731,065 addresses, 51,423 (0.25%) fall more than 110 metres outside the boundary of the comune they are assigned to, according to Istat boundaries, and 0 have no boundary to compare against.

Updated to the 15 September 2026 release, with 20,731,065 addresses.
See the data on a map in the [web viewer](https://anncsu-open.github.io/anncsu-viewer/).

## How to read it

The data is split by resolution 5 H3 cell, in Hive layout. The bulk-access glob is `https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/tiles/h3_cell=*/*.parquet`, but HTTPS offers no directory listing, so a reader cannot expand it on its own. To know which cells you need, read the `comuni-h3.json` index, which maps every comune to its cells.

```shell
curl -s https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/comuni-h3.json \
  | jq -r '.[] | select(.nome_comune == "Roma") | .h3_cells[]'
```

```sql
SELECT count(*)
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/tiles/h3_cell=851fb467fffffff/851fb467fffffff.parquet')
WHERE CODICE_ISTAT = '058091';
```

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

## Schema

| Column | Type | Description |
|---|---|---|
| `CODICE_COMUNE` | varchar | Administrative code assigned to Italian comuni by the Agenzia delle Entrate and used in composing tax codes. |
| `CODICE_ISTAT` | varchar | Administrative code assigned to Italian comuni by Istat. Six digits. It is the join key with the comuni list and with the Istat boundaries. |
| `NOME_COMUNE` | varchar | Name of the comune, added by the pipeline by joining CODICE_ISTAT with the official list of Italian comuni published by Istat. Null when the code has no match. |
| `PROGRESSIVO_NAZIONALE` | bigint | National unique sequential code identifying the circulation area, that is the street. |
| `CODICE_COMUNALE` | varchar | Street code supplied by the comune. Identifier used by the comune, where present. |
| `ODONIMO` | varchar | Full name of the circulation area, made of DUG and DUF. The DUG is the generic urban denomination, the type such as via or piazza; the DUF is the official denomination assigned by the comune under current rules. |
| `DIZIONE_LINGUA1` | varchar | Street name recorded in a first language other than Italian, under the rules on bilingualism and on the use of recognised minority languages. |
| `DIZIONE_LINGUA2` | varchar | Street name recorded in a second language other than Italian, under the same rules on bilingualism and recognised minority languages. |
| `PROGRESSIVO_ACCESSO` | bigint | National unique sequential code identifying the external access, that is the entrance. |
| `CODICE_COMUNALE_ACCESSO` | varchar | House number code supplied by the comune. Identifier used by the comune, where present. The pipeline forces it to VARCHAR because it contains alphanumeric codes that automatic inference would read as integers, dropping the non-conforming rows. |
| `CIVICO` | bigint | House number assigned to the external access following the natural sequence of numbers. The source documents it as text of at most 5 characters, but in the published data it is always numeric and the pipeline keeps it as an integer. |
| `ESPONENTE` | varchar | Letter part of the house number, where present. For example A, B, bis. |
| `SPECIFICITA` | varchar | Value used where a specific house-numbering classification validated by Istat applies, for example ROSSO and NERO. |
| `METRICO` | varchar | House number expressed in metres, used by comuni that adopt metric numbering instead of the natural sequence of numbers. |
| `PROGRESSIVO_SNC` | bigint | When set, the access placed after the given house or metric number has no standard house number. When the references to the previous access are absent, the SNC access is at the start of the street. |
| `longitude` | double | Longitude of the access in decimal degrees, from the source column COORD_X_COMUNE. The reference system declared by the source is ETRF2000 at epoch 2008.0, the Italian realisation of ETRS89. The pipeline converts the decimal comma to a point. |
| `latitude` | double | Latitude of the access in decimal degrees, from the source column COORD_Y_COMUNE. Same reference system and same decimal conversion as the longitude. |
| `QUOTA` | varchar | Orthometric height of the access in the official national height reference systems. The pipeline keeps it as text because the values use a comma as decimal separator. |
| `METODO` | bigint | How the comune assigned the coordinates. 1 field survey with instruments, accuracy below 5 m; 2 field survey with instruments, accuracy of 5 m or more; 3 indirect derivation from a spatial database, estimated accuracy below 5 m; 4 indirect derivation from a spatial database, estimated accuracy of 5 m or more; 5 indirect derivation through the functions of the Portale per i Comuni. |
| `oob_distance_m` | double | Distance in metres between the address and the boundary of its comune according to Istat administrative boundaries, computed by the pipeline. Null when the comune has no matching boundary, zero when the point falls inside it. |
| `out_of_bounds` | boolean | True when the address falls more than 110 metres outside the boundary of the comune it is assigned to. The threshold absorbs geocoding tolerance. Null when the comune has no matching boundary. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Bounding box of the point, with all four values equal to its coordinates. It is the covering column defined by GeoParquet, which lets a reader skip whole row groups without decoding geometries. |
| `geometry` | geometry | Point built by the pipeline from longitude and latitude. Declared in OGC:CRS84. The source expresses coordinates in ETRF2000, which differs from WGS84 by less than a metre in Italy, so the offset is negligible against address precision. |
| `h3_cell` | varchar | Hexadecimal identifier of the resolution 5 H3 cell containing the address. Present only in the partitioned files, where it matches the directory and file name. |

## Licence

The data is published under the [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/) licence, SPDX identifier `CC-BY-4.0`. The official ANNCSU pages cite EU implementing regulation 2023/138 on high-value datasets, which mandates this licence for the address series, but do not state it in full. Anyone who needs certainty for a commercial reuse should ask the Agenzia delle Entrate.

## Provenance

The data comes from the [ANNCSU open data portal](https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/), which is
its original source. The archive is owned by the Agenzia delle Entrate and
Istat; comuni are responsible for keeping it up to date. The conversion is done
by the pipeline in [https://github.com/anncsu-open/anncsu-viewer](https://github.com/anncsu-open/anncsu-viewer). This catalog is a derived copy, not
the source.

## Generated automatically

Do not edit this file by hand: it is rewritten at every data update. The
sources live in `scripts/catalog/` in the repository.
