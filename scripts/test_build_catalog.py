# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb==2.0.0",
#     "geoparquet-io>=1.8.0",
#     "httpx",
#     "jsonschema",
#     "pillow",
#     "pmtiles",
#     "pyarrow",
#     "pytest",
#     "pyyaml",
#     "rashid>=0.4.0,<0.5.0",
#     "typer",
# ]
# [tool.uv]
# # geoparquet-io caps DuckDB below 1.6 for the S2 extension, which this
# # project does not use. See scripts/test_dependencies.py.
# override-dependencies = ["duckdb==2.0.0"]
# ///
"""Tests for build_catalog.py, the Portolan catalog generator.

Usage:
    uv run scripts/test_build_catalog.py
"""

import shutil
from pathlib import Path

import pytest

import build_catalog
import build_geocoding_index
from build_catalog import (
    ACCESS_POINTS_SORT,
    ADDRESS_INDEX_EXTENSION,
    FILE_SCHEMA,
    GAZETTEER_EXTENSION,
    GEOCODING_COLUMNS_FILE,
    PARTITION_SCHEMA,
    PORTOLAN_SCHEMA,
    DIFF_ANNCSU_URL,
    PUBLIC_BASE,
    RAW_COLUMNS,
    SOURCE_PORTAL,
    STRAD_COLUMNS,
    STRADARIO_ORIGINS,
    STREETS_SORT,
    TABLE_SCHEMA,
    VERSION_SCHEMA,
    VIEWER_URL,
    build,
    build_gazetteer,
    build_indirizzi,
    build_indirizzi_h3,
    build_indirizzi_index,
    build_release_item,
    build_rilasci,
    build_root,
    build_stradario,
    build_stradario_item,
    data_updated,
    dataset_statistics,
    dataset_stats,
    file_facts,
    geocoding_files_table,
    geocoding_table_columns,
    human_count,
    human_date,
    human_percent,
    load_columns,
    load_geocoding_index,
    load_releases,
    multihash_sha256,
    providers,
    raw_table_columns,
    read_parquet_columns,
    release_asset_url,
    render_template,
    render_thumbnail,
    schema_table,
    stac_type,
    statistics_table,
    stradario_table_columns,
    table_columns,
    tile_inventory,
)
from update_data import enhance_parquet

COLUMNS_YAML = Path(__file__).resolve().parent / "catalog" / "columns.yaml"


def write_parquet(path: Path, columns: str) -> None:
    """Write a one-row parquet with an explicit column list.

    ``columns`` is the SELECT list, so a test can shape the schema it needs.
    """
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"COPY (SELECT {columns}) TO '{path}' (FORMAT PARQUET)")
    con.close()


def build_pmtiles_fixture(parquet_path: Path, pmtiles_path: Path) -> None:
    """Produce a real PMTiles from a fixture parquet, via geoparquet-io."""
    from geoparquet_io.api import ops

    ops.create_pmtiles(
        str(parquet_path),
        str(pmtiles_path),
        layer="addresses",
        include_cols="ODONIMO,CIVICO,CODICE_ISTAT,NOME_COMUNE,oob_distance_m,out_of_bounds",
        repair_geometry=False,
    )


class TestStacType:
    def test_geometry_drops_its_crs_parameter(self):
        assert stac_type("GEOMETRY('OGC:CRS84')") == "geometry"

    def test_plain_types_are_lowercased(self):
        assert stac_type("VARCHAR") == "varchar"
        assert stac_type("BIGINT") == "bigint"

    def test_struct_keeps_its_fields(self):
        assert stac_type("STRUCT(xmin DOUBLE)") == "struct(xmin double)"


class TestLoadColumns:
    def test_every_column_has_a_non_empty_description(self):
        columns = load_columns(COLUMNS_YAML)
        assert columns, "columns.yaml must not be empty"
        for name, spec in columns.items():
            assert spec["description"].strip(), f"{name} has no description"
            assert spec["type"].strip(), f"{name} has no type"

    def test_documents_the_tile_only_column(self):
        columns = load_columns(COLUMNS_YAML)
        assert columns["h3_cell"]["tiles_only"] is True


class TestTableColumns:
    def test_emits_one_entry_per_parquet_column_in_file_order(self, tmp_path):
        parquet = tmp_path / "in.parquet"
        write_parquet(parquet, "'x' AS CODICE_ISTAT, 1::BIGINT AS CIVICO")
        yaml_path = tmp_path / "columns.yaml"
        yaml_path.write_text(
            "CODICE_ISTAT:\n"
            "  type: VARCHAR\n"
            "  description: codice Istat\n"
            "  description_en: Istat code\n"
            "CIVICO:\n"
            "  type: BIGINT\n"
            "  description: numero civico\n"
            "  description_en: house number\n",
            encoding="utf-8",
        )

        result = table_columns(parquet, yaml_path)

        assert [c["name"] for c in result] == ["CODICE_ISTAT", "CIVICO"]
        assert result[0] == {
            "name": "CODICE_ISTAT",
            "type": "varchar",
            "description": "codice Istat",
        }

    def test_fails_when_a_parquet_column_is_undocumented(self, tmp_path):
        parquet = tmp_path / "in.parquet"
        write_parquet(parquet, "'x' AS CODICE_ISTAT, 'y' AS SORPRESA")
        yaml_path = tmp_path / "columns.yaml"
        yaml_path.write_text(
            "CODICE_ISTAT:\n  type: VARCHAR\n"
            "  description: codice Istat\n  description_en: Istat code\n",
            encoding="utf-8",
        )

        with pytest.raises(SystemExit, match="SORPRESA"):
            table_columns(parquet, yaml_path)

    def test_fails_when_a_documented_column_is_gone(self, tmp_path):
        parquet = tmp_path / "in.parquet"
        write_parquet(parquet, "'x' AS CODICE_ISTAT")
        yaml_path = tmp_path / "columns.yaml"
        yaml_path.write_text(
            "CODICE_ISTAT:\n  type: VARCHAR\n"
            "  description: codice Istat\n  description_en: Istat code\n"
            "SPARITA:\n  type: VARCHAR\n"
            "  description: non esiste piu\n  description_en: gone\n",
            encoding="utf-8",
        )

        with pytest.raises(SystemExit, match="SPARITA"):
            table_columns(parquet, yaml_path)

    def test_fails_when_the_documented_type_is_wrong(self, tmp_path):
        parquet = tmp_path / "in.parquet"
        write_parquet(parquet, "1::BIGINT AS CIVICO")
        yaml_path = tmp_path / "columns.yaml"
        yaml_path.write_text(
            "CIVICO:\n  type: VARCHAR\n"
            "  description: numero civico\n  description_en: house number\n",
            encoding="utf-8",
        )

        with pytest.raises(SystemExit, match="CIVICO"):
            table_columns(parquet, yaml_path)

    def test_ignores_a_tiles_only_column_when_reading_the_main_parquet(self, tmp_path):
        parquet = tmp_path / "in.parquet"
        write_parquet(parquet, "'x' AS CODICE_ISTAT")
        yaml_path = tmp_path / "columns.yaml"
        yaml_path.write_text(
            "CODICE_ISTAT:\n  type: VARCHAR\n"
            "  description: codice Istat\n  description_en: Istat code\n"
            "h3_cell:\n"
            "  type: VARCHAR\n"
            "  tiles_only: true\n"
            "  description: cella H3\n"
            "  description_en: H3 cell\n",
            encoding="utf-8",
        )

        result = table_columns(parquet, yaml_path)

        assert [c["name"] for c in result] == ["CODICE_ISTAT"]


class TestMultihash:
    def test_uses_the_sha256_multihash_prefix(self, tmp_path):
        target = tmp_path / "f.bin"
        target.write_bytes(b"portolan")

        digest = multihash_sha256(target)

        assert digest.startswith("1220"), "sha256 multihash starts with 1220"
        assert len(digest) == 4 + 64

    def test_matches_a_known_digest(self, tmp_path):
        import hashlib

        target = tmp_path / "f.bin"
        target.write_bytes(b"portolan")

        expected = "1220" + hashlib.sha256(b"portolan").hexdigest()
        assert multihash_sha256(target) == expected


class TestFileFacts:
    def test_reports_the_real_size(self, tmp_path):
        target = tmp_path / "f.bin"
        target.write_bytes(b"x" * 1234)

        facts = file_facts(target)

        assert facts["file:size"] == 1234
        assert facts["file:checksum"] == multihash_sha256(target)


class TestTileInventory:
    def test_counts_partition_files_and_names_the_key(self, tmp_path):
        tiles = tmp_path / "tiles"
        for cell in ("851e1243fffffff", "851e12c3fffffff"):
            (tiles / f"h3_cell={cell}").mkdir(parents=True)
            (tiles / f"h3_cell={cell}" / f"{cell}.parquet").write_bytes(b"")

        inventory = tile_inventory(tiles)

        assert inventory["file_count"] == 2
        assert inventory["key"] == "h3_cell"

    def test_fails_on_an_empty_directory(self, tmp_path):
        tiles = tmp_path / "tiles"
        tiles.mkdir()

        with pytest.raises(SystemExit, match="no partition files"):
            tile_inventory(tiles)


class TestDatasetStats:
    def test_reports_row_count_and_bbox(self, tmp_path):
        import duckdb

        parquet = tmp_path / "in.parquet"
        con = duckdb.connect()
        con.execute(
            f"COPY (SELECT * FROM (VALUES "
            f"(9.0::DOUBLE, 45.0::DOUBLE), (12.5::DOUBLE, 41.9::DOUBLE)) "
            f"AS t(longitude, latitude)) TO '{parquet}' (FORMAT PARQUET)"
        )
        con.close()

        stats = dataset_stats(parquet)

        assert stats["row_count"] == 2
        assert stats["bbox"] == [9.0, 41.9, 12.5, 45.0]


class TestDataUpdated:
    def test_falls_back_to_the_marker_date_outside_git(self, tmp_path):
        marker = tmp_path / ".last_remote_date"
        marker.write_text("20260915")
        parquet = tmp_path / "in.parquet"
        parquet.write_bytes(b"")

        assert data_updated(parquet, marker) == "2026-09-15T00:00:00Z"

    def test_is_stable_across_calls(self, tmp_path):
        marker = tmp_path / ".last_remote_date"
        marker.write_text("20260915")
        parquet = tmp_path / "in.parquet"
        parquet.write_bytes(b"")

        assert data_updated(parquet, marker) == data_updated(parquet, marker)


STYLE_DIR_SRC = Path(__file__).resolve().parent / "catalog" / "styles"


class TestStyles:
    @pytest.mark.parametrize("name", ["indirizzi.json", "indirizzi-h3.json"])
    def test_is_a_self_contained_maplibre_v8_style(self, name):
        import json

        style = json.loads((STYLE_DIR_SRC / name).read_text(encoding="utf-8"))

        assert style["version"] == 8
        assert style["name"]
        assert style["sources"]["data"]["url"] == (
            "pmtiles://../../anncsu-indirizzi.pmtiles"
        )
        assert style["layers"], "a style with no layers draws nothing"
        for layer in style["layers"]:
            assert layer["source"] == "data"
            assert layer["source-layer"] == "addresses"


class TestThumbnail:
    def _points_parquet(self, path):
        import duckdb

        rows = ", ".join(
            f"({9.0 + i * 0.01}::DOUBLE, {45.0 + i * 0.01}::DOUBLE)" for i in range(200)
        )
        con = duckdb.connect()
        con.execute(
            f"COPY (SELECT * FROM (VALUES {rows}) AS t(longitude, latitude)) "
            f"TO '{path}' (FORMAT PARQUET)"
        )
        con.close()

    def test_writes_a_png_of_the_requested_width(self, tmp_path):
        from PIL import Image

        parquet = tmp_path / "in.parquet"
        self._points_parquet(parquet)
        out = tmp_path / "thumbnail.png"

        render_thumbnail(
            parquet, out, [9.0, 45.0, 11.0, 47.0], (0, 102, 204), width=400
        )

        with Image.open(out) as image:
            assert image.format == "PNG"
            assert image.width == 400
            assert image.height > 0

    def test_is_deterministic(self, tmp_path):
        parquet = tmp_path / "in.parquet"
        self._points_parquet(parquet)
        first = tmp_path / "a.png"
        second = tmp_path / "b.png"

        render_thumbnail(
            parquet, first, [9.0, 45.0, 11.0, 47.0], (0, 102, 204), width=400
        )
        render_thumbnail(
            parquet, second, [9.0, 45.0, 11.0, 47.0], (0, 102, 204), width=400
        )

        assert first.read_bytes() == second.read_bytes()

    def test_draws_something(self, tmp_path):
        from PIL import Image

        parquet = tmp_path / "in.parquet"
        self._points_parquet(parquet)
        out = tmp_path / "thumbnail.png"

        render_thumbnail(
            parquet, out, [9.0, 45.0, 11.0, 47.0], (0, 102, 204), width=400
        )

        with Image.open(out) as image:
            colours = {c for _, c in image.convert("RGB").getcolors(maxcolors=100000)}
        assert len(colours) > 1, "the image is a flat background, nothing was drawn"


