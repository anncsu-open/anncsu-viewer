# Indirizzi ANNCSU

Gli indirizzi certificati dei comuni italiani, dall'Archivio Nazionale dei
Numeri Civici e delle Strade Urbane, convertiti in formati cloud-native e
pubblicati come catalogo STAC secondo il profilo Portolan.

Aggiornato al $dataset_date_human, con $row_count_human indirizzi. Il catalogo
si può esplorare nel [Portolan Browser]($browser_url) e i dati si vedono sulla
mappa nel [visualizzatore web]($viewer_url).

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

$statistics_table

## Licenza

$license_paragraph

## Provenienza

I dati provengono dal [portale open data ANNCSU]($source_portal), dove sono
pubblicati mensilmente in CSV. Titolari dell'archivio sono l'Agenzia delle
Entrate e l'Istat; l'aggiornamento compete ai Comuni.

La conversione in GeoParquet, PMTiles e tile H3 è eseguita dalla pipeline in
[$repo_url]($repo_url) e non modifica i valori: aggiunge la denominazione del
comune tramite join sul codice Istat, la geometria puntuale costruita dalle
coordinate, un riquadro di delimitazione per riga, e due colonne che segnalano
gli indirizzi che cadono fuori dal confine del proprio comune.

Questo catalogo è una copia derivata, non la fonte originale. Per il dato
autoritativo si faccia riferimento al portale ANNCSU.

## Generato automaticamente

Non modificare questi file a mano: sono riscritti a ogni aggiornamento dei
dati. Le sorgenti sono in `scripts/catalog/` nel repository.
