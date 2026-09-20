# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.5.5",
#     "pillow",
#     "pmtiles",
#     "pyyaml",
#     "typer",
# ]
# ///
"""Generate the Portolan STAC catalog for the ANNCSU dataset.

Usage:
    uv run scripts/build_catalog.py

Reads the data already in data/ and the hand-written sources in
scripts/catalog/, then writes the catalog into data/ so the existing rclone
sync publishes it alongside the data.

The output is deterministic: run twice over unchanged data and the bytes are
identical, so the workflow commits nothing when nothing changed.

See docs/how-to-portolan.md for the design and CATALOG.md for usage.
"""

import hashlib
import json
import math
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from string import Template

import typer
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
SOURCE_DIR = Path(__file__).resolve().parent / "catalog"
COLUMNS_FILE = SOURCE_DIR / "columns.yaml"
TEMPLATE_DIR = SOURCE_DIR / "templates"
STYLE_DIR = SOURCE_DIR / "styles"

PARQUET_FILE = DATA_DIR / "anncsu-indirizzi.parquet"
PMTILES_FILE = DATA_DIR / "anncsu-indirizzi.pmtiles"
COMUNI_H3_FILE = DATA_DIR / "comuni-h3.json"
TILES_DIR = DATA_DIR / "tiles"
MARKER_FILE = DATA_DIR / ".last_remote_date"
RELEASES_DIR = DATA_DIR / "rilasci"
RELEASES_FILE = RELEASES_DIR / "releases.json"

# The upstream CSV columns, in file order. The raw archive Parquet keeps
# exactly these, all as text.
RAW_COLUMNS = [
    "CODICE_COMUNE",
    "CODICE_ISTAT",
    "PROGRESSIVO_NAZIONALE",
    "CODICE_COMUNALE",
    "ODONIMO",
    "LOCALITA'",
    "DIZIONE_LINGUA1",
    "DIZIONE_LINGUA2",
    "PROGRESSIVO_ACCESSO",
    "CODICE_COMUNALE_ACCESSO",
    "CIVICO",
    "ESPONENTE",
    "SPECIFICITA",
    "METRICO",
    "PROGRESSIVO_SNC",
    "COORD_X_COMUNE",
    "COORD_Y_COMUNE",
    "QUOTA",
    "METODO",
]
RELEASE_ORIGINS = ("original", "reconstructed")

PUBLIC_BASE = "https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev"
REPO_URL = "https://github.com/anncsu-open/anncsu-viewer"
SOURCE_PORTAL = "https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/"
LICENSE_ID = "CC-BY-4.0"
VIEWER_URL = "https://anncsu-open.github.io/anncsu-viewer/"
BROWSER_URL = (
    "https://browser.portolan-sdi.org/#/external/"
    + PUBLIC_BASE.removeprefix("https://")
    + "/catalog.json"
)

PORTOLAN_SCHEMA = "https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json"
PARTITION_SCHEMA = (
    "https://schemas.portolan-sdi.org/incubating/partition/v1.0.0/schema.json"
)
FILE_SCHEMA = "https://stac-extensions.github.io/file/v2.1.0/schema.json"
TABLE_SCHEMA = "https://stac-extensions.github.io/table/v1.2.0/schema.json"
PROJECTION_SCHEMA = "https://stac-extensions.github.io/projection/v2.0.0/schema.json"
WEB_MAP_LINKS_SCHEMA = (
    "https://stac-extensions.github.io/web-map-links/v1.3.0/schema.json"
)

H3_RESOLUTION = 5


def stac_type(duckdb_type: str) -> str:
    """Map a DuckDB type name onto the string the table extension carries.

    GEOMETRY carries its CRS as a parameter, which is metadata about the
    column rather than its type, and the projection extension already states
    the CRS. Everything else is lowercased as-is, matching the reference
    catalog in the Portolan spec.
    """
    text = duckdb_type.strip()
    if text.upper().startswith("GEOMETRY"):
        return "geometry"
    return text.lower()


def load_columns(path: Path) -> dict[str, dict]:
    """Load the hand-written column documentation in both languages.

    A column without an English description would silently publish Italian
    text in the English tree, so its absence stops the build.
    """
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    untranslated = [
        name
        for name, spec in raw.items()
        if not str(spec.get("description_en", "")).strip()
    ]
    if untranslated:
        raise SystemExit(
            f"Columns without description_en in {path.name}: "
            f"{', '.join(untranslated)}. The English tree needs every column."
        )

    columns = {}
    for name, spec in raw.items():
        columns[name] = {
            "type": str(spec["type"]),
            "description": " ".join(str(spec["description"]).split()),
            "description_en": " ".join(str(spec["description_en"]).split()),
            "derived": bool(spec.get("derived", False)),
            "tiles_only": bool(spec.get("tiles_only", False)),
            "raw_only": bool(spec.get("raw_only", False)),
        }
    return columns


def read_parquet_columns(parquet_path: Path) -> list[tuple[str, str]]:
    """Return (name, DuckDB type) for every column, in file order."""
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}')"
    ).fetchall()
    con.close()
    return [(row[0], row[1]) for row in rows]


def table_columns(
    parquet_path: Path, columns_path: Path, lang: str = "it"
) -> list[dict]:
    """Build the STAC table:columns array, failing on any schema drift.

    An upstream schema change must stop the build rather than produce a
    catalog that describes columns the data no longer has, or omits columns it
    gained. Columns flagged tiles_only are expected to be absent from a file
    that is not a partition; columns flagged raw_only are expected to be
    absent from any enriched file. ``lang`` selects the description language.
    """
    description_key = "description" if lang == "it" else f"description_{lang}"
    documented = load_columns(columns_path)
    actual = read_parquet_columns(parquet_path)
    actual_names = {name for name, _ in actual}

    undocumented = [name for name, _ in actual if name not in documented]
    if undocumented:
        raise SystemExit(
            f"Columns present in {parquet_path.name} but missing from "
            f"{columns_path.name}: {', '.join(undocumented)}. "
            f"Add them to columns.yaml."
        )

    missing = [
        name
        for name, spec in documented.items()
        if name not in actual_names and not spec["tiles_only"] and not spec["raw_only"]
    ]
    if missing:
        raise SystemExit(
            f"Columns documented in {columns_path.name} but absent from "
            f"{parquet_path.name}: {', '.join(missing)}. "
            f"Remove them from columns.yaml."
        )

    wrong_type = [
        f"{name} is {found} but columns.yaml says {documented[name]['type']}"
        for name, found in actual
        if found.strip().lower() != documented[name]["type"].strip().lower()
    ]
    if wrong_type:
        raise SystemExit(
            f"Type mismatch between {parquet_path.name} and "
            f"{columns_path.name}: {'; '.join(wrong_type)}."
        )

    return [
        {
            "name": name,
            "type": stac_type(found),
            "description": documented[name][description_key],
        }
        for name, found in actual
    ]


