# Instructions for agents

Collection `$id` of the ANNCSU catalog, conforming to the
[Portolan](https://github.com/portolan-sdi/portolan-spec) profile v0.2.0.
This is the English translation; the Italian source collection is the
`alternate` link with `hreflang: it`, and the data assets live in that tree.

## Data access

$usage

## Schema

Columns are documented in `table:columns` inside `collection.json`, with name,
type and description. The same table is in the README.

Mind three types that diverge from the source documentation, because the
conversion infers them from the real data: `CIVICO` is an integer although the
source describes it as text, `QUOTA` is text because the values use a decimal
comma, `METODO` is an integer although the source describes it as a single
character.

## Rendering

Styles are assets with the `style` role. The one that also carries the
`default` role is the default. They are complete MapLibre GL style files: load
them directly, nothing needs assembling.

## What not to do

Do not treat this collection as the authoritative source: it is a copy of the
ANNCSU portal, indicated by the `via` link.
