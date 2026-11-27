# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb==2.0.0",
#     "pyarrow",
#     "pytest",
# ]
# ///
"""Tests for build_geocoding_index.py, the files the geocoder package reads.

Usage:
    uv run scripts/test_build_geocoding_index.py

Every test builds from a small synthetic addresses file with the real ANNCSU
column names and types, and a synthetic comuni.json.
"""

import hashlib
import json
from pathlib import Path

import duckdb
import pyarrow.parquet as pq
import pytest

from geocoding_normalize import fold_name
from build_geocoding_index import build_access_points, build_gazetteer, build_streets, main

FAR = (9.0, 45.0)  # an out-of-bounds point, far from every comune below

# (CODICE_ISTAT, NOME_COMUNE, PROGRESSIVO_NAZIONALE, ODONIMO, DIZIONE_LINGUA1,
#  PROGRESSIVO_ACCESSO, CIVICO, ESPONENTE, SPECIFICITA, METRICO, lon, lat,
#  out_of_bounds)
ROWS = [
    (
        "057072",
        "VACONE",
        1001,
        "VIA DELLA LIBERTA'",
        None,
        1,
        1,
        None,
        None,
        None,
        12.64,
        42.38,
        False,
    ),
    (
        "057072",
        "VACONE",
        1001,
        "VIA DELLA LIBERTA'",
        None,
        2,
        2,
        None,
        None,
        None,
        12.65,
        42.39,
        False,
    ),
    (
        "057072",
        "VACONE",
        1001,
        "VIA DELLA LIBERTA'",
        None,
        3,
        3,
        "A",
        None,
        None,
        12.65,
        42.39,
        False,
    ),
    (
        "057072",
        "VACONE",
        1001,
        "VIA DELLA LIBERTA'",
        None,
        4,
        3,
        "B",
        None,
        None,
        12.65,
        42.39,
        False,
    ),
    (
        "057072",
        "VACONE",
        1001,
        "VIA DELLA LIBERTA'",
        None,
        5,
        5,
        None,
        None,
        None,
        *FAR,
        True,
    ),
    (
        "057072",
        "VACONE",
        1002,
        "VIA ROMA",
        None,
        6,
        1,
        None,
        None,
        None,
        12.63,
        42.37,
        False,
    ),
    (
        "057072",
        "VACONE",
        1002,
        "VIA ROMA",
        None,
        7,
        1,
        None,
        None,
        None,
        12.63,
        42.37,
        False,
    ),
    (
        "057072",
        "VACONE",
        1002,
        "VIA ROMA",
        None,
        8,
        10,
        None,
        "R",
        None,
        12.63,
        42.37,
        False,
    ),
    (
        "057072",
        "VACONE",
        1003,
        "VIA ROMA",
        None,
        9,
        2,
        None,
        None,
        None,
        12.66,
        42.40,
        False,
    ),
    (
        "057072",
        "VACONE",
        1003,
        "VIA ROMA",
        None,
        10,
        40,
        None,
        None,
        None,
        12.66,
        42.40,
        False,
    ),
    (
        "057072",
        "VACONE",
        1004,
        "STRADA PROVINCIALE 34",
        None,
        11,
        None,
        None,
        None,
        "12",
        12.62,
        42.36,
        False,
    ),
    (
        "016070",
        "CASTRO",
        2001,
        "VIA MARCONI",
        None,
        12,
        1,
        None,
        None,
        None,
        10.07,
        45.80,
        False,
    ),
    (
        "075096",
        "CASTRO",
        3001,
        "VIA MARCONI",
        None,
        13,
        5,
        None,
        None,
        None,
        18.42,
        40.00,
        False,
    ),
    (
        "021001",
        "ALDINO",
        4001,
        "VIA CHIESA",
        "Kirchweg",
        14,
        1,
        None,
        None,
        None,
        11.35,
        46.37,
        False,
    ),
    (
        "021001",
        "ALDINO",
        4002,
        "VIA ROMA",
        "Via Roma",
        15,
        1,
        None,
        None,
        None,
        11.35,
        46.37,
        False,
    ),
    (
        "001226",
        "SANT'AMBROGIO DI TORINO",
        5001,
        "VIA ROMA",
        None,
        16,
        1,
        None,
        None,
        None,
        7.36,
        45.10,
        False,
    ),
    (
        "001999",
        "TUTTO FUORI",
        6001,
        "VIA LONTANA",
        None,
        17,
        1,
        None,
        None,
        None,
        *FAR,
        True,
    ),
]