def raw_table_columns(columns_path: Path, lang: str = "it") -> list[dict]:
    """table:columns for the raw archive Parquet: the 19 CSV columns as text.

    The raw Parquet is a faithful copy of the CSV, so every column is VARCHAR
    whatever columns.yaml says about the enriched schema. Descriptions still
    come from columns.yaml, in the requested language.
    """
    description_key = "description" if lang == "it" else f"description_{lang}"
    documented = load_columns(columns_path)
    missing = [name for name in RAW_COLUMNS if name not in documented]
    if missing:
        raise SystemExit(
            f"Raw CSV columns without documentation in {columns_path.name}: "
            f"{', '.join(missing)}."
        )
    return [
        {
            "name": name,
            "type": "varchar",
            "description": documented[name][description_key],
        }
        for name in RAW_COLUMNS
    ]


def load_releases(path: Path) -> list[dict]:
    """Load and validate the release index, oldest first.

    The index is the only source of facts about the archive: the generator
    never lists the bucket. A malformed entry stops the build rather than
    producing an item that lies about a file.
    """
    if not path.exists():
        raise SystemExit(
            f"{path} not found. The release index is written by update_data.py "
            f"and by rebuild_archive.py; the catalog cannot be built without it."
        )
    with open(path, encoding="utf-8") as handle:
        releases = json.load(handle).get("releases", [])

    required = {"date", "origin", "note", "zip", "parquet", "archived"}
    file_keys = {"name", "size", "sha256"}
    seen = set()
    for entry in releases:
        missing = required - entry.keys()
        if missing:
            raise SystemExit(f"Release entry missing {sorted(missing)}: {entry}")
        if entry["origin"] not in RELEASE_ORIGINS:
            raise SystemExit(
                f"Release {entry['date']}: origin must be one of "
                f"{RELEASE_ORIGINS}, got {entry['origin']!r}."
            )
        for key in ("zip", "parquet"):
            wanted = file_keys | ({"rows"} if key == "parquet" else set())
            lacking = wanted - entry[key].keys()
            if lacking:
                raise SystemExit(
                    f"Release {entry['date']}: {key} entry missing {sorted(lacking)}."
                )
        if entry["date"] in seen:
            raise SystemExit(f"Release {entry['date']} appears twice in the index.")
        seen.add(entry["date"])
        datetime.strptime(entry["date"], "%Y-%m-%d")

    return sorted(releases, key=lambda entry: entry["date"])


