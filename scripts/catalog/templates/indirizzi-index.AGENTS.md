# Istruzioni per agenti

Collection `indirizzi-index` del catalogo ANNCSU, conforme al profilo
[Portolan](https://github.com/portolan-sdi/portolan-spec) $portolan_version.
Dichiara la [bozza dell'estensione address-index]($address_index_spec), che
per ora vive solo in questo repository. È una collection tabulare, senza
colonna di geometria.

## Dove sono i dati

Due asset Parquet: quello con ruolo `address-streets` è `vie.parquet`, le
strade; quello con ruolo `address-points` è `civici.parquet`, gli accessi.
Ciascuno porta `address_index:sort`, le colonne per cui le righe sono
ordinate, e `address_index:row_groups`, `address_index:row_group_rows` e
`address_index:footer_metadata_bytes` per pianificare le richieste HTTP range,
oltre a `file:size`, `file:checksum` nel formato multihash e `table:columns`.
Sulla collection, `address_index:normalization` è `anncsu-odonimo/1` e
`address_index:place_column` è `codice_istat`. `version` è la data del
rilascio ANNCSU da cui i file sono costruiti.

## Come cercare

Prendi le righe di un comune con le statistiche di `codice_istat`, normalizza
il nome della strada con `anncsu-odonimo/1` e confrontalo con `name_norm`. Per
i civici, filtra `civici.parquet` su `codice_istat` e `street_id`.
L'ordinamento è byte per byte su UTF-8, con i valori nulli in fondo.

Il codice del comune è il `feature_id` della collection `gazetteer`, indicata
dal link `related`.

## Cosa non fare

Non normalizzare la query con la funzione del gazetteer:
`anncsu-odonimo/1` trasforma gli apostrofi in spazi, `nfd-strip-marks-lower/1`
li conserva. Non contare come strade distinte le righe con `alt_of`
valorizzato: sono altri nomi della stessa strada. Non dare per scontato che
ogni accesso abbia un numero: `number` è nullo dove la fonte non lo ha. Non
trattare la collection come fonte autoritativa: deriva da ANNCSU, l'archivio
dell'Agenzia delle Entrate e dell'Istat indicato dal link `via`.