COMUNI = [
    {
        "codice_istat": "001226",
        "nome_comune": "Sant'Ambrogio di Torino",
        "codice_provincia": "201",
        "provincia": "Torino",
        "sigla_provincia": "TO",
        "altra_lingua": None,
        "lingua": None,
    },
    {
        "codice_istat": "001999",
        "nome_comune": "Tutto Fuori",
        "codice_provincia": "201",
        "provincia": "Torino",
        "sigla_provincia": "TO",
        "altra_lingua": None,
        "lingua": None,
    },
    {
        "codice_istat": "016070",
        "nome_comune": "Castro",
        "codice_provincia": "016",
        "provincia": "Bergamo",
        "sigla_provincia": "BG",
        "altra_lingua": None,
        "lingua": None,
    },
    {
        "codice_istat": "021001",
        "nome_comune": "Aldino",
        "codice_provincia": "021",
        "provincia": "Bolzano/Bozen",
        "sigla_provincia": "BZ",
        "altra_lingua": "Aldein",
        "lingua": "deu",
    },
    {
        "codice_istat": "057001",
        "nome_comune": "Accumoli",
        "codice_provincia": "057",
        "provincia": "Rieti",
        "sigla_provincia": "RI",
        "altra_lingua": None,
        "lingua": None,
    },
    {
        "codice_istat": "057072",
        "nome_comune": "Vacone",
        "codice_provincia": "057",
        "provincia": "Rieti",
        "sigla_provincia": "RI",
        "altra_lingua": None,
        "lingua": None,
    },
    {
        "codice_istat": "075096",
        "nome_comune": "Castro",
        "codice_provincia": "075",
        "provincia": "Lecce",
        "sigla_provincia": "LE",
        "altra_lingua": None,
        "lingua": None,
    },
]


def write_addresses(path: Path, rows=ROWS) -> Path:
    con = duckdb.connect()
    con.execute(
        """CREATE TABLE a (CODICE_ISTAT VARCHAR, NOME_COMUNE VARCHAR,
        PROGRESSIVO_NAZIONALE BIGINT, ODONIMO VARCHAR, DIZIONE_LINGUA1 VARCHAR,
        PROGRESSIVO_ACCESSO BIGINT, CIVICO BIGINT, ESPONENTE VARCHAR,
        SPECIFICITA VARCHAR, METRICO VARCHAR, longitude DOUBLE, latitude DOUBLE,
        out_of_bounds BOOLEAN)"""
    )
    con.executemany(
        "INSERT INTO a VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
    )
    # DIZIONE_LINGUA2 exists in the source and is empty on these rows.
    con.execute(
        f"COPY (SELECT *, NULL::VARCHAR AS DIZIONE_LINGUA2 FROM a) TO '{path}' (FORMAT parquet)"
    )
    return path


def write_comuni(path: Path, comuni=COMUNI) -> Path:
    path.write_text(json.dumps(comuni, ensure_ascii=False))
    return path


@pytest.fixture
def gazetteer(tmp_path):
    facts = build_gazetteer(
        write_addresses(tmp_path / "addresses.parquet"),
        write_comuni(tmp_path / "comuni.json"),
        tmp_path / "comuni.parquet",
        row_group_rows=4,
    )
    return facts, pq.read_table(facts["path"]).to_pylist()


def primary(rows):
    return [r for r in rows if r["alt_of"] is None]


def by_id(rows):
    return {r["feature_id"]: r for r in primary(rows)}


