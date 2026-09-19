# $title

$description

Aggiornato al $dataset_date_human, con $row_count_human indirizzi. I dati si
vedono sulla mappa nel [visualizzatore web]($viewer_url).

> **Nota sulla visualizzazione.** Nel Portolan Browser, come in STAC Browser
> da cui deriva, l'estensione temporale di questa collection compare come
> "fino ad ora" senza la data di inizio in tutte le lingue dell'interfaccia
> diverse dall'inglese. È un difetto del browser, non del catalogo:
> l'intervallo dichiarato in `extent.temporal` inizia il $dataset_date_human
> ed è aperto, e si legge per intero con l'interfaccia in inglese o nel JSON
> tramite Source.

## Come si legge

$usage

## Statistiche

$statistics_table

## Schema

$schema_table

## Licenza

$license_paragraph

## Provenienza

I dati provengono dal [portale open data ANNCSU]($source_portal), che ne è la
fonte originale. Titolari dell'archivio sono l'Agenzia delle Entrate e l'Istat;
l'aggiornamento compete ai Comuni. La conversione è eseguita dalla pipeline in
[$repo_url]($repo_url). Questo catalogo è una copia derivata, non la fonte.

## Generato automaticamente

Non modificare questo file a mano: è riscritto a ogni aggiornamento dei dati.
Le sorgenti sono in `scripts/catalog/` nel repository.
