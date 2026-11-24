# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb==2.0.1",
# ]
# ///
"""Write the data the end-to-end tests serve: Vacone's addresses.

Usage:
    uv run e2e/fixtures/make_fixtures.py

The rows come from the published catalog and keep its schema, including the
GEOMETRY('OGC:CRS84') column that DuckDB-Wasm needs a workaround to read.
The same rows serve both modes: an H3 tile plus the comuni index for the
national one, a single GeoParquet file for the municipal one.
"""

import json
from pathlib import Path

import duckdb

PUBLIC_BASE = "https://pub-1e760dc850cb4a5aa5f8afb77713f8cd.r2.dev"
CODICE_ISTAT = "057072"  # Vacone
OUT = Path(__file__).resolve().parent / "data"


def main() -> None:
    con = duckdb.connect()
    con.sql("INSTALL spatial; LOAD spatial;")
    # DuckDB rather than urllib: the bucket refuses Python's default client.
    codice_istat, nome_comune, h3_cells = con.sql(
        f"SELECT codice_istat, nome_comune, h3_cells "
        f"FROM read_json('{PUBLIC_BASE}/comuni-h3.json') "
        f"WHERE codice_istat = '{CODICE_ISTAT}'"
    ).fetchall()[0]
    comune = {
        "codice_istat": codice_istat,
        "nome_comune": nome_comune,
        "h3_cells": h3_cells,
    }
    (cell,) = h3_cells

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "comuni-h3.json").write_text(
        json.dumps([comune], indent=2) + "\n", encoding="utf-8"
    )

    tile = OUT / "tiles" / f"h3_cell={cell}" / f"{cell}.parquet"
    tile.parent.mkdir(parents=True, exist_ok=True)
    rows = (
        f"SELECT * FROM read_parquet('{PUBLIC_BASE}/tiles/h3_cell={cell}/{cell}.parquet') "
        f"WHERE CODICE_ISTAT = '{CODICE_ISTAT}' ORDER BY PROGRESSIVO_ACCESSO"
    )
    for target in (tile, OUT / "anncsu-indirizzi.parquet"):
        con.sql(f"COPY ({rows}) TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        count, geometry = con.sql(
            f"SELECT count(*), any_value(typeof(geometry)) FROM read_parquet('{target}')"
        ).fetchall()[0]
        print(f"{target.relative_to(OUT)}: {count} rows, {geometry}")


if __name__ == "__main__":
    main()