class TestGazetteer:
    def test_one_row_per_comune_with_addresses(self, gazetteer):
        _, rows = gazetteer
        assert sorted(by_id(rows)) == [
            "001226",
            "001999",
            "016070",
            "021001",
            "057072",
            "075096",
        ]
        assert by_id(rows)["057072"]["addresses"] == 11

    def test_feature_id_is_the_codice_istat(self, gazetteer):
        _, rows = gazetteer
        vacone = by_id(rows)["057072"]
        assert (vacone["name"], vacone["name_norm"]) == ("Vacone", "vacone")
        assert (vacone["level"], vacone["country"], vacone["country_name"]) == (
            3,
            "ITA",
            "Italia",
        )
        assert (vacone["parent_name"], vacone["parent_id"]) == ("Rieti", "057")

    def test_bbox_leaves_out_of_bounds_points(self, gazetteer):
        _, rows = gazetteer
        assert by_id(rows)["057072"]["bbox"] == {
            "xmin": 12.62,
            "ymin": 42.36,
            "xmax": 12.66,
            "ymax": 42.40,
        }

    def test_bbox_falls_back_when_every_point_is_out_of_bounds(self, gazetteer):
        _, rows = gazetteer
        assert by_id(rows)["001999"]["bbox"] == {
            "xmin": FAR[0],
            "ymin": FAR[1],
            "xmax": FAR[0],
            "ymax": FAR[1],
        }

    def test_two_castro(self, gazetteer):
        _, rows = gazetteer
        castro = [r for r in primary(rows) if r["name_norm"] == "castro"]
        assert [(r["feature_id"], r["parent_name"]) for r in castro] == [
            ("016070", "Bergamo"),
            ("075096", "Lecce"),
        ]

    def test_other_language_name_is_an_alternate_row(self, gazetteer):
        _, rows = gazetteer
        aldein = [r for r in rows if r["name_norm"] == "aldein"]
        assert len(aldein) == 1
        assert (
            aldein[0]["alt_of"],
            aldein[0]["feature_id"],
            aldein[0]["name_lang"],
        ) == (
            "021001",
            "021001",
            "deu",
        )

    def test_apostrophe_name_has_a_spelling_with_a_space(self, gazetteer):
        _, rows = gazetteer
        norms = [r["name_norm"] for r in rows if r["feature_id"] == "001226"]
        assert sorted(norms) == ["sant ambrogio di torino", "sant'ambrogio di torino"]

    def test_every_name_norm_is_the_fold_of_its_name(self, gazetteer):
        # The contract: name_norm comes from name by the declared normalization,
        # on alternate rows too, so the space spelling shows its own name.
        _, rows = gazetteer
        assert [r["name"] for r in rows if r["name_norm"] != fold_name(r["name"])] == []
        spaced = [r for r in rows if r["name_norm"] == "sant ambrogio di torino"]
        assert [(r["name"], r["alt_of"]) for r in spaced] == [("Sant Ambrogio di Torino", "001226")]

    def test_no_alternate_row_that_folds_to_the_primary(self, gazetteer):
        _, rows = gazetteer
        assert len([r for r in rows if r["feature_id"] == "057072"]) == 1

    def test_sorted_and_declared(self, gazetteer):
        facts, rows = gazetteer
        keys = [
            (r["name_norm"].encode(), r["level"], r["country"], r["feature_id"])
            for r in rows
        ]
        assert keys == sorted(keys)
        metadata = pq.ParquetFile(facts["path"]).metadata
        names = [metadata.schema.column(i).name for i in range(metadata.num_columns)]
        sorting = metadata.row_group(0).sorting_columns
        assert [names[s.column_index] for s in sorting] == [
            "name_norm",
            "level",
            "country",
            "feature_id",
        ]
        for g in range(metadata.num_row_groups):
            stats = metadata.row_group(g).column(names.index("name_norm")).statistics
            assert stats is not None and stats.has_min_max

    def test_facts(self, gazetteer):
        facts, rows = gazetteer
        assert facts["rows"] == len(rows) == 8
        assert facts["row_groups"] == 2
        assert facts["row_group_rows"] == 4
        assert facts["footer_metadata_bytes"] > 0
        assert facts["size"] == Path(facts["path"]).stat().st_size

    def test_missing_comune_stops_the_build(self, tmp_path):
        rows = ROWS + [
            (
                "999999",
                "IGNOTO",
                7001,
                "VIA X",
                None,
                99,
                1,
                None,
                None,
                None,
                12.0,
                42.0,
                False,
            )
        ]
        with pytest.raises(ValueError, match="999999"):
            build_gazetteer(
                write_addresses(tmp_path / "addresses.parquet", rows),
                write_comuni(tmp_path / "comuni.json"),
                tmp_path / "comuni.parquet",
            )


@pytest.fixture
def streets(tmp_path):
    facts = build_streets(
        write_addresses(tmp_path / "addresses.parquet"),
        write_comuni(tmp_path / "comuni.json"),
        tmp_path / "vie.parquet",
        row_group_rows=4,
    )
    return facts, pq.read_table(facts["path"]).to_pylist()


@pytest.fixture
def access_points(tmp_path):
    facts = build_access_points(
        write_addresses(tmp_path / "addresses.parquet"),
        tmp_path / "civici.parquet",
        row_group_rows=4,
    )
    return facts, pq.read_table(facts["path"]).to_pylist()


