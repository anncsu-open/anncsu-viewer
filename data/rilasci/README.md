# Rilasci mensili ANNCSU

Ogni scarico mensile dell'indirizzario nazionale, dal 3 settembre 2025 al 15 settembre 2026, così come pubblicato dal [portale ANNCSU](https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/). Il portale serve solo l'ultimo rilascio: qui restano tutti.

Ogni rilascio ha due file:

- l'**archivio ZIP** come lo distribuisce il portale;
- una **copia Parquet senza perdita** del CSV, con tutte le righe e le 19 colonne originali come testo, coordinate comprese ma senza geometria.

È lo storico da cui le collection `indirizzi` e `indirizzi-h3` derivano il rilascio corrente. I rilasci precedenti al 15 settembre 2026 sono ricostruiti dal parquet consolidato di [mfortini/diff_ANNCSU](https://github.com/mfortini/diff_ANNCSU), con un metodo verificato byte per byte sul rilascio di settembre.

## Rilasci

| Rilascio | Origine | Accessi | ZIP | Parquet |
|---|---|---|---|---|
| [2026-09-15](./2026-09-15/2026-09-15.json) | originale | 27.415.954 | [336,1 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-09-15/indirizzarioItalia_20260915.zip) | [258,9 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-09-15/INDIR_ITA_20260915.parquet) |
| [2026-08-03](./2026-08-03/2026-08-03.json) | ricostruito | 27.405.709 | [324,7 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-08-03/indirizzarioItalia_20260803.zip) | [258,5 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-08-03/INDIR_ITA_20260803.parquet) |
| [2026-07-03](./2026-07-03/2026-07-03.json) | ricostruito | 27.405.384 | [324,4 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-07-03/indirizzarioItalia_20260703.zip) | [258,1 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-07-03/INDIR_ITA_20260703.parquet) |
| [2026-06-02](./2026-06-02/2026-06-02.json) | ricostruito | 27.418.271 | [323,7 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-06-02/indirizzarioItalia_20260602.zip) | [257,5 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-06-02/INDIR_ITA_20260602.parquet) |
| [2026-05-04](./2026-05-04/2026-05-04.json) | ricostruito | 27.416.925 | [321,6 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-05-04/indirizzarioItalia_20260504.zip) | [255,2 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-05-04/INDIR_ITA_20260504.parquet) |
| [2026-04-06](./2026-04-06/2026-04-06.json) | ricostruito | 27.458.420 | [309,3 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-04-06/indirizzarioItalia_20260406.zip) | [242,9 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-04-06/INDIR_ITA_20260406.parquet) |
| [2026-03-06](./2026-03-06/2026-03-06.json) | ricostruito | 27.569.011 | [276,0 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-03-06/indirizzarioItalia_20260306.zip) | [209,9 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-03-06/INDIR_ITA_20260306.parquet) |
| [2026-02-06](./2026-02-06/2026-02-06.json) | ricostruito | 27.843.626 | [232,1 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-02-06/indirizzarioItalia_20260206.zip) | [172,1 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-02-06/INDIR_ITA_20260206.parquet) |
| [2026-01-14](./2026-01-14/2026-01-14.json) | ricostruito | 27.862.795 | [215,4 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-01-14/indirizzarioItalia_20260114.zip) | [160,4 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-01-14/INDIR_ITA_20260114.parquet) |
| [2025-12-02](./2025-12-02/2025-12-02.json) | ricostruito | 27.964.607 | [185,7 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-12-02/indirizzarioItalia_20251202.zip) | [128,6 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-12-02/INDIR_ITA_20251202.parquet) |
| [2025-11-04](./2025-11-04/2025-11-04.json) | ricostruito | 27.956.679 | [174,8 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-11-04/indirizzarioItalia_20251104.zip) | [113,1 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-11-04/INDIR_ITA_20251104.parquet) |
| [2025-10-10](./2025-10-10/2025-10-10.json) | ricostruito | 27.949.296 | [173,1 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-10-10/indirizzarioItalia_20251010.zip) | [110,9 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-10-10/INDIR_ITA_20251010.parquet) |
| [2025-09-03](./2025-09-03/2025-09-03.json) | ricostruito | 27.950.169 | [172,4 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-09-03/indirizzarioItalia_20250903.zip) | [109,9 MB](https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2025-09-03/INDIR_ITA_20250903.parquet) |

## Come si legge

Ogni rilascio ha due file su R2. Lo ZIP è l'archivio come lo pubblica il
portale, con dentro `INDIR_ITA_aaaammgg.csv`: 19 colonne separate da `;`,
senza virgolette, con la virgola decimale. Il Parquet ne è la copia senza
perdita, tutte le righe e tutte le colonne come testo, ordinato per codice
Istat e progressivi, e si interroga via HTTP:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT count(*) FILTER (WHERE COORD_X_COMUNE IS NULL) AS senza_coordinate
FROM read_parquet('https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/rilasci/2026-09-15/INDIR_ITA_20260915.parquet');
```

Per confrontare due rilasci si uniscono sui `PROGRESSIVO_ACCESSO`, univoci in
ogni rilascio.

## Provenienza dei rilasci

Il portale ANNCSU conserva solo l'ultimo scarico. Il rilascio del 15 settembre
2026 è lo scarico originale. I rilasci precedenti sono ricostruiti dal parquet
consolidato di [mfortini/diff_ANNCSU](https://github.com/mfortini/diff_ANNCSU),
che ha conservato ogni scarico mensile da settembre 2025 con un flag di
presenza per rilascio. Il metodo riproduce il dialetto del CSV del portale,
compresi due dettagli non ovvi: `QUOTA` non usa mai la notazione scientifica
e non scrive lo zero prima della virgola quando la parte intera è zero, e un
valore `T` di `SPECIFICITA` era stato trasformato in `true` nel consolidato.
Verificato sul rilascio di settembre 2026, l'unico con l'originale a
disposizione: stessi byte, stesso md5 del contenuto ordinato; solo l'ordine
delle righe, che il portale non fissa, non è riproducibile.

Ogni item dichiara la propria origine nella descrizione.

## Schema

| Colonna | Tipo | Descrizione |
|---|---|---|
| `CODICE_COMUNE` | varchar | Codice amministrativo assegnato ai Comuni italiani dall'Agenzia delle Entrate e utilizzato nella composizione dei codici fiscali. |
| `CODICE_ISTAT` | varchar | Codice amministrativo assegnato ai Comuni italiani dall'Istat. Sei cifre. È la chiave di join con l'elenco dei comuni e con i confini ISTAT. |
| `PROGRESSIVO_NAZIONALE` | varchar | Codice progressivo univoco nazionale, identificativo dell'area di circolazione. |
| `CODICE_COMUNALE` | varchar | Codice dell'odonimo fornito dal Comune. Identificativo utilizzato dal Comune ove presente. |
| `ODONIMO` | varchar | Denominazione completa dell'area di circolazione, composta da DUG e DUF. La DUG è la Denominazione Urbanistica Generica, cioè la tipologia come via o piazza; la DUF è la Denominazione Ufficiale attribuita dal Comune ai sensi delle norme vigenti. |
| `LOCALITA'` | varchar | Denominazione della località, ove il Comune la registra. Presente solo nel CSV originale e nel parquet grezzo dell'archivio: il GeoParquet arricchito non la riporta. |
| `DIZIONE_LINGUA1` | varchar | Odonimo registrato in una prima lingua diversa dall'italiano, secondo le norme in materia di bilinguismo e sull'uso delle lingue delle minoranze linguistiche riconosciute. |
| `DIZIONE_LINGUA2` | varchar | Odonimo registrato in una seconda lingua diversa dall'italiano, secondo le norme in materia di bilinguismo e sull'uso delle lingue delle minoranze linguistiche riconosciute. |
| `PROGRESSIVO_ACCESSO` | varchar | Codice progressivo univoco nazionale, identificativo dell'accesso esterno. |
| `CODICE_COMUNALE_ACCESSO` | varchar | Codice del numero civico fornito dal Comune. Identificativo utilizzato dal Comune ove presente. La pipeline lo forza a VARCHAR perché contiene codici alfanumerici che un'inferenza automatica leggerebbe come interi, scartando le righe non conformi. |
| `CIVICO` | varchar | Valore del numero civico assegnato all'accesso esterno secondo la successione naturale dei numeri. La documentazione della fonte lo descrive come testo di al massimo 5 caratteri, ma nei dati pubblicati è sempre numerico e la pipeline lo conserva come intero. |
| `ESPONENTE` | varchar | Parte letterale del numero civico, ove presente. Per esempio A, B, bis. |
| `SPECIFICITA` | varchar | Valore utilizzato in presenza di uno specifico metodo di classificazione della numerazione civica validato dall'Istat, per esempio ROSSO e NERO. |
| `METRICO` | varchar | Valore del numero civico espresso in metri, usato dai comuni che adottano il sistema metrico anziché la successione naturale dei numeri. |
| `PROGRESSIVO_SNC` | varchar | Se valorizzato indica che l'accesso, posizionato dopo il civico o il metrico indicato, è privo di numero civico standard. Se i riferimenti all'accesso precedente sono assenti, l'accesso SNC è a inizio strada. |
| `COORD_X_COMUNE` | varchar | Longitudine dell'accesso come la scrive il portale: gradi decimali con la virgola come separatore, in ETRF2000. Nel GeoParquet arricchito diventa la colonna longitude, numerica. |
| `COORD_Y_COMUNE` | varchar | Latitudine dell'accesso come la scrive il portale: gradi decimali con la virgola come separatore, in ETRF2000. Nel GeoParquet arricchito diventa la colonna latitude, numerica. |
| `QUOTA` | varchar | Altezza ortometrica dell'accesso nei sistemi di riferimento altimetrici nazionali ufficiali. La pipeline la conserva come testo perché i valori usano la virgola come separatore decimale. |
| `METODO` | varchar | Modalità con cui il Comune ha attribuito le coordinate. 1 rilevazione strumentale sul campo con accuratezza inferiore a 5 m; 2 rilevazione strumentale sul campo con accuratezza pari o superiore a 5 m; 3 derivazione indiretta da base dati territoriale con accuratezza stimata inferiore a 5 m; 4 derivazione indiretta da base dati territoriale con accuratezza stimata pari o superiore a 5 m; 5 derivazione indiretta tramite le funzioni del Portale per i Comuni. |

## Licenza

I dati sono pubblicati con licenza [Creative Commons Attribuzione 4.0 Internazionale](https://creativecommons.org/licenses/by/4.0/deed.it), identificativo SPDX `CC-BY-4.0`. Le pagine ufficiali ANNCSU richiamano il Regolamento di esecuzione (UE) 2023/138 sui dati di elevato valore, che per la serie degli indirizzi impone questa licenza, ma non la riportano per esteso. Chi ha bisogno di certezza per un riutilizzo commerciale conviene che si rivolga all'Agenzia delle Entrate.

## Generato automaticamente

Non modificare questo file a mano: è riscritto a ogni aggiornamento dei dati.
Le sorgenti sono in `scripts/catalog/` nel repository; i fatti sui rilasci sono
in `rilasci/releases.json`.