def multihash_sha256(path: Path) -> str:
    """Return the sha256 of a file as a multihash hex string.

    PORTO-CORE-029 requires multihash rather than a bare digest. The 1220
    prefix is the sha2-256 code followed by the 32-byte length.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "1220" + digest.hexdigest()


def file_facts(path: Path) -> dict:
    """Return the file extension fields for an asset."""
    return {
        "file:size": path.stat().st_size,
        "file:checksum": multihash_sha256(path),
    }


def pmtiles_facts(path: Path) -> dict:
    """Read the layer names and zoom range out of a PMTiles archive.

    The pmtiles:layers array must be non-empty (PORTO-FMT-012), and reading it
    from the file keeps it true when the pipeline changes what it publishes.
    """
    from pmtiles.reader import MmapSource, Reader

    with open(path, "rb") as handle:
        reader = Reader(MmapSource(handle))
        header = reader.header()
        metadata = reader.metadata()

    layers = [layer["id"] for layer in metadata.get("vector_layers", [])]
    if not layers:
        raise SystemExit(
            f"{path.name} declares no vector layers, so the catalog would "
            f"publish an empty pmtiles:layers array."
        )
    return {
        "layers": layers,
        "min_zoom": header["min_zoom"],
        "max_zoom": header["max_zoom"],
    }


def tile_inventory(tiles_dir: Path) -> dict:
    """Count the partition files and confirm the Hive key they use."""
    files = sorted(tiles_dir.glob("*=*/*.parquet"))
    if not files:
        raise SystemExit(
            f"{tiles_dir} contains no partition files matching <key>=<value>/*.parquet."
        )

    keys = {path.parent.name.split("=", 1)[0] for path in files}
    if len(keys) != 1:
        raise SystemExit(
            f"{tiles_dir} mixes partition keys: {', '.join(sorted(keys))}."
        )

    return {"file_count": len(files), "key": keys.pop()}


def dataset_stats(parquet_path: Path) -> dict:
    """Read the row count and the bounding box from the parquet itself."""
    import duckdb

    con = duckdb.connect()
    row = con.execute(f"""
        SELECT
            count(*),
            min(longitude), min(latitude),
            max(longitude), max(latitude)
        FROM read_parquet('{parquet_path}')
    """).fetchone()
    con.close()

    return {
        "row_count": row[0],
        "bbox": [row[1], row[2], row[3], row[4]],
    }


def dataset_date(marker_path: Path) -> str:
    """Read the release date of the current dataset as an RFC 3339 instant."""
    raw = marker_path.read_text().strip()
    parsed = datetime.strptime(raw, "%Y%m%d").replace(tzinfo=timezone.utc)
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def data_updated(parquet_path: Path, marker_path: Path) -> str:
    """Return when the data was last synced, as an RFC 3339 instant.

    PORTO-CORE-057 wants the time of the sync. The commit that brought the
    parquet in is exactly that, and using it instead of the wall clock keeps
    the generated catalog byte-identical across runs over unchanged data.

    Outside a git checkout, or before the parquet is committed, the dataset
    release date stands in. It is equally deterministic.

    A shallow clone is not trusted either: with no history, ``git log`` for
    any path returns HEAD, so ``updated`` would follow every unrelated commit
    and the workflow would commit a changed catalog on every run. This is
    what actions/checkout produces at its default depth of 1; the workflow
    fetches the full history precisely to avoid this fallback.
    """

    def git(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=parquet_path.parent,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    if git("rev-parse", "--is-shallow-repository") == "true":
        print(
            "Warning: shallow git clone, git log cannot date the parquet; "
            "using the dataset release date as `updated`.",
            flush=True,
        )
        return dataset_date(marker_path)

    committed = git("log", "-1", "--format=%cI", "--", str(parquet_path))
    if committed:
        parsed = datetime.fromisoformat(committed)
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return dataset_date(marker_path)


def render_thumbnail(
    parquet_path: Path,
    output_path: Path,
    bbox: list[float],
    colour: tuple[int, int, int],
    width: int = 800,
) -> None:
    """Render a point-density PNG over the dataset extent.

    PORTO-CORE-067 wants a thumbnail generated from the default styling. A
    MapLibre screenshot would need a headless browser in CI, so this draws the
    same data in the same colour by aggregating points into pixels with
    DuckDB. Density is mapped through a log curve, because address density
    spans several orders of magnitude between countryside and city centre.

    The height is derived from the bounding box with a cosine correction on
    the mean latitude, so Italy is not stretched.
    """
    import duckdb
    from PIL import Image

    xmin, ymin, xmax, ymax = bbox
    lon_span = xmax - xmin
    lat_span = ymax - ymin
    if lon_span <= 0 or lat_span <= 0:
        raise SystemExit(f"Cannot render a thumbnail over an empty bbox: {bbox}")

    mean_lat_rad = math.radians((ymin + ymax) / 2)
    height = max(1, round(width * (lat_span / lon_span) / math.cos(mean_lat_rad)))

    con = duckdb.connect()
    cells = con.execute(f"""
        SELECT
            least({width - 1}, greatest(0,
                floor((longitude - {xmin}) / {lon_span} * {width})::INTEGER)) AS px,
            least({height - 1}, greatest(0,
                floor(({ymax} - latitude) / {lat_span} * {height})::INTEGER)) AS py,
            count(*) AS n
        FROM read_parquet('{parquet_path}')
        WHERE longitude IS NOT NULL AND latitude IS NOT NULL
        GROUP BY px, py
    """).fetchall()
    con.close()

    background = (255, 255, 255)
    image = Image.new("RGB", (width, height), background)
    pixels = image.load()

    peak = max((count for _, _, count in cells), default=1)
    scale = math.log1p(peak)
    for px, py, count in cells:
        weight = math.log1p(count) / scale if scale else 1.0
        pixels[px, py] = tuple(
            round(background[i] + (colour[i] - background[i]) * weight)
            for i in range(3)
        )

    image.save(output_path, format="PNG", optimize=True)


def dataset_statistics(parquet_path: Path) -> dict:
    """Global figures the catalog states about the addresses.

    Recomputed from the parquet rather than carried over from the data
    workflow, so the catalog never depends on another run's log. The spec has
    no machine field for attribute statistics beyond table:row_count, so these
    feed the descriptions and the README tables.
    """
    import duckdb

    con = duckdb.connect()
    out_of_bounds, no_boundary, comuni = con.execute(f"""
        SELECT
            count(*) FILTER (WHERE out_of_bounds),
            count(*) FILTER (WHERE out_of_bounds IS NULL),
            count(DISTINCT CODICE_ISTAT)
        FROM read_parquet('{parquet_path}')
    """).fetchone()
    methods = con.execute(f"""
        SELECT METODO, count(*)
        FROM read_parquet('{parquet_path}')
        WHERE METODO IS NOT NULL
        GROUP BY METODO
        ORDER BY METODO
    """).fetchall()
    con.close()

    return {
        "out_of_bounds": out_of_bounds,
        "no_boundary": no_boundary,
        "comuni": comuni,
        "metodo": {str(code): count for code, count in methods},
    }


# ---------------------------------------------------------------------------
# Languages. Italian is the source tree at the root of data/; every other
# language is a translated tree in data/<lang>/ that references the data,
# styles and thumbnails of the source tree (Portolan multilingual practice).
# ---------------------------------------------------------------------------

LANGUAGE_SCHEMA = "https://stac-extensions.github.io/language/v1.0.0/schema.json"
SOURCE_LANG = "it"
TRANSLATIONS = ["en"]
ALL_LANGS = [SOURCE_LANG, *TRANSLATIONS]

LANGUAGES = {
    "it": {"code": "it", "name": "Italiano", "alternate": "Italian"},
    "en": {"code": "en", "name": "English", "alternate": "Inglese"},
}

COLLECTION_EXTENSIONS = [
    PORTOLAN_SCHEMA,
    FILE_SCHEMA,
    TABLE_SCHEMA,
    PROJECTION_SCHEMA,
    WEB_MAP_LINKS_SCHEMA,
    LANGUAGE_SCHEMA,
]

MONTHS = {
    "it": [
        "gennaio",
        "febbraio",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    ],
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
}

METHOD_LABELS = {
    "it": {
        "1": "rilevazione strumentale sul campo, accuratezza inferiore a 5 m",
        "2": "rilevazione strumentale sul campo, accuratezza pari o superiore a 5 m",
        "3": "derivazione indiretta da base dati territoriale, accuratezza stimata inferiore a 5 m",
        "4": "derivazione indiretta da base dati territoriale, accuratezza stimata pari o superiore a 5 m",
        "5": "derivazione indiretta tramite le funzioni del Portale per i Comuni",
    },
    "en": {
        "1": "field survey with instruments, accuracy below 5 m",
        "2": "field survey with instruments, accuracy of 5 m or more",
        "3": "indirect derivation from a spatial database, estimated accuracy below 5 m",
        "4": "indirect derivation from a spatial database, estimated accuracy of 5 m or more",
        "5": "indirect derivation through the functions of the Portale per i Comuni",
    },
}

TEXTS = {
    "it": {
        "root_title": "Indirizzi ANNCSU",
        "root_description": (
            "Gli indirizzi certificati dei comuni italiani, dall'Archivio "
            "Nazionale dei Numeri Civici e delle Strade Urbane, convertiti in "
            "formati cloud-native. Il catalogo pubblica lo stesso insieme di "
            "dati in due forme: un unico file GeoParquet per l'analisi "
            "complessiva, e una partizione in celle H3 per leggere un comune "
            "alla volta senza scaricare tutto."
        ),
        "indirizzi_title": "Indirizzi ANNCSU, file unico",
        "indirizzi_description": (
            "Tutti gli accessi esterni censiti in ANNCSU in un unico file "
            "GeoParquet, ordinato spazialmente secondo una curva di Hilbert e "
            "corredato di colonna bbox, così che un lettore possa scartare "
            "interi gruppi di righe senza decodificare le geometrie. Adatto "
            "all'analisi sull'intero territorio nazionale. Per leggere un "
            "singolo comune conviene la collection partizionata. $statistics"
        ),
        "h3_title": "Indirizzi ANNCSU, partizionati per cella H3",
        "h3_description": (
            "Gli stessi indirizzi della collection indirizzi, ripartiti in "
            "$tile_count file secondo la cella H3 di risoluzione $resolution "
            "che li contiene, con struttura Hive "
            "tiles/h3_cell=<cella>/<cella>.parquet. Ogni file pesa meno di un "
            "megabyte, quindi un client può leggere un comune senza scaricare "
            "il file nazionale. Il glob di accesso massivo è $glob, ma su "
            "HTTPS non esiste il listing: per sapere quali celle servono si "
            "usa l'indice comuni-h3.json, registrato come asset di metadati. "
            "$statistics"
        ),
        "statistics_sentence": (
            "Su $total accessi, $oob ($pct) cadono oltre 110 metri fuori dal "
            "confine del comune a cui sono attribuiti secondo i confini Istat, "
            "e $nob non hanno un confine di riferimento."
        ),
        "vcs": "Repository del catalogo e della pipeline",
        "issues": "Segnalazioni",
        "via": "Portale open data ANNCSU",
        "license": "Creative Commons Attribuzione 4.0 Internazionale",
        "agents": "Istruzioni per agenti automatici",
        "describedby": "Documentazione leggibile",
        "viewer": "Visualizzatore web",
        "other_tree": {"en": "Inglese"},
        "data_title": "Indirizzi ANNCSU (GeoParquet)",
        "visual_title": "Indirizzi ANNCSU (PMTiles)",
        "pmtiles_link": "Tile vettoriali per la mappa",
        "style_indirizzi_title": "Punti indirizzo",
        "style_indirizzi_description": "Tutti gli accessi come punti uniformi.",
        "style_h3_title": "Indirizzi fuori confine",
        "style_h3_description": (
            "Gli accessi colorati per posizione rispetto al confine comunale."
        ),
        "thumbnail": "Densità degli indirizzi sul territorio nazionale",
        "cell_index_title": "Indice delle celle H3 per comune",
        "cell_index_description": (
            "Per ogni comune, l'elenco delle celle H3 che ne contengono gli "
            "indirizzi. Sostituisce il listing che HTTPS non offre."
        ),
        "partition_key": "Cella H3 di risoluzione $resolution che contiene l'indirizzo.",
        "keywords": ["indirizzi", "numeri civici", "toponomastica", "italia", "anncsu"],
        "keywords_h3": ["h3", "partizionato"],
        "stats_header": ("Statistica", "Valore"),
        "stats_total": "Accessi totali",
        "stats_oob": "Fuori dal confine comunale, oltre 110 m",
        "stats_nob": "Senza confine comunale di riferimento",
        "stats_comuni": "Comuni con almeno un accesso",
        "stats_method": "Metodo $code, $label",
    },
    "en": {
        "root_title": "ANNCSU addresses",
        "root_description": (
            "The certified addresses of Italian comuni, from the National "
            "Archive of House Numbers and Urban Streets (ANNCSU), converted to "
            "cloud-native formats. The catalog publishes the same data in two "
            "shapes: one GeoParquet file for country-wide analysis, and a "
            "partition into H3 cells for reading one comune at a time without "
            "downloading everything."
        ),
        "indirizzi_title": "ANNCSU addresses, single file",
        "indirizzi_description": (
            "Every external access recorded in ANNCSU in one GeoParquet file, "
            "spatially sorted along a Hilbert curve and carrying a bbox column, "
            "so a reader can skip whole row groups without decoding geometries. "
            "Suited to analysis over the whole country. To read a single comune "
            "the partitioned collection is the better choice. $statistics"
        ),
        "h3_title": "ANNCSU addresses, partitioned by H3 cell",
        "h3_description": (
            "The same addresses as the indirizzi collection, split into "
            "$tile_count files by the resolution $resolution H3 cell that "
            "contains them, in Hive layout tiles/h3_cell=<cell>/<cell>.parquet. "
            "Every file is under a megabyte, so a client can read one comune "
            "without downloading the national file. The bulk-access glob is "
            "$glob, but HTTPS offers no listing: to know which cells you need, "
            "use the comuni-h3.json index, registered as a metadata asset. "
            "$statistics"
        ),
        "statistics_sentence": (
            "Of $total addresses, $oob ($pct) fall more than 110 metres outside "
            "the boundary of the comune they are assigned to, according to "
            "Istat boundaries, and $nob have no boundary to compare against."
        ),
        "vcs": "Catalog and pipeline repository",
        "issues": "Issue tracker",
        "via": "ANNCSU open data portal",
        "license": "Creative Commons Attribution 4.0 International",
        "agents": "Instructions for automated agents",
        "describedby": "Human-readable documentation",
        "viewer": "Web viewer",
        "other_tree": {"it": "Italian"},
        "data_title": "ANNCSU addresses (GeoParquet)",
        "visual_title": "ANNCSU addresses (PMTiles)",
        "pmtiles_link": "Vector tiles for the map",
        "style_indirizzi_title": "Address points",
        "style_indirizzi_description": "Every access as a uniform point.",
        "style_h3_title": "Out-of-bounds addresses",
        "style_h3_description": (
            "Accesses coloured by their position against the comune boundary."
        ),
        "thumbnail": "Address density over the country",
        "cell_index_title": "Index of H3 cells per comune",
        "cell_index_description": (
            "For every comune, the list of H3 cells containing its addresses. "
            "It stands in for the listing HTTPS does not offer."
        ),
        "partition_key": "H3 cell at resolution $resolution containing the address.",
        "keywords": ["addresses", "house numbers", "street names", "italy", "anncsu"],
        "keywords_h3": ["h3", "partitioned"],
        "stats_header": ("Statistic", "Value"),
        "stats_total": "Total addresses",
        "stats_oob": "Outside the comune boundary, beyond 110 m",
        "stats_nob": "Without a comune boundary to compare against",
        "stats_comuni": "Comuni with at least one address",
        "stats_method": "Method $code, $label",
    },
}

LICENSE_PARAGRAPHS = {
    "it": (
        "I dati sono pubblicati con licenza "
        "[Creative Commons Attribuzione 4.0 Internazionale]"
        "(https://creativecommons.org/licenses/by/4.0/deed.it), identificativo "
        "SPDX `CC-BY-4.0`. Le pagine ufficiali ANNCSU richiamano il Regolamento "
        "di esecuzione (UE) 2023/138 sui dati di elevato valore, che per la serie "
        "degli indirizzi impone questa licenza, ma non la riportano per esteso. "
        "Chi ha bisogno di certezza per un riutilizzo commerciale conviene che si "
        "rivolga all'Agenzia delle Entrate."
    ),
    "en": (
        "The data is published under the "
        "[Creative Commons Attribution 4.0 International]"
        "(https://creativecommons.org/licenses/by/4.0/) licence, SPDX "
        "identifier `CC-BY-4.0`. The official ANNCSU pages cite EU implementing "
        "regulation 2023/138 on high-value datasets, which mandates this licence "
        "for the address series, but do not state it in full. Anyone who needs "
        "certainty for a commercial reuse should ask the Agenzia delle Entrate."
    ),
}

USAGE = {
    "it": {
        "indirizzi": (
            "Il file è un GeoParquet leggibile via HTTP con DuckDB, GDAL, "
            "GeoPandas o qualunque lettore Parquet. Le righe sono ordinate lungo "
            "una curva di Hilbert e ogni riga porta un riquadro di delimitazione, "
            "quindi un filtro spaziale o su un comune legge solo i gruppi di righe "
            "che servono.\n\n"
            "```sql\n"
            "INSTALL httpfs; LOAD httpfs;\n"
            "SELECT ODONIMO, CIVICO, ESPONENTE\n"
            "FROM read_parquet('$public_base/anncsu-indirizzi.parquet')\n"
            "WHERE CODICE_ISTAT = '058091'\n"
            "LIMIT 10;\n"
            "```"
        ),
        "indirizzi-h3": (
            "I dati sono divisi per cella H3 di risoluzione 5, con struttura "
            "Hive. Il glob di accesso massivo è "
            "`$public_base/tiles/h3_cell=*/*.parquet`, ma su HTTPS non esiste il "
            "listing delle directory, quindi un lettore non può espanderlo da "
            "solo. Per sapere quali celle servono si legge l'indice "
            "`comuni-h3.json`, che mappa ogni comune sulle sue celle.\n\n"
            "```shell\n"
            "curl -s $public_base/comuni-h3.json \\\n"
            "  | jq -r '.[] | select(.nome_comune == \"Roma\") | .h3_cells[]'\n"
            "```\n\n"
            "```sql\n"
            "SELECT count(*)\n"
            "FROM read_parquet('$public_base/tiles/h3_cell=851fb467fffffff/851fb467fffffff.parquet')\n"
            "WHERE CODICE_ISTAT = '058091';\n"
            "```"
        ),
    },
    "en": {
        "indirizzi": (
            "The file is a GeoParquet readable over HTTP with DuckDB, GDAL, "
            "GeoPandas or any Parquet reader. Rows are sorted along a Hilbert "
            "curve and every row carries a bounding box, so a spatial filter or a "
            "filter on one comune reads only the row groups it needs.\n\n"
            "```sql\n"
            "INSTALL httpfs; LOAD httpfs;\n"
            "SELECT ODONIMO, CIVICO, ESPONENTE\n"
            "FROM read_parquet('$public_base/anncsu-indirizzi.parquet')\n"
            "WHERE CODICE_ISTAT = '058091'\n"
            "LIMIT 10;\n"
            "```"
        ),
        "indirizzi-h3": (
            "The data is split by resolution 5 H3 cell, in Hive layout. The "
            "bulk-access glob is `$public_base/tiles/h3_cell=*/*.parquet`, but "
            "HTTPS offers no directory listing, so a reader cannot expand it on "
            "its own. To know which cells you need, read the `comuni-h3.json` "
            "index, which maps every comune to its cells.\n\n"
            "```shell\n"
            "curl -s $public_base/comuni-h3.json \\\n"
            "  | jq -r '.[] | select(.nome_comune == \"Roma\") | .h3_cells[]'\n"
            "```\n\n"
            "```sql\n"
            "SELECT count(*)\n"
            "FROM read_parquet('$public_base/tiles/h3_cell=851fb467fffffff/851fb467fffffff.parquet')\n"
            "WHERE CODICE_ISTAT = '058091';\n"
            "```"
        ),
    },
}


def human_date(rfc3339: str, lang: str = SOURCE_LANG) -> str:
    """Format an RFC 3339 instant as a date spelled in the language."""
    parsed = datetime.strptime(rfc3339, "%Y-%m-%dT%H:%M:%SZ")
    return f"{parsed.day} {MONTHS[lang][parsed.month - 1]} {parsed.year}"


def human_count(value: int, lang: str = SOURCE_LANG) -> str:
    """Format an integer with the language's thousands separator."""
    english = f"{value:,}"
    return english if lang == "en" else english.replace(",", ".")


