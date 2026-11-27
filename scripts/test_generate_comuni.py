# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
#     "pytest",
# ]
# ///
"""Tests for generate_comuni.py, the ISTAT list of comuni.

Usage:
    uv run scripts/test_generate_comuni.py
"""

import pytest

from generate_comuni import parse_comuni

# The real header, with the two quoted names that contain a line break, and
# three rows. ISTAT publishes the
# file in Windows-1252, which has the Š of Števerjan; latin-1 does not.
HEADER = (
    "Codice Regione;\"Codice dell'Unità territoriale sovracomunale \n(valida a fini statistici)\";"
    "Codice Provincia (Storico)(1);Progressivo del Comune (2);Codice Comune formato alfanumerico;"
    "Denominazione (Italiana e straniera);Denominazione in italiano;Denominazione altra lingua;"
    "Codice Ripartizione Geografica;Ripartizione geografica;Denominazione Regione;"
    "\"Denominazione dell'Unità territoriale sovracomunale \n(valida a fini statistici)\";"
    "Tipologia di Unità territoriale sovracomunale ;"
    "Flag Comune capoluogo di provincia/città metropolitana/libero consorzio;"
    "Sigla automobilistica;Codice Comune formato numerico\n"
)
ROWS = [
    "12;057;057;072;057072;Vacone;Vacone;;3;Centro;Lazio;Rieti;1;0;RI;57072\n",
    "04;021;021;001;021001;Aldino/Aldein;Aldino;Aldein;1;Nord-est;Trentino-Alto Adige/Südtirol;Bolzano/Bozen;2;0;BZ;21001\n",
    "06;031;031;019;031019;San Floriano del Collio/Števerjan;San Floriano del Collio;Števerjan;1;Nord-est;"
    "Friuli-Venezia Giulia;Gorizia;4;0;GO;31019\n",
]
CSV = (HEADER + "".join(ROWS)).encode("cp1252")


def by_code(comuni):
    return {c["codice_istat"]: c for c in comuni}


def test_keeps_code_and_name():
    vacone = by_code(parse_comuni(CSV))["057072"]
    assert vacone["nome_comune"] == "Vacone"


def test_keeps_the_province():
    vacone = by_code(parse_comuni(CSV))["057072"]
    assert vacone["codice_provincia"] == "057"
    assert vacone["provincia"] == "Rieti"
    assert vacone["sigla_provincia"] == "RI"


def test_no_other_language_name():
    vacone = by_code(parse_comuni(CSV))["057072"]
    assert vacone["altra_lingua"] is None
    assert vacone["lingua"] is None


def test_german_name_in_bolzano():
    aldino = by_code(parse_comuni(CSV))["021001"]
    assert aldino["altra_lingua"] == "Aldein"
    assert aldino["lingua"] == "deu"


def test_slovene_name_decoded_from_windows_1252():
    floriano = by_code(parse_comuni(CSV))["031019"]
    assert floriano["altra_lingua"] == "Števerjan"
    assert floriano["lingua"] == "slv"


def test_sorted_by_code():
    codes = [c["codice_istat"] for c in parse_comuni(CSV)]
    assert codes == sorted(codes)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
