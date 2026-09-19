# Istruzioni per agenti

Collection `indirizzi` del catalogo ANNCSU, conforme al profilo
[Portolan](https://github.com/portolan-sdi/portolan-spec) v0.2.0.

## Accesso ai dati

Il file è un GeoParquet leggibile via HTTP con DuckDB, GDAL, GeoPandas o qualunque lettore Parquet. Le righe sono ordinate lungo una curva di Hilbert e ogni riga porta un riquadro di delimitazione, quindi un filtro spaziale o su un comune legge solo i gruppi di righe che servono.

```sql
INSTALL httpfs; LOAD httpfs;
SELECT ODONIMO, CIVICO, ESPONENTE
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/anncsu-indirizzi.parquet')
WHERE CODICE_ISTAT = '058091'
LIMIT 10;
```

## Schema

Le colonne sono documentate in `table:columns` dentro `collection.json`, con
nome, tipo e descrizione in italiano. La stessa tabella è nel README.

Attenzione a tre tipi che divergono dalla documentazione della fonte, perché la
conversione li inferisce dai dati reali: `CIVICO` è intero benché la fonte lo
descriva come testo, `QUOTA` è testo perché i valori usano la virgola decimale,
`METODO` è intero benché la fonte lo descriva come carattere singolo.

## Resa cartografica

Gli stili sono asset con ruolo `style`. Quello con anche il ruolo `default` è
l'impostazione predefinita. Sono file MapLibre GL completi: si caricano
direttamente, senza assemblare nulla.

## Cosa non fare

Non trattare questa collection come fonte autoritativa: è una copia del portale
ANNCSU, indicato dal link `via`.