def human_percent(part: int, total: int, lang: str = SOURCE_LANG) -> str:
    """Format part/total as a percentage with two decimals, or a dash."""
    if not total:
        return "-"
    english = f"{part / total * 100:.2f}%"
    return english if lang == "en" else english.replace(".", ",")


def statistics_sentence(facts: dict, lang: str) -> str:
    stats = facts["statistics"]
    total = facts["row_count"]
    return Template(TEXTS[lang]["statistics_sentence"]).substitute(
        total=human_count(total, lang),
        oob=human_count(stats["out_of_bounds"], lang),
        pct=human_percent(stats["out_of_bounds"], total, lang),
        nob=human_count(stats["no_boundary"], lang),
    )


def statistics_table(facts: dict, lang: str = SOURCE_LANG) -> str:
    """Render the global statistics as a Markdown table."""
    text = TEXTS[lang]
    stats = facts["statistics"]
    total = facts["row_count"]
    header, value = text["stats_header"]
    rows = [
        f"| {header} | {value} |",
        "|---|---|",
        f"| {text['stats_total']} | {human_count(total, lang)} |",
        f"| {text['stats_oob']} | {human_count(stats['out_of_bounds'], lang)} "
        f"({human_percent(stats['out_of_bounds'], total, lang)}) |",
        f"| {text['stats_nob']} | {human_count(stats['no_boundary'], lang)} |",
        f"| {text['stats_comuni']} | {human_count(stats['comuni'], lang)} |",
    ]
    for code, count in stats["metodo"].items():
        label = METHOD_LABELS[lang].get(code, "")
        name = Template(text["stats_method"]).substitute(code=code, label=label)
        rows.append(
            f"| {name} | {human_count(count, lang)} "
            f"({human_percent(count, total, lang)}) |"
        )
    return "\n".join(rows)


