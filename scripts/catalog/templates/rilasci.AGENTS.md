# Istruzioni per agenti

Collection `rilasci` del catalogo ANNCSU: l'archivio degli scarichi mensili,
conforme al profilo [Portolan](https://github.com/portolan-sdi/portolan-spec)
v0.2.0. È una collection tabulare: gli item non hanno geometria e i file non
hanno una colonna geometry; le coordinate sono testo nelle colonne
`COORD_X_COMUNE` e `COORD_Y_COMUNE`, con la virgola decimale.

## Struttura

Un item per rilascio, con `id` e `version` uguali alla data del rilascio e
`datetime` alla mezzanotte UTC di quel giorno. Gli item sono concatenati con
`predecessor-version` e `successor-version`; la collection punta all'ultimo
con `latest-version`. Le collection `indirizzi` e `indirizzi-h3` puntano al
rilascio da cui derivano con `derived_from` e a questa collection con
`version-history`.

## Asset

Ogni item ha due asset con href assoluti su R2: `data`, il Parquet senza
perdita del CSV, e `source`, lo ZIP originale o ricostruito. `file:size` e
`file:checksum` sono nel formato multihash. La descrizione dell'item dice se
il rilascio è originale o ricostruito.

## Cosa non fare

Non dedurre lo stato corrente da questa collection: il rilascio corrente è
nelle collection `indirizzi` e `indirizzi-h3`, che contengono solo gli accessi
georeferenziati. Non trattare il catalogo come fonte autoritativa: è una
copia del portale ANNCSU, indicato dal link `via`.