def fake_facts():
    """A facts dict shaped like collect_facts() returns, with stable values."""
    return {
        "row_count": 20_731_065,
        "bbox": [6.7003, 35.5017, 18.66, 47.0805],
        "updated": "2026-09-15T00:00:00Z",
        "dataset_date": "2026-09-15T00:00:00Z",
        "parquet": {"file:size": 1_058_248_645, "file:checksum": "1220" + "a" * 64},
        "pmtiles": {"file:size": 333_154_611, "file:checksum": "1220" + "b" * 64},
        "comuni_h3": {"file:size": 512_000, "file:checksum": "1220" + "c" * 64},
        "style_indirizzi": {"file:size": 640, "file:checksum": "1220" + "d" * 64},
        "style_indirizzi_h3": {"file:size": 780, "file:checksum": "1220" + "e" * 64},
        "thumbnail": {"file:size": 91_000, "file:checksum": "1220" + "f" * 64},
        "pmtiles_layers": ["addresses"],
        "tile_count": 1348,
        "tile_key": "h3_cell",
        "statistics": {
            "out_of_bounds": 51_423,
            "no_boundary": 1_200,
            "comuni": 7_896,
            "metodo": {"1": 100, "2": 200, "3": 300, "4": 400, "5": 500},
        },
        "table_columns": [
            {"name": "CODICE_ISTAT", "type": "varchar", "description": "x"}
        ],
        "tile_table_columns": [
            {"name": "CODICE_ISTAT", "type": "varchar", "description": "x"},
            {"name": "h3_cell", "type": "varchar", "description": "y"},
        ],
        "table_columns_en": [
            {"name": "CODICE_ISTAT", "type": "varchar", "description": "x en"}
        ],
        "tile_table_columns_en": [
            {"name": "CODICE_ISTAT", "type": "varchar", "description": "x en"},
            {"name": "h3_cell", "type": "varchar", "description": "y en"},
        ],
        "releases": fake_releases(),
        "stradario": fake_stradario(),
        "stradario_table_columns": [
            {"name": n, "type": "varchar", "description": "x"} for n in STRAD_COLUMNS
        ],
        "stradario_table_columns_en": [
            {"name": n, "type": "varchar", "description": "x en"} for n in STRAD_COLUMNS
        ],
        "raw_table_columns": [
            {"name": n, "type": "varchar", "description": "x"} for n in RAW_COLUMNS
        ],
        "raw_table_columns_en": [
            {"name": n, "type": "varchar", "description": "x en"} for n in RAW_COLUMNS
        ],
        "gazetteer": fake_gazetteer_index(),
        "indirizzi-index": fake_address_index(),
        **{
            f"{section}_columns{suffix}": [
                {"name": name, "type": "varchar", "description": f"{name}{text}"}
                for name in names
            ]
            for section, names in (
                ("gazetteer", ["name", "feature_id"]),
                ("streets", ["codice_istat", "name_norm"]),
                ("access_points", ["codice_istat", "street_id"]),
            )
            for suffix, text in (("", " it"), ("_en", " en"))
        },
    }


def fake_gazetteer_index():
    """data/gazetteer/index.json as load_geocoding_index returns it."""
    return {
        "release": "2026-09-15",
        "files": {
            "comuni": {
                "href": "./2026-09-15/comuni.parquet",
                "size": 349_472,
                "checksum": "1220" + "2" * 64,
                "rows": 5_821,
                "row_groups": 2,
                "row_group_rows": 4096,
                "footer_metadata_bytes": 5_277,
            }
        },
    }


def fake_address_index():
    """data/indirizzi-index/index.json as load_geocoding_index returns it."""
    return {
        "release": "2026-09-15",
        "files": {
            "vie": {
                "href": "./2026-09-15/vie.parquet",
                "size": 42_730_958,
                "checksum": "1220" + "3" * 64,
                "rows": 786_969,
                "row_groups": 193,
                "row_group_rows": 4096,
                "footer_metadata_bytes": 332_699,
            },
            "civici": {
                "href": "./2026-09-15/civici.parquet",
                "size": 420_591_389,
                "checksum": "1220" + "4" * 64,
                "rows": 20_728_959,
                "row_groups": 2531,
                "row_group_rows": 8192,
                "footer_metadata_bytes": 3_061_756,
            },
        },
    }


def links_by_rel(document, rel):
    return [link for link in document["links"] if link["rel"] == rel]


def fake_releases():
    """Two releases shaped like releases.json entries."""
    return [
        {
            "date": "2026-08-03",
            "origin": "reconstructed",
            "note": "Ricostruzione da diff_ANNCSU.",
            "zip": {
                "name": "indirizzarioItalia_20260803.zip",
                "size": 324_000_000,
                "sha256": "a" * 64,
            },
            "parquet": {
                "name": "INDIR_ITA_20260803.parquet",
                "size": 310_000_000,
                "sha256": "b" * 64,
                "rows": 27_400_000,
            },
            "archived": "2026-09-20T10:00:00Z",
        },
        {
            "date": "2026-09-15",
            "origin": "original",
            "note": "Scarico dal portale ANNCSU del 2026-09-19.",
            "zip": {
                "name": "indirizzarioItalia_20260915.zip",
                "size": 336_123_456,
                "sha256": "c" * 64,
            },
            "parquet": {
                "name": "INDIR_ITA_20260915.parquet",
                "size": 320_000_000,
                "sha256": "d" * 64,
                "rows": 27_415_954,
            },
            "archived": "2026-09-20T10:00:00Z",
        },
    ]


def fake_stradario():
    """Two stradario releases shaped like stradario/releases.json entries."""
    return [
        {
            "date": "2025-01-28",
            "origin": "third-party",
            "note": "Copia Parquet di ondata/archivio_anncsu.",
            "zip": None,
            "parquet": {
                "name": "STRAD_ITA_20250128.parquet",
                "size": 30_000_000,
                "sha256": "e" * 64,
                "rows": 1_050_000,
            },
            "archived": "2026-11-20T09:00:00Z",
        },
        {
            "date": "2026-09-15",
            "origin": "original",
            "note": "Scarico dal portale ANNCSU.",
            "zip": {
                "name": "stradarioItalia_20260915.zip",
                "size": 20_000_000,
                "sha256": "f" * 64,
            },
            "parquet": {
                "name": "STRAD_ITA_20260915.parquet",
                "size": 31_000_000,
                "sha256": "1" * 64,
                "rows": 1_057_710,
            },
            "archived": "2026-11-24T08:00:00Z",
        },
    ]


def write_releases(path, releases):
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"releases": releases}, indent=2), encoding="utf-8")


class TestProviders:
    def test_lists_exactly_one_host_and_puts_it_last(self):
        result = providers()

        hosts = [p for p in result if "host" in p["roles"]]
        assert len(hosts) == 1
        assert result[-1] is hosts[0]

    def test_the_host_is_reachable(self):
        host = providers()[-1]
        assert host.get("url") or host.get("email")

    def test_names_a_producer(self):
        assert any("producer" in p["roles"] for p in providers())


class TestBuildRoot:
    def test_declares_the_portolan_schema(self):
        root = build_root("2026-09-15T00:00:00Z")
        assert PORTOLAN_SCHEMA in root["stac_extensions"]

    def test_declares_portolan_v0_3_0(self):
        root = build_root("2026-09-15T00:00:00Z")
        assert (
            "https://schemas.portolan-sdi.org/portolan/v0.3.0/schema.json"
            in root["stac_extensions"]
        )

    def test_has_a_title_and_description(self):
        root = build_root("2026-09-15T00:00:00Z")
        assert root["title"].strip()
        assert root["description"].strip()

    def test_carries_an_absolute_self_link_at_the_public_base(self):
        root = build_root("2026-09-15T00:00:00Z")
        self_links = links_by_rel(root, "self")
        assert len(self_links) == 1
        assert self_links[0]["href"] == f"{PUBLIC_BASE}/catalog.json"

    def test_has_no_parent_link(self):
        assert links_by_rel(build_root("2026-09-15T00:00:00Z"), "parent") == []

    def test_links_every_collection_with_titles(self):
        children = links_by_rel(build_root("2026-09-15T00:00:00Z"), "child")
        assert {c["href"] for c in children} == {
            "./indirizzi/collection.json",
            "./indirizzi-h3/collection.json",
            "./rilasci/collection.json",
            "./stradario/collection.json",
        }
        for child in children:
            assert child["title"].strip()
            assert child["type"] == "application/json"

    def test_carries_the_repository_links(self):
        root = build_root("2026-09-15T00:00:00Z")
        assert links_by_rel(root, "vcs")[0]["href"].startswith("https://github.com/")
        assert links_by_rel(root, "issues")[0]["href"].startswith("https://github.com/")

    def test_is_a_mirror_so_it_records_via_and_updated(self):
        root = build_root("2026-09-15T00:00:00Z")
        via = links_by_rel(root, "via")[0]
        assert via["type"] == "text/html"
        assert root["updated"] == "2026-09-15T00:00:00Z"

    def test_points_at_its_own_documentation(self):
        root = build_root("2026-09-15T00:00:00Z")
        assert links_by_rel(root, "agents")[0]["type"] == "text/markdown"
        assert links_by_rel(root, "describedby")[0]["type"] == "text/markdown"


class TestBuildIndirizzi:
    def test_is_a_single_file_collection_with_a_data_asset(self):
        collection = build_indirizzi(fake_facts())
        data = collection["assets"]["data"]
        assert data["href"] == "../anncsu-indirizzi.parquet"
        assert data["type"] == "application/vnd.apache.parquet"
        assert "data" in data["roles"]

    def test_carries_size_and_multihash_checksum_on_every_asset(self):
        collection = build_indirizzi(fake_facts())
        for key, asset in collection["assets"].items():
            assert asset["file:size"] > 0, key
            assert asset["file:checksum"].startswith("1220"), key

    def test_registers_the_pmtiles_as_a_visual_asset_and_a_link(self):
        collection = build_indirizzi(fake_facts())
        assert "visual" in collection["assets"]["visual"]["roles"]
        link = links_by_rel(collection, "pmtiles")[0]
        assert link["type"] == "application/vnd.pmtiles"
        assert link["pmtiles:layers"] == ["addresses"]

    def test_has_exactly_one_default_style(self):
        collection = build_indirizzi(fake_facts())
        styles = [a for a in collection["assets"].values() if "style" in a["roles"]]
        assert len(styles) >= 1
        defaults = [a for a in styles if "default" in a["roles"]]
        assert len(defaults) == 1
        assert defaults[0]["type"] == "application/vnd.mapbox.style+json"

    def test_has_a_thumbnail(self):
        collection = build_indirizzi(fake_facts())
        assert "thumbnail" in collection["assets"]["thumbnail"]["roles"]
        assert collection["assets"]["thumbnail"]["type"] == "image/png"

    def test_declares_the_licence_and_a_licence_link(self):
        collection = build_indirizzi(fake_facts())
        assert collection["license"] == "CC-BY-4.0"
        assert links_by_rel(collection, "license")

    def test_documents_its_columns(self):
        collection = build_indirizzi(fake_facts())
        assert collection["table:columns"][0]["name"] == "CODICE_ISTAT"
        assert collection["table:row_count"] == 20_731_065
        assert collection["table:primary_geometry"] == "geometry"

    def test_states_the_real_extent(self):
        collection = build_indirizzi(fake_facts())
        assert collection["extent"]["spatial"]["bbox"] == [
            [6.7003, 35.5017, 18.66, 47.0805]
        ]

    def test_carries_no_items(self):
        assert links_by_rel(build_indirizzi(fake_facts()), "item") == []


class TestBuildIndirizziH3:
    def test_declares_the_partition_extension(self):
        collection = build_indirizzi_h3(fake_facts())
        assert PARTITION_SCHEMA in collection["stac_extensions"]

    def test_carries_the_required_partition_fields(self):
        collection = build_indirizzi_h3(fake_facts())
        assert collection["partition:scheme"] == "hive"
        assert collection["partition:strategy"] == "h3"
        assert collection["partition:keys"] == [
            {
                "name": "h3_cell",
                "type": "string",
                "description": "Cella H3 di risoluzione 5 che contiene l'indirizzo.",
            }
        ]
        assert collection["partition:file_count"] == 1348

    def test_the_glob_is_the_listable_bucket_url(self):
        # PORTO-FMT-064: HTTPS cannot be listed, so the glob names the bucket.
        collection = build_indirizzi_h3(fake_facts())
        assert collection["partition:glob"] == (
            "s3://anncsu-data/tiles/h3_cell=*/*.parquet"
        )

    @pytest.mark.parametrize("lang", ["it", "en"])
    def test_keeps_the_account_endpoint_out_of_the_catalog(self, lang):
        # The S3 endpoint of R2 carries the Cloudflare account id, which stays
        # private: storage:schemes (PORTO-FMT-066, a SHOULD) is left out.
        import json

        collection = build_indirizzi_h3(fake_facts(), lang=lang)
        assert "storage:schemes" not in collection
        assert "r2.cloudflarestorage.com" not in json.dumps(collection)

    def test_has_no_data_asset_because_the_data_is_behind_the_glob(self):
        collection = build_indirizzi_h3(fake_facts())
        data_assets = [a for a in collection["assets"].values() if "data" in a["roles"]]
        assert data_assets == []

    def test_registers_the_cell_index_as_metadata(self):
        collection = build_indirizzi_h3(fake_facts())
        index = collection["assets"]["cell-index"]
        assert index["href"] == "../comuni-h3.json"
        assert index["roles"] == ["metadata"]
        assert index["type"] == "application/json"

    def test_documents_the_partition_key_column(self):
        collection = build_indirizzi_h3(fake_facts())
        assert [c["name"] for c in collection["table:columns"]][-1] == "h3_cell"

    def test_carries_no_items(self):
        assert links_by_rel(build_indirizzi_h3(fake_facts()), "item") == []


class TestBothCollections:
    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_has_the_structural_and_documentation_links(self, builder):
        collection = builder(fake_facts())
        assert links_by_rel(collection, "root")[0]["href"] == "../catalog.json"
        assert links_by_rel(collection, "parent")[0]["href"] == "../catalog.json"
        assert links_by_rel(collection, "agents")[0]["href"] == "./AGENTS.md"
        assert links_by_rel(collection, "describedby")[0]["href"] == "./README.md"

    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_is_a_mirror(self, builder):
        collection = builder(fake_facts())
        assert links_by_rel(collection, "via")[0]["type"] == "text/html"
        assert collection["updated"] == "2026-09-15T00:00:00Z"

    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_declares_its_language(self, builder):
        assert builder(fake_facts())["language"]["code"] == "it"

    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_every_asset_has_a_type_and_a_role(self, builder):
        for key, asset in builder(fake_facts())["assets"].items():
            assert asset["type"], key
            assert asset["roles"], key


class TestSchemaTable:
    def test_renders_one_row_per_column(self):
        table = schema_table(
            [
                {"name": "CIVICO", "type": "bigint", "description": "numero civico"},
                {"name": "ODONIMO", "type": "varchar", "description": "via o piazza"},
            ]
        )

        lines = table.strip().splitlines()
        assert lines[0].startswith("| Colonna")
        assert len(lines) == 4, "header, separator, two rows"
        assert "`CIVICO`" in lines[2]
        assert "bigint" in lines[2]
        assert "numero civico" in lines[2]

    def test_escapes_a_pipe_in_a_description(self):
        table = schema_table([{"name": "X", "type": "varchar", "description": "a | b"}])
        assert r"a \| b" in table


