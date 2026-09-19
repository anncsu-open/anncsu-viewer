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

PUBLIC_BASE = "https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev"
REPO_URL = "https://github.com/anncsu-open/anncsu-viewer"
SOURCE_PORTAL = "https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/"
LICENSE_ID = "CC-BY-4.0"

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
    """Load the hand-written column documentation."""
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    columns = {}
    for name, spec in raw.items():
        columns[name] = {
            "type": str(spec["type"]),
            "description": " ".join(str(spec["description"]).split()),
            "derived": bool(spec.get("derived", False)),
            "tiles_only": bool(spec.get("tiles_only", False)),
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


def table_columns(parquet_path: Path, columns_path: Path) -> list[dict]:
    """Build the STAC table:columns array, failing on any schema drift.

    An upstream schema change must stop the build rather than produce a
    catalog that describes columns the data no longer has, or omits columns it
    gained. Columns flagged tiles_only are expected to be absent from a file
    that is not a partition.
    """
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
        if name not in actual_names and not spec["tiles_only"]
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
            "description": documented[name]["description"],
        }
        for name, found in actual
    ]


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
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(parquet_path)],
            cwd=parquet_path.parent,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        result = None

    if result is not None and result.returncode == 0 and result.stdout.strip():
        committed = datetime.fromisoformat(result.stdout.strip())
        return committed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

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


LANGUAGE = {"code": "it", "name": "Italiano", "alternate": "Italian"}
LANGUAGE_SCHEMA = "https://stac-extensions.github.io/language/v1.0.0/schema.json"

COLLECTION_EXTENSIONS = [
    PORTOLAN_SCHEMA,
    FILE_SCHEMA,
    TABLE_SCHEMA,
    PROJECTION_SCHEMA,
    WEB_MAP_LINKS_SCHEMA,
    LANGUAGE_SCHEMA,
]


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


def _source_links() -> list[dict]:
    """The provenance and licence links every object in this catalog carries."""
    return [
        {
            "rel": "via",
            "href": SOURCE_PORTAL,
            "type": "text/html",
            "title": "Portale open data ANNCSU",
        },
        {
            "rel": "license",
            "href": "https://creativecommons.org/licenses/by/4.0/deed.it",
            "type": "text/html",
            "title": "Creative Commons Attribuzione 4.0 Internazionale",
        },
    ]


def _documentation_links() -> list[dict]:
    return [
        {
            "rel": "agents",
            "href": "./AGENTS.md",
            "type": "text/markdown",
            "title": "Istruzioni per agenti automatici",
            "hreflang": "it",
        },
        {
            "rel": "describedby",
            "href": "./README.md",
            "type": "text/markdown",
            "title": "Documentazione leggibile",
            "hreflang": "it",
        },
    ]