def schema_table(columns: list[dict], lang: str = SOURCE_LANG) -> str:
    """Render table:columns as a Markdown table.

    The same descriptions feed the JSON and this table, so they cannot drift.
    """
    header = (
        "| Colonna | Tipo | Descrizione |"
        if lang == "it"
        else "| Column | Type | Description |"
    )
    lines = [header, "|---|---|---|"]
    for column in columns:
        description = column["description"].replace("|", r"\|")
        lines.append(f"| `{column['name']}` | {column['type']} | {description} |")
    return "\n".join(lines)


def render_template(name: str, values: dict) -> str:
    """Fill a Markdown template.

    Uses string.Template rather than an engine so the templates stay readable
    and the only dependency is the standard library. A missing value raises
    KeyError rather than leaving a placeholder in published output.
    """
    text = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
    return Template(text).substitute(values)


def template_name(base: str, lang: str) -> str:
    """catalog.README.md -> catalog.README.en.md for a translation."""
    if lang == SOURCE_LANG:
        return base
    stem, suffix = base.rsplit(".", 1)
    return f"{stem}.{lang}.{suffix}"


# --- relative paths between trees -------------------------------------------


def _tree_root(lang: str) -> str:
    """Path of a language tree's root, relative to data/."""
    return "" if lang == SOURCE_LANG else f"{lang}/"


