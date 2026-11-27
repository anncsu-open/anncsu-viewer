# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb==2.0.0",
#     "pyarrow",
# ]
# ///
"""Build the files the geocoder package reads.

Usage:
    uv run scripts/build_geocoding_index.py --input data/anncsu-indirizzi.parquet \\
        --comuni data/comuni.json --out data --release 2026-11-02

Writes three Parquet files, each sorted so that a browser can find its rows
with HTTP range requests and the row-group statistics:

- <out>/gazetteer/<release>/comuni.parquet, the comuni in the index format of
  the Portolan gazetteer extension, readable by @cngeo/geocoder-core;
- <out>/indirizzi-index/<release>/vie.parquet, one row per street;
- <out>/indirizzi-index/<release>/civici.parquet, one row per access point.

The input can be the national file or one comune's own: the files have the
same format at any size. See docs/superpowers/specs/2026-11-25-geocoder-package-design.md.

DuckDB computes the rows; PyArrow writes them, because DuckDB does not declare
the sort in the Parquet footer and the gazetteer contract asks for it.
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from geocoding_normalize import fold_name, fold_street

BBOX = pa.struct(
    [
        ("xmin", pa.float64()),
        ("ymin", pa.float64()),
        ("xmax", pa.float64()),
        ("ymax", pa.float64()),
    ]
)

GAZETTEER_SCHEMA = pa.schema(
    [
        ("name", pa.string()),
        ("name_norm", pa.string()),
        ("level", pa.int32()),
        ("country", pa.string()),
        ("feature_id", pa.string()),
        ("country_name", pa.string()),
        ("parent_name", pa.string()),
        ("parent_id", pa.string()),
        ("name_lang", pa.string()),
        ("alt_of", pa.string()),
        ("source", pa.string()),
        ("addresses", pa.int32()),
        ("bbox", BBOX),
    ]
)
GAZETTEER_SORT = ["name_norm", "level", "country", "feature_id"]

STREETS_SCHEMA = pa.schema(
    [
        ("codice_istat", pa.string()),
        ("comune", pa.string()),
        ("street_id", pa.int64()),
        ("name", pa.string()),
        ("name_norm", pa.string()),
        ("name_lang", pa.string()),
        ("alt_of", pa.int64()),
        ("numbers", pa.int32()),
        ("number_min", pa.int32()),
        ("number_max", pa.int32()),
        ("bbox", BBOX),
    ]
)
STREETS_SORT = ["codice_istat", "name_norm", "street_id"]

ACCESS_POINTS_SCHEMA = pa.schema(
    [
        ("codice_istat", pa.string()),
        ("street_id", pa.int64()),
        ("id", pa.int64()),
        ("number", pa.int32()),
        ("suffix", pa.string()),
        ("specificita", pa.string()),
        ("metrico", pa.string()),
        ("out_of_bounds", pa.bool_()),
        ("lon", pa.float64()),
        ("lat", pa.float64()),
    ]
)
ACCESS_POINTS_SORT = [
    "codice_istat",
    "street_id",
    "number",
    "suffix",
    "specificita",
    "id",
]

# The extent of a group of access points, without those ANNCSU places outside
# their comune, unless every point of the group is one.
BBOX_SQL = """
    coalesce(min(longitude) FILTER (WHERE NOT out_of_bounds), min(longitude)),
    coalesce(min(latitude) FILTER (WHERE NOT out_of_bounds), min(latitude)),
    coalesce(max(longitude) FILTER (WHERE NOT out_of_bounds), max(longitude)),
    coalesce(max(latitude) FILTER (WHERE NOT out_of_bounds), max(latitude))
"""
COMUNE_LEVEL = 3  # comuni are ADM3 in geoBoundaries, localadmin in Who's On First


def write_sorted(
    table: pa.Table, path: Path, sort: list[str], row_group_rows: int
) -> None:
    """Write rows already in `sort` order, declaring that order in the footer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        table,
        path,
        row_group_size=row_group_rows,
        compression="zstd",
        write_statistics=True,
        write_page_index=True,
        sorting_columns=sorting_columns(table.schema, sort),
    )


def sorting_columns(schema: pa.Schema, sort: list[str]) -> tuple:
    # Parquet counts leaf columns, so a struct before a sort column would
    # shift a plain field index; from_ordering maps the names correctly.
    return pq.SortingColumn.from_ordering(schema, [(c, "ascending") for c in sort])


