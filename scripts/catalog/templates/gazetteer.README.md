# $title

$description

## File

$files_table

Il file non ha una colonna di geometria. La posizione di un comune è il
riquadro `bbox`, calcolato sui suoi accessi: è più stretto del territorio
comunale, ma basta per portare la mappa sul comune.

## Come si legge

Un client normalizza il testo digitato con `nfd-strip-marks-lower/1`, la
stessa funzione che ha prodotto `name_norm`: scomposizione NFD, segni
diacritici tolti, minuscole, tolti i caratteri diversi da lettere, cifre,
spazi, apostrofi e trattini, spazi ripetuti ridotti a uno. Poi legge il footer
del Parquet, sceglie dalle statistiche min/max di `name_norm` i gruppi di righe
che possono contenere il prefisso cercato e scarica solo quelli, con richieste
HTTP range. Il file è piccolo, quindi un client può anche leggerlo per intero.

[`@cngeo/geocoder-core`]($geocoder_core), del progetto cng-map-widgets,
prende l'asset con ruolo `gazetteer-index` e pianifica le letture con i campi
`gazetteer:*`. Il formato del file e quei
campi sono definiti dall'[estensione gazetteer]($gazetteer_spec).

Con DuckDB, i due comuni che si chiamano Castro, distinti dalla provincia:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT name, parent_name, feature_id, bbox
FROM read_parquet('$public_base/gazetteer/$release/comuni.parquet')
WHERE name_norm = 'castro';
```

## Nomi alternativi e indice degli indirizzi

Una riga con `alt_of` valorizzato è un altro nome dello stesso comune: il nome
in altra lingua dell'elenco Istat, con la lingua in `name_lang` (Bozen per
Bolzano), oppure il nome scritto con uno spazio al posto dell'apostrofo, così
che chi digita "sant ambrogio" trovi Sant'Ambrogio di Torino. Per contare i
comuni o per unirli ad altri dati si tengono le righe con `alt_of` nullo.

Il `feature_id` è il codice Istat del comune, sei cifre come testo. La
collection [`indirizzi-index`](../indirizzi-index/) ha lo stesso valore nella
colonna `codice_istat`, quindi dal comune trovato qui si passa alle sue strade.

## Schema

$gazetteer_table

## Provenienza

Il file è costruito da `scripts/build_geocoding_index.py`, nel repository
[$repo_url]($repo_url), a partire dagli accessi georeferenziati della
collection [`indirizzi`](../indirizzi/) e dall'[elenco dei comuni italiani
dell'Istat]($istat_comuni), da cui vengono i nomi, le province e i nomi in
altra lingua. La fonte originale degli indirizzi è il [portale open data
ANNCSU]($source_portal), di cui sono titolari l'Agenzia delle Entrate e
l'Istat. Questo catalogo ne è una copia derivata.

## Licenza

$license_paragraph

Anche l'elenco dei comuni dell'Istat è pubblicato con licenza CC BY 4.0. Chi
riusa il file deve citare sia ANNCSU sia l'Istat.

## Generato automaticamente

Non modificare questo file a mano: è riscritto a ogni generazione del catalogo.
Le sorgenti sono in `scripts/catalog/` nel repository; i fatti sui file sono in
`gazetteer/index.json`, scritto da `scripts/build_geocoding_index.py`.