def _to_data(lang: str, from_collection: bool) -> str:
    """Path from an object's directory up to data/."""
    levels = (0 if lang == SOURCE_LANG else 1) + (1 if from_collection else 0)
    return "../" * levels


def _href_to_tree(lang: str, other: str, from_collection: bool, tail: str) -> str:
    href = _to_data(lang, from_collection) + _tree_root(other) + tail
    return href if href.startswith("../") else f"./{href}"


def _language_fields(lang: str) -> dict:
    return {
        "language": LANGUAGES[lang],
        "languages": [LANGUAGES[code] for code in ALL_LANGS if code != lang],
    }


def _tree_alternates(lang: str, from_collection: bool, tail: str) -> list[dict]:
    """alternate links to the same object in every other language tree."""
    return [
        {
            "rel": "alternate",
            "href": _href_to_tree(lang, other, from_collection, tail),
            "type": "application/json",
            "title": TEXTS[lang]["other_tree"][other],
            "hreflang": other,
        }
        for other in ALL_LANGS
        if other != lang
    ]


def _viewer_link(lang: str) -> dict:
    """The web viewer, as an HTML alternate representation of the data."""
    return {
        "rel": "alternate",
        "href": VIEWER_URL,
        "type": "text/html",
        "title": TEXTS[lang]["viewer"],
    }


def providers() -> list[dict]:
    """The parties responsible for the data.

    PORTO-CORE-047 wants at least one producer and exactly one host, listed
    last. Producer and host differ, which is what makes this catalog a mirror.
    """
    return [
        {
            "name": "Agenzia delle Entrate",
            "url": "https://www.agenziaentrate.gov.it/",
            "roles": ["producer", "licensor"],
        },
        {
            "name": "Istat",
            "url": "https://www.istat.it/",
            "roles": ["producer"],
        },
        {
            "name": "anncsu-open",
            "url": REPO_URL,
            "roles": ["processor"],
        },
        {
            "name": "Geobeyond",
            "url": "https://geobeyond.it/",
            "roles": ["host"],
        },
    ]


def _source_links(lang: str) -> list[dict]:
    """The provenance and licence links every object in this catalog carries."""
    deed = "deed.it" if lang == "it" else ""
    return [
        {
            "rel": "via",
            "href": SOURCE_PORTAL,
            "type": "text/html",
            "title": TEXTS[lang]["via"],
        },
        {
            "rel": "license",
            "href": f"https://creativecommons.org/licenses/by/4.0/{deed}",
            "type": "text/html",
            "title": TEXTS[lang]["license"],
        },
    ]


def _documentation_links(lang: str) -> list[dict]:
    return [
        {
            "rel": "agents",
            "href": "./AGENTS.md",
            "type": "text/markdown",
            "title": TEXTS[lang]["agents"],
            "hreflang": lang,
        },
        {
            "rel": "describedby",
            "href": "./README.md",
            "type": "text/markdown",
            "title": TEXTS[lang]["describedby"],
            "hreflang": lang,
        },
    ]


def build_root(updated: str, lang: str = SOURCE_LANG) -> dict:
    """Build the root catalog of one language tree.

    The source tree's root sits at data/; a translated root has no parent
    either, because each language tree stands on its own (PORTO-CORE-080).
    """
    text = TEXTS[lang]
    return {
        "type": "Catalog",
        "stac_version": "1.1.0",
        "stac_extensions": [PORTOLAN_SCHEMA, LANGUAGE_SCHEMA],
        "id": "anncsu",
        "title": text["root_title"],
        "description": text["root_description"],
        **_language_fields(lang),
        "updated": updated,
        "links": [
            {"rel": "root", "href": "./catalog.json", "type": "application/json"},
            {
                "rel": "self",
                "href": f"{PUBLIC_BASE}/{_tree_root(lang)}catalog.json",
                "type": "application/json",
            },
            {
                "rel": "child",
                "href": "./indirizzi/collection.json",
                "type": "application/json",
                "title": text["indirizzi_title"],
            },
            {
                "rel": "child",
                "href": "./indirizzi-h3/collection.json",
                "type": "application/json",
                "title": text["h3_title"],
            },
            *_tree_alternates(lang, False, "catalog.json"),
            _viewer_link(lang),
            {
                "rel": "vcs",
                "href": REPO_URL,
                "type": "text/html",
                "title": text["vcs"],
            },
            {
                "rel": "issues",
                "href": f"{REPO_URL}/issues",
                "type": "text/html",
                "title": text["issues"],
            },
            *_source_links(lang),
            *_documentation_links(lang),
        ],
    }