def parquet_facts(path: Path, row_group_rows: int) -> dict:
    """What a client and the catalog need to know about a written file."""
    metadata = pq.ParquetFile(path).metadata
    with path.open("rb") as f:
        f.seek(-8, 2)
        # The footer ends with its thrift length (4 bytes, little endian) and PAR1.
        footer_metadata_bytes = struct.unpack("<I", f.read(4))[0]
    return {
        "path": str(path),
        "rows": metadata.num_rows,
        "row_groups": metadata.num_row_groups,
        "row_group_rows": row_group_rows,
        "footer_metadata_bytes": footer_metadata_bytes,
        "size": path.stat().st_size,
    }


def build_gazetteer(
    addresses: Path, comuni: Path, out: Path, row_group_rows: int = 4096
) -> dict:
    """Write the comuni gazetteer: one row per comune with addresses, plus alternates."""
    istat = {
        c["codice_istat"]: c for c in json.loads(comuni.read_text(encoding="utf-8"))
    }
    counts = duckdb.sql(
        f"""
        SELECT CODICE_ISTAT, count(*)::INTEGER, {BBOX_SQL}
        FROM read_parquet($path)
        GROUP BY CODICE_ISTAT
        """,
        params={"path": str(addresses)},
    ).fetchall()
    missing = sorted(code for code, *_ in counts if code not in istat)
    if missing:
        raise ValueError(
            f"comuni in the addresses but not in {comuni.name}: {', '.join(missing)}"
        )

    rows = []
    for code, count, xmin, ymin, xmax, ymax in counts:
        comune = istat[code]
        base = {
            "level": COMUNE_LEVEL,
            "country": "ITA",
            "feature_id": code,
            "country_name": "Italia",
            "parent_name": comune["provincia"],
            "parent_id": comune["codice_provincia"],
            "source": "anncsu",
            "addresses": count,
            "bbox": {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax},
        }
        name = comune["nome_comune"]
        spellings = [(name, fold_name(name), None, None)]
        # The contract keeps apostrophes, so "sant ambrogio" typed with a
        # space would miss "sant'ambrogio": a second spelling catches it. Its
        # name is spelled the same way, because name_norm must be the fold
        # of name on every row.
        spaced = name.replace("'", " ")
        spellings.append((spaced, fold_name(spaced), None, code))
        if comune.get("altra_lingua"):
            altra = comune["altra_lingua"]
            spellings.append((altra, fold_name(altra), comune.get("lingua"), code))
        seen = set()
        for display, norm, lang, alt_of in spellings:
            if norm in seen:
                continue
            seen.add(norm)
            rows.append(
                {
                    **base,
                    "name": display,
                    "name_norm": norm,
                    "name_lang": lang,
                    "alt_of": alt_of,
                }
            )

    # Python compares strings by code point, which is UTF-8 byte order.
    rows.sort(key=lambda r: (r["name_norm"], r["level"], r["country"], r["feature_id"]))
    write_sorted(
        pa.Table.from_pylist(rows, schema=GAZETTEER_SCHEMA),
        out,
        GAZETTEER_SORT,
        row_group_rows,
    )
    return parquet_facts(out, row_group_rows)


def build_streets(
    addresses: Path, comuni: Path, out: Path, row_group_rows: int = 4096
) -> dict:
    """Write one row per street, plus a row for each other-language name."""
    istat = {
        c["codice_istat"]: c for c in json.loads(comuni.read_text(encoding="utf-8"))
    }
    streets = duckdb.sql(
        f"""
        SELECT CODICE_ISTAT, PROGRESSIVO_NAZIONALE, any_value(ODONIMO),
               any_value(DIZIONE_LINGUA1), any_value(DIZIONE_LINGUA2),
               count(*)::INTEGER, min(CIVICO)::INTEGER, max(CIVICO)::INTEGER,
               {BBOX_SQL}
        FROM read_parquet($path)
        GROUP BY CODICE_ISTAT, PROGRESSIVO_NAZIONALE
        """,
        params={"path": str(addresses)},
    ).fetchall()

    rows = []
    for code, street_id, name, dizione1, dizione2, numbers, low, high, *bbox in streets:
        comune = istat.get(code, {})
        base = {
            "codice_istat": code,
            "comune": comune.get("nome_comune"),
            "street_id": street_id,
            "numbers": numbers,
            "number_min": low,
            "number_max": high,
            "bbox": dict(zip(("xmin", "ymin", "xmax", "ymax"), bbox)),
        }
        primary = fold_street(name)
        rows.append(
            {
                **base,
                "name": name,
                "name_norm": primary,
                "name_lang": None,
                "alt_of": None,
            }
        )
        # The other-language names, where they fold to something new. ANNCSU
        # does not say which language each one is: the comune's ISTAT
        # other language is the best guess, and null where it has none.
        seen = {primary}
        for dizione, lang in ((dizione1, comune.get("lingua")), (dizione2, None)):
            if not dizione or fold_street(dizione) in seen:
                continue
            seen.add(fold_street(dizione))
            rows.append(
                {
                    **base,
                    "name": dizione,
                    "name_norm": fold_street(dizione),
                    "name_lang": lang,
                    "alt_of": street_id,
                }
            )

    rows.sort(key=lambda r: (r["codice_istat"], r["name_norm"], r["street_id"]))
    write_sorted(
        pa.Table.from_pylist(rows, schema=STREETS_SCHEMA),
        out,
        STREETS_SORT,
        row_group_rows,
    )
    return parquet_facts(out, row_group_rows)


