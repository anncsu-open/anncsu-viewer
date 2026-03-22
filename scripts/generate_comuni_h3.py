# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "duckdb>=1.2.0",
# ]
# ///
"""Generate comuni-h3.json mapping each comune to its H3 tile cells.

Usage:
    uv run scripts/generate_comuni_h3.py

Reads the GeoParquet file and computes which H3 resolution-5 cells
contain addresses for each comune. Outputs a JSON file used by the
frontend to know which tiles to load for a given comune search.
"""

import json
from pathlib import Path

import duckdb

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
PARQUET_FILE = OUTPUT_DIR / "anncsu-indirizzi.parquet"
OUTPUT_FILE = OUTPUT_DIR / "comuni-h3.json"
H3_RESOLUTION = 5


def main() -> None:
    if not PARQUET_FILE.exists():
        raise RuntimeError(f"{PARQUET_FILE} not found. Run update_data.py first.")

    print("Computing H3 cells per comune ...")
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("INSTALL h3 FROM community; LOAD h3;")

    result = con.execute(f"""
        SELECT
            CODICE_ISTAT,
            NOME_COMUNE,
            list(DISTINCT h3_latlng_to_cell(latitude, longitude, {H3_RESOLUTION})::BIGINT) as h3_cells
        FROM read_parquet('{PARQUET_FILE}')
        WHERE NOME_COMUNE IS NOT NULL
          AND latitude IS NOT NULL
          AND longitude IS NOT NULL
        GROUP BY CODICE_ISTAT, NOME_COMUNE
        ORDER BY CODICE_ISTAT
    """).fetchall()

    comuni_h3 = []
    for codice_istat, nome_comune, h3_cells in result:
        # Convert to hex strings matching the tile directory names
        hex_cells = [hex(c)[2:] for c in h3_cells]
        comuni_h3.append({
            "codice_istat": codice_istat,
            "nome_comune": nome_comune,
            "h3_cells": hex_cells,
        })

    con.close()

    print(f"Found {len(comuni_h3)} comuni with H3 cells")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(comuni_h3, f, ensure_ascii=False)

    size_kb = OUTPUT_FILE.stat().st_size / 1024
    print(f"Written to {OUTPUT_FILE} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
