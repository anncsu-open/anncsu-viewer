# Indirizzi ANNCSU, file unico

Tutti gli accessi esterni censiti in ANNCSU in un unico file GeoParquet, ordinato spazialmente secondo una curva di Hilbert e corredato di colonna bbox, così che un lettore possa scartare interi gruppi di righe senza decodificare le geometrie. Adatto all'analisi sull'intero territorio nazionale. Per leggere un singolo comune conviene la collection partizionata.

Aggiornato al 15 settembre 2026, con 20.731.065 indirizzi.

## Come si legge

Il file è un GeoParquet leggibile via HTTP con DuckDB, GDAL, GeoPandas o qualunque lettore Parquet. Le righe sono ordinate lungo una curva di Hilbert e ogni riga porta un riquadro di delimitazione, quindi un filtro spaziale o su un comune legge solo i gruppi di righe che servono.

```sql
INSTALL httpfs; LOAD httpfs;
SELECT ODONIMO, CIVICO, ESPONENTE
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/anncsu-indirizzi.parquet')
WHERE CODICE_ISTAT = '058091'
LIMIT 10;
```

## Schema

| Colonna | Tipo | Descrizione |
|---|---|---|
| `CODICE_COMUNE` | varchar | Codice amministrativo assegnato ai Comuni italiani dall'Agenzia delle Entrate e utilizzato nella composizione dei codici fiscali. |
| `CODICE_ISTAT` | varchar | Codice amministrativo assegnato ai Comuni italiani dall'Istat. Sei cifre. È la chiave di join con l'elenco dei comuni e con i confini ISTAT. |
| `NOME_COMUNE` | varchar | Denominazione del comune, aggiunta dalla pipeline tramite join su CODICE_ISTAT con l'elenco ufficiale dei comuni italiani pubblicato dall'Istat. Nulla quando il codice non trova corrispondenza. |
| `PROGRESSIVO_NAZIONALE` | bigint | Codice progressivo univoco nazionale, identificativo dell'area di circolazione. |
| `CODICE_COMUNALE` | varchar | Codice dell'odonimo fornito dal Comune. Identificativo utilizzato dal Comune ove presente. |
| `ODONIMO` | varchar | Denominazione completa dell'area di circolazione, composta da DUG e DUF. La DUG è la Denominazione Urbanistica Generica, cioè la tipologia come via o piazza; la DUF è la Denominazione Ufficiale attribuita dal Comune ai sensi delle norme vigenti. |
| `DIZIONE_LINGUA1` | varchar | Odonimo registrato in una prima lingua diversa dall'italiano, secondo le norme in materia di bilinguismo e sull'uso delle lingue delle minoranze linguistiche riconosciute. |
| `DIZIONE_LINGUA2` | varchar | Odonimo registrato in una seconda lingua diversa dall'italiano, secondo le norme in materia di bilinguismo e sull'uso delle lingue delle minoranze linguistiche riconosciute. |
| `PROGRESSIVO_ACCESSO` | bigint | Codice progressivo univoco nazionale, identificativo dell'accesso esterno. |
| `CODICE_COMUNALE_ACCESSO` | varchar | Codice del numero civico fornito dal Comune. Identificativo utilizzato dal Comune ove presente. La pipeline lo forza a VARCHAR perché contiene codici alfanumerici che un'inferenza automatica leggerebbe come interi, scartando le righe non conformi. |
| `CIVICO` | bigint | Valore del numero civico assegnato all'accesso esterno secondo la successione naturale dei numeri. La documentazione della fonte lo descrive come testo di al massimo 5 caratteri, ma nei dati pubblicati è sempre numerico e la pipeline lo conserva come intero. |
| `ESPONENTE` | varchar | Parte letterale del numero civico, ove presente. Per esempio A, B, bis. |
| `SPECIFICITA` | varchar | Valore utilizzato in presenza di uno specifico metodo di classificazione della numerazione civica validato dall'Istat, per esempio ROSSO e NERO. |
| `METRICO` | varchar | Valore del numero civico espresso in metri, usato dai comuni che adottano il sistema metrico anziché la successione naturale dei numeri. |
| `PROGRESSIVO_SNC` | bigint | Se valorizzato indica che l'accesso, posizionato dopo il civico o il metrico indicato, è privo di numero civico standard. Se i riferimenti all'accesso precedente sono assenti, l'accesso SNC è a inizio strada. |
| `longitude` | double | Longitudine dell'accesso in gradi decimali, dalla colonna COORD_X_COMUNE della fonte. Il sistema di riferimento dichiarato dalla fonte è ETRF2000 alla epoca 2008.0, realizzazione italiana di ETRS89. La pipeline converte la virgola decimale in punto. |
| `latitude` | double | Latitudine dell'accesso in gradi decimali, dalla colonna COORD_Y_COMUNE della fonte. Stesso sistema di riferimento e stessa conversione decimale della longitudine. |
| `QUOTA` | varchar | Altezza ortometrica dell'accesso nei sistemi di riferimento altimetrici nazionali ufficiali. La pipeline la conserva come testo perché i valori usano la virgola come separatore decimale. |
| `METODO` | bigint | Modalità con cui il Comune ha attribuito le coordinate. 1 rilevazione strumentale sul campo con accuratezza inferiore a 5 m; 2 rilevazione strumentale sul campo con accuratezza pari o superiore a 5 m; 3 derivazione indiretta da base dati territoriale con accuratezza stimata inferiore a 5 m; 4 derivazione indiretta da base dati territoriale con accuratezza stimata pari o superiore a 5 m; 5 derivazione indiretta tramite le funzioni del Portale per i Comuni. |
| `oob_distance_m` | double | Distanza in metri fra l'indirizzo e il confine del suo comune secondo i confini amministrativi Istat, calcolata dalla pipeline. Nulla quando il comune non ha un confine corrispondente, zero quando il punto cade dentro il confine. |
| `out_of_bounds` | boolean | Vero quando l'indirizzo cade oltre 110 metri fuori dal confine del comune a cui è attribuito. La soglia assorbe la tolleranza di geocodifica. Nullo quando il comune non ha un confine corrispondente. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Riquadro di delimitazione del punto, con i quattro valori uguali alle sue coordinate. È la colonna di covering prevista da GeoParquet, che consente a un lettore di scartare interi gruppi di righe senza decodificare le geometrie. |
| `geometry` | geometry | Punto costruito dalla pipeline a partire da longitudine e latitudine. Dichiarato in OGC:CRS84. La fonte esprime le coordinate in ETRF2000, che differisce da WGS84 per meno di un metro in Italia, quindi lo scarto è trascurabile rispetto alla precisione degli indirizzi. |

## Licenza

I dati sono pubblicati con licenza [Creative Commons Attribuzione 4.0 Internazionale](https://creativecommons.org/licenses/by/4.0/deed.it), identificativo SPDX `CC-BY-4.0`. Le pagine ufficiali ANNCSU richiamano il Regolamento di esecuzione (UE) 2023/138 sui dati di elevato valore, che per la serie degli indirizzi impone questa licenza, ma non la riportano per esteso. Chi ha bisogno di certezza per un riutilizzo commerciale conviene che si rivolga all'Agenzia delle Entrate.

## Provenienza

I dati provengono dal [portale open data ANNCSU](https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/), che ne è la
fonte originale. Titolari dell'archivio sono l'Agenzia delle Entrate e l'Istat;
l'aggiornamento compete ai Comuni. La conversione è eseguita dalla pipeline in
[https://github.com/anncsu-open/anncsu-viewer](https://github.com/anncsu-open/anncsu-viewer). Questo catalogo è una copia derivata, non la fonte.

## Generato automaticamente

Non modificare questo file a mano: è riscritto a ogni aggiornamento dei dati.
Le sorgenti sono in `scripts/catalog/` nel repository.
