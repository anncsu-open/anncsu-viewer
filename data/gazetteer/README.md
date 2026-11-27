# Gazetteer dei comuni ANNCSU

I comuni che hanno almeno un indirizzo in ANNCSU, in un file Parquet nel formato indice dell'estensione STAC [gazetteer](https://github.com/cholmes/stac-gazetteer/blob/main/gazetteer/v1.0.0/README.md). Ogni comune ha il nome, la provincia, il codice Istat come `feature_id` e il riquadro dei suoi accessi. I nomi in altra lingua e le grafie con uno spazio al posto dell'apostrofo sono righe in più. Le righe sono ordinate per `name_norm`, quindi un client trova un comune per nome con poche richieste HTTP range, senza un server; [`@cngeo/geocoder-core`](https://github.com/cholmes/cng-map-widgets/tree/main/packages/geocoder-core) legge questa collection così com'è.

Il `feature_id` è la chiave con cui la collection `indirizzi-index` cerca le strade del comune. I dati sono quelli del rilascio ANNCSU del 2 novembre 2026.

## File

| File | Righe | Gruppi di righe | Dimensione |
|---|---|---|---|
| [`comuni.parquet`](./2026-11-02/comuni.parquet) | 5.821 | 2 da 4.096 righe | 0,4 MB |

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

[`@cngeo/geocoder-core`](https://github.com/cholmes/cng-map-widgets/tree/main/packages/geocoder-core), del progetto cng-map-widgets,
prende l'asset con ruolo `gazetteer-index` e pianifica le letture con i campi
`gazetteer:*`. Il formato del file e quei
campi sono definiti dall'[estensione gazetteer](https://github.com/cholmes/stac-gazetteer/blob/main/gazetteer/v1.0.0/README.md).

Con DuckDB, i due comuni che si chiamano Castro, distinti dalla provincia:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT name, parent_name, feature_id, bbox
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/gazetteer/2026-11-02/comuni.parquet')
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

| Colonna | Tipo | Descrizione |
|---|---|---|
| `name` | varchar | Il nome da mostrare, dall'elenco dei comuni dell'Istat. Su una riga alternativa è il nome in altra lingua, oppure lo stesso nome quando la riga cambia solo name_norm. |
| `name_norm` | varchar | Il nome normalizzato con nfd-strip-marks-lower/1: scomposizione NFD, segni diacritici tolti, minuscole, tolti i caratteri diversi da lettere, cifre, spazi, apostrofi e trattini, spazi ripetuti ridotti a uno. È la colonna di ordinamento, confrontata byte per byte. |
| `level` | integer | Livello amministrativo, sempre 3: il livello dei comuni in geoBoundaries (ADM3) e in Who's On First (localadmin). |
| `country` | varchar | Codice ISO 3166-1 alpha-3 del paese, sempre ITA. |
| `feature_id` | varchar | Codice Istat del comune, sei cifre come testo. Le righe alternative ripetono il codice del loro comune. È il valore della colonna codice_istat nell'indice degli indirizzi. |
| `country_name` | varchar | Nome del paese, sempre Italia. |
| `parent_name` | varchar | Nome della provincia, cioè dell'unità territoriale sovracomunale dell'Istat. Distingue i comuni con lo stesso nome. |
| `parent_id` | varchar | Codice Istat dell'unità territoriale sovracomunale. |
| `name_lang` | varchar | Lingua del nome in ISO 639-3, per esempio deu o slv, sulle righe in altra lingua. Nulla sulle altre righe. |
| `alt_of` | varchar | Nulla sulla riga principale. Su una riga alternativa, il feature_id del comune di cui la riga è un altro nome. |
| `source` | varchar | Origine della riga, sempre anncsu. |
| `addresses` | integer | Numero di accessi georeferenziati del comune nel rilascio, compresi quelli che ANNCSU colloca fuori dal confine comunale. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Riquadro degli accessi del comune in gradi WGS84, senza quelli fuori dal confine comunale; se lo sono tutti, li comprende tutti. È più stretto del territorio del comune. |

## Provenienza

Il file è costruito da `scripts/build_geocoding_index.py`, nel repository
[https://github.com/anncsu-open/anncsu-viewer](https://github.com/anncsu-open/anncsu-viewer), a partire dagli accessi georeferenziati della
collection [`indirizzi`](../indirizzi/) e dall'[elenco dei comuni italiani
dell'Istat](https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv), da cui vengono i nomi, le province e i nomi in
altra lingua. La fonte originale degli indirizzi è il [portale open data
ANNCSU](https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/), di cui sono titolari l'Agenzia delle Entrate e
l'Istat. Questo catalogo ne è una copia derivata.

## Licenza

I dati sono pubblicati con licenza [Creative Commons Attribuzione 4.0 Internazionale](https://creativecommons.org/licenses/by/4.0/deed.it), identificativo SPDX `CC-BY-4.0`. Le pagine ufficiali ANNCSU richiamano il Regolamento di esecuzione (UE) 2023/138 sui dati di elevato valore, che per la serie degli indirizzi impone questa licenza, ma non la riportano per esteso. Chi ha bisogno di certezza per un riutilizzo commerciale conviene che si rivolga all'Agenzia delle Entrate.

Anche l'elenco dei comuni dell'Istat è pubblicato con licenza CC BY 4.0. Chi
riusa il file deve citare sia ANNCSU sia l'Istat.

## Generato automaticamente

Non modificare questo file a mano: è riscritto a ogni generazione del catalogo.
Le sorgenti sono in `scripts/catalog/` nel repository; i fatti sui file sono in
`gazetteer/index.json`, scritto da `scripts/build_geocoding_index.py`.
