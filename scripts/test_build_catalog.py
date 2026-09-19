# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.5.5",
#     "geoparquet-io>=1.5.0",
#     "httpx",
#     "pillow",
#     "pmtiles",
#     "pytest",
#     "pyyaml",
#     "rashid>=0.1.8,<0.2.0",
#     "typer",
# ]
# ///
"""Tests for build_catalog.py, the Portolan catalog generator.

Usage:
    uv run scripts/test_build_catalog.py
"""

import shutil
from pathlib import Path

import pytest

import build_catalog
from build_catalog import (
    PARTITION_SCHEMA,
    PORTOLAN_SCHEMA,
    PUBLIC_BASE,
    VIEWER_URL,
    build,
    build_indirizzi,
    build_indirizzi_h3,
    build_root,
    data_updated,
    dataset_statistics,
    dataset_stats,
    file_facts,
    human_count,
    human_date,
    human_percent,
    load_columns,
    multihash_sha256,
    providers,
    read_parquet_columns,
    render_template,
    render_thumbnail,
    schema_table,
    stac_type,
    statistics_table,
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
    }


def links_by_rel(document, rel):
    return [link for link in document["links"] if link["rel"] == rel]


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

    def test_links_both_collections_with_titles(self):
        children = links_by_rel(build_root("2026-09-15T00:00:00Z"), "child")
        assert {c["href"] for c in children} == {
            "./indirizzi/collection.json",
            "./indirizzi-h3/collection.json",
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

    def test_the_glob_points_at_the_published_tiles(self):
        collection = build_indirizzi_h3(fake_facts())
        assert collection["partition:glob"] == (
            f"{PUBLIC_BASE}/tiles/h3_cell=*/*.parquet"
        )

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
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(build_catalog, "COLUMNS_FILE", path)
    return path


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
        import json
        import subprocess

        build(fixture_data_dir)

        # rashid ships only as a console script: `python -m rashid` fails
        # with "rashid is a package and cannot be directly executed".
        rashid = shutil.which("rashid")
        assert rashid, (
            "rashid is a test dependency; run via `uv run scripts/test_build_catalog.py`"
        )

        result = subprocess.run(
            [rashid, "check", str(fixture_data_dir), "--schema", "--json", "--all"],
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
        assert (
            collection["partition:glob"] == f"{PUBLIC_BASE}/tiles/h3_cell=*/*.parquet"
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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
