# Istruzioni per agenti

Collection `indirizzi-h3` del catalogo ANNCSU, conforme al profilo
[Portolan](https://github.com/portolan-sdi/portolan-spec) v0.2.0.

## Accesso ai dati

I dati sono divisi per cella H3 di risoluzione 5, con struttura Hive. Il glob di accesso massivo è `https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/tiles/h3_cell=*/*.parquet`, ma su HTTPS non esiste il listing delle directory, quindi un lettore non può espanderlo da solo. Per sapere quali celle servono si legge l'indice `comuni-h3.json`, che mappa ogni comune sulle sue celle.

```shell
curl -s https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/comuni-h3.json \
  | jq -r '.[] | select(.nome_comune == "Roma") | .h3_cells[]'
```

```sql
SELECT count(*)
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/tiles/h3_cell=851fb467fffffff/851fb467fffffff.parquet')
WHERE CODICE_ISTAT = '058091';
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