def declared_sort(path):
    metadata = pq.ParquetFile(path).metadata
    names = [metadata.schema.column(i).name for i in range(metadata.num_columns)]
    return names, [names[s.column_index] for s in metadata.row_group(0).sorting_columns]


class TestStreets:
    def test_one_row_per_street_plus_alternates(self, streets):
        _, rows = streets
        primary_ids = sorted(r["street_id"] for r in rows if r["alt_of"] is None)
        assert primary_ids == [1001, 1002, 1003, 1004, 2001, 3001, 4001, 4002, 5001, 6001]
        assert len(rows) == 11

    def test_apostrophe_street(self, streets):
        _, rows = streets
        liberta = next(r for r in rows if r["street_id"] == 1001)
        assert (liberta["name"], liberta["name_norm"]) == ("VIA DELLA LIBERTA'", "via della liberta")
        assert (liberta["codice_istat"], liberta["comune"]) == ("057072", "Vacone")

    def test_street_number_range_and_count(self, streets):
        _, rows = streets
        liberta = next(r for r in rows if r["street_id"] == 1001)
        assert (liberta["numbers"], liberta["number_min"], liberta["number_max"]) == (5, 1, 5)
        provinciale = next(r for r in rows if r["street_id"] == 1004)
        assert (provinciale["numbers"], provinciale["number_min"], provinciale["number_max"]) == (1, None, None)

    def test_street_bbox_leaves_out_of_bounds(self, streets):
        _, rows = streets
        liberta = next(r for r in rows if r["street_id"] == 1001)
        assert liberta["bbox"] == {"xmin": 12.64, "ymin": 42.38, "xmax": 12.65, "ymax": 42.39}

    def test_same_name_streets_kept_apart(self, streets):
        _, rows = streets
        roma = [r for r in rows if r["codice_istat"] == "057072" and r["name_norm"] == "via roma"]
        assert [(r["street_id"], r["number_min"], r["number_max"]) for r in roma] == [
            (1002, 1, 10),
            (1003, 2, 40),
        ]

    def test_other_language_name_is_an_alternate_row(self, streets):
        _, rows = streets
        kirchweg = [r for r in rows if r["name_norm"] == "kirchweg"]
        assert len(kirchweg) == 1
        assert (kirchweg[0]["street_id"], kirchweg[0]["alt_of"], kirchweg[0]["name_lang"]) == (4001, 4001, "deu")

    def test_no_alternate_that_folds_to_the_primary(self, streets):
        _, rows = streets
        assert len([r for r in rows if r["street_id"] == 4002]) == 1

    def test_streets_sorted_and_declared(self, streets):
        facts, rows = streets
        keys = [(r["codice_istat"], r["name_norm"].encode(), r["street_id"]) for r in rows]
        assert keys == sorted(keys)
        names, sort = declared_sort(facts["path"])
        assert sort == ["codice_istat", "name_norm", "street_id"]
        metadata = pq.ParquetFile(facts["path"]).metadata
        for g in range(metadata.num_row_groups):
            assert metadata.row_group(g).column(names.index("codice_istat")).statistics.has_min_max


class TestAccessPoints:
    def test_one_row_per_source_row(self, access_points):
        facts, rows = access_points
        assert len(rows) == facts["rows"] == len(ROWS)

    def test_access_point_columns(self, access_points):
        _, rows = access_points
        three_a = next(r for r in rows if r["id"] == 3)
        assert three_a == {
            "codice_istat": "057072", "street_id": 1001, "id": 3, "number": 3, "suffix": "A",
            "specificita": None, "metrico": None, "out_of_bounds": False, "lon": 12.65, "lat": 42.39,
        }
        assert next(r for r in rows if r["id"] == 8)["specificita"] == "R"
        km = next(r for r in rows if r["id"] == 11)
        assert (km["number"], km["metrico"]) == (None, "12")

    def test_same_number_twice_is_two_rows(self, access_points):
        _, rows = access_points
        assert [r["id"] for r in rows if r["street_id"] == 1002 and r["number"] == 1] == [6, 7]

    def test_out_of_bounds_kept_and_flagged(self, access_points):
        _, rows = access_points
        assert next(r for r in rows if r["id"] == 5)["out_of_bounds"] is True

    def test_access_points_sorted_and_declared(self, access_points):
        facts, rows = access_points
        keys = [(r["codice_istat"], r["street_id"]) for r in rows]
        assert keys == sorted(keys)
        names, sort = declared_sort(facts["path"])
        assert sort == ["codice_istat", "street_id", "number", "suffix", "specificita", "id"]
        metadata = pq.ParquetFile(facts["path"]).metadata
        for g in range(metadata.num_row_groups):
            for column in ("codice_istat", "street_id"):
                assert metadata.row_group(g).column(names.index(column)).statistics.has_min_max

    def test_uniform_row_groups(self, access_points):
        facts, _ = access_points
        metadata = pq.ParquetFile(facts["path"]).metadata
        sizes = [metadata.row_group(g).num_rows for g in range(metadata.num_row_groups)]
        assert sizes[:-1] == [4] * (len(sizes) - 1)


