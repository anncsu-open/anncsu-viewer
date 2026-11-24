# $title

$description

## Rilasci

$releases_table

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
FROM read_parquet('$public_base/rilasci/<data>/INDIR_ITA_<aaaammgg>.parquet')
GROUP BY ALL;
```

La query riproduce lo stradario originale solo dove il rilascio dei civici è
esatto. Su quello del 2 novembre 2026 combacia per tutte le strade; su quello
del 14 gennaio 2026 differisce per una strada, perché il CSV originale dei
civici ne ripete le righe e l'archivio dei civici ricostruito le ha
deduplicate. Le strade senza alcun accesso non si ricavano dai civici: per
questo i rilasci derivati non sono pubblicati.

## Schema

$schema_table

## Licenza

$license_paragraph

## Generato automaticamente

Non modificare questo file a mano: è riscritto a ogni aggiornamento dei dati.
Le sorgenti sono in `scripts/catalog/` nel repository; i fatti sui rilasci sono
in `stradario/releases.json`.