def _style_asset(
    href: str, title: str, description: str, facts: dict, default: bool
) -> dict:
    roles = ["style", "default"] if default else ["style"]
    return {
        "href": href,
        "type": "application/vnd.mapbox.style+json",
        "title": title,
        "description": description,
        "roles": roles,
        **facts,
    }


def _shared_asset_href(lang: str, collection_id: str, tail: str) -> str:
    """Path to a style or thumbnail, which live in the source tree only."""
    if lang == SOURCE_LANG:
        return f"./{tail}"
    return f"{_to_data(lang, True)}{collection_id}/{tail}"


def _thumbnail_asset(facts: dict, lang: str, collection_id: str) -> dict:
    return {
        "href": _shared_asset_href(lang, collection_id, "thumbnail.png"),
        "type": "image/png",
        "title": TEXTS[lang]["thumbnail"],
        "roles": ["thumbnail"],
        **facts["thumbnail"],
    }


def _pmtiles_link(facts: dict, lang: str) -> dict:
    return {
        "rel": "pmtiles",
        "href": f"{_to_data(lang, True)}anncsu-indirizzi.pmtiles",
        "type": "application/vnd.pmtiles",
        "title": TEXTS[lang]["pmtiles_link"],
        "pmtiles:layers": facts["pmtiles_layers"],
    }


def _extent(facts: dict) -> dict:
    return {
        "spatial": {"bbox": [facts["bbox"]]},
        "temporal": {"interval": [[facts["dataset_date"], None]]},
    }


def _collection_links(facts: dict, lang: str, collection_id: str) -> list[dict]:
    return [
        {"rel": "root", "href": "../catalog.json", "type": "application/json"},
        {"rel": "parent", "href": "../catalog.json", "type": "application/json"},
        _pmtiles_link(facts, lang),
        *_tree_alternates(lang, True, f"{collection_id}/collection.json"),
        _viewer_link(lang),
        *_source_links(lang),
        *_documentation_links(lang),
    ]


def _columns_for(facts: dict, key: str, lang: str) -> list[dict]:
    return facts[key if lang == SOURCE_LANG else f"{key}_{lang}"]


def build_indirizzi(facts: dict, lang: str = SOURCE_LANG) -> dict:
    """Build the single-file collection.

    PORTO-CORE-017: one data file means a collection-level asset and no items.
    """
    text = TEXTS[lang]
    up = _to_data(lang, True)
    return {
        "type": "Collection",
        "stac_version": "1.1.0",
        "stac_extensions": list(COLLECTION_EXTENSIONS),
        "id": "indirizzi",
        "title": text["indirizzi_title"],
        "description": Template(text["indirizzi_description"]).substitute(
            statistics=statistics_sentence(facts, lang)
        ),
        "license": LICENSE_ID,
        "keywords": list(text["keywords"]),
        "providers": providers(),
        "extent": _extent(facts),
        **_language_fields(lang),
        "updated": facts["updated"],
        "table:columns": _columns_for(facts, "table_columns", lang),
        "table:row_count": facts["row_count"],
        "table:primary_geometry": "geometry",
        "assets": {
            "data": {
                "href": f"{up}anncsu-indirizzi.parquet",
                "type": "application/vnd.apache.parquet",
                "title": text["data_title"],
                "roles": ["data"],
                "proj:code": "OGC:CRS84",
                **facts["parquet"],
            },
            "visual": {
                "href": f"{up}anncsu-indirizzi.pmtiles",
                "type": "application/vnd.pmtiles",
                "title": text["visual_title"],
                "roles": ["visual"],
                **facts["pmtiles"],
            },
            "style-indirizzi": _style_asset(
                _shared_asset_href(lang, "indirizzi", "styles/indirizzi.json"),
                text["style_indirizzi_title"],
                text["style_indirizzi_description"],
                facts["style_indirizzi"],
                default=True,
            ),
            "thumbnail": _thumbnail_asset(facts, lang, "indirizzi"),
        },
        "links": _collection_links(facts, lang, "indirizzi"),
    }


def build_indirizzi_h3(facts: dict, lang: str = SOURCE_LANG) -> dict:
    """Build the partitioned collection.

    PORTO-FMT-022 advises against items for an opaque scheme with hundreds of
    partitions, so the glob is the access path and there are no items.
    """
    text = TEXTS[lang]
    up = _to_data(lang, True)
    glob = f"{PUBLIC_BASE}/tiles/{facts['tile_key']}=*/*.parquet"
    return {
        "type": "Collection",
        "stac_version": "1.1.0",
        "stac_extensions": [*COLLECTION_EXTENSIONS, PARTITION_SCHEMA],
        "id": "indirizzi-h3",
        "title": text["h3_title"],
        "description": Template(text["h3_description"]).substitute(
            tile_count=human_count(facts["tile_count"], lang),
            resolution=H3_RESOLUTION,
            glob=glob,
            statistics=statistics_sentence(facts, lang),
        ),
        "license": LICENSE_ID,
        "keywords": [*text["keywords"], *text["keywords_h3"]],
        "providers": providers(),
        "extent": _extent(facts),
        **_language_fields(lang),
        "updated": facts["updated"],
        "table:columns": _columns_for(facts, "tile_table_columns", lang),
        "table:row_count": facts["row_count"],
        "table:primary_geometry": "geometry",
        "partition:scheme": "hive",
        "partition:strategy": "h3",
        "partition:keys": [
            {
                "name": facts["tile_key"],
                "type": "string",
                "description": Template(text["partition_key"]).substitute(
                    resolution=H3_RESOLUTION
                ),
            }
        ],
        "partition:file_count": facts["tile_count"],
        "partition:glob": glob,
        "assets": {
            "cell-index": {
                "href": f"{up}comuni-h3.json",
                "type": "application/json",
                "title": text["cell_index_title"],
                "description": text["cell_index_description"],
                "roles": ["metadata"],
                **facts["comuni_h3"],
            },
            "style-indirizzi-h3": _style_asset(
                _shared_asset_href(lang, "indirizzi-h3", "styles/indirizzi-h3.json"),
                text["style_h3_title"],
                text["style_h3_description"],
                facts["style_indirizzi_h3"],
                default=True,
            ),
            "thumbnail": _thumbnail_asset(facts, lang, "indirizzi-h3"),
        },
        "links": _collection_links(facts, lang, "indirizzi-h3"),
    }