def build_root(updated: str) -> dict:
    """Build the root catalog."""
    return {
        "type": "Catalog",
        "stac_version": "1.1.0",
        "stac_extensions": [PORTOLAN_SCHEMA, LANGUAGE_SCHEMA],
        "id": "anncsu",
        "title": "Indirizzi ANNCSU",
        "description": (
            "Gli indirizzi certificati dei comuni italiani, dall'Archivio "
            "Nazionale dei Numeri Civici e delle Strade Urbane, convertiti in "
            "formati cloud-native. Il catalogo pubblica lo stesso insieme di "
            "dati in due forme: un unico file GeoParquet per l'analisi "
            "complessiva, e una partizione in celle H3 per leggere un comune "
            "alla volta senza scaricare tutto."
        ),
        "language": LANGUAGE,
        "updated": updated,
        "links": [
            {"rel": "root", "href": "./catalog.json", "type": "application/json"},
            {
                "rel": "self",
                "href": f"{PUBLIC_BASE}/catalog.json",
                "type": "application/json",
            },
            {
                "rel": "child",
                "href": "./indirizzi/collection.json",
                "type": "application/json",
                "title": "Indirizzi ANNCSU, file unico",
            },
            {
                "rel": "child",
                "href": "./indirizzi-h3/collection.json",
                "type": "application/json",
                "title": "Indirizzi ANNCSU, partizionati per cella H3",
            },
            {
                "rel": "vcs",
                "href": REPO_URL,
                "type": "text/html",
                "title": "Repository del catalogo e della pipeline",
            },
            {
                "rel": "issues",
                "href": f"{REPO_URL}/issues",
                "type": "text/html",
                "title": "Segnalazioni",
            },
            *_source_links(),
            *_documentation_links(),
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


def _thumbnail_asset(facts: dict) -> dict:
    return {
        "href": "./thumbnail.png",
        "type": "image/png",
        "title": "Densità degli indirizzi sul territorio nazionale",
        "roles": ["thumbnail"],
        **facts["thumbnail"],
    }


def _pmtiles_link(facts: dict) -> dict:
    return {
        "rel": "pmtiles",
        "href": "../anncsu-indirizzi.pmtiles",
        "type": "application/vnd.pmtiles",
        "title": "Tile vettoriali per la mappa",
        "pmtiles:layers": facts["pmtiles_layers"],
    }


def _extent(facts: dict) -> dict:
    return {
        "spatial": {"bbox": [facts["bbox"]]},
        "temporal": {"interval": [[facts["dataset_date"], None]]},
    }


def _keywords() -> list[str]:
    return ["indirizzi", "numeri civici", "toponomastica", "italia", "anncsu"]


def build_indirizzi(facts: dict) -> dict:
    """Build the single-file collection.

    PORTO-CORE-017: one data file means a collection-level asset and no items.
    """
    return {
        "type": "Collection",
        "stac_version": "1.1.0",
        "stac_extensions": list(COLLECTION_EXTENSIONS),
        "id": "indirizzi",
        "title": "Indirizzi ANNCSU, file unico",
        "description": (
            "Tutti gli accessi esterni censiti in ANNCSU in un unico file "
            "GeoParquet, ordinato spazialmente secondo una curva di Hilbert e "
            "corredato di colonna bbox, così che un lettore possa scartare "
            "interi gruppi di righe senza decodificare le geometrie. Adatto "
            "all'analisi sull'intero territorio nazionale. Per leggere un "
            "singolo comune conviene la collection partizionata."
        ),
        "license": LICENSE_ID,
        "keywords": _keywords(),
        "providers": providers(),
        "extent": _extent(facts),
        "language": LANGUAGE,
        "updated": facts["updated"],
        "table:columns": facts["table_columns"],
        "table:row_count": facts["row_count"],
        "table:primary_geometry": "geometry",
        "assets": {
            "data": {
                "href": "../anncsu-indirizzi.parquet",
                "type": "application/vnd.apache.parquet",
                "title": "Indirizzi ANNCSU (GeoParquet)",
                "roles": ["data"],
                "proj:code": "OGC:CRS84",
                **facts["parquet"],
            },
            "visual": {
                "href": "../anncsu-indirizzi.pmtiles",
                "type": "application/vnd.pmtiles",
                "title": "Indirizzi ANNCSU (PMTiles)",
                "roles": ["visual"],
                **facts["pmtiles"],
            },
            "style-indirizzi": _style_asset(
                "./styles/indirizzi.json",
                "Punti indirizzo",
                "Tutti gli accessi come punti uniformi.",
                facts["style_indirizzi"],
                default=True,
            ),
            "thumbnail": _thumbnail_asset(facts),
        },
        "links": [
            {"rel": "root", "href": "../catalog.json", "type": "application/json"},
            {"rel": "parent", "href": "../catalog.json", "type": "application/json"},
            _pmtiles_link(facts),
            *_source_links(),
            *_documentation_links(),
        ],
    }


def build_indirizzi_h3(facts: dict) -> dict:
    """Build the partitioned collection.

    PORTO-FMT-022 advises against items for an opaque scheme with hundreds of
    partitions, so the glob is the access path and there are no items.
    """
    return {
        "type": "Collection",
        "stac_version": "1.1.0",
        "stac_extensions": [*COLLECTION_EXTENSIONS, PARTITION_SCHEMA],
        "id": "indirizzi-h3",
        "title": "Indirizzi ANNCSU, partizionati per cella H3",
        "description": (
            "Gli stessi indirizzi della collection indirizzi, ripartiti in "
            f"{facts['tile_count']} file secondo la cella H3 di risoluzione "
            f"{H3_RESOLUTION} che li contiene, con struttura Hive "
            "tiles/h3_cell=<cella>/<cella>.parquet. Ogni file pesa meno di un "
            "megabyte, quindi un client può leggere un comune senza scaricare "
            "il file nazionale. Il glob di accesso massivo è "
            f"{PUBLIC_BASE}/tiles/h3_cell=*/*.parquet, ma su HTTPS non esiste "
            "il listing: per sapere quali celle servono si usa l'indice "
            "comuni-h3.json, registrato come asset di metadati."
        ),
        "license": LICENSE_ID,
        "keywords": [*_keywords(), "h3", "partizionato"],
        "providers": providers(),
        "extent": _extent(facts),
        "language": LANGUAGE,
        "updated": facts["updated"],
        "table:columns": facts["tile_table_columns"],
        "table:row_count": facts["row_count"],
        "table:primary_geometry": "geometry",
        "partition:scheme": "hive",
        "partition:strategy": "h3",
        "partition:keys": [
            {
                "name": facts["tile_key"],
                "type": "string",
                "description": (
                    f"Cella H3 di risoluzione {H3_RESOLUTION} che contiene l'indirizzo."
                ),
            }
        ],
        "partition:file_count": facts["tile_count"],
        "partition:glob": f"{PUBLIC_BASE}/tiles/{facts['tile_key']}=*/*.parquet",
        "assets": {
            "cell-index": {
                "href": "../comuni-h3.json",
                "type": "application/json",
                "title": "Indice delle celle H3 per comune",
                "description": (
                    "Per ogni comune, l'elenco delle celle H3 che ne "
                    "contengono gli indirizzi. Sostituisce il listing che "
                    "HTTPS non offre."
                ),
                "roles": ["metadata"],
                **facts["comuni_h3"],
            },
            "style-indirizzi-h3": _style_asset(
                "./styles/indirizzi-h3.json",
                "Indirizzi fuori confine",
                "Gli accessi colorati per posizione rispetto al confine comunale.",
                facts["style_indirizzi_h3"],
                default=True,
            ),
            "thumbnail": _thumbnail_asset(facts),
        },
        "links": [
            {"rel": "root", "href": "../catalog.json", "type": "application/json"},
            {"rel": "parent", "href": "../catalog.json", "type": "application/json"},
            _pmtiles_link(facts),
            *_source_links(),
            *_documentation_links(),
        ],
    }


MONTHS_IT = [
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
]

LICENSE_PARAGRAPH = (
    "I dati sono pubblicati con licenza "
    "[Creative Commons Attribuzione 4.0 Internazionale]"
    "(https://creativecommons.org/licenses/by/4.0/deed.it), identificativo "
    "SPDX `CC-BY-4.0`. Le pagine ufficiali ANNCSU richiamano il Regolamento di "
    "esecuzione (UE) 2023/138 sui dati di elevato valore, che per la serie "
    "degli indirizzi impone questa licenza, ma non la riportano per esteso. "
    "Chi ha bisogno di certezza per un riutilizzo commerciale conviene che si "
    "rivolga all'Agenzia delle Entrate."
)

USAGE_INDIRIZZI = (
    "Il file è un GeoParquet leggibile via HTTP con DuckDB, GDAL, GeoPandas o "
    "qualunque lettore Parquet. Le righe sono ordinate lungo una curva di "
    "Hilbert e ogni riga porta un riquadro di delimitazione, quindi un filtro "
    "spaziale o su un comune legge solo i gruppi di righe che servono.\n\n"
    "```sql\n"
    "INSTALL httpfs; LOAD httpfs;\n"
    "SELECT ODONIMO, CIVICO, ESPONENTE\n"
    "FROM read_parquet('$public_base/anncsu-indirizzi.parquet')\n"
    "WHERE CODICE_ISTAT = '058091'\n"
    "LIMIT 10;\n"
    "```"
)

USAGE_INDIRIZZI_H3 = (
    "I dati sono divisi per cella H3 di risoluzione 5, con struttura Hive. Il "
    "glob di accesso massivo è `$public_base/tiles/h3_cell=*/*.parquet`, ma su "
    "HTTPS non esiste il listing delle directory, quindi un lettore non può "
    "espanderlo da solo. Per sapere quali celle servono si legge l'indice "
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
)


def human_date(rfc3339: str) -> str:
    """Format an RFC 3339 instant as an Italian date."""
    parsed = datetime.strptime(rfc3339, "%Y-%m-%dT%H:%M:%SZ")
    return f"{parsed.day} {MONTHS_IT[parsed.month - 1]} {parsed.year}"


def human_count(value: int) -> str:
    """Format an integer with the Italian thousands separator."""
    return f"{value:,}".replace(",", ".")


def schema_table(columns: list[dict]) -> str:
    """Render table:columns as a Markdown table.

    The same descriptions feed the JSON and this table, so they cannot drift.
    """
    lines = ["| Colonna | Tipo | Descrizione |", "|---|---|---|"]
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
    columns = table_columns(parquet, COLUMNS_FILE)

    inventory = tile_inventory(tiles)
    sample_tile = sorted(tiles.glob("*=*/*.parquet"))[0]
    tile_columns = table_columns(sample_tile, COLUMNS_FILE)

    print("Reading the PMTiles header ...", flush=True)
    pmtiles_info = pmtiles_facts(pmtiles)

    return {
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
        "table_columns": columns,
        "tile_table_columns": tile_columns,
    }


def _install_collection_assets(
    data_dir: Path, collection_id: str, style_name: str, facts: dict
) -> dict:
    """Copy the style and render the thumbnail, returning their file facts.

    The assets must exist before the collection JSON can state their size and
    checksum, so this runs first and feeds the builders.
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


def build(data_dir: Path) -> None:
    """Generate the whole catalog into data_dir."""
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

    shared = {
        "dataset_date_human": human_date(facts["dataset_date"]),
        "row_count_human": human_count(facts["row_count"]),
        "license_paragraph": LICENSE_PARAGRAPH,
        "source_portal": SOURCE_PORTAL,
        "repo_url": REPO_URL,
    }

    print("Writing the catalog ...", flush=True)
    write_json(data_dir / "catalog.json", build_root(facts["updated"]))
    write_text(data_dir / "README.md", render_template("catalog.README.md", shared))
    write_text(data_dir / "AGENTS.md", render_template("catalog.AGENTS.md", {}))

    collections = [
        (
            "indirizzi",
            build_indirizzi(facts),
            facts["table_columns"],
            Template(USAGE_INDIRIZZI).substitute(public_base=PUBLIC_BASE),
        ),
        (
            "indirizzi-h3",
            build_indirizzi_h3(facts),
            facts["tile_table_columns"],
            Template(USAGE_INDIRIZZI_H3).substitute(public_base=PUBLIC_BASE),
        ),
    ]

    for collection_id, document, columns, usage in collections:
        target = data_dir / collection_id
        write_json(target / "collection.json", document)
        write_text(
            target / "README.md",
            render_template(
                "collection.README.md",
                {
                    **shared,
                    "title": document["title"],
                    "description": document["description"],
                    "usage": usage,
                    "schema_table": schema_table(columns),
                },
            ),
        )
        write_text(
            target / "AGENTS.md",
            render_template(
                "collection.AGENTS.md", {"id": collection_id, "usage": usage}
            ),
        )

    print(
        f"Catalog written: {facts['row_count']:,} rows, "
        f"{facts['tile_count']} tiles, updated {facts['updated']}",
        flush=True,
    )


def main() -> None:
    build(DATA_DIR)


if __name__ == "__main__":
    typer.run(main)
