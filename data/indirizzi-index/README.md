# Indice degli indirizzi ANNCSU

Le strade e gli accessi di ANNCSU in due file Parquet ordinati per comune. Un client legge le righe di un comune con richieste HTTP range, senza un server, e ci cerca prima la strada e poi il numero civico. Il formato è descritto da una [bozza di estensione STAC](https://github.com/anncsu-open/anncsu-viewer/blob/main/geocoding/address-index/v0.1.0/README.md) tenuta in questo repository.

La colonna `codice_istat` contiene il `feature_id` della collection `gazetteer`: con il gazetteer si trova il comune, con questo indice l'indirizzo. Un'applicazione che lavora sempre in un solo comune può usare questo indice da solo, con il codice del comune. I dati sono quelli del rilascio ANNCSU del 2 novembre 2026.

## File

| File | Righe | Gruppi di righe | Dimensione |
|---|---|---|---|
| [`vie.parquet`](./2026-11-02/vie.parquet) | 786.969 | 193 da 4.096 righe | 42,7 MB |
| [`civici.parquet`](./2026-11-02/civici.parquet) | 20.728.959 | 633 da 32.768 righe | 425,3 MB |

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
[`geocoding/normalization-vectors.json`](https://github.com/anncsu-open/anncsu-viewer/blob/main/geocoding/normalization-vectors.json).

Il formato dei file e i campi `address_index:*` sono definiti dalla
[bozza dell'estensione address-index](https://github.com/anncsu-open/anncsu-viewer/blob/main/geocoding/address-index/v0.1.0/README.md), che ha anche uno
schema JSON e una collection di esempio.

Con DuckDB, le strade di Vacone (codice Istat 057072) che si chiamano San
Giovanni, poi i civici di una di esse:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT street_id, name, numbers, number_min, number_max
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/indirizzi-index/2026-11-02/vie.parquet')
WHERE codice_istat = '057072' AND name_norm LIKE '%san giovanni%';

SELECT number, suffix, lon, lat
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/indirizzi-index/2026-11-02/civici.parquet')
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

| Colonna | Tipo | Descrizione |
|---|---|---|
| `codice_istat` | varchar | Codice Istat del comune, sei cifre come testo: il feature_id del gazetteer. Prima colonna di ordinamento. |
| `comune` | varchar | Nome del comune dall'elenco Istat, per mostrare un risultato senza leggere il gazetteer. |
| `street_id` | bigint | Identificativo stabile della strada, il PROGRESSIVO_NAZIONALE di ANNCSU. |
| `name` | varchar | Il nome della strada da mostrare: l'ODONIMO come pubblicato, o il nome in altra lingua su una riga alternativa. |
| `name_norm` | varchar | Il nome normalizzato con anncsu-odonimo/1: scomposizione NFD, segni diacritici tolti, minuscole, ogni carattere diverso da lettere, cifre, spazi e trattini sostituito da uno spazio, spazi ripetuti ridotti a uno. Così LIBERTA' e libertà danno entrambi liberta. |
| `name_lang` | varchar | Lingua ISO 639-3 del nome sulle righe in altra lingua, quando è nota. Nulla sulla riga principale. |
| `alt_of` | bigint | Nulla sulla riga principale. Su una riga in altra lingua, lo street_id della strada. |
| `numbers` | integer | Numero di accessi della strada. |
| `number_min` | integer | Il numero civico più basso della strada. Nullo se nessun accesso ha un numero. |
| `number_max` | integer | Il numero civico più alto della strada. Con number_min distingue strade con lo stesso nome. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Riquadro degli accessi della strada in gradi WGS84, senza quelli fuori dal confine comunale; se lo sono tutti, li comprende tutti. |

### Accessi (`civici.parquet`)

| Colonna | Tipo | Descrizione |
|---|---|---|
| `codice_istat` | varchar | Codice Istat del comune, sei cifre come testo: il feature_id del gazetteer. Prima colonna di ordinamento. |
| `street_id` | bigint | La strada dell'accesso: lo street_id del file delle strade, cioè il PROGRESSIVO_NAZIONALE di ANNCSU. |
| `id` | bigint | Identificativo stabile dell'accesso, il PROGRESSIVO_ACCESSO di ANNCSU. |
| `number` | integer | Il numero civico, il CIVICO di ANNCSU. Nullo dove la fonte non lo ha. |
| `suffix` | varchar | L'ESPONENTE di ANNCSU, la parte letterale del civico: A, B, BIS, 1. |
| `specificita` | varchar | La SPECIFICITA di ANNCSU, che contiene tra l'altro la numerazione rossa e nera di Genova, Firenze e Savona. |
| `metrico` | varchar | Il METRICO di ANNCSU: il civico espresso in metri, nei comuni che usano la numerazione metrica. Testo, come nella fonte. |
| `out_of_bounds` | boolean | Vero quando l'accesso cade oltre 110 metri fuori dal confine del suo comune secondo i confini Istat. Nullo quando il comune non ha un confine corrispondente. |
| `lon` | double | Longitudine dell'accesso in gradi, WGS84 (EPSG:4326). |
| `lat` | double | Latitudine dell'accesso in gradi, WGS84 (EPSG:4326). |

## Provenienza

I due file sono costruiti da `scripts/build_geocoding_index.py`, nel
repository [https://github.com/anncsu-open/anncsu-viewer](https://github.com/anncsu-open/anncsu-viewer), a partire dagli accessi georeferenziati
della collection [`indirizzi`](../indirizzi/). Il nome del comune nella
colonna `comune` viene dall'[elenco dei comuni italiani
dell'Istat](https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv). La fonte originale di strade e accessi è il
[portale open data ANNCSU](https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/), di cui sono titolari l'Agenzia
delle Entrate e l'Istat. Questo catalogo ne è una copia derivata.

## Licenza

I dati sono pubblicati con licenza [Creative Commons Attribuzione 4.0 Internazionale](https://creativecommons.org/licenses/by/4.0/deed.it), identificativo SPDX `CC-BY-4.0`. Le pagine ufficiali ANNCSU richiamano il Regolamento di esecuzione (UE) 2023/138 sui dati di elevato valore, che per la serie degli indirizzi impone questa licenza, ma non la riportano per esteso. Chi ha bisogno di certezza per un riutilizzo commerciale conviene che si rivolga all'Agenzia delle Entrate.

Anche l'elenco dei comuni dell'Istat è pubblicato con licenza CC BY 4.0. Chi
riusa i file deve citare sia ANNCSU sia l'Istat.

## Generato automaticamente

Non modificare questo file a mano: è riscritto a ogni generazione del catalogo.
Le sorgenti sono in `scripts/catalog/` nel repository; i fatti sui file sono in
`indirizzi-index/index.json`, scritto da `scripts/build_geocoding_index.py`.
