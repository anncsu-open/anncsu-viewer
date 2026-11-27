# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
# ]
# ///
"""Generate comuni.json from the ISTAT list of comuni.

Usage:
    uv run scripts/generate_comuni.py

Downloads the ISTAT list of Italian comuni and writes, for each one, its
CODICE_ISTAT and Italian name, its province (the "unità territoriale
sovracomunale"), and its name in the other official language where it has
one. The geocoding gazetteer uses the province to tell apart comuni with the
same name, and the other-language names as alternative spellings.
"""

import csv
import io
import json
from pathlib import Path

import httpx

ISTAT_URL = "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.csv"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "comuni.json"

# The language of ISTAT's "altra lingua" names, by province: German in South
# Tyrol, Ladin in the one Trentino comune that has one, Slovene in Trieste and
# Gorizia. ISO 639-3, as in the gazetteer's name_lang.
LANGUAGE_BY_PROVINCE = {"BZ": "deu", "TN": "lld", "TS": "slv", "GO": "slv"}


def _column(row: dict, prefix: str) -> str:
    # Two headers contain a line break, so they are matched by their start.
    for name, value in row.items():
        if name and name.startswith(prefix):
            return (value or "").strip()
    raise KeyError(f"no ISTAT column starts with {prefix!r}")


def parse_comuni(content: bytes) -> list[dict]:
    """Parse the ISTAT CSV, which is Windows-1252 and separated by semicolons."""
    reader = csv.DictReader(io.StringIO(content.decode("cp1252")), delimiter=";")
    comuni = []
    for row in reader:
        codice = _column(row, "Codice Comune formato numerico")
        nome = _column(row, "Denominazione in italiano")
        if not (codice and nome):
            continue
        sigla = _column(row, "Sigla automobilistica")
        altra = _column(row, "Denominazione altra lingua") or None
        comuni.append(
            {
                # Six digits, as CODICE_ISTAT in ANNCSU.
                "codice_istat": codice.zfill(6),
                "nome_comune": nome,
                "codice_provincia": _column(
                    row, "Codice dell'Unità territoriale sovracomunale"
                ),
                "provincia": _column(
                    row, "Denominazione dell'Unità territoriale sovracomunale"
                ),
                "sigla_provincia": sigla,
                "altra_lingua": altra,
                "lingua": LANGUAGE_BY_PROVINCE.get(sigla) if altra else None,
            }
        )
    comuni.sort(key=lambda x: x["codice_istat"])
    return comuni


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading ISTAT comuni list from {ISTAT_URL} ...")
    response = httpx.get(ISTAT_URL, follow_redirects=True, timeout=60)
    response.raise_for_status()

    comuni = parse_comuni(response.content)
    print(f"Found {len(comuni)} comuni")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(comuni, f, ensure_ascii=False, indent=2)

    print(f"Written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
