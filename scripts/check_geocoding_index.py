# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyarrow",
# ]
# ///
"""Check the geocoding index files against their contract.

Usage:
    uv run scripts/check_geocoding_index.py data

A STAC validator only sees the JSON. What makes these files usable is inside
them: a client binary-searches the row-group statistics, so the rows must be
in the declared order, the footer must declare it, the statistics of the
search columns must be there and exact, and the names must be folded by the
normalization the collection declares. This script opens the files and
checks exactly that. It exits 1 if any file breaks the contract.
"""

import sys
from pathlib import Path
from typing import Callable

import pyarrow as pa
import pyarrow.parquet as pq

from geocoding_normalize import (
    NAME_NORMALIZATION,
    STREET_NORMALIZATION,
    fold_name,
    fold_street,
)

BBOX = pa.struct(
    [
        ("xmin", pa.float64()),
        ("ymin", pa.float64()),
        ("xmax", pa.float64()),
        ("ymax", pa.float64()),
    ]
)


def _gazetteer_norm_ok(name: str, norm: str) -> bool:
    return norm == fold_name(name)


def _street_norm_ok(name: str, norm: str) -> bool:
    return norm == fold_street(name)


def _key(values: tuple) -> tuple:
    # Nulls sort last, and never compare with a value.
    return tuple((v is None, v if v is not None else 0) for v in values)


def _check(
    path: Path,
    required: dict[str, pa.DataType],
    sort: list[str],
    search: list[str],
    normalization: tuple[str, Callable[[str, str], bool]] | None,
) -> list[str]:
    problems = []
    parquet = pq.ParquetFile(path)
    schema = parquet.schema_arrow
    for name, expected in required.items():
        if name not in schema.names:
            problems.append(f"missing column {name}")
        elif not schema.field(name).type.equals(expected):
            problems.append(
                f"column {name} is {schema.field(name).type}, expected {expected}"
            )
    if any(column not in schema.names for column in sort):
        return problems

    metadata = parquet.metadata
    leaves = [metadata.schema.column(i).path for i in range(metadata.num_columns)]
    for g in range(metadata.num_row_groups):
        declared = [
            leaves[s.column_index] for s in metadata.row_group(g).sorting_columns or ()
        ]
        if declared != sort:
            problems.append(
                f"row group {g}: sorting_columns declare {declared}, expected {sort}"
            )
            break

    previous = None
    row = 0
    bad_norms = []
    for g in range(metadata.num_row_groups):
        columns = sort + ([c for c in ("name",) if normalization and c not in sort])
        group = parquet.read_row_group(g, columns=columns).to_pydict()
        keys = list(zip(*(group[c] for c in sort)))
        for i, key in enumerate(keys):
            if previous is not None and _key(key) < _key(previous):
                problems.append(
                    f"rows out of order at row {row + i}: {key} after {previous}"
                )
                previous = None
                break
            previous = key
        for column in search:
            values = [v for v in group[column] if v is not None]
            stats = metadata.row_group(g).column(leaves.index(column)).statistics
            if not values:
                continue
            if stats is None or not stats.has_min_max:
                problems.append(f"row group {g}: no min/max statistics on {column}")
            elif (stats.min, stats.max) != (min(values), max(values)):
                problems.append(
                    f"row group {g}: statistics on {column} are truncated or wrong"
                )
        if normalization:
            check = normalization[1]
            bad_norms += [
                (name, norm)
                for name, norm in zip(group["name"], group["name_norm"])
                if not check(name, norm)
            ]
        row += len(keys)
    if bad_norms:
        problems.append(
            f"{len(bad_norms)} rows whose name_norm is not the {normalization[0]} normalization "
            f"of name (first: {bad_norms[0]})"
        )
    return problems


def check_gazetteer(path) -> list[str]:
    """Problems with a comuni gazetteer file; an empty list means it conforms."""
    required = {
        "name": pa.string(),
        "name_norm": pa.string(),
        "level": pa.int32(),
        "country": pa.string(),
        "feature_id": pa.string(),
        "bbox": BBOX,
    }
    sort = ["name_norm", "level", "country", "feature_id"]
    return _check(
        Path(path),
        required,
        sort,
        ["name_norm"],
        (NAME_NORMALIZATION, _gazetteer_norm_ok),
    )


def check_streets(path) -> list[str]:
    """Problems with a streets file; an empty list means it conforms."""
    required = {
        "codice_istat": pa.string(),
        "comune": pa.string(),
        "street_id": pa.int64(),
        "name": pa.string(),
        "name_norm": pa.string(),
        "numbers": pa.int32(),
        "bbox": BBOX,
    }
    sort = ["codice_istat", "name_norm", "street_id"]
    return _check(
        Path(path),
        required,
        sort,
        ["codice_istat", "name_norm"],
        (STREET_NORMALIZATION, _street_norm_ok),
    )


def check_access_points(path) -> list[str]:
    """Problems with an access points file; an empty list means it conforms."""
    required = {
        "codice_istat": pa.string(),
        "street_id": pa.int64(),
        "id": pa.int64(),
        "number": pa.int32(),
        "suffix": pa.string(),
        "specificita": pa.string(),
        "metrico": pa.string(),
        "out_of_bounds": pa.bool_(),
        "lon": pa.float64(),
        "lat": pa.float64(),
    }
    sort = ["codice_istat", "street_id", "number", "suffix", "specificita", "id"]
    return _check(Path(path), required, sort, ["codice_istat", "street_id"], None)


def main(argv: list[str] | None = None) -> int:
    root = Path((argv or sys.argv[1:])[0])
    files = [
        (p, check_gazetteer) for p in sorted(root.glob("gazetteer/*/comuni.parquet"))
    ]
    files += [
        (p, check_streets) for p in sorted(root.glob("indirizzi-index/*/vie.parquet"))
    ]
    files += [
        (p, check_access_points)
        for p in sorted(root.glob("indirizzi-index/*/civici.parquet"))
    ]
    if not files:
        print(f"no geocoding index files under {root}")
        return 1
    failed = False
    for path, check in files:
        problems = check(path)
        print(f"{'FAIL' if problems else 'ok  '} {path}")
        for problem in problems:
            print(f"     {problem}")
        failed = failed or bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
