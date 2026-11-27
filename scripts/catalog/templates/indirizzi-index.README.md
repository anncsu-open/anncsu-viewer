# $title

$description

## File

$files_table

I file non hanno una colonna di geometria. La posizione di una strada è il
riquadro `bbox` dei suoi accessi, quella di un accesso è la coppia `lon`,
`lat`.

## Come si legge

La ricerca di un indirizzo procede in due passi, entrambi con richieste HTTP
range.

1. La strada. Il client legge il footer di `vie.parquet`, sceglie dalle
   statistiche min/max di `codice_istat` i gruppi di righe del comune e scarica
   solo quelli: le righe di un comune sono contigue, circa 15.000 per Roma, il
   comune più grande. Poi normalizza il nome digitato con `anncsu-odonimo/1` e
   lo confronta in memoria con `name_norm`.
2. Il civico. Trovata la strada, il client sceglie in `civici.parquet` i
   gruppi di righe che contengono la coppia `codice_istat`, `street_id`,
   sempre dalle statistiche, e cerca tra quelle righe il numero e l'esponente.

`anncsu-odonimo/1` fa la scomposizione NFD, toglie i segni diacritici, passa
alle minuscole, sostituisce con uno spazio ogni carattere diverso da lettere,
cifre, spazi e trattini, e riduce gli spazi ripetuti a uno. Così "LIBERTA'",
come lo scrive ANNCSU, e "libertà" digitato danno entrambi "liberta". Il
gazetteer usa un'altra funzione, che conserva gli apostrofi: una query si
normalizza con la funzione del file che si interroga. I casi di prova delle due
funzioni sono in
[`geocoding/normalization-vectors.json`]($repo_url/blob/main/geocoding/normalization-vectors.json).

Il formato dei file e i campi `address_index:*` sono definiti dalla
[bozza dell'estensione address-index]($address_index_spec), che ha anche uno
schema JSON e una collection di esempio.

Con DuckDB, le strade di Vacone (codice Istat 057072) che si chiamano San
Giovanni, poi i civici di una di esse:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT street_id, name, numbers, number_min, number_max
FROM read_parquet('$public_base/indirizzi-index/$release/vie.parquet')
WHERE codice_istat = '057072' AND name_norm LIKE '%san giovanni%';

SELECT number, suffix, lon, lat
FROM read_parquet('$public_base/indirizzi-index/$release/civici.parquet')
WHERE codice_istat = '057072' AND street_id = 468312
ORDER BY number;
```

## Il legame con il gazetteer

La colonna `codice_istat` contiene il codice Istat del comune, cioè il
`feature_id` della collection [`gazetteer`](../gazetteer/). Un'applicazione
cerca il comune nel gazetteer e poi l'indirizzo qui. Un'applicazione che lavora
sempre nello stesso comune conosce già il codice e legge solo questi due file.

In `vie.parquet`, le righe con `alt_of` valorizzato sono i nomi in altra lingua
di una strada, da `DIZIONE_LINGUA1` e `DIZIONE_LINGUA2` di ANNCSU: hanno lo
stesso `street_id` della strada, quindi portano agli stessi civici. Per contare
le strade si tengono le righe con `alt_of` nullo.

## Schema

### Strade (`vie.parquet`)

$streets_table

### Accessi (`civici.parquet`)

$access_points_table

## Provenienza

I due file sono costruiti da `scripts/build_geocoding_index.py`, nel
repository [$repo_url]($repo_url), a partire dagli accessi georeferenziati
della collection [`indirizzi`](../indirizzi/). Il nome del comune nella
colonna `comune` viene dall'[elenco dei comuni italiani
dell'Istat]($istat_comuni). La fonte originale di strade e accessi è il
[portale open data ANNCSU]($source_portal), di cui sono titolari l'Agenzia
delle Entrate e l'Istat. Questo catalogo ne è una copia derivata.

## Licenza

$license_paragraph

Anche l'elenco dei comuni dell'Istat è pubblicato con licenza CC BY 4.0. Chi
riusa i file deve citare sia ANNCSU sia l'Istat.

## Generato automaticamente

Non modificare questo file a mano: è riscritto a ogni generazione del catalogo.
Le sorgenti sono in `scripts/catalog/` nel repository; i fatti sui file sono in
`indirizzi-index/index.json`, scritto da `scripts/build_geocoding_index.py`.
