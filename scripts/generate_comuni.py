# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
# ]
# ///
"""Generate comuni.json mapping CODICE_ISTAT to commune name.

Usage:
    uv run scripts/generate_comuni.py

Downloads the ISTAT list of Italian communes and produces a JSON file
mapping the numeric CODICE_ISTAT to the Italian denomination.
"""

import csv
import io
import json
from pathlib import Path

import httpx

ISTAT_URL = "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "comuni.json"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading ISTAT comuni list from {ISTAT_URL} ...")
    response = httpx.get(ISTAT_URL, follow_redirects=True, timeout=60)
    response.raise_for_status()

    # ISTAT CSV uses semicolon separator and latin-1 encoding
    text = response.content.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")

    comuni = []
    for row in reader:
        codice = row.get("Codice Comune formato numerico", "").strip()
        nome = row.get("Denominazione in italiano", "").strip()
        if codice and nome:
            # Pad to 6 digits to match CODICE_ISTAT in ANNCSU
            codice_padded = codice.zfill(6)
            comuni.append({"codice_istat": codice_padded, "nome_comune": nome})

    comuni.sort(key=lambda x: x["codice_istat"])
    print(f"Found {len(comuni)} comuni")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(comuni, f, ensure_ascii=False, indent=2)

    print(f"Written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
