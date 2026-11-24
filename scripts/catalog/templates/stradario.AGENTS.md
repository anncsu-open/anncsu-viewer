# Istruzioni per agenti

Collection `stradario` del catalogo ANNCSU: l'archivio dello stradario
nazionale, conforme al profilo
[Portolan](https://github.com/portolan-sdi/portolan-spec)
$portolan_version. È una collection tabulare: gli item non hanno geometria e i
file non hanno una colonna geometry. Le nove colonne sono tutte testo.

## Struttura

Un item per rilascio, con `id` e `version` uguali alla data del rilascio e
`datetime` alla mezzanotte UTC di quel giorno. Gli item sono concatenati con
`predecessor-version` e `successor-version`; la collection punta all'ultimo
con `latest-version`. L'item di un rilascio che ha anche i civici in `rilasci`
li indica con un link `related`, e viceversa.

## Asset

Ogni item ha l'asset `data`, il Parquet del CSV, senza perdita per i
rilasci originali, e di solito l'asset `source`, lo ZIP originale del
portale. Un item senza asset `source` non
ha lo ZIP: ha origine `third-party`, cioè un Parquet convertito da altri, e la
descrizione lo dice. Gli href sono assoluti su R2; `file:size` e
`file:checksum` sono nel formato multihash.

## Cosa non fare

Non assumere che ogni mese abbia un rilascio: l'archivio ha lacune, descritte
nel README. Non ricostruire lo stradario di un mese mancante raggruppando i
civici senza dire che le strade senza accessi mancano. Non trattare il
catalogo come fonte autoritativa: è una copia del portale ANNCSU, indicato dal
link `via`.
