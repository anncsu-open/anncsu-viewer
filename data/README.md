# Indirizzi ANNCSU

Gli indirizzi certificati dei comuni italiani, dall'Archivio Nazionale dei
Numeri Civici e delle Strade Urbane, convertiti in formati cloud-native e
pubblicati come catalogo STAC secondo il profilo Portolan.

Aggiornato al 15 settembre 2026, con 20.731.065 indirizzi. Il catalogo
si può esplorare nel [Portolan Browser](https://browser.portolan-sdi.org/#/external/pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/catalog.json) e i dati si vedono sulla
mappa nel [visualizzatore web](https://anncsu-open.github.io/anncsu-viewer/).

## Cosa contiene

| Collection | Cosa serve |
|---|---|
| [Indirizzi ANNCSU, file unico](./indirizzi/) | Analisi sull'intero territorio nazionale |
| [Indirizzi ANNCSU, partizionati per cella H3](./indirizzi-h3/) | Leggere un comune senza scaricare tutto |
| [Rilasci mensili ANNCSU](./rilasci/) | Recuperare uno scarico passato, o confrontare due rilasci |

Le prime due descrivono gli stessi dati in due forme di accesso, e contengono
i soli indirizzi georeferenziati del rilascio corrente. La terza conserva ogni
scarico mensile per intero, comprese le righe senza coordinate. Una versione in
inglese di questo catalogo è in [`en/`](./en/).

## Statistiche

| Statistica | Valore |
|---|---|
| Accessi totali | 20.731.065 |
| Fuori dal confine comunale, oltre 110 m | 51.423 (0,25%) |
| Senza confine comunale di riferimento | 0 |
| Comuni con almeno un accesso | 5.493 |
| Metodo 1, rilevazione strumentale sul campo, accuratezza inferiore a 5 m | 1.714.163 (8,27%) |
| Metodo 2, rilevazione strumentale sul campo, accuratezza pari o superiore a 5 m | 290.652 (1,40%) |
| Metodo 3, derivazione indiretta da base dati territoriale, accuratezza stimata inferiore a 5 m | 7.125.819 (34,37%) |
| Metodo 4, derivazione indiretta da base dati territoriale, accuratezza stimata pari o superiore a 5 m | 10.894.269 (52,55%) |
| Metodo 5, derivazione indiretta tramite le funzioni del Portale per i Comuni | 706.162 (3,41%) |

## Licenza

I dati sono pubblicati con licenza [Creative Commons Attribuzione 4.0 Internazionale](https://creativecommons.org/licenses/by/4.0/deed.it), identificativo SPDX `CC-BY-4.0`. Le pagine ufficiali ANNCSU richiamano il Regolamento di esecuzione (UE) 2023/138 sui dati di elevato valore, che per la serie degli indirizzi impone questa licenza, ma non la riportano per esteso. Chi ha bisogno di certezza per un riutilizzo commerciale conviene che si rivolga all'Agenzia delle Entrate.

## Provenienza

I dati provengono dal [portale open data ANNCSU](https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/), dove sono
pubblicati mensilmente in CSV. Titolari dell'archivio sono l'Agenzia delle
Entrate e l'Istat; l'aggiornamento compete ai Comuni.

La conversione in GeoParquet, PMTiles e tile H3 è eseguita dalla pipeline in
[https://github.com/anncsu-open/anncsu-viewer](https://github.com/anncsu-open/anncsu-viewer) e non modifica i valori: aggiunge la denominazione del
comune tramite join sul codice Istat, la geometria puntuale costruita dalle
coordinate, un riquadro di delimitazione per riga, e due colonne che segnalano
gli indirizzi che cadono fuori dal confine del proprio comune.

Questo catalogo è una copia derivata, non la fonte originale. Per il dato
autoritativo si faccia riferimento al portale ANNCSU.

## Generato automaticamente

Non modificare questi file a mano: sono riscritti a ogni aggiornamento dei
dati. Le sorgenti sono in `scripts/catalog/` nel repository.
