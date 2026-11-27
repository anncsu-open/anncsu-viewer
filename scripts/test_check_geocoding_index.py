# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb==2.0.0",
#     "pyarrow",
#     "pytest",
# ]
# ///
"""Tests for check_geocoding_index.py, the contract checks of the index files.

Usage:
    uv run scripts/test_check_geocoding_index.py

A file passes when a client could binary-search it: rows in the declared
order, the order declared in the footer, exact statistics on the sort
columns, and names folded by the declared normalization. Each test below
breaks one of those and expects the checker to name it.
"""

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from build_geocoding_index import build_access_points, build_gazetteer, build_streets
from check_geocoding_index import check_access_points, check_gazetteer, check_streets
from test_build_geocoding_index import write_addresses, write_comuni


@pytest.fixture
def built(tmp_path):
    addresses = write_addresses(tmp_path / "addresses.parquet")
    comuni = write_comuni(tmp_path / "comuni.json")
    return {
        "gazetteer": build_gazetteer(addresses, comuni, tmp_path / "comuni.parquet", 4)[
            "path"
        ],
        "streets": build_streets(addresses, comuni, tmp_path / "vie.parquet", 4)[
            "path"
        ],
        "access_points": build_access_points(addresses, tmp_path / "civici.parquet", 4)[
            "path"
        ],
    }


CHECKS = {
    "gazetteer": check_gazetteer,
    "streets": check_streets,
    "access_points": check_access_points,
}
SORTS = {
    "gazetteer": ["name_norm", "level", "country", "feature_id"],
    "streets": ["codice_istat", "name_norm", "street_id"],
    "access_points": [
        "codice_istat",
        "street_id",
        "number",
        "suffix",
        "specificita",
        "id",
    ],
}


def rewrite(source, target, table=None, sort=None, **options):
    """Write `table` (or the source's rows) with the given writer options."""
    table = table if table is not None else pq.read_table(source)
    sorting = (
        [pq.SortingColumn(table.schema.get_field_index(c)) for c in sort]
        if sort
        else None
    )
    pq.write_table(table, target, row_group_size=4, sorting_columns=sorting, **options)
    return target


@pytest.mark.parametrize("kind", list(CHECKS))
def test_a_built_file_passes(built, kind):
    assert CHECKS[kind](built[kind]) == []


@pytest.mark.parametrize("kind", list(CHECKS))
def test_rows_out_of_order(built, kind, tmp_path):
    table = pq.read_table(built[kind])
    reversed_rows = table.take(list(range(table.num_rows - 1, -1, -1)))
    path = rewrite(built[kind], tmp_path / "bad.parquet", reversed_rows, SORTS[kind])
    assert any("order" in p for p in CHECKS[kind](path))


@pytest.mark.parametrize("kind", list(CHECKS))
def test_sort_not_declared(built, kind, tmp_path):
    path = rewrite(built[kind], tmp_path / "bad.parquet")
    assert any("sorting_columns" in p for p in CHECKS[kind](path))


@pytest.mark.parametrize("kind", list(CHECKS))
def test_no_statistics(built, kind, tmp_path):
    path = rewrite(
        built[kind], tmp_path / "bad.parquet", sort=SORTS[kind], write_statistics=False
    )
    assert any("statistics" in p for p in CHECKS[kind](path))


@pytest.mark.parametrize("kind", ["gazetteer", "streets"])
def test_name_not_folded_by_the_declared_normalization(built, kind, tmp_path):
    table = pq.read_table(built[kind])
    norms = table.column("name_norm").to_pylist()
    # Keep the order intact: only the last row changes, to something after it.
    norms[-1] = norms[-1] + "zz"
    table = table.set_column(
        table.schema.get_field_index("name_norm"), "name_norm", pa.array(norms)
    )
    path = rewrite(built[kind], tmp_path / "bad.parquet", table, SORTS[kind])
    assert any("normaliz" in p for p in CHECKS[kind](path))


@pytest.mark.parametrize("kind", list(CHECKS))
def test_missing_column(built, kind, tmp_path):
    table = pq.read_table(built[kind])
    path = rewrite(
        built[kind],
        tmp_path / "bad.parquet",
        table.drop_columns(["codice_istat" if kind != "gazetteer" else "bbox"]),
    )
    assert any("missing column" in p for p in CHECKS[kind](path))


def test_statistics_dropped_for_a_long_value(built, tmp_path):
    # Arrow writes no min/max for a row group with a very long value, and
    # a client with no statistics cannot binary-search that row group.
    table = pq.read_table(built["streets"])
    names = table.column("name").to_pylist()
    norms = table.column("name_norm").to_pylist()
    names[-1] = names[-1] + " " + "x" * 5000
    norms[-1] = norms[-1] + " " + "x" * 5000
    table = table.set_column(
        table.schema.get_field_index("name"), "name", pa.array(names)
    )
    table = table.set_column(
        table.schema.get_field_index("name_norm"), "name_norm", pa.array(norms)
    )
    path = rewrite(
        built["streets"],
        tmp_path / "bad.parquet",
        table,
        SORTS["streets"],
    )
    assert any("statistics" in p for p in check_streets(path))


def test_space_spelling_on_a_primary_row(built, tmp_path):
    # Only an alternate row may carry the spelling with a space, and then its
    # name must say so: a primary "Sant'Ambrogio" folded with a space would be
    # missed by a client typing the apostrophe.
    table = pq.read_table(built["gazetteer"])
    rows = [r for r in table.to_pylist() if r["alt_of"] is None]
    for r in rows:
        if "'" in r["name"]:
            r["name_norm"] = r["name_norm"].replace("'", " ")
    rows.sort(key=lambda r: (r["name_norm"], r["level"], r["country"], r["feature_id"]))
    path = rewrite(built["gazetteer"], tmp_path / "bad.parquet", pa.Table.from_pylist(rows, schema=table.schema), SORTS["gazetteer"])
    assert any("normaliz" in p for p in check_gazetteer(path))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
