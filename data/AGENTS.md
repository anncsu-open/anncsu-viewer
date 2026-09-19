# Istruzioni per agenti

Questo è un catalogo STAC 1.1.0 conforme al profilo
[Portolan](https://github.com/portolan-sdi/portolan-spec) v0.2.0.

## Come leggerlo

Parti da `catalog.json` e segui i link `child`. Ogni collection dichiara i
propri asset con `href` relativi, risolvibili rispetto alla posizione del
`collection.json`. Il link `self` sulla radice riporta la base pubblica, quindi
un href relativo si risolve in URL assoluto anche partendo da una copia locale.

## Cosa sapere prima di interrogare i dati

Ci sono due collection sugli stessi indirizzi. `indirizzi` espone un unico
GeoParquet da circa un gigabyte, ordinato spazialmente: conviene per
aggregazioni nazionali. `indirizzi-h3` espone gli stessi dati partizionati in
file da meno di un megabyte: conviene per un singolo comune o una singola area.

Il campo `partition:glob` di `indirizzi-h3` non è espandibile su HTTPS, perché
il protocollo non offre il listing delle directory. Per sapere quali celle
servono, leggi l'asset `cell-index`, cioè `comuni-h3.json`, che mappa ogni
comune sulle celle che ne contengono gli indirizzi.

Le descrizioni delle colonne sono in `table:columns` su ogni collection.

## Cosa non fare

Non dedurre la copertura temporale dai nomi dei file. La data di riferimento
del rilascio è in `extent.temporal` e il momento dell'ultima sincronizzazione
nel campo `updated`.

Non trattare questo catalogo come fonte autoritativa: è una copia del portale
ANNCSU, indicato dal link `via`.
