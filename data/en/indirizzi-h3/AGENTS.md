# Instructions for agents

Collection `indirizzi-h3` of the ANNCSU catalog, conforming to the
[Portolan](https://github.com/portolan-sdi/portolan-spec) profile v0.2.0.
This is the English translation; the Italian source collection is the
`alternate` link with `hreflang: it`, and the data assets live in that tree.

## Data access

The data is split by resolution 5 H3 cell, in Hive layout. The bulk-access glob is `https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/tiles/h3_cell=*/*.parquet`, but HTTPS offers no directory listing, so a reader cannot expand it on its own. To know which cells you need, read the `comuni-h3.json` index, which maps every comune to its cells.

```shell
curl -s https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/comuni-h3.json \
  | jq -r '.[] | select(.nome_comune == "Roma") | .h3_cells[]'
```

```sql
SELECT count(*)
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/tiles/h3_cell=851fb467fffffff/851fb467fffffff.parquet')
WHERE CODICE_ISTAT = '058091';
```

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
