# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyarrow",
# ]
# ///
"""Measure what a browser downloads to search the geocoding index.

Usage:
    uv run scripts/measure_geocoding_index.py data/gazetteer/<release>/comuni.parquet \\
        data/indirizzi-index/<release>/vie.parquet data/indirizzi-index/<release>/civici.parquet

Works from the Parquet footers alone, as a range-reading client plans its
requests: for a comune, the row groups of its streets; for its longest street,
the row groups of that street's access points. Adjacent row groups count as one
request. Prints a Markdown table.
"""

import struct
import sys
from pathlib import Path

import pyarrow.parquet as pq

COMUNI = {"057072": "Vacone", "058091": "Roma"}


def footer_bytes(path: Path) -> int:
    with path.open("rb") as f:
        f.seek(-8, 2)
        return struct.unpack("<I", f.read(4))[0] + 8


def group_bytes(metadata, g: int) -> int:
    group = metadata.row_group(g)
    return sum(group.column(c).total_compressed_size for c in range(group.num_columns))


def column_index(metadata, name: str) -> int:
    return [metadata.schema.column(i).path for i in range(metadata.num_columns)].index(
        name
    )


def stats(metadata, g: int, name: str):
    s = metadata.row_group(g).column(column_index(metadata, name)).statistics
    return s.min, s.max


def requests(groups: list[int]) -> int:
    return sum(1 for i, g in enumerate(groups) if i == 0 or g != groups[i - 1] + 1)


def comune_groups(metadata, code: str) -> list[int]:
    return [
        g
        for g in range(metadata.num_row_groups)
        if stats(metadata, g, "codice_istat")[0]
        <= code
        <= stats(metadata, g, "codice_istat")[1]
    ]


def street_groups(metadata, code: str, street: int) -> list[int]:
    found = []
    for g in range(metadata.num_row_groups):
        (lo_c, hi_c), (lo_s, hi_s) = (
            stats(metadata, g, "codice_istat"),
            stats(metadata, g, "street_id"),
        )
        # Per-column statistics bound the (comune, street) pairs conservatively.
        if (lo_c, lo_s) <= (code, street) <= (hi_c, hi_s) or lo_c < code < hi_c:
            found.append(g)
    return found


def median_comune(vie: Path) -> str:
    table = pq.read_table(
        vie, columns=["codice_istat", "numbers", "alt_of"]
    ).to_pylist()
    totals = {}
    for row in table:
        if row["alt_of"] is None:
            totals[row["codice_istat"]] = (
                totals.get(row["codice_istat"], 0) + row["numbers"]
            )
    ordered = sorted(totals, key=totals.get)
    return ordered[len(ordered) // 2]


def longest_street(vie: Path, code: str) -> tuple[int, int]:
    rows = pq.read_table(
        vie,
        columns=["codice_istat", "street_id", "numbers", "alt_of"],
        filters=[("codice_istat", "=", code)],
    ).to_pylist()
    best = max((r for r in rows if r["alt_of"] is None), key=lambda r: r["numbers"])
    return best["street_id"], best["numbers"]


def kib(n: int) -> str:
    return f"{n / 1024:,.0f} KiB"


def main(gazetteer: Path, vie: Path, civici: Path) -> None:
    v, c = pq.ParquetFile(vie).metadata, pq.ParquetFile(civici).metadata
    print(f"gazetteer: {kib(gazetteer.stat().st_size)} whole file")
    print(
        f"vie: {v.num_row_groups} row groups of {v.row_group(0).num_rows}, footer {kib(footer_bytes(vie))}"
    )
    print(
        f"civici: {c.num_row_groups} row groups of {c.row_group(0).num_rows}, footer {kib(footer_bytes(civici))}"
    )
    print()
    print(
        "| comune | streets: groups / requests / bytes | longest street (numbers) | its access points: groups / requests / bytes | first address, all included |"
    )
    print("|---|---|---|---|---|")
    comuni = dict(COMUNI)
    comuni[median_comune(vie)] = "median comune"
    for code, label in comuni.items():
        sg = comune_groups(v, code)
        street, numbers = longest_street(vie, code)
        pg = street_groups(c, code, street)
        streets_bytes = sum(group_bytes(v, g) for g in sg)
        points_bytes = sum(group_bytes(c, g) for g in pg)
        total = (
            gazetteer.stat().st_size
            + footer_bytes(vie)
            + streets_bytes
            + footer_bytes(civici)
            + points_bytes
        )
        print(
            f"| {label} ({code}) | {len(sg)} / {requests(sg)} / {kib(streets_bytes)} | {street} ({numbers}) "
            f"| {len(pg)} / {requests(pg)} / {kib(points_bytes)} | {kib(total)} |"
        )


if __name__ == "__main__":
    main(*(Path(p) for p in sys.argv[1:4]))
