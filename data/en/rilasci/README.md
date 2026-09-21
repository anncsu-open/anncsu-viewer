# ANNCSU monthly releases

Every monthly download of the national address register, from 3 September 2025 to 15 September 2026, as published by the [ANNCSU portal](https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/). The portal serves only the latest release: all of them are kept here.

Every release has two files:

- the **ZIP archive** as the portal distributes it;
- a **lossless Parquet copy** of the CSV, with every row and the 19 original columns as text, coordinates included but no geometry.

It is the history the `indirizzi` and `indirizzi-h3` collections derive their current release from. Releases before 15 September 2026 are reconstructed from the consolidated parquet of [mfortini/diff_ANNCSU](https://github.com/mfortini/diff_ANNCSU), with a method verified byte for byte on the September release.

## Releases

| Release | Origin | Addresses | ZIP | Parquet |
|---|---|---|---|---|
| [2026-09-15](./2026-09-15/2026-09-15.json) | original | 27,415,954 | [336.1 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-09-15/indirizzarioItalia_20260915.zip) | [258.9 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-09-15/INDIR_ITA_20260915.parquet) |
| [2026-08-03](./2026-08-03/2026-08-03.json) | reconstructed | 27,405,709 | [324.7 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-08-03/indirizzarioItalia_20260803.zip) | [258.5 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-08-03/INDIR_ITA_20260803.parquet) |
| [2026-07-03](./2026-07-03/2026-07-03.json) | reconstructed | 27,405,384 | [324.4 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-07-03/indirizzarioItalia_20260703.zip) | [258.1 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-07-03/INDIR_ITA_20260703.parquet) |
| [2026-06-02](./2026-06-02/2026-06-02.json) | reconstructed | 27,418,271 | [323.7 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-06-02/indirizzarioItalia_20260602.zip) | [257.5 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-06-02/INDIR_ITA_20260602.parquet) |
| [2026-05-04](./2026-05-04/2026-05-04.json) | reconstructed | 27,416,925 | [321.6 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-05-04/indirizzarioItalia_20260504.zip) | [255.2 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-05-04/INDIR_ITA_20260504.parquet) |
| [2026-04-06](./2026-04-06/2026-04-06.json) | reconstructed | 27,458,420 | [309.3 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-04-06/indirizzarioItalia_20260406.zip) | [242.9 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-04-06/INDIR_ITA_20260406.parquet) |
| [2026-03-06](./2026-03-06/2026-03-06.json) | reconstructed | 27,569,011 | [276.0 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-03-06/indirizzarioItalia_20260306.zip) | [209.9 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-03-06/INDIR_ITA_20260306.parquet) |
| [2026-02-06](./2026-02-06/2026-02-06.json) | reconstructed | 27,843,626 | [232.1 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-02-06/indirizzarioItalia_20260206.zip) | [172.1 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-02-06/INDIR_ITA_20260206.parquet) |
| [2026-01-14](./2026-01-14/2026-01-14.json) | reconstructed | 27,862,795 | [215.4 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-01-14/indirizzarioItalia_20260114.zip) | [160.4 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-01-14/INDIR_ITA_20260114.parquet) |
| [2025-12-02](./2025-12-02/2025-12-02.json) | reconstructed | 27,964,607 | [185.7 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-12-02/indirizzarioItalia_20251202.zip) | [128.6 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-12-02/INDIR_ITA_20251202.parquet) |
| [2025-11-04](./2025-11-04/2025-11-04.json) | reconstructed | 27,956,679 | [174.8 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-11-04/indirizzarioItalia_20251104.zip) | [113.1 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-11-04/INDIR_ITA_20251104.parquet) |
| [2025-10-10](./2025-10-10/2025-10-10.json) | reconstructed | 27,949,296 | [173.1 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-10-10/indirizzarioItalia_20251010.zip) | [110.9 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-10-10/INDIR_ITA_20251010.parquet) |
| [2025-09-03](./2025-09-03/2025-09-03.json) | reconstructed | 27,950,169 | [172.4 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-09-03/indirizzarioItalia_20250903.zip) | [109.9 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-09-03/INDIR_ITA_20250903.parquet) |

## How to read it

Every release has two files on R2. The ZIP is the archive as the portal
publishes it, containing `INDIR_ITA_yyyymmdd.csv`: 19 columns separated by
`;`, no quoting, decimal comma. The Parquet is its lossless copy, every row
and every column as text, ordered by Istat code and sequential ids, and it
can be queried over HTTP:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT count(*) FILTER (WHERE COORD_X_COMUNE IS NULL) AS without_coordinates
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-09-15/INDIR_ITA_20260915.parquet');
```

To compare two releases, join them on `PROGRESSIVO_ACCESSO`, unique within
every release.

## Provenance of the releases

The ANNCSU portal keeps only the latest download. The 15 September 2026
release is the original download. Earlier releases are reconstructed from the
consolidated parquet of
[mfortini/diff_ANNCSU](https://github.com/mfortini/diff_ANNCSU), which kept
every monthly download since September 2025 with a presence flag per release.
The method reproduces the portal's CSV dialect, including two details that
are not obvious: `QUOTA` never uses exponent notation and drops the zero
before the decimal comma when the integer part is zero, and one `T` value of
`SPECIFICITA` had been turned into `true` in the consolidated file. Verified
on the September 2026 release, the only one with an original at hand: same
bytes, same md5 of the sorted content; only the row order, which the portal
does not define, cannot be reproduced.

Every item states its own origin in its description.

## Schema

| Column | Type | Description |
|---|---|---|
| `CODICE_COMUNE` | varchar | Administrative code assigned to Italian comuni by the Agenzia delle Entrate and used in composing tax codes. |
| `CODICE_ISTAT` | varchar | Administrative code assigned to Italian comuni by Istat. Six digits. It is the join key with the comuni list and with the Istat boundaries. |
| `PROGRESSIVO_NAZIONALE` | varchar | National unique sequential code identifying the circulation area, that is the street. |
| `CODICE_COMUNALE` | varchar | Street code supplied by the comune. Identifier used by the comune, where present. |
| `ODONIMO` | varchar | Full name of the circulation area, made of DUG and DUF. The DUG is the generic urban denomination, the type such as via or piazza; the DUF is the official denomination assigned by the comune under current rules. |
| `LOCALITA'` | varchar | Locality name, where the comune records one. Present only in the original CSV and in the raw archive Parquet: the enriched GeoParquet does not carry it. |
| `DIZIONE_LINGUA1` | varchar | Street name recorded in a first language other than Italian, under the rules on bilingualism and on the use of recognised minority languages. |
| `DIZIONE_LINGUA2` | varchar | Street name recorded in a second language other than Italian, under the same rules on bilingualism and recognised minority languages. |
| `PROGRESSIVO_ACCESSO` | varchar | National unique sequential code identifying the external access, that is the entrance. |
| `CODICE_COMUNALE_ACCESSO` | varchar | House number code supplied by the comune. Identifier used by the comune, where present. The pipeline forces it to VARCHAR because it contains alphanumeric codes that automatic inference would read as integers, dropping the non-conforming rows. |
| `CIVICO` | varchar | House number assigned to the external access following the natural sequence of numbers. The source documents it as text of at most 5 characters, but in the published data it is always numeric and the pipeline keeps it as an integer. |
| `ESPONENTE` | varchar | Letter part of the house number, where present. For example A, B, bis. |
| `SPECIFICITA` | varchar | Value used where a specific house-numbering classification validated by Istat applies, for example ROSSO and NERO. |
| `METRICO` | varchar | House number expressed in metres, used by comuni that adopt metric numbering instead of the natural sequence of numbers. |
| `PROGRESSIVO_SNC` | varchar | When set, the access placed after the given house or metric number has no standard house number. When the references to the previous access are absent, the SNC access is at the start of the street. |
| `COORD_X_COMUNE` | varchar | Longitude of the access as the portal writes it: decimal degrees with a comma as decimal separator, in ETRF2000. The enriched GeoParquet turns it into the numeric longitude column. |
| `COORD_Y_COMUNE` | varchar | Latitude of the access as the portal writes it: decimal degrees with a comma as decimal separator, in ETRF2000. The enriched GeoParquet turns it into the numeric latitude column. |
| `QUOTA` | varchar | Orthometric height of the access in the official national height reference systems. The pipeline keeps it as text because the values use a comma as decimal separator. |
| `METODO` | varchar | How the comune assigned the coordinates. 1 field survey with instruments, accuracy below 5 m; 2 field survey with instruments, accuracy of 5 m or more; 3 indirect derivation from a spatial database, estimated accuracy below 5 m; 4 indirect derivation from a spatial database, estimated accuracy of 5 m or more; 5 indirect derivation through the functions of the Portale per i Comuni. |

## Licence

The data is published under the [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/) licence, SPDX identifier `CC-BY-4.0`. The official ANNCSU pages cite EU implementing regulation 2023/138 on high-value datasets, which mandates this licence for the address series, but do not state it in full. Anyone who needs certainty for a commercial reuse should ask the Agenzia delle Entrate.

## Generated automatically

Do not edit this file by hand: it is rewritten at every data update. The
sources live in `scripts/catalog/` in the repository; the facts about the
releases are in `rilasci/releases.json`.
