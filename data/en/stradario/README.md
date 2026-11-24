# ANNCSU street register

The releases of the ANNCSU national street register kept here. The [ANNCSU portal](https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/) serves only the latest release, so the archive holds the releases listed, not every month.

A release downloaded from the portal has two files: the **ZIP** as the portal distributes it and a **lossless Parquet copy** of the CSV, with every row and the 9 original columns as text. Releases that come from ondata/archivio_anncsu have only the Parquet and cannot be called lossless: their completeness against the original CSV cannot be verified.

`TOTALE_ACCESSI` is computed by the portal from the house numbers of the same release.

Releases for which no original street register survives are not published. The part that can be derived, the streets with at least one access, comes from grouping the house numbers of the `rilasci` collection.

## Releases

| Release | Origin | Streets | ZIP | Parquet |
|---|---|---|---|---|
| [2026-11-02](./2026-11-02/2026-11-02.json) | original | 1,221,302 | [13.9 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2026-11-02/stradarioItalia_20261102.zip) | [11.5 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2026-11-02/STRAD_ITA_20261102.parquet) |
| [2026-01-14](./2026-01-14/2026-01-14.json) | original | 1,217,062 | [13.8 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2026-01-14/stradarioItalia_20260114.zip) | [11.4 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2026-01-14/STRAD_ITA_20260114.parquet) |
| [2025-08-04](./2025-08-04/2025-08-04.json) | original | 1,214,161 | [13.8 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2025-08-04/stradarioItalia_20250804.zip) | [11.3 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2025-08-04/STRAD_ITA_20250804.parquet) |
| [2025-01-28](./2025-01-28/2025-01-28.json) | third-party | 1,212,812 | - | [11.3 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2025-01-28/STRAD_ITA_20250128.parquet) |

An original release is the download from the ANNCSU portal, with its ZIP.
A third-party release has no ZIP: the Parquet comes from a conversion
of the CSV made by others,
[ondata/archivio_anncsu](https://github.com/ondata/archivio_anncsu), and the
item has no `source` asset.

## Known gaps

The portal keeps only the latest street register, so the archive has holes
that cannot be filled.

- The copy of 15 September 2026 is lost: nobody had saved the download. The
  addresses of that release are in
  [`rilasci`](../rilasci/2026-09-15/2026-09-15.json).
- There is no original for the months between the releases in the table above.
  No reconstructed releases are published.

## Deriving part of a missing release

For every street with at least one access, grouping the raw house numbers of
the `rilasci` collection gives the street register row, as text, in all nine
columns. Replace `<date>` and `<yyyymmdd>` with the date of the release:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT CODICE_COMUNE, CODICE_ISTAT, PROGRESSIVO_NAZIONALE, CODICE_COMUNALE,
       ODONIMO, "LOCALITA'", count(*)::VARCHAR AS TOTALE_ACCESSI,
       DIZIONE_LINGUA1, DIZIONE_LINGUA2
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/<date>/INDIR_ITA_<yyyymmdd>.parquet')
GROUP BY ALL;
```

The query reproduces the original street register only where the house number
release is exact. On the 2 November 2026 release it matches for every street;
on the 14 January 2026 release it differs for one street, because the original
house number CSV repeats its rows and the rebuilt house number archive kept
them once. Streets with no access at all cannot be derived from the house
numbers, which is why derived releases are not published.

## Schema

| Column | Type | Description |
|---|---|---|
| `CODICE_COMUNE` | varchar | Administrative code assigned to Italian comuni by the Agenzia delle Entrate and used in composing tax codes. |
| `CODICE_ISTAT` | varchar | Administrative code assigned to Italian comuni by Istat. Six digits. It is the join key with the comuni list and with the Istat boundaries. |
| `PROGRESSIVO_NAZIONALE` | varchar | National unique sequential code identifying the circulation area, that is the street. |
| `CODICE_COMUNALE` | varchar | Street code supplied by the comune. Identifier used by the comune, where present. |
| `ODONIMO` | varchar | Full name of the circulation area, made of DUG and DUF. The DUG is the generic urban denomination, the type such as via or piazza; the DUF is the official denomination assigned by the comune under current rules. |
| `LOCALITA'` | varchar | Locality name, where the comune records one. Present only in the original CSV and in the raw archive Parquet: the enriched GeoParquet does not carry it. |
| `TOTALE_ACCESSI` | varchar | Number of accesses (house numbers) on the street in the same release, computed by ANNCSU from the house numbers. It equals the count of the portal's house numbers, street by street. Present only in the street register. |
| `DIZIONE_LINGUA1` | varchar | Street name recorded in a first language other than Italian, under the rules on bilingualism and on the use of recognised minority languages. |
| `DIZIONE_LINGUA2` | varchar | Street name recorded in a second language other than Italian, under the same rules on bilingualism and recognised minority languages. |

## Licence

The data is published under the [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/) licence, SPDX identifier `CC-BY-4.0`. The official ANNCSU pages cite EU implementing regulation 2023/138 on high-value datasets, which mandates this licence for the address series, but do not state it in full. Anyone who needs certainty for a commercial reuse should ask the Agenzia delle Entrate.

## Generated automatically

Do not edit this file by hand: it is rewritten at every data update. The
sources live in `scripts/catalog/` in the repository; the facts about the
releases are in `stradario/releases.json`.
