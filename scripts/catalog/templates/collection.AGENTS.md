# Istruzioni per agenti

Collection `$id` del catalogo ANNCSU, conforme al profilo
[Portolan](https://github.com/portolan-sdi/portolan-spec) v0.2.0.

## Accesso ai dati

$usage

## Schema

Le colonne sono documentate in `table:columns` dentro `collection.json`, con
nome, tipo e descrizione in italiano. La stessa tabella è nel README.

Attenzione a tre tipi che divergono dalla documentazione della fonte, perché la
conversione li inferisce dai dati reali: `CIVICO` è intero benché la fonte lo
descriva come testo, `QUOTA` è testo perché i valori usano la virgola decimale,
`METODO` è intero benché la fonte lo descriva come carattere singolo.

## Resa cartografica

Gli stili sono asset con ruolo `style`. Quello con anche il ruolo `default` è
l'impostazione predefinita. Sono file MapLibre GL completi: si caricano
direttamente, senza assemblare nulla.

## Cosa non fare

Non trattare questa collection come fonte autoritativa: è una copia del portale
ANNCSU, indicato dal link `via`.