# --- writing -----------------------------------------------------------------


def write_json(path: Path, document: dict) -> None:
    """Write a STAC document deterministically and atomically.

    Keys keep insertion order, which the builders control, so two runs over
    the same data produce the same bytes. A trailing newline keeps diffs and
    text tools happy.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def write_text(path: Path, text: str) -> None:
    """Write a Markdown file atomically, with exactly one trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    tmp.replace(path)


def collect_facts(data_dir: Path) -> dict:
    """Measure everything the catalog states, in one pass over the data."""
    parquet = data_dir / "anncsu-indirizzi.parquet"
    pmtiles = data_dir / "anncsu-indirizzi.pmtiles"
    comuni_h3 = data_dir / "comuni-h3.json"
    tiles = data_dir / "tiles"
    marker = data_dir / ".last_remote_date"

    for required in (parquet, pmtiles, comuni_h3, marker):
        if not required.exists():
            raise SystemExit(f"{required} not found. Run scripts/update_data.py first.")

    print("Reading the parquet ...", flush=True)
    stats = dataset_stats(parquet)
    statistics = dataset_statistics(parquet)

    inventory = tile_inventory(tiles)
    sample_tile = sorted(tiles.glob("*=*/*.parquet"))[0]

    print("Reading the PMTiles header ...", flush=True)
    pmtiles_info = pmtiles_facts(pmtiles)

    facts = {
        "row_count": stats["row_count"],
        "bbox": stats["bbox"],
        "updated": data_updated(parquet, marker),
        "dataset_date": dataset_date(marker),
        "parquet": file_facts(parquet),
        "pmtiles": file_facts(pmtiles),
        "comuni_h3": file_facts(comuni_h3),
        "pmtiles_layers": pmtiles_info["layers"],
        "tile_count": inventory["file_count"],
        "tile_key": inventory["key"],
        "statistics": statistics,
    }
    for lang in ALL_LANGS:
        suffix = "" if lang == SOURCE_LANG else f"_{lang}"
        facts[f"table_columns{suffix}"] = table_columns(parquet, COLUMNS_FILE, lang)
        facts[f"tile_table_columns{suffix}"] = table_columns(
            sample_tile, COLUMNS_FILE, lang
        )
    return facts


def _install_collection_assets(
    data_dir: Path, collection_id: str, style_name: str, facts: dict
) -> dict:
    """Copy the style and render the thumbnail, returning their file facts.

    The assets must exist before the collection JSON can state their size and
    checksum, so this runs first and feeds the builders. Assets live in the
    source tree only; translated trees reference them.
    """
    target = data_dir / collection_id
    (target / "styles").mkdir(parents=True, exist_ok=True)

    style_target = target / "styles" / style_name
    shutil.copyfile(STYLE_DIR / style_name, style_target)

    thumbnail = target / "thumbnail.png"
    render_thumbnail(
        data_dir / "anncsu-indirizzi.parquet",
        thumbnail,
        facts["bbox"],
        (0, 102, 204),
    )

    return {"style": file_facts(style_target), "thumbnail": file_facts(thumbnail)}


def _write_tree(data_dir: Path, facts: dict, lang: str) -> None:
    """Write one language tree: root catalog, READMEs, both collections."""
    tree = data_dir / _tree_root(lang)
    shared = {
        "dataset_date_human": human_date(facts["dataset_date"], lang),
        "row_count_human": human_count(facts["row_count"], lang),
        "license_paragraph": LICENSE_PARAGRAPHS[lang],
        "source_portal": SOURCE_PORTAL,
        "repo_url": REPO_URL,
        "viewer_url": VIEWER_URL,
        "browser_url": BROWSER_URL,
        "statistics_table": statistics_table(facts, lang),
    }

    write_json(tree / "catalog.json", build_root(facts["updated"], lang))
    write_text(
        tree / "README.md",
        render_template(template_name("catalog.README.md", lang), shared),
    )
    write_text(
        tree / "AGENTS.md",
        render_template(template_name("catalog.AGENTS.md", lang), {}),
    )

    collections = [
        ("indirizzi", build_indirizzi(facts, lang), "table_columns"),
        ("indirizzi-h3", build_indirizzi_h3(facts, lang), "tile_table_columns"),
    ]
    for collection_id, document, columns_key in collections:
        usage = Template(USAGE[lang][collection_id]).substitute(public_base=PUBLIC_BASE)
        target = tree / collection_id
        write_json(target / "collection.json", document)
        write_text(
            target / "README.md",
            render_template(
                template_name("collection.README.md", lang),
                {
                    **shared,
                    "title": document["title"],
                    "description": document["description"],
                    "usage": usage,
                    "schema_table": schema_table(
                        _columns_for(facts, columns_key, lang), lang
                    ),
                },
            ),
        )
        write_text(
            target / "AGENTS.md",
            render_template(
                template_name("collection.AGENTS.md", lang),
                {"id": collection_id, "usage": usage},
            ),
        )


def build(data_dir: Path) -> None:
    """Generate the whole catalog, in every language, into data_dir."""
    facts = collect_facts(data_dir)

    print("Rendering styles and thumbnails ...", flush=True)
    indirizzi_assets = _install_collection_assets(
        data_dir, "indirizzi", "indirizzi.json", facts
    )
    h3_assets = _install_collection_assets(
        data_dir, "indirizzi-h3", "indirizzi-h3.json", facts
    )
    facts["style_indirizzi"] = indirizzi_assets["style"]
    facts["style_indirizzi_h3"] = h3_assets["style"]
    facts["thumbnail"] = indirizzi_assets["thumbnail"]

    for lang in ALL_LANGS:
        print(f"Writing the {lang} tree ...", flush=True)
        _write_tree(data_dir, facts, lang)

    print(
        f"Catalog written: {facts['row_count']:,} rows, "
        f"{facts['tile_count']} tiles, updated {facts['updated']}, "
        f"languages {', '.join(ALL_LANGS)}",
        flush=True,
    )


def main() -> None:
    build(DATA_DIR)


if __name__ == "__main__":
    typer.run(main)
