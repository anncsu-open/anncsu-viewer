# Indirizzi ANNCSU

Gli indirizzi certificati dei comuni italiani, dall'Archivio Nazionale dei
Numeri Civici e delle Strade Urbane, convertiti in formati cloud-native e
pubblicati come catalogo STAC secondo il profilo Portolan.

Aggiornato al 15 settembre 2026, con 20.731.065 indirizzi.

## Cosa contiene

| Collection | Cosa serve |
|---|---|
| [Indirizzi ANNCSU, file unico](./indirizzi/) | Analisi sull'intero territorio nazionale |
| [Indirizzi ANNCSU, partizionati per cella H3](./indirizzi-h3/) | Leggere un comune senza scaricare tutto |

Le due collection descrivono gli stessi dati in due forme di accesso.

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
