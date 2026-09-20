# $title

$description

## Rilasci

$releases_table

## Come si legge

Ogni rilascio ha due file su R2. Lo ZIP è l'archivio come lo pubblica il
portale, con dentro `INDIR_ITA_aaaammgg.csv`: 19 colonne separate da `;`,
senza virgolette, con la virgola decimale. Il Parquet ne è la copia senza
perdita, tutte le righe e tutte le colonne come testo, ordinato per codice
Istat e progressivi, e si interroga via HTTP:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT count(*) FILTER (WHERE COORD_X_COMUNE IS NULL) AS senza_coordinate
FROM read_parquet('$public_base/rilasci/$last_date/INDIR_ITA_$last_ymd.parquet');
```

Per confrontare due rilasci si uniscono sui `PROGRESSIVO_ACCESSO`, univoci in
ogni rilascio.

## Provenienza dei rilasci

Il portale ANNCSU conserva solo l'ultimo scarico. Il rilascio del 15 settembre
2026 è lo scarico originale. I rilasci precedenti sono ricostruiti dal parquet
consolidato di [mfortini/diff_ANNCSU](https://github.com/mfortini/diff_ANNCSU),
che ha conservato ogni scarico mensile da settembre 2025 con un flag di
presenza per rilascio. Il metodo riproduce il dialetto del CSV del portale,
compresi due dettagli non ovvi: `QUOTA` non usa mai la notazione scientifica
e non scrive lo zero prima della virgola quando la parte intera è zero, e un
valore `T` di `SPECIFICITA` era stato trasformato in `true` nel consolidato.
Verificato sul rilascio di settembre 2026, l'unico con l'originale a
disposizione: stessi byte, stesso md5 del contenuto ordinato; solo l'ordine
delle righe, che il portale non fissa, non è riproducibile.

Ogni item dichiara la propria origine nella descrizione.

## Schema

$schema_table

## Licenza

$license_paragraph

## Generato automaticamente

Non modificare questo file a mano: è riscritto a ogni aggiornamento dei dati.
Le sorgenti sono in `scripts/catalog/` nel repository; i fatti sui rilasci sono
in `rilasci/releases.json`.