class TestRenderTemplate:
    def test_substitutes_every_placeholder(self):
        rendered = render_template(
            "collection.README.md",
            {
                "title": "Titolo",
                "description": "Descrizione",
                "dataset_date_human": "15 settembre 2026",
                "row_count_human": "20.731.065",
                "usage": "Uso",
                "schema_table": "| Colonna |\n|---|\n",
                "statistics_table": "| Statistica |\n|---|\n",
                "license_paragraph": "Licenza",
                "source_portal": "https://example.invalid/",
                "repo_url": "https://github.com/example/repo",
                "viewer_url": "https://example.invalid/viewer/",
            },
        )

        assert "$" not in rendered, "an unsubstituted placeholder remains"
        assert "Titolo" in rendered
        assert "20.731.065" in rendered

    def test_fails_loudly_on_a_missing_value(self):
        with pytest.raises(KeyError):
            render_template("collection.README.md", {"title": "solo questo"})


@pytest.fixture
def fixture_data_dir(tmp_path):
    """A miniature data/ directory shaped like the real one.

    Small enough to build in a second, complete enough that the generator and
    the validator both have everything they need.
    """
    import duckdb

    data = tmp_path / "data"
    (data / "tiles" / "h3_cell=851fb467fffffff").mkdir(parents=True)

    def oob(i):
        # 4 rows out of bounds, 1 with no boundary to compare against.
        if i % 50 == 0:
            return "true"
        if i == 199:
            return "NULL::BOOLEAN"
        return "false"

    rows = ", ".join(
        f"('058091', 'Roma', 'VIA ROMA {i}', {i}::BIGINT, "
        f"{12.49 + i * 0.0001}::DOUBLE, {41.90 + i * 0.0001}::DOUBLE, "
        f"NULL::DOUBLE, {oob(i)}, {1 + i % 5}::BIGINT)"
        for i in range(200)
    )
    # Shaped like csv_to_parquet output: no bbox yet, DuckDB's own geo block.
    # enhance_parquet then adds bbox, sorts, and writes the GeoParquet 1.1
    # metadata exactly as the pipeline does, so the validator sees real output.
    select = f"""
        SELECT
            *,
            ST_Point(longitude, latitude) AS geometry
        FROM (VALUES {rows}) AS t(
            CODICE_ISTAT, NOME_COMUNE, ODONIMO, CIVICO,
            longitude, latitude, oob_distance_m, out_of_bounds, METODO
        )
    """
    parquet = data / "anncsu-indirizzi.parquet"
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"COPY ({select}) TO '{parquet}' (FORMAT PARQUET)")
    con.close()

    enhance_parquet(parquet)

    tile = data / "tiles" / "h3_cell=851fb467fffffff" / "851fb467fffffff.parquet"
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(
        f"COPY (SELECT *, '851fb467fffffff' AS h3_cell "
        f"FROM read_parquet('{parquet}')) TO '{tile}' (FORMAT PARQUET)"
    )
    con.close()

    (data / "comuni-h3.json").write_text(
        '[{"codice_istat":"058091","nome_comune":"Roma",'
        '"h3_cells":["851fb467fffffff"]}]',
        encoding="utf-8",
    )
    (data / ".last_remote_date").write_text("20260915")

    # The release index only: ZIP and raw Parquet live on R2, never in the
    # checkout, and the generator reads facts from the index alone.
    (data / "rilasci").mkdir()
    write_releases(data / "rilasci" / "releases.json", fake_releases())
    write_releases(data / "stradario" / "releases.json", fake_stradario())

    build_pmtiles_fixture(
        data / "anncsu-indirizzi.parquet", data / "anncsu-indirizzi.pmtiles"
    )
    return data