def build_access_points(
    addresses: Path, out: Path, row_group_rows: int = 32768
) -> dict:
    """Write one row per ANNCSU access point, sorted by comune, street and number.

    32768 rows per group keeps the footer near 760 KiB for the national file,
    which a client reads before any search, while one group stays under
    700 KiB; docs/geocoding-index-measurements.md has the numbers.
    """
    order = ", ".join(f"{c} NULLS LAST" for c in ACCESS_POINTS_SORT)
    relation = duckdb.sql(
        f"""
        SELECT CODICE_ISTAT AS codice_istat, PROGRESSIVO_NAZIONALE AS street_id,
               PROGRESSIVO_ACCESSO AS id, CIVICO::INTEGER AS number,
               ESPONENTE AS suffix, SPECIFICITA AS specificita, METRICO AS metrico,
               out_of_bounds, longitude AS lon, latitude AS lat
        FROM read_parquet($path)
        ORDER BY {order}
        """,
        params={"path": str(addresses)},
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    sorting = sorting_columns(ACCESS_POINTS_SCHEMA, ACCESS_POINTS_SORT)
    # Twenty million rows do not fit a single write: they are streamed, and
    # cut into groups of exactly row_group_rows so the groups stay uniform.
    pending: list[pa.RecordBatch] = []
    pending_rows = 0
    with pq.ParquetWriter(
        out,
        ACCESS_POINTS_SCHEMA,
        compression="zstd",
        write_statistics=True,
        write_page_index=True,
        sorting_columns=sorting,
    ) as writer:
        for batch in relation.to_arrow_reader(batch_size=row_group_rows):
            pending.append(batch.cast(ACCESS_POINTS_SCHEMA))
            pending_rows += batch.num_rows
            while pending_rows >= row_group_rows:
                table = pa.Table.from_batches(pending)
                writer.write_table(
                    table.slice(0, row_group_rows), row_group_size=row_group_rows
                )
                rest = table.slice(row_group_rows)
                pending, pending_rows = rest.to_batches(), rest.num_rows
        if pending_rows:
            writer.write_table(
                pa.Table.from_batches(pending), row_group_size=row_group_rows
            )
    return parquet_facts(out, row_group_rows)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--input", type=Path, required=True, help="the ANNCSU addresses Parquet"
    )
    parser.add_argument(
        "--comuni", type=Path, required=True, help="comuni.json from generate_comuni.py"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="where gazetteer/ and indirizzi-index/ go",
    )
    parser.add_argument(
        "--release", required=True, help="the ANNCSU release date, YYYY-MM-DD"
    )
    args = parser.parse_args(argv)

    index = args.out / "indirizzi-index" / args.release
    facts = {
        "gazetteer": build_gazetteer(
            args.input,
            args.comuni,
            args.out / "gazetteer" / args.release / "comuni.parquet",
        ),
        "streets": build_streets(args.input, args.comuni, index / "vie.parquet"),
        "access_points": build_access_points(args.input, index / "civici.parquet"),
    }
    write_index(args.out / "gazetteer", args.release, {"comuni": facts["gazetteer"]})
    write_index(
        args.out / "indirizzi-index",
        args.release,
        {"vie": facts["streets"], "civici": facts["access_points"]},
    )
    print(json.dumps(facts, indent=2))


def write_index(collection: Path, release: str, files: dict[str, dict]) -> None:
    """Write <collection>/index.json, the facts build_catalog.py publishes.

    The Parquet files stay out of git, as the release archive's do, so the
    catalog cannot measure them in CI: it reads this small committed file.
    """
    entries = {}
    for name, facts in files.items():
        path = Path(facts["path"])
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        entries[name] = {
            "href": f"./{release}/{path.name}",
            "size": facts["size"],
            # Multihash, as the catalog's file:checksum: sha2-256, 32 bytes.
            "checksum": "1220" + digest.hexdigest(),
            "rows": facts["rows"],
            "row_groups": facts["row_groups"],
            "row_group_rows": facts["row_group_rows"],
            "footer_metadata_bytes": facts["footer_metadata_bytes"],
        }
    document = {"release": release, "files": entries}
    (collection / "index.json").write_text(json.dumps(document, indent=2) + "\n")


if __name__ == "__main__":
    main()
