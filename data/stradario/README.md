# Stradario ANNCSU

I rilasci dello stradario nazionale ANNCSU conservati qui. Il [portale ANNCSU](https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/) serve solo l'ultimo rilascio, quindi l'archivio contiene i rilasci elencati e non tutti i mesi.

Un rilascio scaricato dal portale ha due file: lo **ZIP** come lo distribuisce il portale e una **copia Parquet senza perdita** del CSV, con tutte le righe e le 9 colonne originali come testo. I rilasci che vengono da ondata/archivio_anncsu hanno solo il Parquet, e non si può dire che siano senza perdita: la loro completezza rispetto al CSV originale non è verificabile.

`TOTALE_ACCESSI` è calcolato dal portale sui civici dello stesso rilascio.

I rilasci di cui non sopravvive lo stradario originale non sono pubblicati. La parte ricavabile, cioè le strade con almeno un accesso, si ottiene raggruppando i civici della collection `rilasci`.

## Rilasci

| Rilascio | Origine | Strade | ZIP | Parquet |
|---|---|---|---|---|
| [2026-11-02](./2026-11-02/2026-11-02.json) | originale | 1.221.302 | [13,9 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2026-11-02/stradarioItalia_20261102.zip) | [11,5 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2026-11-02/STRAD_ITA_20261102.parquet) |
| [2026-01-14](./2026-01-14/2026-01-14.json) | originale | 1.217.062 | [13,8 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2026-01-14/stradarioItalia_20260114.zip) | [11,4 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2026-01-14/STRAD_ITA_20260114.parquet) |
| [2025-08-04](./2025-08-04/2025-08-04.json) | originale | 1.214.161 | [13,8 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2025-08-04/stradarioItalia_20250804.zip) | [11,3 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2025-08-04/STRAD_ITA_20250804.parquet) |
| [2025-01-28](./2025-01-28/2025-01-28.json) | terza parte | 1.212.812 | - | [11,3 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/stradario/2025-01-28/STRAD_ITA_20250128.parquet) |

Un rilascio originale è lo scarico del portale ANNCSU, con il suo ZIP.
Un rilascio di terza parte non ha lo ZIP: il Parquet viene da una
conversione del CSV fatta da altri,
[ondata/archivio_anncsu](https://github.com/ondata/archivio_anncsu), e l'item
non ha l'asset `source`.

## Lacune note

Il portale conserva solo l'ultimo stradario, quindi l'archivio ha buchi che non
si possono colmare.

- La copia del 15 settembre 2026 è persa: nessuno aveva salvato lo scarico. Gli
  accessi di quel rilascio sono in [`rilasci`](../rilasci/2026-09-15/2026-09-15.json).
- Non esiste un originale per i mesi tra un rilascio e l'altro della tabella
  qui sopra. Non sono pubblicati rilasci ricostruiti.

## Come ricavare in parte un rilascio mancante

Per ogni strada con almeno un accesso, raggruppare i civici grezzi della
collection `rilasci` dà la riga dello stradario, come testo, nelle nove
colonne. Sostituire `<data>` e `<aaaammgg>` con la data del rilascio:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT CODICE_COMUNE, CODICE_ISTAT, PROGRESSIVO_NAZIONALE, CODICE_COMUNALE,
       ODONIMO, "LOCALITA'", count(*)::VARCHAR AS TOTALE_ACCESSI,
       DIZIONE_LINGUA1, DIZIONE_LINGUA2
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/<data>/INDIR_ITA_<aaaammgg>.parquet')
GROUP BY ALL;
```

La query riproduce lo stradario originale solo dove il rilascio dei civici è
esatto. Su quello del 2 novembre 2026 combacia per tutte le strade; su quello
del 14 gennaio 2026 differisce per una strada, perché il CSV originale dei
civici ne ripete le righe e l'archivio dei civici ricostruito le ha
deduplicate. Le strade senza alcun accesso non si ricavano dai civici: per
questo i rilasci derivati non sono pubblicati.

## Schema

| Colonna | Tipo | Descrizione |
|---|---|---|
| `CODICE_COMUNE` | varchar | Codice amministrativo assegnato ai Comuni italiani dall'Agenzia delle Entrate e utilizzato nella composizione dei codici fiscali. |
| `CODICE_ISTAT` | varchar | Codice amministrativo assegnato ai Comuni italiani dall'Istat. Sei cifre. È la chiave di join con l'elenco dei comuni e con i confini ISTAT. |
| `PROGRESSIVO_NAZIONALE` | varchar | Codice progressivo univoco nazionale, identificativo dell'area di circolazione. |
| `CODICE_COMUNALE` | varchar | Codice dell'odonimo fornito dal Comune. Identificativo utilizzato dal Comune ove presente. |
| `ODONIMO` | varchar | Denominazione completa dell'area di circolazione, composta da DUG e DUF. La DUG è la Denominazione Urbanistica Generica, cioè la tipologia come via o piazza; la DUF è la Denominazione Ufficiale attribuita dal Comune ai sensi delle norme vigenti. |
| `LOCALITA'` | varchar | Denominazione della località, ove il Comune la registra. Presente solo nel CSV originale e nel parquet grezzo dell'archivio: il GeoParquet arricchito non la riporta. |
| `TOTALE_ACCESSI` | varchar | Numero di accessi (civici) della strada nello stesso rilascio, calcolato da ANNCSU a partire dai civici. Coincide con il conteggio dei civici del portale strada per strada. Presente solo nello stradario. |
| `DIZIONE_LINGUA1` | varchar | Odonimo registrato in una prima lingua diversa dall'italiano, secondo le norme in materia di bilinguismo e sull'uso delle lingue delle minoranze linguistiche riconosciute. |
| `DIZIONE_LINGUA2` | varchar | Odonimo registrato in una seconda lingua diversa dall'italiano, secondo le norme in materia di bilinguismo e sull'uso delle lingue delle minoranze linguistiche riconosciute. |

## Licenza

I dati sono pubblicati con licenza [Creative Commons Attribuzione 4.0 Internazionale](https://creativecommons.org/licenses/by/4.0/deed.it), identificativo SPDX `CC-BY-4.0`. Le pagine ufficiali ANNCSU richiamano il Regolamento di esecuzione (UE) 2023/138 sui dati di elevato valore, che per la serie degli indirizzi impone questa licenza, ma non la riportano per esteso. Chi ha bisogno di certezza per un riutilizzo commerciale conviene che si rivolga all'Agenzia delle Entrate.

## Generato automaticamente

Non modificare questo file a mano: è riscritto a ogni aggiornamento dei dati.
Le sorgenti sono in `scripts/catalog/` nel repository; i fatti sui rilasci sono
in `stradario/releases.json`.