@pytest.fixture
def fixture_columns(tmp_path, monkeypatch):
    """columns.yaml trimmed to the fixture's schema."""
    path = tmp_path / "columns.yaml"

    def column(name, ctype, it, en, extra=""):
        return (
            f"{name}:\n  type: {ctype}\n{extra}"
            f"  description: {it}\n  description_en: {en}\n"
        )

    path.write_text(
        column("CODICE_ISTAT", "VARCHAR", "codice Istat del comune", "Istat code")
        + column(
            "NOME_COMUNE",
            "VARCHAR",
            "nome del comune",
            "comune name",
            "  derived: true\n",
        )
        + column("ODONIMO", "VARCHAR", "denominazione della strada", "street name")
        + column("CIVICO", "BIGINT", "numero civico", "house number")
        + column("longitude", "DOUBLE", "longitudine", "longitude")
        + column("latitude", "DOUBLE", "latitudine", "latitude")
        + column(
            "oob_distance_m",
            "DOUBLE",
            "distanza dal confine",
            "distance",
            "  derived: true\n",
        )
        + column(
            "out_of_bounds",
            "BOOLEAN",
            "fuori confine",
            "out of bounds",
            "  derived: true\n",
        )
        + column("METODO", "BIGINT", "metodo", "method")
        + column(
            "bbox",
            "STRUCT(xmin DOUBLE, ymin DOUBLE, xmax DOUBLE, ymax DOUBLE)",
            "riquadro del punto",
            "point bbox",
            "  derived: true\n",
        )
        + column(
            "geometry",
            "GEOMETRY('OGC:CRS84')",
            "punto WGS84",
            "WGS84 point",
            "  derived: true\n",
        )
        + column(
            "h3_cell",
            "VARCHAR",
            "cella H3",
            "H3 cell",
            "  derived: true\n  tiles_only: true\n",
        )
        # The raw archive documents all 19 CSV columns. The fixture parquet
        # has four of them, so the other fifteen are raw_only here: in
        # production only three are, but the flag describes this fixture
        # truthfully. Keys are quoted for the apostrophe in LOCALITA'.
        + "".join(
            column(
                f'"{name}"',
                "VARCHAR",
                f"colonna grezza {name}",
                f"raw column {name}",
                "  raw_only: true\n",
            )
            for name in (
                "CODICE_COMUNE",
                "PROGRESSIVO_NAZIONALE",
                "CODICE_COMUNALE",
                "LOCALITA'",
                "TOTALE_ACCESSI",
                "DIZIONE_LINGUA1",
                "DIZIONE_LINGUA2",
                "PROGRESSIVO_ACCESSO",
                "CODICE_COMUNALE_ACCESSO",
                "ESPONENTE",
                "SPECIFICITA",
                "METRICO",
                "PROGRESSIVO_SNC",
                "COORD_X_COMUNE",
                "COORD_Y_COMUNE",
                "QUOTA",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(build_catalog, "COLUMNS_FILE", path)
    return path


GEOCODING_RELEASE = "2026-09-15"


@pytest.fixture
def fixture_geocoding(fixture_data_dir):
    """fixture_data_dir plus the three geocoding files and their index.json.

    Written with build_geocoding_index's own schemas, writer and index
    writer, so the catalog is tested against what that script produces.
    """
    import pyarrow as pa

    bgi = build_geocoding_index
    bbox = {"xmin": 12.49, "ymin": 41.90, "xmax": 12.51, "ymax": 41.92}
    gazetteer_dir = fixture_data_dir / "gazetteer"
    index_dir = fixture_data_dir / "indirizzi-index"
    files = {
        "comuni": (
            gazetteer_dir / GEOCODING_RELEASE / "comuni.parquet",
            bgi.GAZETTEER_SCHEMA,
            bgi.GAZETTEER_SORT,
            {
                "name": "Roma",
                "name_norm": "roma",
                "level": 3,
                "country": "ITA",
                "feature_id": "058091",
                "country_name": "Italia",
                "parent_name": "Roma",
                "parent_id": "258",
                "name_lang": None,
                "alt_of": None,
                "source": "anncsu",
                "addresses": 200,
                "bbox": bbox,
            },
        ),
        "vie": (
            index_dir / GEOCODING_RELEASE / "vie.parquet",
            bgi.STREETS_SCHEMA,
            bgi.STREETS_SORT,
            {
                "codice_istat": "058091",
                "comune": "Roma",
                "street_id": 1,
                "name": "VIA ROMA",
                "name_norm": "via roma",
                "name_lang": None,
                "alt_of": None,
                "numbers": 200,
                "number_min": 0,
                "number_max": 199,
                "bbox": bbox,
            },
        ),
        "civici": (
            index_dir / GEOCODING_RELEASE / "civici.parquet",
            bgi.ACCESS_POINTS_SCHEMA,
            bgi.ACCESS_POINTS_SORT,
            {
                "codice_istat": "058091",
                "street_id": 1,
                "id": 10,
                "number": 1,
                "suffix": None,
                "specificita": None,
                "metrico": None,
                "out_of_bounds": False,
                "lon": 12.5,
                "lat": 41.91,
            },
        ),
    }
    facts = {}
    for name, (path, schema, sort, row) in files.items():
        bgi.write_sorted(pa.Table.from_pylist([row], schema=schema), path, sort, 4096)
        facts[name] = bgi.parquet_facts(path, 4096)
    bgi.write_index(gazetteer_dir, GEOCODING_RELEASE, {"comuni": facts["comuni"]})
    bgi.write_index(
        index_dir, GEOCODING_RELEASE, {"vie": facts["vie"], "civici": facts["civici"]}
    )
    return fixture_data_dir


GENERATED_SUFFIXES = {".json", ".md", ".png"}


def generated_files(data_dir: Path) -> dict[Path, bytes]:
    return {
        p.relative_to(data_dir): p.read_bytes()
        for p in sorted(data_dir.rglob("*"))
        if p.is_file() and p.suffix in GENERATED_SUFFIXES
    }


@pytest.mark.skipif(
    shutil.which("tippecanoe") is None, reason="tippecanoe not installed"
)
class TestBuild:
    def test_writes_the_whole_tree(self, fixture_data_dir, fixture_columns):
        build(fixture_data_dir)

        for relative in [
            "catalog.json",
            "README.md",
            "AGENTS.md",
            "indirizzi/collection.json",
            "indirizzi/README.md",
            "indirizzi/AGENTS.md",
            "indirizzi/thumbnail.png",
            "indirizzi/styles/indirizzi.json",
            "indirizzi-h3/collection.json",
            "indirizzi-h3/README.md",
            "indirizzi-h3/AGENTS.md",
            "indirizzi-h3/thumbnail.png",
            "indirizzi-h3/styles/indirizzi-h3.json",
        ]:
            assert (fixture_data_dir / relative).exists(), relative

    def test_agents_files_name_the_declared_profile_version(
        self, fixture_data_dir, fixture_columns
    ):
        build(fixture_data_dir)
        agents = sorted(fixture_data_dir.rglob("AGENTS.md"))
        assert len(agents) == 10
        for path in agents:
            text = path.read_text(encoding="utf-8")
            assert "v0.3.0" in text and "v0.2.0" not in text, path

    @pytest.mark.parametrize("tree", ["", "en/"])
    def test_partitioned_docs_show_the_bucket_glob(
        self, fixture_data_dir, fixture_columns, tree
    ):
        build(fixture_data_dir)
        for name in ("README.md", "AGENTS.md"):
            text = (fixture_data_dir / tree / "indirizzi-h3" / name).read_text(
                encoding="utf-8"
            )
            assert "s3://anncsu-data/tiles/h3_cell=*/*.parquet" in text, name
            assert f"{PUBLIC_BASE}/tiles/h3_cell=*" not in text, name

    def test_is_byte_identical_on_a_second_run(self, fixture_data_dir, fixture_columns):
        build(fixture_data_dir)
        first = generated_files(fixture_data_dir)

        build(fixture_data_dir)
        second = generated_files(fixture_data_dir)

        assert first.keys() == second.keys()
        for name in first:
            assert first[name] == second[name], f"{name} changed between runs"

    def test_declared_checksums_match_the_real_bytes(
        self, fixture_data_dir, fixture_columns
    ):
        import json

        build(fixture_data_dir)
        collection = json.loads(
            (fixture_data_dir / "indirizzi" / "collection.json").read_text()
        )
        base = fixture_data_dir / "indirizzi"
        for key, asset in collection["assets"].items():
            target = (base / asset["href"]).resolve()
            assert target.exists(), f"{key} points at a missing file"
            assert asset["file:size"] == target.stat().st_size, key
            assert asset["file:checksum"] == multihash_sha256(target), key

    def test_every_relative_link_resolves(self, fixture_data_dir, fixture_columns):
        import json

        build(fixture_data_dir)
        for document_path in sorted(fixture_data_dir.rglob("*.json")):
            if document_path.name not in {"catalog.json", "collection.json"}:
                continue
            document = json.loads(document_path.read_text())
            for link in document["links"]:
                href = link["href"]
                if href.startswith("http"):
                    continue
                target = (document_path.parent / href).resolve()
                assert target.exists(), f"{document_path.name} {link['rel']} -> {href}"

    def test_the_readme_carries_the_schema_table(
        self, fixture_data_dir, fixture_columns
    ):
        build(fixture_data_dir)
        readme = (fixture_data_dir / "indirizzi" / "README.md").read_text()
        assert "| Colonna | Tipo | Descrizione |" in readme
        assert "`ODONIMO`" in readme
        assert "$" not in readme, "an unsubstituted placeholder reached the output"


@pytest.mark.skipif(
    shutil.which("tippecanoe") is None, reason="tippecanoe not installed"
)
class TestConformance:
    """The Portolan validator is the arbiter, not our reading of the spec."""

    def test_rashid_reports_no_findings(self, fixture_data_dir, fixture_columns):
        build(fixture_data_dir)
        self.assert_rashid_passes(fixture_data_dir)

    def test_rashid_reports_no_findings_on_the_geocoding_collections(
        self, fixture_geocoding, fixture_columns
    ):
        build(fixture_geocoding)
        assert (fixture_geocoding / "gazetteer" / "collection.json").exists()
        assert (fixture_geocoding / "indirizzi-index" / "collection.json").exists()
        self.assert_rashid_passes(fixture_geocoding)

    @staticmethod
    def assert_rashid_passes(fixture_data_dir):
        import json
        import subprocess

        # rashid ships only as a console script: `python -m rashid` fails
        # with "rashid is a package and cannot be directly executed".
        rashid = shutil.which("rashid")
        assert rashid, (
            "rashid is a test dependency; run via `uv run scripts/test_build_catalog.py`"
        )

        result = subprocess.run(
            [
                rashid,
                "check",
                str(fixture_data_dir),
                "--schema",
                # The archive's assets are absolute URLs to R2 and are not in
                # the checkout; local scope verifies every asset that is.
                "--data-scope",
                "local",
                "--json",
                "--all",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        report = json.loads(result.stdout)
        # Report shape, verified against rashid 0.1.8:
        #   passed, files_checked, error_count, warning_count, info_count,
        #   summary, findings[]. Each finding carries rule_id, severity
        #   (error | warning | info), message, path, object_id, fix_hint,
        #   expected. Rule ids are rashid's own (PTL-FIL-001), not the spec's
        #   PORTO-* requirement ids.
        blocking = [
            f for f in report["findings"] if f["severity"] in ("error", "warning")
        ]
        assert report["passed"] and not blocking, json.dumps(
            blocking, indent=2, ensure_ascii=False
        )


class TestEnglishColumns:
    def test_every_real_column_has_an_english_description(self):
        columns = load_columns(COLUMNS_YAML)
        for name, spec in columns.items():
            assert spec["description_en"].strip(), f"{name} has no description_en"

    def test_table_columns_picks_the_requested_language(self, tmp_path):
        parquet = tmp_path / "in.parquet"
        write_parquet(parquet, "'x' AS CODICE_ISTAT")
        yaml_path = tmp_path / "columns.yaml"
        yaml_path.write_text(
            "CODICE_ISTAT:\n  type: VARCHAR\n"
            "  description: codice Istat\n  description_en: Istat code\n",
            encoding="utf-8",
        )

        assert table_columns(parquet, yaml_path)[0]["description"] == "codice Istat"
        assert (
            table_columns(parquet, yaml_path, lang="en")[0]["description"]
            == "Istat code"
        )

    def test_fails_when_the_english_description_is_missing(self, tmp_path):
        yaml_path = tmp_path / "columns.yaml"
        yaml_path.write_text(
            "CODICE_ISTAT:\n  type: VARCHAR\n  description: codice Istat\n",
            encoding="utf-8",
        )

        with pytest.raises(SystemExit, match="description_en"):
            load_columns(yaml_path)


class TestDatasetStatistics:
    def _parquet(self, path):
        import duckdb

        con = duckdb.connect()
        con.execute(f"""
            COPY (SELECT * FROM (VALUES
                ('058091', true,  1::BIGINT),
                ('058091', false, 1::BIGINT),
                ('058091', false, 3::BIGINT),
                ('001001', NULL::BOOLEAN, 5::BIGINT),
                ('001001', false, NULL::BIGINT)
            ) AS t(CODICE_ISTAT, out_of_bounds, METODO)) TO '{path}' (FORMAT PARQUET)
        """)
        con.close()

    def test_counts_out_of_bounds_no_boundary_comuni_and_methods(self, tmp_path):
        parquet = tmp_path / "in.parquet"
        self._parquet(parquet)

        stats = dataset_statistics(parquet)

        assert stats["out_of_bounds"] == 1
        assert stats["no_boundary"] == 1
        assert stats["comuni"] == 2
        assert stats["metodo"] == {"1": 2, "3": 1, "5": 1}


class TestHumanFormats:
    def test_count_uses_the_language_thousands_separator(self):
        assert human_count(20_731_065) == "20.731.065"
        assert human_count(20_731_065, lang="en") == "20,731,065"

    def test_date_is_spelled_in_the_language(self):
        assert human_date("2026-09-15T00:00:00Z") == "15 settembre 2026"
        assert human_date("2026-09-15T00:00:00Z", lang="en") == "15 September 2026"

    def test_percent_uses_two_decimals_and_the_language_decimal_mark(self):
        assert human_percent(51_423, 20_731_065) == "0,25%"
        assert human_percent(51_423, 20_731_065, lang="en") == "0.25%"

    def test_percent_of_zero_total_is_a_dash(self):
        assert human_percent(0, 0) == "-"


class TestStatisticsTable:
    def test_lists_totals_and_every_method_in_italian(self):
        table = statistics_table(fake_facts())
        assert "| 20.731.065 |" in table
        assert "51.423" in table and "0,25%" in table
        assert "7.896" in table
        for code in "12345":
            assert f"| {code} " in table or f"metodo {code}" in table.lower()

    def test_lists_totals_in_english(self):
        table = statistics_table(fake_facts(), lang="en")
        assert "| 20,731,065 |" in table
        assert "51,423" in table and "0.25%" in table


class TestLanguageTrees:
    def test_italian_root_announces_and_links_the_english_tree(self):
        root = build_root("2026-09-15T00:00:00Z")
        assert root["language"]["code"] == "it"
        assert [lang["code"] for lang in root["languages"]] == ["en"]
        alternate = [
            l
            for l in links_by_rel(root, "alternate")
            if l["type"] == "application/json"
        ]
        assert len(alternate) == 1
        assert alternate[0]["href"] == "./en/catalog.json"
        assert alternate[0]["hreflang"] == "en"

    def test_english_root_is_its_own_tree(self):
        root = build_root("2026-09-15T00:00:00Z", lang="en")
        assert root["language"]["code"] == "en"
        assert [lang["code"] for lang in root["languages"]] == ["it"]
        assert links_by_rel(root, "parent") == []
        assert links_by_rel(root, "self")[0]["href"] == f"{PUBLIC_BASE}/en/catalog.json"
        alternate = [
            l
            for l in links_by_rel(root, "alternate")
            if l["type"] == "application/json"
        ]
        assert alternate[0]["href"] == "../catalog.json"
        assert alternate[0]["hreflang"] == "it"
        assert {c["href"] for c in links_by_rel(root, "child")} == {
            "./indirizzi/collection.json",
            "./indirizzi-h3/collection.json",
            "./rilasci/collection.json",
            "./stradario/collection.json",
        }
        assert root["title"] == "ANNCSU addresses"

    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_italian_collection_links_its_translation(self, builder):
        collection = builder(fake_facts())
        alternate = [
            l
            for l in links_by_rel(collection, "alternate")
            if l["type"] == "application/json"
        ]
        assert alternate[0]["href"] == f"../en/{collection['id']}/collection.json"
        assert alternate[0]["hreflang"] == "en"

    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_english_collection_reaches_data_two_levels_up(self, builder):
        collection = builder(fake_facts(), lang="en")
        assert collection["language"]["code"] == "en"
        assert links_by_rel(collection, "root")[0]["href"] == "../catalog.json"
        assert links_by_rel(collection, "parent")[0]["href"] == "../catalog.json"
        assert links_by_rel(collection, "pmtiles")[0]["href"] == (
            "../../anncsu-indirizzi.pmtiles"
        )
        alternate = [
            l
            for l in links_by_rel(collection, "alternate")
            if l["type"] == "application/json"
        ]
        assert alternate[0]["href"] == f"../../{collection['id']}/collection.json"
        assert alternate[0]["hreflang"] == "it"
        for key, asset in collection["assets"].items():
            assert asset["href"].startswith("../../"), f"{key}: {asset['href']}"
        assert collection["assets"]["thumbnail"]["href"] == (
            f"../../{collection['id']}/thumbnail.png"
        )
        assert collection["table:columns"][0]["description"] == "x en"

    def test_english_single_file_collection_points_at_the_shared_style(self):
        collection = build_indirizzi(fake_facts(), lang="en")
        assert collection["assets"]["style-indirizzi"]["href"] == (
            "../../indirizzi/styles/indirizzi.json"
        )
        assert collection["assets"]["data"]["href"] == "../../anncsu-indirizzi.parquet"

    def test_english_partitioned_collection_keeps_the_index_and_glob(self):
        collection = build_indirizzi_h3(fake_facts(), lang="en")
        assert collection["assets"]["cell-index"]["href"] == "../../comuni-h3.json"
        assert collection["partition:glob"] == (
            "s3://anncsu-data/tiles/h3_cell=*/*.parquet"
        )
        assert collection["partition:keys"][0]["description"].startswith("H3 cell")


class TestViewerLink:
    @pytest.mark.parametrize("lang", ["it", "en"])
    def test_root_links_the_web_viewer_as_html_alternate(self, lang):
        root = build_root("2026-09-15T00:00:00Z", lang=lang)
        viewer = [
            l for l in links_by_rel(root, "alternate") if l["type"] == "text/html"
        ]
        assert len(viewer) == 1
        assert viewer[0]["href"] == VIEWER_URL
        assert viewer[0]["title"].strip()
        assert "hreflang" not in viewer[0], "an html alternate is not a language tree"

    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    @pytest.mark.parametrize("lang", ["it", "en"])
    def test_collections_link_the_web_viewer(self, builder, lang):
        collection = builder(fake_facts(), lang=lang)
        viewer = [
            l for l in links_by_rel(collection, "alternate") if l["type"] == "text/html"
        ]
        assert [v["href"] for v in viewer] == [VIEWER_URL]


class TestStatisticsInDescriptions:
    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_italian_description_states_the_out_of_bounds_share(self, builder):
        description = builder(fake_facts())["description"]
        assert "20.731.065" in description
        assert "51.423" in description
        assert "0,25%" in description

    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_english_description_states_the_out_of_bounds_share(self, builder):
        description = builder(fake_facts(), lang="en")["description"]
        assert "20,731,065" in description
        assert "51,423" in description
        assert "0.25%" in description


@pytest.mark.skipif(
    shutil.which("tippecanoe") is None, reason="tippecanoe not installed"
)
class TestEnglishBuild:
    def test_writes_the_english_tree(self, fixture_data_dir, fixture_columns):
        build(fixture_data_dir)

        for relative in [
            "en/catalog.json",
            "en/README.md",
            "en/AGENTS.md",
            "en/indirizzi/collection.json",
            "en/indirizzi/README.md",
            "en/indirizzi/AGENTS.md",
            "en/indirizzi-h3/collection.json",
            "en/indirizzi-h3/README.md",
            "en/indirizzi-h3/AGENTS.md",
        ]:
            assert (fixture_data_dir / relative).exists(), relative
        assert not (fixture_data_dir / "en" / "indirizzi" / "thumbnail.png").exists(), (
            "assets stay in the source tree; the translation only references them"
        )

    def test_english_assets_resolve_with_matching_checksums(
        self, fixture_data_dir, fixture_columns
    ):
        import json

        build(fixture_data_dir)
        for collection_id in ("indirizzi", "indirizzi-h3"):
            base = fixture_data_dir / "en" / collection_id
            collection = json.loads((base / "collection.json").read_text())
            for key, asset in collection["assets"].items():
                target = (base / asset["href"]).resolve()
                assert target.exists(), f"{collection_id}/{key} -> {asset['href']}"
                assert asset["file:checksum"] == multihash_sha256(target), key

    def test_readmes_carry_statistics_and_the_browser_link(
        self, fixture_data_dir, fixture_columns
    ):
        build(fixture_data_dir)
        root_readme = (fixture_data_dir / "README.md").read_text()
        assert "browser.portolan-sdi.org" in root_readme
        for readme in (
            fixture_data_dir / "indirizzi" / "README.md",
            fixture_data_dir / "en" / "indirizzi" / "README.md",
        ):
            text = readme.read_text()
            assert "$" not in text, f"placeholder left in {readme}"
            assert "METODO" in text or "metodo" in text.lower()
            assert "200" in text, (
                "the fixture's 200 rows should appear in the statistics"
            )

    def test_root_readmes_link_portolan_browser_italia_next_to_the_browser(
        self, fixture_data_dir, fixture_columns
    ):
        build(fixture_data_dir)
        url = (
            "https://anncsu-open.github.io/portolan-browser-it/#/external/"
            "pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev/catalog.json"
        )
        for readme in (
            fixture_data_dir / "README.md",
            fixture_data_dir / "en" / "README.md",
        ):
            text = readme.read_text()
            assert f"[Portolan Browser Italia]({url})" in text, readme
            # In the same paragraph as the official browser's link.
            paragraph = next(
                block
                for block in text.split("\n\n")
                if "browser.portolan-sdi.org" in block
            )
            assert url in paragraph, readme

    def test_collection_readmes_warn_about_the_browser_temporal_extent_bug(
        self, fixture_data_dir, fixture_columns
    ):
        """STAC Browser drops the start date of an open temporal extent in
        every non-English interface language, rendering only 'fino ad ora'.
        The README states the date and says the defect is the browser's."""
        build(fixture_data_dir)

        italian = (fixture_data_dir / "indirizzi" / "README.md").read_text()
        assert "fino ad ora" in italian
        assert "15 settembre 2026" in italian
        assert "STAC Browser" in italian

        english = (fixture_data_dir / "en" / "indirizzi" / "README.md").read_text()
        assert "until present" in english
        assert "15 September 2026" in english
        assert "STAC Browser" in english


class TestDataUpdatedInGit:
    """`updated` must come from the commit that brought the parquet in.

    actions/checkout clones at depth 1 by default. In such a clone every file
    looks as if HEAD introduced it, so `git log -1 -- parquet` returns HEAD and
    `updated` would move with every unrelated commit, producing a spurious
    "Update Portolan catalog" commit on every run. That is what happened on
    2026-09-19. A shallow repository must therefore not be trusted.
    """

    def _git(self, *args, cwd, date=None):
        import os
        import subprocess

        env = dict(os.environ)
        if date:
            env["GIT_AUTHOR_DATE"] = date
            env["GIT_COMMITTER_DATE"] = date
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            env=env,
        )

    def _make_origin(self, root):
        """Two commits: the parquet lands first, an unrelated file later."""
        origin = root / "origin"
        (origin / "data").mkdir(parents=True)
        self._git("init", "-q", "-b", "main", cwd=origin)
        (origin / "data" / "in.parquet").write_bytes(b"parquet")
        (origin / "data" / ".last_remote_date").write_text("20260915")
        self._git("add", ".", cwd=origin)
        self._git("commit", "-q", "-m", "data", cwd=origin, date="2026-09-01T10:00:00Z")
        (origin / "other.txt").write_text("later")
        self._git("add", ".", cwd=origin)
        self._git(
            "commit", "-q", "-m", "unrelated", cwd=origin, date="2026-09-02T10:00:00Z"
        )
        return origin

    def test_full_history_gives_the_parquet_commit_date(self, tmp_path):
        origin = self._make_origin(tmp_path)

        result = data_updated(
            origin / "data" / "in.parquet", origin / "data" / ".last_remote_date"
        )

        assert result == "2026-09-01T10:00:00Z"

    def test_shallow_clone_falls_back_to_the_dataset_date(self, tmp_path):
        origin = self._make_origin(tmp_path)
        clone = tmp_path / "shallow"
        self._git(
            "clone", "-q", "--depth", "1", f"file://{origin}", str(clone), cwd=tmp_path
        )

        result = data_updated(
            clone / "data" / "in.parquet", clone / "data" / ".last_remote_date"
        )

        assert result != "2026-09-02T10:00:00Z", (
            "HEAD's date is not when the parquet changed"
        )
        assert result == "2026-09-15T00:00:00Z"


class TestLoadReleases:
    def test_returns_entries_sorted_by_date(self, tmp_path):
        path = tmp_path / "releases.json"
        write_releases(path, list(reversed(fake_releases())))

        releases = load_releases(path)

        assert [r["date"] for r in releases] == ["2026-08-03", "2026-09-15"]

    def test_rejects_a_duplicate_date(self, tmp_path):
        path = tmp_path / "releases.json"
        write_releases(path, [fake_releases()[0], fake_releases()[0]])

        with pytest.raises(SystemExit, match="2026-08-03"):
            load_releases(path)

    def test_rejects_an_unknown_origin(self, tmp_path):
        bad = fake_releases()[0]
        bad["origin"] = "guessed"
        path = tmp_path / "releases.json"
        write_releases(path, [bad])

        with pytest.raises(SystemExit, match="origin"):
            load_releases(path)

    def test_rejects_a_missing_field(self, tmp_path):
        bad = fake_releases()[0]
        del bad["parquet"]["rows"]
        path = tmp_path / "releases.json"
        write_releases(path, [bad])

        with pytest.raises(SystemExit, match="rows"):
            load_releases(path)

    def test_fails_loudly_when_the_index_is_missing(self, tmp_path):
        with pytest.raises(SystemExit, match="releases.json"):
            load_releases(tmp_path / "releases.json")


class TestRawTableColumns:
    def test_lists_the_nineteen_csv_columns_in_order_as_varchar(self):
        columns = raw_table_columns(COLUMNS_YAML)

        assert [c["name"] for c in columns] == RAW_COLUMNS
        assert len(columns) == 19
        assert {c["type"] for c in columns} == {"varchar"}
        assert all(c["description"].strip() for c in columns)

    def test_uses_the_english_descriptions_when_asked(self):
        columns = raw_table_columns(COLUMNS_YAML, lang="en")
        by_name = {c["name"]: c["description"] for c in columns}
        assert by_name["LOCALITA'"].startswith("Locality name")

    def test_raw_only_columns_stay_out_of_the_enriched_schema_check(self, tmp_path):
        parquet = tmp_path / "in.parquet"
        write_parquet(parquet, "'x' AS CODICE_ISTAT")
        yaml_path = tmp_path / "columns.yaml"
        yaml_path.write_text(
            "CODICE_ISTAT:\n  type: VARCHAR\n"
            "  description: codice Istat\n  description_en: Istat code\n"
            "COORD_X_COMUNE:\n  type: VARCHAR\n  raw_only: true\n"
            "  description: longitudine testo\n  description_en: longitude text\n",
            encoding="utf-8",
        )

        result = table_columns(parquet, yaml_path)

        assert [c["name"] for c in result] == ["CODICE_ISTAT"]


class TestReleaseAssetUrl:
    def test_is_absolute_under_the_public_base(self):
        release = fake_releases()[1]
        assert release_asset_url(release, "zip") == (
            f"{PUBLIC_BASE}/rilasci/2026-09-15/indirizzarioItalia_20260915.zip"
        )
        assert release_asset_url(release, "parquet") == (
            f"{PUBLIC_BASE}/rilasci/2026-09-15/INDIR_ITA_20260915.parquet"
        )


class TestBuildReleaseItem:
    def _item(self, index=1, lang="it"):
        releases = fake_releases()
        return build_release_item(releases[index], releases, fake_facts(), lang=lang)

    def test_is_a_tabular_item_with_null_geometry_and_no_bbox(self):
        item = self._item()
        assert item["type"] == "Feature"
        assert item["geometry"] is None
        assert "bbox" not in item
        assert item["collection"] == "rilasci"

    def test_carries_version_and_datetime_of_the_release(self):
        item = self._item()
        assert item["id"] == "2026-09-15"
        assert item["properties"]["version"] == "2026-09-15"
        assert item["properties"]["datetime"] == "2026-09-15T00:00:00Z"
        assert VERSION_SCHEMA in item["stac_extensions"]

    def test_assets_point_at_r2_with_facts_from_the_index(self):
        item = self._item()
        data = item["assets"]["data"]
        source = item["assets"]["source"]
        assert data["href"] == (
            f"{PUBLIC_BASE}/rilasci/2026-09-15/INDIR_ITA_20260915.parquet"
        )
        assert data["type"] == "application/vnd.apache.parquet"
        assert data["roles"] == ["data"]
        assert data["file:size"] == 320_000_000
        assert data["file:checksum"] == "1220" + "d" * 64
        assert source["href"] == (
            f"{PUBLIC_BASE}/rilasci/2026-09-15/indirizzarioItalia_20260915.zip"
        )
        assert source["type"] == "application/zip"
        assert source["roles"] == ["source"]
        assert source["file:checksum"] == "1220" + "c" * 64

    def test_documents_columns_and_row_count(self):
        item = self._item()
        names = [c["name"] for c in item["properties"]["table:columns"]]
        assert names == RAW_COLUMNS
        assert item["properties"]["table:row_count"] == 27_415_954

    def test_links_the_previous_release_but_not_a_missing_next_one(self):
        latest = self._item(index=1)
        first = self._item(index=0)
        assert links_by_rel(latest, "predecessor-version")[0]["href"] == (
            "../2026-08-03/2026-08-03.json"
        )
        assert links_by_rel(latest, "successor-version") == []
        assert links_by_rel(first, "successor-version")[0]["href"] == (
            "../2026-09-15/2026-09-15.json"
        )
        assert links_by_rel(first, "predecessor-version") == []

    def test_has_the_structural_links(self):
        item = self._item()
        assert links_by_rel(item, "root")[0]["href"] == "../../catalog.json"
        assert links_by_rel(item, "parent")[0]["href"] == "../collection.json"
        assert links_by_rel(item, "collection")[0]["href"] == "../collection.json"
        assert links_by_rel(item, "via")[0]["type"] == "text/html"

    def test_states_the_origin_in_the_description(self):
        original = self._item(index=1)["properties"]["description"]
        reconstructed = self._item(index=0)["properties"]["description"]
        assert "originale" in original.lower()
        assert "diff_ANNCSU" in reconstructed
        assert "ricostru" in reconstructed.lower()

    def test_english_item_reaches_the_italian_twin_and_translates(self):
        item = self._item(lang="en")
        alternate = [
            l
            for l in links_by_rel(item, "alternate")
            if l["type"] == "application/geo+json"
        ]
        assert alternate[0]["href"] == "../../../rilasci/2026-09-15/2026-09-15.json"
        assert alternate[0]["hreflang"] == "it"
        assert links_by_rel(item, "root")[0]["href"] == "../../catalog.json"
        assert item["properties"]["table:columns"][0]["description"] == "x en"
        assert "original" in item["properties"]["description"].lower()

    def test_italian_item_links_its_english_twin(self):
        item = self._item()
        alternate = [
            l
            for l in links_by_rel(item, "alternate")
            if l["type"] == "application/geo+json"
        ]
        assert alternate[0]["href"] == "../../en/rilasci/2026-09-15/2026-09-15.json"
        assert alternate[0]["hreflang"] == "en"


class TestAssetsAreDescribed:
    """PORTO-CORE-088: every asset SHOULD have a title and a description."""

    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_collection_assets_in_both_languages(self, builder):
        italian = builder(fake_facts())["assets"]
        english = builder(fake_facts(), lang="en")["assets"]
        for key in italian:
            for asset in (italian[key], english[key]):
                assert asset.get("title", "").strip(), key
                assert asset.get("description", "").strip(), key
            assert italian[key]["description"] != english[key]["description"], key

    def test_release_item_assets_in_both_languages(self):
        releases = fake_releases()
        for release in releases:
            italian = build_release_item(release, releases, fake_facts())["assets"]
            english = build_release_item(release, releases, fake_facts(), lang="en")[
                "assets"
            ]
            for key in italian:
                for asset in (italian[key], english[key]):
                    assert asset.get("title", "").strip(), key
                    assert asset.get("description", "").strip(), key
                assert italian[key]["description"] != english[key]["description"]


class TestMonthsWithoutARelease:
    """ANNCSU skipped October 2026, and the archive description says so."""

    def test_italian_archive_names_the_month(self):
        description = build_rilasci(fake_facts())["description"]
        assert "ottobre 2026" in description
        assert "15 settembre 2026" in description

    def test_english_archive_names_the_month(self):
        description = build_rilasci(fake_facts(), lang="en")["description"]
        assert "October 2026" in description
        assert "15 September 2026" in description


class TestBuildRilasci:
    def test_is_tabular(self):
        collection = build_rilasci(fake_facts())
        assert "table:primary_geometry" not in collection
        names = {c["name"].lower() for c in collection["table:columns"]}
        assert "geometry" not in names and "geom" not in names
        assert not any("thumbnail" in a["roles"] for a in collection["assets"].values())

    def test_declares_the_version_extension_and_the_area_of_interest(self):
        collection = build_rilasci(fake_facts())
        assert VERSION_SCHEMA in collection["stac_extensions"]
        assert collection["extent"]["spatial"]["bbox"] == [
            [6.7003, 35.5017, 18.66, 47.0805]
        ]
        assert collection["extent"]["temporal"]["interval"] == [
            ["2026-08-03T00:00:00Z", None]
        ]

    def test_links_every_release_and_the_latest_version(self):
        collection = build_rilasci(fake_facts())
        items = links_by_rel(collection, "item")
        assert [l["href"] for l in items] == [
            "./2026-08-03/2026-08-03.json",
            "./2026-09-15/2026-09-15.json",
        ]
        assert all(
            l["title"].strip() and l["type"] == "application/geo+json" for l in items
        )
        assert links_by_rel(collection, "latest-version")[0]["href"] == (
            "./2026-09-15/2026-09-15.json"
        )

    def test_has_the_common_mirror_and_documentation_links(self):
        collection = build_rilasci(fake_facts())
        assert collection["license"] == "CC-BY-4.0"
        assert collection["providers"][-1]["roles"] == ["host"]
        assert links_by_rel(collection, "via")[0]["type"] == "text/html"
        assert links_by_rel(collection, "agents")[0]["href"] == "./AGENTS.md"
        assert links_by_rel(collection, "describedby")[0]["href"] == "./README.md"
        assert collection["updated"] == "2026-09-15T00:00:00Z"

    def test_english_collection(self):
        collection = build_rilasci(fake_facts(), lang="en")
        assert collection["language"]["code"] == "en"
        assert collection["title"] == "ANNCSU monthly releases"
        assert collection["table:columns"][0]["description"] == "x en"


class TestLiveCollectionsAreVersioned:
    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_version_is_the_current_release_date(self, builder):
        collection = builder(fake_facts())
        assert collection["version"] == "2026-09-15"
        assert VERSION_SCHEMA in collection["stac_extensions"]

    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_links_the_release_it_derives_from_and_the_history(self, builder):
        collection = builder(fake_facts())
        derived = links_by_rel(collection, "derived_from")[0]
        assert derived["href"] == "../rilasci/2026-09-15/2026-09-15.json"
        assert derived["type"] == "application/geo+json"
        history = links_by_rel(collection, "version-history")[0]
        assert history["href"] == "../rilasci/collection.json"
        assert history["type"] == "application/json"

    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_english_links_stay_inside_the_english_tree(self, builder):
        collection = builder(fake_facts(), lang="en")
        assert links_by_rel(collection, "derived_from")[0]["href"] == (
            "../rilasci/2026-09-15/2026-09-15.json"
        )

    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_description_states_the_georeferenced_share(self, builder):
        description = builder(fake_facts())["description"]
        assert "20.731.065" in description
        assert "27.415.954" in description


class TestRootLinksTheArchive:
    @pytest.mark.parametrize("lang", ["it", "en"])
    def test_child_link_to_rilasci(self, lang):
        root = build_root("2026-09-15T00:00:00Z", lang=lang)
        children = {c["href"]: c for c in links_by_rel(root, "child")}
        assert "./rilasci/collection.json" in children
        assert children["./rilasci/collection.json"]["title"].strip()


class TestDescriptionFormatting:
    """Descriptions are CommonMark, so lists and links really render.

    STAC declares description fields as CommonMark and the browser renders
    them, as does every README, which substitutes the same text. What matters
    here is that no placeholder leaks through and that the markup is the
    shape a reader expects.
    """

    @pytest.mark.parametrize("lang", ["it", "en"])
    def test_root_lists_every_collection_and_links_the_portal(self, lang):
        description = build_root("2026-09-15T00:00:00Z", lang=lang)["description"]

        assert "$" not in description, "an unsubstituted placeholder reached the output"
        assert description.count("\n- ") == 4, "one bullet per collection"
        for name in ("indirizzi", "indirizzi-h3", "rilasci", "stradario"):
            assert f"`{name}`" in description
        assert f"]({SOURCE_PORTAL})" in description

    @pytest.mark.parametrize("lang", ["it", "en"])
    def test_archive_lists_the_two_files_and_links_the_reconstruction_source(
        self, lang
    ):
        description = build_rilasci(fake_facts(), lang=lang)["description"]

        assert "$" not in description
        assert description.count("\n- ") == 2, "one bullet per file of a release"
        assert f"[mfortini/diff_ANNCSU]({DIFF_ANNCSU_URL})" in description

    def test_reconstructed_item_links_the_reconstruction_source(self):
        releases = fake_releases()

        item = build_release_item(releases[0], releases, fake_facts())

        description = item["properties"]["description"]
        assert f"[mfortini/diff_ANNCSU]({DIFF_ANNCSU_URL})" in description
        assert "$" not in description

    def test_original_item_links_the_portal_it_came_from(self):
        releases = fake_releases()

        item = build_release_item(releases[1], releases, fake_facts())

        description = item["properties"]["description"]
        assert f"]({SOURCE_PORTAL})" in description
        assert "$" not in description

    @pytest.mark.parametrize("builder", [build_indirizzi, build_indirizzi_h3])
    def test_live_collections_name_the_archive_as_code(self, builder):
        description = builder(fake_facts())["description"]
        assert "`rilasci`" in description

    @pytest.mark.parametrize("index", [0, 1])
    def test_item_description_does_not_repeat_the_index_note(self, index):
        """The note is a machine-readable remark, not prose for the reader.

        Rendering it appended the same claim twice for a reconstruction, whose
        template already explains the reconstruction.
        """
        releases = fake_releases()

        item = build_release_item(releases[index], releases, fake_facts())

        assert releases[index]["note"] not in item["properties"]["description"]

    @pytest.mark.parametrize("index", [0, 1])
    def test_english_item_description_is_entirely_english(self, index):
        """The note in the index is Italian; it must not leak into en/."""
        releases = fake_releases()

        item = build_release_item(releases[index], releases, fake_facts(), lang="en")

        description = item["properties"]["description"]
        for italian in ("Scarico", "Ricostruzione", "rilascio"):
            assert italian not in description


@pytest.mark.skipif(
    shutil.which("tippecanoe") is None, reason="tippecanoe not installed"
)
class TestArchiveBuild:
    def test_root_readme_points_at_every_collection(
        self, fixture_data_dir, fixture_columns
    ):
        build(fixture_data_dir)
        for tree in ("", "en/"):
            readme = (fixture_data_dir / tree / "README.md").read_text()
            for target in (
                "./indirizzi/",
                "./indirizzi-h3/",
                "./rilasci/",
                "./stradario/",
            ):
                assert target in readme, f"{tree}README.md does not link {target}"

    def test_writes_the_archive_in_both_trees(self, fixture_data_dir, fixture_columns):
        build(fixture_data_dir)
        for tree in ("", "en/"):
            for relative in [
                "rilasci/collection.json",
                "rilasci/README.md",
                "rilasci/AGENTS.md",
                "rilasci/2026-08-03/2026-08-03.json",
                "rilasci/2026-09-15/2026-09-15.json",
            ]:
                assert (fixture_data_dir / tree / relative).exists(), tree + relative

    def test_readme_lists_every_release_with_its_origin(
        self, fixture_data_dir, fixture_columns
    ):
        build(fixture_data_dir)
        readme = (fixture_data_dir / "rilasci" / "README.md").read_text()
        assert "2026-08-03" in readme and "2026-09-15" in readme
        assert "ricostruito" in readme.lower() and "originale" in readme.lower()
        assert "$" not in readme, "an unsubstituted placeholder reached the output"
        english = (fixture_data_dir / "en" / "rilasci" / "README.md").read_text()
        assert "reconstructed" in english and "original" in english
        assert "$" not in english

    def test_relative_links_of_items_resolve(self, fixture_data_dir, fixture_columns):
        import json

        build(fixture_data_dir)
        item_paths = sorted(fixture_data_dir.rglob("rilasci/*/*.json"))
        assert len(item_paths) == 4, "two releases in two trees"
        for item_path in item_paths:
            item = json.loads(item_path.read_text())
            assert item["geometry"] is None and "bbox" not in item
            for link in item["links"]:
                if link["href"].startswith("http"):
                    continue
                target = (item_path.parent / link["href"]).resolve()
                assert target.exists(), f"{item_path} {link['rel']} -> {link['href']}"


@pytest.mark.skipif(
    shutil.which("tippecanoe") is None, reason="tippecanoe not installed"
)
class TestStradarioBuild:
    def test_writes_the_stradario_in_both_trees(
        self, fixture_data_dir, fixture_columns
    ):
        build(fixture_data_dir)
        for tree in ("", "en/"):
            for relative in [
                "stradario/collection.json",
                "stradario/README.md",
                "stradario/AGENTS.md",
                "stradario/2025-01-28/2025-01-28.json",
                "stradario/2026-09-15/2026-09-15.json",
            ]:
                assert (fixture_data_dir / tree / relative).exists(), tree + relative
        assert not list(fixture_data_dir.rglob("stradario/**/*.parquet"))
        assert not list(fixture_data_dir.rglob("stradario/**/*.zip"))

    def test_root_links_the_stradario_in_both_trees(self):
        for lang in ("it", "en"):
            root = build_root("2026-09-15T00:00:00Z", lang=lang)
            children = {c["href"]: c for c in links_by_rel(root, "child")}
            link = children["./stradario/collection.json"]
            assert link["title"] == build_catalog.TEXTS[lang]["stradario_title"]

    def test_stradario_readme_gives_the_derivation_query(
        self, fixture_data_dir, fixture_columns
    ):
        build(fixture_data_dir)
        italian = (fixture_data_dir / "stradario" / "README.md").read_text()
        english = (fixture_data_dir / "en" / "stradario" / "README.md").read_text()
        for readme in (italian, english):
            assert "count(*)::VARCHAR AS TOTALE_ACCESSI" in readme
            assert f"{PUBLIC_BASE}/rilasci/" in readme
            assert "2026-09-15" in readme
            assert "third-party" in readme or "terza parte" in readme
            assert "$" not in readme, "a placeholder reached the output"
            assert "| `TOTALE_ACCESSI` |" in readme
        assert "15 settembre 2026" in italian and "persa" in italian
        assert "15 September 2026" in english and "lost" in english
        assert "originale" in italian and "original" in english
        for italian_word in ("rilascio", "strade", "Licenza"):
            assert italian_word not in english

    def test_stradario_agents_file_states_the_modelling(
        self, fixture_data_dir, fixture_columns
    ):
        build(fixture_data_dir)
        for tree in ("", "en/"):
            text = (fixture_data_dir / tree / "stradario" / "AGENTS.md").read_text()
            assert "v0.3.0" in text and "source" in text
            assert "$" not in text

    def test_relative_links_of_stradario_items_resolve(
        self, fixture_data_dir, fixture_columns
    ):
        import json

        build(fixture_data_dir)
        item_paths = sorted(fixture_data_dir.rglob("stradario/*/*.json"))
        assert len(item_paths) == 4, "two releases in two trees"
        for item_path in item_paths:
            item = json.loads(item_path.read_text())
            assert item["geometry"] is None and "bbox" not in item
            for link in item["links"]:
                if link["href"].startswith("http"):
                    continue
                target = (item_path.parent / link["href"]).resolve()
                assert target.exists(), f"{item_path} {link['rel']} -> {link['href']}"

    def test_a_missing_stradario_index_stops_the_build(
        self, fixture_data_dir, fixture_columns
    ):
        (fixture_data_dir / "stradario" / "releases.json").unlink()
        with pytest.raises(SystemExit, match="stradario"):
            build(fixture_data_dir)

    def test_an_empty_stradario_index_stops_the_build(
        self, fixture_data_dir, fixture_columns
    ):
        write_releases(fixture_data_dir / "stradario" / "releases.json", [])
        with pytest.raises(SystemExit, match="stradario"):
            build(fixture_data_dir)


class TestStradarioDescription:
    def test_does_not_promise_a_zip_or_every_release(self):
        english = build_stradario(fake_facts(), lang="en")["description"]
        italian = build_stradario(fake_facts())["description"]

        assert "all of them are kept" not in english
        assert "each as the **ZIP archive**" not in english
        assert "the releases listed, not every month" in english
        assert "serve solo l'ultimo rilascio" in italian
        assert "restano tutti" not in italian
        assert "i rilasci elencati e non tutti i mesi" in italian
        assert "$" not in english and "$" not in italian

    def test_lossless_covers_the_portal_releases_not_the_third_party_one(self):
        english = build_stradario(fake_facts(), lang="en")["description"]
        italian = build_stradario(fake_facts())["description"]
        portal_en = english.split("downloaded from the portal")[1].split(".")[0]
        portal_it = italian.split("scaricato dal portale")[1].split(".")[0]
        assert "ZIP" in portal_en and "lossless" in portal_en
        assert "ZIP" in portal_it and "senza perdita" in portal_it
        assert "ondata/archivio_anncsu" in english
        assert "cannot be called lossless" in english
        assert "non si può dire che siano senza perdita" in italian


THIRD_PARTY = frozenset({"third-party"})


class TestStradarioIndex:
    def test_origins(self):
        assert STRADARIO_ORIGINS == ("original", "third-party")

    def test_third_party_without_zip_is_accepted(self, tmp_path):
        path = tmp_path / "releases.json"
        write_releases(path, fake_stradario())

        releases = load_releases(
            path, origins=STRADARIO_ORIGINS, zip_optional=THIRD_PARTY
        )

        assert [r["date"] for r in releases] == ["2025-01-28", "2026-09-15"]
        assert releases[0]["zip"] is None

    def test_original_without_zip_is_rejected(self, tmp_path):
        bad = fake_stradario()[1]
        bad["zip"] = None
        path = tmp_path / "releases.json"
        write_releases(path, [bad])

        with pytest.raises(SystemExit, match="zip"):
            load_releases(path, origins=STRADARIO_ORIGINS, zip_optional=THIRD_PARTY)

    def test_third_party_is_not_a_civici_origin(self, tmp_path):
        path = tmp_path / "releases.json"
        write_releases(path, [fake_stradario()[0]])

        with pytest.raises(SystemExit, match="origin"):
            load_releases(path)


class TestStradarioTableColumns:
    def test_lists_the_nine_columns_as_varchar_in_both_languages(self):
        italian = stradario_table_columns(COLUMNS_YAML)
        english = stradario_table_columns(COLUMNS_YAML, lang="en")

        assert [c["name"] for c in italian] == STRAD_COLUMNS
        assert len(italian) == 9
        assert {c["type"] for c in italian} == {"varchar"}
        by_name = {c["name"]: c["description"] for c in english}
        assert by_name["TOTALE_ACCESSI"].strip()
        assert (
            by_name["TOTALE_ACCESSI"]
            != {c["name"]: c["description"] for c in italian}["TOTALE_ACCESSI"]
        )


class TestBuildStradario:
    def test_is_tabular(self):
        collection = build_stradario(fake_facts())
        assert collection["id"] == "stradario"
        assert "table:primary_geometry" not in collection
        names = {c["name"].lower() for c in collection["table:columns"]}
        assert "geometry" not in names and "geom" not in names
        assert collection["assets"] == {}
        assert collection["extent"]["spatial"]["bbox"] == [
            [6.7003, 35.5017, 18.66, 47.0805]
        ]
        assert collection["extent"]["temporal"]["interval"] == [
            ["2025-01-28T00:00:00Z", None]
        ]

    def test_updated_comes_from_the_stradario_index(self):
        collection = build_stradario(fake_facts())
        assert collection["updated"] == "2026-11-24T08:00:00Z"
        assert collection["updated"] != fake_facts()["updated"]

    def test_links_every_release_and_the_latest(self):
        collection = build_stradario(fake_facts())
        items = links_by_rel(collection, "item")
        assert [l["href"] for l in items] == [
            "./2025-01-28/2025-01-28.json",
            "./2026-09-15/2026-09-15.json",
        ]
        assert all(
            l["title"].strip() and l["type"] == "application/geo+json" for l in items
        )
        assert links_by_rel(collection, "latest-version")[0]["href"] == (
            "./2026-09-15/2026-09-15.json"
        )
        alternate = [
            l for l in links_by_rel(collection, "alternate") if l.get("hreflang")
        ]
        assert [l["href"] for l in alternate] == ["../en/stradario/collection.json"]

    def test_has_the_common_mirror_and_documentation_links(self):
        collection = build_stradario(fake_facts())
        assert collection["license"] == "CC-BY-4.0"
        assert collection["providers"][-1]["roles"] == ["host"]
        assert links_by_rel(collection, "via")[0]["type"] == "text/html"
        assert {"stradario", "strade", "storico"} <= set(collection["keywords"])

    def test_description_states_the_caveats(self):
        description = build_stradario(fake_facts())["description"]
        assert "TOTALE_ACCESSI" in description
        assert "rilasci" in description

    def test_english_collection(self):
        collection = build_stradario(fake_facts(), lang="en")
        assert collection["language"]["code"] == "en"
        assert collection["table:columns"][0]["description"] == "x en"
        assert "street register" in collection["keywords"]
        assert "TOTALE_ACCESSI" in collection["description"]
        assert "portale" not in collection["description"].lower()
        assert links_by_rel(collection, "alternate")[0]["hreflang"] == "it"
        assert links_by_rel(collection, "item")[0]["title"].startswith(
            "Street register of"
        )


class TestBuildStradarioItem:
    def item(self, index, lang="it"):
        releases = fake_stradario()
        return build_stradario_item(releases[index], releases, fake_facts(), lang)

    def test_assets_point_at_r2_under_stradario(self):
        item = self.item(1)
        assert item["collection"] == "stradario"
        assert item["id"] == item["properties"]["version"] == "2026-09-15"
        assert item["geometry"] is None and "bbox" not in item
        assert item["properties"]["datetime"] == "2026-09-15T00:00:00Z"
        assert item["properties"]["table:row_count"] == 1_057_710
        data, source = item["assets"]["data"], item["assets"]["source"]
        assert data["href"] == (
            f"{PUBLIC_BASE}/stradario/2026-09-15/STRAD_ITA_20260915.parquet"
        )
        assert data["type"] == "application/vnd.apache.parquet"
        assert data["roles"] == ["data"]
        assert data["file:checksum"] == "1220" + "1" * 64
        assert data["file:size"] == 31_000_000
        assert source["href"] == (
            f"{PUBLIC_BASE}/stradario/2026-09-15/stradarioItalia_20260915.zip"
        )
        assert source["type"] == "application/zip"
        assert source["roles"] == ["source"]
        assert source["file:checksum"] == "1220" + "f" * 64

    def test_third_party_item_has_no_source_asset(self):
        item = self.item(0)
        assert list(item["assets"]) == ["data"]
        assert "ondata/archivio_anncsu" in item["properties"]["description"]
        assert "28 gennaio 2025" in item["properties"]["description"]

    def test_only_the_original_data_asset_claims_to_be_lossless(self):
        for lang, claim in (("it", "senza perdita"), ("en", "lossless")):
            third_party = self.item(0, lang)["assets"]["data"]
            original = self.item(1, lang)["assets"]["data"]
            for key in ("title", "description"):
                assert claim not in third_party[key].lower()
            assert claim in original["title"].lower()
            assert claim in original["description"].lower()
            assert "ondata/archivio_anncsu" in third_party["title"]
            assert "BIGINT" in third_party["description"]

    def test_version_chain_and_alternates(self):
        first, last = self.item(0), self.item(1)
        assert links_by_rel(first, "predecessor-version") == []
        assert links_by_rel(first, "successor-version")[0]["href"] == (
            "../2026-09-15/2026-09-15.json"
        )
        assert links_by_rel(last, "predecessor-version")[0]["href"] == (
            "../2025-01-28/2025-01-28.json"
        )
        assert links_by_rel(last, "root")[0]["href"] == "../../catalog.json"
        alternate = links_by_rel(last, "alternate")[0]
        assert alternate["href"] == "../../en/stradario/2026-09-15/2026-09-15.json"
        assert links_by_rel(last, "via") and links_by_rel(last, "license")
        assert VERSION_SCHEMA in last["stac_extensions"]

    def test_related_link_to_the_civici_of_the_same_date(self):
        related = links_by_rel(self.item(1), "related")
        assert related == [
            {
                "rel": "related",
                "href": "../../rilasci/2026-09-15/2026-09-15.json",
                "type": "application/geo+json",
                "title": build_catalog.TEXTS["it"]["related_civici"],
            }
        ]

    def test_no_related_link_when_the_dates_differ(self):
        assert links_by_rel(self.item(0), "related") == []

    def test_every_asset_has_a_title_and_a_description_in_both_languages(self):
        for index in (0, 1):
            italian, english = (
                self.item(index)["assets"],
                self.item(index, "en")["assets"],
            )
            for key in italian:
                for asset in (italian[key], english[key]):
                    assert asset.get("title", "").strip(), key
                    assert asset.get("description", "").strip(), key
                assert italian[key]["description"] != english[key]["description"]

    def test_english_item_is_english(self):
        item = self.item(1, "en")
        assert item["properties"]["language"]["code"] == "en"
        assert item["properties"]["title"] == "Street register of 15 September 2026"
        assert item["properties"]["table:columns"][0]["description"] == "x en"
        assert "street" in item["properties"]["description"]
        assert (
            links_by_rel(item, "related")[0]["title"]
            == (build_catalog.TEXTS["en"]["related_civici"])
        )


class TestReleaseItemLinksTheStradario:
    def test_civici_item_links_the_stradario_of_the_same_date(self):
        releases = fake_releases()
        item = build_release_item(releases[1], releases, fake_facts())
        assert links_by_rel(item, "related") == [
            {
                "rel": "related",
                "href": "../../stradario/2026-09-15/2026-09-15.json",
                "type": "application/geo+json",
                "title": build_catalog.TEXTS["it"]["related_stradario"],
            }
        ]

    def test_no_link_when_the_stradario_has_no_such_date(self):
        releases = fake_releases()
        item = build_release_item(releases[0], releases, fake_facts())
        assert links_by_rel(item, "related") == []

    def test_no_link_when_there_is_no_stradario(self):
        releases = fake_releases()
        facts = fake_facts()
        del facts["stradario"]
        item = build_release_item(releases[1], releases, facts)
        assert links_by_rel(item, "related") == []


# --- the geocoding index: the gazetteer and the address index ---------------

ADDRESS_INDEX_DRAFT = (
    Path(__file__).resolve().parent.parent
    / "geocoding"
    / "address-index"
    / "v0.1.0"
    / "schema.json"
)


def write_index_json(path, document):
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


class TestLoadGeocodingIndex:
    def test_reads_the_release_and_the_files(self, tmp_path):
        path = tmp_path / "index.json"
        write_index_json(path, fake_address_index())

        assert load_geocoding_index(path, ("vie", "civici")) == fake_address_index()

    def test_a_missing_index_leaves_the_collection_out_and_says_so(
        self, tmp_path, capsys
    ):
        assert load_geocoding_index(tmp_path / "index.json", ("comuni",)) is None
        assert "index.json" in capsys.readouterr().out

    def test_a_missing_file_stops_the_build(self, tmp_path):
        document = fake_address_index()
        del document["files"]["civici"]
        path = tmp_path / "index.json"
        write_index_json(path, document)

        with pytest.raises(SystemExit, match="civici"):
            load_geocoding_index(path, ("vie", "civici"))

    @pytest.mark.parametrize(
        "key",
        ["href", "size", "checksum", "rows", "row_groups", "row_group_rows"],
    )
    def test_a_file_without_one_of_its_facts_stops_the_build(self, tmp_path, key):
        document = fake_gazetteer_index()
        del document["files"]["comuni"][key]
        path = tmp_path / "index.json"
        write_index_json(path, document)

        with pytest.raises(SystemExit, match=key):
            load_geocoding_index(path, ("comuni",))

    def test_a_file_of_another_release_stops_the_build(self, tmp_path):
        # Mixing two builds is what the per-release folders exist to prevent.
        document = fake_gazetteer_index()
        document["files"]["comuni"]["href"] = "./2026-08-03/comuni.parquet"
        path = tmp_path / "index.json"
        write_index_json(path, document)

        with pytest.raises(SystemExit, match="2026-09-15"):
            load_geocoding_index(path, ("comuni",))

    def test_a_checksum_that_is_not_a_sha256_multihash_stops_the_build(self, tmp_path):
        document = fake_gazetteer_index()
        document["files"]["comuni"]["checksum"] = "2" * 64
        path = tmp_path / "index.json"
        write_index_json(path, document)

        with pytest.raises(SystemExit, match="multihash"):
            load_geocoding_index(path, ("comuni",))

    def test_reads_what_build_geocoding_index_writes(self, tmp_path):
        """The interface between the two scripts, pinned from both ends."""
        parquet = tmp_path / "gazetteer" / "2026-09-15" / "comuni.parquet"
        parquet.parent.mkdir(parents=True)
        write_parquet(parquet, "'roma' AS name_norm")
        facts = {
            "path": str(parquet),
            "rows": 1,
            "row_groups": 1,
            "row_group_rows": 4096,
            "footer_metadata_bytes": 300,
            "size": parquet.stat().st_size,
        }
        build_geocoding_index.write_index(
            tmp_path / "gazetteer", "2026-09-15", {"comuni": facts}
        )

        loaded = load_geocoding_index(
            tmp_path / "gazetteer" / "index.json", ("comuni",)
        )

        entry = loaded["files"]["comuni"]
        assert loaded["release"] == "2026-09-15"
        assert entry["href"] == "./2026-09-15/comuni.parquet"
        assert entry["size"] == parquet.stat().st_size
        assert entry["checksum"] == multihash_sha256(parquet)


class TestGeocodingColumns:
    """The column docs cannot be checked against the Parquet in CI, where the
    files are absent, so they are checked against the builder's schemas."""

    @pytest.mark.parametrize(
        "section, schema",
        [
            ("gazetteer", "GAZETTEER_SCHEMA"),
            ("streets", "STREETS_SCHEMA"),
            ("access_points", "ACCESS_POINTS_SCHEMA"),
        ],
    )
    def test_documents_every_column_of_the_builder_with_its_type(
        self, tmp_path, section, schema
    ):
        import pyarrow.parquet as pq

        path = tmp_path / f"{section}.parquet"
        pq.write_table(getattr(build_geocoding_index, schema).empty_table(), path)

        documented = geocoding_table_columns(GEOCODING_COLUMNS_FILE, section)

        assert [(c["name"], c["type"]) for c in documented] == [
            (name, stac_type(found)) for name, found in read_parquet_columns(path)
        ]

    @pytest.mark.parametrize("section", ["gazetteer", "streets", "access_points"])
    def test_every_column_is_described_in_both_languages(self, section):
        italian = geocoding_table_columns(GEOCODING_COLUMNS_FILE, section)
        english = geocoding_table_columns(GEOCODING_COLUMNS_FILE, section, lang="en")

        for it, en in zip(italian, english, strict=True):
            assert it["name"] == en["name"]
            assert it["description"].strip() and en["description"].strip()
            assert it["description"] != en["description"], it["name"]

    def test_fails_when_the_english_description_is_missing(self, tmp_path):
        path = tmp_path / "geocoding_columns.yaml"
        path.write_text(
            "gazetteer:\n  name:\n    type: VARCHAR\n    description: nome\n",
            encoding="utf-8",
        )

        with pytest.raises(SystemExit, match="description_en"):
            geocoding_table_columns(path, "gazetteer")

    def test_the_sorts_match_the_builder(self):
        assert STREETS_SORT == build_geocoding_index.STREETS_SORT
        assert ACCESS_POINTS_SORT == build_geocoding_index.ACCESS_POINTS_SORT
        assert build_geocoding_index.GAZETTEER_SORT[0] == "name_norm"


class TestBuildGazetteer:
    def test_gazetteer_collection_declares_the_extension(self):
        collection = build_gazetteer(fake_facts())

        assert GAZETTEER_EXTENSION == (
            "https://cholmes.github.io/stac-gazetteer/gazetteer/v1.0.0/schema.json"
        )
        assert collection["id"] == "gazetteer"
        assert GAZETTEER_EXTENSION in collection["stac_extensions"]
        assert collection["gazetteer:levels"] == [3]
        assert collection["gazetteer:normalization"] == "nfd-strip-marks-lower/1"
        assert collection["gazetteer:sort"] == "name_norm"

    @pytest.mark.parametrize("lang", ["it", "en"])
    def test_gazetteer_index_asset(self, lang):
        collection = build_gazetteer(fake_facts(), lang=lang)

        [asset] = [
            a for a in collection["assets"].values() if "gazetteer-index" in a["roles"]
        ]
        assert asset["roles"] == ["data", "gazetteer-index"]
        assert asset["type"] == "application/vnd.apache.parquet"
        assert asset["gazetteer:row_groups"] == 2
        assert asset["gazetteer:row_group_rows"] == 4096
        assert asset["gazetteer:footer_metadata_bytes"] == 5_277
        assert asset["file:size"] == 349_472
        assert asset["file:checksum"] == "1220" + "2" * 64
        assert asset["table:row_count"] == 5_821
        assert asset["table:columns"] == [
            {"name": "name", "type": "varchar", "description": f"name {lang}"},
            {
                "name": "feature_id",
                "type": "varchar",
                "description": f"feature_id {lang}",
            },
        ]
        # The Parquet lives in the source tree; the English tree points back.
        assert (
            asset["href"]
            == {
                "it": "./2026-09-15/comuni.parquet",
                "en": "../../gazetteer/2026-09-15/comuni.parquet",
            }[lang]
        )

    def test_is_tabular_and_versioned_by_its_release(self):
        collection = build_gazetteer(fake_facts())

        assert "table:primary_geometry" not in collection
        assert not any("thumbnail" in a["roles"] for a in collection["assets"].values())
        assert collection["version"] == "2026-09-15"
        assert VERSION_SCHEMA in collection["stac_extensions"]
        assert collection["updated"] == "2026-09-15T00:00:00Z"
        assert collection["extent"] == {
            "spatial": {"bbox": [[6.7003, 35.5017, 18.66, 47.0805]]},
            "temporal": {"interval": [["2026-09-15T00:00:00Z", None]]},
        }

    def test_links_the_address_index_as_related(self):
        related = links_by_rel(build_gazetteer(fake_facts()), "related")
        assert [l["href"] for l in related] == ["../indirizzi-index/collection.json"]
        assert related[0]["type"] == "application/json"
        assert related[0]["title"] == build_catalog.TEXTS["it"]["related_address_index"]

    def test_no_related_link_without_the_address_index(self):
        facts = fake_facts()
        facts["indirizzi-index"] = None
        assert links_by_rel(build_gazetteer(facts), "related") == []


class TestBuildAddressIndex:
    def test_address_index_collection_declares_the_draft_extension(self):
        collection = build_indirizzi_index(fake_facts())

        assert ADDRESS_INDEX_EXTENSION == (
            "https://raw.githubusercontent.com/anncsu-open/anncsu-viewer/main/"
            "geocoding/address-index/v0.1.0/schema.json"
        )
        assert collection["id"] == "indirizzi-index"
        assert ADDRESS_INDEX_EXTENSION in collection["stac_extensions"]
        assert FILE_SCHEMA in collection["stac_extensions"]
        assert TABLE_SCHEMA in collection["stac_extensions"]
        assert collection["address_index:normalization"] == "anncsu-odonimo/1"
        assert collection["address_index:place_column"] == "codice_istat"
        # The gazetteer extension stays off: geocoder-core takes any
        # collection declaring a /gazetteer/ schema for a gazetteer.
        assert not any("/gazetteer/" in url for url in collection["stac_extensions"])

    @pytest.mark.parametrize("lang", ["it", "en"])
    def test_address_index_assets(self, lang):
        assets = build_indirizzi_index(fake_facts(), lang=lang)["assets"]
        streets, points = assets["streets"], assets["access-points"]
        prefix = {"it": "./", "en": "../../indirizzi-index/"}[lang]

        assert streets["roles"] == ["data", "address-streets"]
        assert streets["href"] == f"{prefix}2026-09-15/vie.parquet"
        assert streets["address_index:sort"] == [
            "codice_istat",
            "name_norm",
            "street_id",
        ]
        assert streets["address_index:row_groups"] == 193
        assert streets["address_index:row_group_rows"] == 4096
        assert streets["address_index:footer_metadata_bytes"] == 332_699
        assert streets["file:size"] == 42_730_958
        assert streets["file:checksum"] == "1220" + "3" * 64
        assert streets["table:row_count"] == 786_969
        assert [c["name"] for c in streets["table:columns"]] == [
            "codice_istat",
            "name_norm",
        ]

        assert points["roles"] == ["data", "address-points"]
        assert points["href"] == f"{prefix}2026-09-15/civici.parquet"
        assert points["address_index:sort"] == [
            "codice_istat",
            "street_id",
            "number",
            "suffix",
            "specificita",
            "id",
        ]
        assert points["address_index:row_groups"] == 2531
        assert points["address_index:row_group_rows"] == 8192
        assert points["address_index:footer_metadata_bytes"] == 3_061_756
        assert points["file:size"] == 420_591_389
        assert points["file:checksum"] == "1220" + "4" * 64
        assert points["table:row_count"] == 20_728_959
        assert points["table:columns"][1]["description"] == f"street_id {lang}"
        for asset in (streets, points):
            assert asset["type"] == "application/vnd.apache.parquet"

    def test_links_the_gazetteer_as_related(self):
        related = links_by_rel(build_indirizzi_index(fake_facts()), "related")
        assert related == [
            {
                "rel": "related",
                "href": "../gazetteer/collection.json",
                "type": "application/json",
                "title": build_catalog.TEXTS["it"]["related_gazetteer"],
            }
        ]

    def test_no_related_link_without_the_gazetteer(self):
        facts = fake_facts()
        facts["gazetteer"] = None
        assert links_by_rel(build_indirizzi_index(facts), "related") == []

    @pytest.mark.parametrize("lang", ["it", "en"])
    def test_validates_against_the_draft_extension_schema(self, lang):
        import json

        import jsonschema

        schema = json.loads(ADDRESS_INDEX_DRAFT.read_text(encoding="utf-8"))
        assert schema["$id"] == ADDRESS_INDEX_EXTENSION
        collection = build_indirizzi_index(fake_facts(), lang=lang)

        errors = list(jsonschema.Draft7Validator(schema).iter_errors(collection))

        assert errors == [], [e.message for e in errors]


GEOCODING_BUILDERS = [build_gazetteer, build_indirizzi_index]


class TestGeocodingCollections:
    @pytest.mark.parametrize("builder", GEOCODING_BUILDERS)
    @pytest.mark.parametrize("lang", ["it", "en"])
    def test_has_the_structural_mirror_and_documentation_links(self, builder, lang):
        collection = builder(fake_facts(), lang=lang)
        cid = collection["id"]

        assert collection["language"]["code"] == lang
        assert collection["license"] == "CC-BY-4.0"
        assert collection["providers"] == providers()
        assert links_by_rel(collection, "root")[0]["href"] == "../catalog.json"
        assert links_by_rel(collection, "parent")[0]["href"] == "../catalog.json"
        assert links_by_rel(collection, "agents")[0]["href"] == "./AGENTS.md"
        assert links_by_rel(collection, "describedby")[0]["href"] == "./README.md"
        assert links_by_rel(collection, "via")[0]["href"] == SOURCE_PORTAL
        assert links_by_rel(collection, "license")
        alternate = [
            l for l in links_by_rel(collection, "alternate") if l.get("hreflang")
        ]
        assert [l["href"] for l in alternate] == [
            {
                "it": f"../en/{cid}/collection.json",
                "en": f"../../{cid}/collection.json",
            }[lang]
        ]

    @pytest.mark.parametrize("builder", GEOCODING_BUILDERS)
    def test_derives_from_the_release_it_was_built_from(self, builder):
        derived = links_by_rel(builder(fake_facts()), "derived_from")
        assert [l["href"] for l in derived] == ["../rilasci/2026-09-15/2026-09-15.json"]

    @pytest.mark.parametrize("builder", GEOCODING_BUILDERS)
    def test_no_derived_from_link_for_a_release_the_archive_lacks(self, builder):
        facts = fake_facts()
        facts["releases"] = facts["releases"][:1]
        assert links_by_rel(builder(facts), "derived_from") == []

    @pytest.mark.parametrize("builder", GEOCODING_BUILDERS)
    def test_every_asset_has_a_title_and_a_description_in_both_languages(self, builder):
        italian = builder(fake_facts())["assets"]
        english = builder(fake_facts(), lang="en")["assets"]
        assert italian.keys() == english.keys()
        for key in italian:
            for asset in (italian[key], english[key]):
                assert asset.get("title", "").strip(), key
                assert asset.get("description", "").strip(), key
            assert italian[key]["description"] != english[key]["description"], key

    @pytest.mark.parametrize("builder", GEOCODING_BUILDERS)
    @pytest.mark.parametrize("lang", ["it", "en"])
    def test_description_names_the_release_and_leaves_no_placeholder(
        self, builder, lang
    ):
        description = builder(fake_facts(), lang=lang)["description"]
        assert "$" not in description
        assert {"it": "15 settembre 2026", "en": "15 September 2026"}[lang] in (
            description
        )
        assert "`feature_id`" in description

    def test_the_english_collections_are_english(self):
        for builder in GEOCODING_BUILDERS:
            italian = builder(fake_facts())
            english = builder(fake_facts(), lang="en")
            assert english["title"] != italian["title"]
            assert english["keywords"] != italian["keywords"]
            for word in ("rilascio", "strade", " della ", " dei "):
                assert word not in english["description"]


class TestGeocodingFilesTable:
    def test_one_row_per_file_in_italian(self):
        table = geocoding_files_table(build_gazetteer(fake_facts()))
        assert table.splitlines() == [
            "| File | Righe | Gruppi di righe | Dimensione |",
            "|---|---|---|---|",
            (
                "| [`comuni.parquet`](./2026-09-15/comuni.parquet) | 5.821 | "
                "2 da 4.096 righe | 0,3 MB |"
            ),
        ]

    def test_english_rows_link_the_source_tree(self):
        table = geocoding_files_table(
            build_indirizzi_index(fake_facts(), lang="en"), lang="en"
        )
        lines = table.splitlines()
        assert lines[0] == "| File | Rows | Row groups | Size |"
        assert lines[2] == (
            "| [`vie.parquet`](../../indirizzi-index/2026-09-15/vie.parquet) | "
            "786,969 | 193 × 4,096 rows | 42.7 MB |"
        )
        assert lines[3].startswith("| [`civici.parquet`]")
        assert "2,531 × 8,192 rows" in lines[3]


class TestRootLinksTheGeocodingIndex:
    @pytest.mark.parametrize("lang", ["it", "en"])
    def test_root_links_the_two_collections(self, lang):
        root = build_root(
            "2026-09-15T00:00:00Z",
            lang=lang,
            geocoding=["gazetteer", "indirizzi-index"],
        )

        children = {c["href"]: c for c in links_by_rel(root, "child")}
        texts = build_catalog.TEXTS[lang]
        assert len(children) == 6
        assert (
            children["./gazetteer/collection.json"]["title"]
            == (texts["gazetteer_title"])
        )
        assert (
            children["./indirizzi-index/collection.json"]["title"]
            == (texts["indirizzi_index_title"])
        )
        description = root["description"]
        assert description.count("\n- ") == 6
        assert "`gazetteer`" in description and "`indirizzi-index`" in description
        assert {"it": "sei collection", "en": "six collections"}[lang] in description
        assert "$" not in description

    @pytest.mark.parametrize("lang", ["it", "en"])
    def test_root_leaves_out_a_collection_without_its_index(self, lang):
        root = build_root("2026-09-15T00:00:00Z", lang=lang, geocoding=["gazetteer"])

        hrefs = {c["href"] for c in links_by_rel(root, "child")}
        assert "./gazetteer/collection.json" in hrefs
        assert "./indirizzi-index/collection.json" not in hrefs
        assert root["description"].count("\n- ") == 5
        assert {"it": "cinque collection", "en": "five collections"}[lang] in (
            root["description"]
        )

    def test_without_geocoding_the_root_is_unchanged(self):
        root = build_root("2026-09-15T00:00:00Z")
        assert "quattro collection" in root["description"]
        assert len(links_by_rel(root, "child")) == 4


@pytest.mark.skipif(
    shutil.which("tippecanoe") is None, reason="tippecanoe not installed"
)
class TestGeocodingBuild:
    COLLECTIONS = ("gazetteer", "indirizzi-index")

    def test_writes_both_collections_in_both_trees(
        self, fixture_geocoding, fixture_columns
    ):
        build(fixture_geocoding)
        for tree in ("", "en/"):
            for cid in self.COLLECTIONS:
                for name in ("collection.json", "README.md", "AGENTS.md"):
                    path = fixture_geocoding / tree / cid / name
                    assert path.exists(), f"{tree}{cid}/{name}"
        assert not list((fixture_geocoding / "en").rglob("*.parquet")), (
            "the files stay in the source tree; the translation only points at them"
        )

    def test_assets_resolve_with_matching_sizes_and_checksums(
        self, fixture_geocoding, fixture_columns
    ):
        import json

        build(fixture_geocoding)
        for tree in ("", "en/"):
            for cid in self.COLLECTIONS:
                base = fixture_geocoding / tree / cid
                collection = json.loads((base / "collection.json").read_text())
                for key, asset in collection["assets"].items():
                    target = (base / asset["href"]).resolve()
                    assert target.exists(), f"{tree}{cid}/{key} -> {asset['href']}"
                    assert asset["file:size"] == target.stat().st_size, key
                    assert asset["file:checksum"] == multihash_sha256(target), key

    def test_every_relative_link_resolves(self, fixture_geocoding, fixture_columns):
        import json

        build(fixture_geocoding)
        documents = [
            fixture_geocoding / tree / name
            for tree in ("", "en/")
            for name in (
                "catalog.json",
                "gazetteer/collection.json",
                "indirizzi-index/collection.json",
            )
        ]
        for document_path in documents:
            document = json.loads(document_path.read_text())
            for link in document["links"]:
                if link["href"].startswith("http"):
                    continue
                target = (document_path.parent / link["href"]).resolve()
                assert target.exists(), (
                    f"{document_path} {link['rel']} -> {link['href']}"
                )

    def test_root_readme_and_agents_point_at_the_two_collections(
        self, fixture_geocoding, fixture_columns
    ):
        build(fixture_geocoding)
        for tree in ("", "en/"):
            readme = (fixture_geocoding / tree / "README.md").read_text()
            agents = (fixture_geocoding / tree / "AGENTS.md").read_text()
            for cid in self.COLLECTIONS:
                assert f"(./{cid}/)" in readme, f"{tree}README.md"
                assert f"`{cid}`" in agents, f"{tree}AGENTS.md"
            assert "$" not in readme and "$" not in agents

    def test_collection_docs_explain_the_reading_and_the_join(
        self, fixture_geocoding, fixture_columns
    ):
        build(fixture_geocoding)
        for tree in ("", "en/"):
            gazetteer = fixture_geocoding / tree / "gazetteer"
            index = fixture_geocoding / tree / "indirizzi-index"
            docs = {
                path: path.read_text(encoding="utf-8")
                for path in (
                    gazetteer / "README.md",
                    gazetteer / "AGENTS.md",
                    index / "README.md",
                    index / "AGENTS.md",
                )
            }
            for path, text in docs.items():
                assert "$" not in text, f"placeholder left in {path}"
                assert "feature_id" in text and "codice_istat" in text, path
                assert "v0.3.0" in text or "README" in path.name, path
            readme = docs[gazetteer / "README.md"]
            assert "@cngeo/geocoder-core" in readme
            assert build_catalog.GAZETTEER_SPEC_URL in readme
            assert "nfd-strip-marks-lower/1" in readme
            assert f"{PUBLIC_BASE}/gazetteer/2026-09-15/comuni.parquet" in readme
            assert "| `feature_id` |" in readme
            readme = docs[index / "README.md"]
            assert build_catalog.ADDRESS_INDEX_SPEC_URL in readme
            assert "anncsu-odonimo/1" in readme
            assert f"{PUBLIC_BASE}/indirizzi-index/2026-09-15/vie.parquet" in readme
            assert "| `street_id` |" in readme and "| `lon` |" in readme
            for text in docs.values():
                assert "Agenzia delle Entrate" in text or "Istat" in text

    def test_english_docs_are_english(self, fixture_geocoding, fixture_columns):
        build(fixture_geocoding)
        for cid in self.COLLECTIONS:
            for name in ("README.md", "AGENTS.md"):
                text = (fixture_geocoding / "en" / cid / name).read_text()
                for italian in ("Licenza", "rilascio", " della ", "Come si legge"):
                    assert italian not in text, f"en/{cid}/{name}: {italian}"

    def test_is_byte_identical_on_a_second_run(
        self, fixture_geocoding, fixture_columns
    ):
        build(fixture_geocoding)
        first = generated_files(fixture_geocoding)
        build(fixture_geocoding)
        second = generated_files(fixture_geocoding)
        assert first == second

    def test_a_missing_index_leaves_its_collection_out(
        self, fixture_geocoding, fixture_columns, capsys
    ):
        import json

        (fixture_geocoding / "indirizzi-index" / "index.json").unlink()
        build(fixture_geocoding)

        assert (fixture_geocoding / "gazetteer" / "collection.json").exists()
        assert not (fixture_geocoding / "indirizzi-index" / "collection.json").exists()
        root = json.loads((fixture_geocoding / "catalog.json").read_text())
        hrefs = {l["href"] for l in links_by_rel(root, "child")}
        assert "./gazetteer/collection.json" in hrefs
        assert "./indirizzi-index/collection.json" not in hrefs
        gazetteer = json.loads(
            (fixture_geocoding / "gazetteer" / "collection.json").read_text()
        )
        assert links_by_rel(gazetteer, "related") == []
        assert "indirizzi-index" in capsys.readouterr().out

    def test_without_any_index_the_catalog_has_only_the_four_collections(
        self, fixture_data_dir, fixture_columns
    ):
        build(fixture_data_dir)
        for cid in self.COLLECTIONS:
            assert not (fixture_data_dir / cid).exists(), cid
            assert not (fixture_data_dir / "en" / cid).exists(), cid


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