class TestCli:
    def test_writes_the_three_files(self, tmp_path, capsys):
        addresses = write_addresses(tmp_path / "addresses.parquet")
        comuni = write_comuni(tmp_path / "comuni.json")
        main(["--input", str(addresses), "--comuni", str(comuni), "--out", str(tmp_path / "out"),
              "--release", "2026-11-02"])
        for path in ("gazetteer/2026-11-02/comuni.parquet", "indirizzi-index/2026-11-02/vie.parquet",
                     "indirizzi-index/2026-11-02/civici.parquet"):
            assert (tmp_path / "out" / path).exists(), path
        facts = json.loads(capsys.readouterr().out)
        assert set(facts) == {"gazetteer", "streets", "access_points"}
        assert facts["access_points"]["rows"] == len(ROWS)

    def test_writes_an_index_of_the_files_for_the_catalog(self, tmp_path):
        # The Parquet files stay out of git, so the catalog reads their facts
        # from these committed index files, as it does for the release archive.
        addresses = write_addresses(tmp_path / "addresses.parquet")
        comuni = write_comuni(tmp_path / "comuni.json")
        main(["--input", str(addresses), "--comuni", str(comuni), "--out", str(tmp_path / "out"),
              "--release", "2026-11-02"])
        gazetteer = json.loads((tmp_path / "out/gazetteer/index.json").read_text())
        index = json.loads((tmp_path / "out/indirizzi-index/index.json").read_text())
        assert gazetteer["release"] == index["release"] == "2026-11-02"
        assert set(gazetteer["files"]) == {"comuni"}
        assert set(index["files"]) == {"vie", "civici"}
        civici = index["files"]["civici"]
        path = tmp_path / "out/indirizzi-index/2026-11-02/civici.parquet"
        assert civici["href"] == "./2026-11-02/civici.parquet"
        assert civici["size"] == path.stat().st_size
        assert civici["checksum"] == "1220" + hashlib.sha256(path.read_bytes()).hexdigest()
        assert civici["rows"] == len(ROWS)
        assert {"row_groups", "row_group_rows", "footer_metadata_bytes"} <= set(civici)

    def test_input_path_with_an_apostrophe(self, tmp_path):
        # A comune's own folder is often named after it: Sant'Ambrogio.
        folder = tmp_path / "Sant'Ambrogio"
        folder.mkdir()
        addresses = write_addresses(tmp_path / "addresses.parquet")
        (folder / "addresses.parquet").write_bytes(addresses.read_bytes())
        comuni = write_comuni(tmp_path / "comuni.json")
        main(["--input", str(folder / "addresses.parquet"), "--comuni", str(comuni),
              "--out", str(tmp_path / "out"), "--release", "2026-11-02"])
        assert (tmp_path / "out/indirizzi-index/2026-11-02/civici.parquet").exists()

    def test_one_comune_input(self, tmp_path):
        vacone = [r for r in ROWS if r[0] == "057072"]
        addresses = write_addresses(tmp_path / "addresses.parquet", vacone)
        comuni = write_comuni(tmp_path / "comuni.json")
        main(["--input", str(addresses), "--comuni", str(comuni), "--out", str(tmp_path / "out"),
              "--release", "2026-11-02"])
        gazetteer = pq.read_table(tmp_path / "out/gazetteer/2026-11-02/comuni.parquet").to_pylist()
        assert [r["feature_id"] for r in gazetteer] == ["057072"]
        civici = pq.read_table(tmp_path / "out/indirizzi-index/2026-11-02/civici.parquet")
        assert civici.num_rows == len(vacone)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
