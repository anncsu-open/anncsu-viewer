# Istruzioni per agenti

Collection `gazetteer` del catalogo ANNCSU, conforme al profilo
[Portolan](https://github.com/portolan-sdi/portolan-spec) $portolan_version.
Dichiara l'estensione [gazetteer]($gazetteer_spec): è l'indice dei nomi dei
comuni, da leggere senza un server. È una collection tabulare, senza colonna di
geometria.

## Dove sono i dati

L'asset con ruolo `gazetteer-index` è il file Parquet. Sull'asset,
`gazetteer:row_groups`, `gazetteer:row_group_rows` e
`gazetteer:footer_metadata_bytes` servono a pianificare le richieste HTTP
range; `file:size` dice se il file è cambiato e `file:checksum` è nel formato
multihash. Sulla collection, `gazetteer:levels` è `[3]`, il livello dei
comuni, `gazetteer:normalization` è `nfd-strip-marks-lower/1` e
`gazetteer:sort` è `name_norm`. `version` è la data del rilascio ANNCSU da cui
il file è costruito.

## Come cercare

Normalizza la query con `nfd-strip-marks-lower/1` prima di confrontarla con
`name_norm`. Confronto e ordinamento sono byte per byte su UTF-8, mai secondo
la collazione di una lingua. Due comuni possono avere lo stesso `name_norm`: li
distingue `parent_name`, la provincia.

Il `feature_id` è il codice Istat del comune. Per passare alle strade, cercalo
nella colonna `codice_istat` della collection `indirizzi-index`, indicata dal
link `related`.

## Cosa non fare

Non trattare le righe con `alt_of` valorizzato come comuni distinti: sono altri
nomi dello stesso comune, con lo stesso `feature_id`. Non usare `bbox` come
confine del comune: copre i suoi accessi, non il territorio. Non trattare la
collection come fonte autoritativa: deriva da ANNCSU, indicato dal link `via`,
e dall'elenco dei comuni dell'Istat.
