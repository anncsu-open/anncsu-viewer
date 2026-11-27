# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "jsonschema",
#     "pytest",
# ]
# ///
"""Tests for the JSON Schema of the draft address-index STAC extension.

Usage:
    uv run scripts/test_address_index_schema.py
"""

import copy
import json
from pathlib import Path

import jsonschema
import pytest

EXTENSION = Path(__file__).resolve().parent.parent / "geocoding" / "address-index" / "v0.1.0"
SCHEMA = json.loads((EXTENSION / "schema.json").read_text(encoding="utf-8"))
EXAMPLE = json.loads((EXTENSION / "examples" / "collection.json").read_text(encoding="utf-8"))


def errors(document):
    return list(jsonschema.Draft7Validator(SCHEMA).iter_errors(document))


def test_the_example_declares_the_schema_id():
    assert SCHEMA["$id"] in EXAMPLE["stac_extensions"]


def test_the_example_validates():
    assert errors(EXAMPLE) == []


def test_normalization_is_required():
    document = copy.deepcopy(EXAMPLE)
    del document["address_index:normalization"]
    assert errors(document)


def test_an_index_asset_needs_its_row_groups():
    document = copy.deepcopy(EXAMPLE)
    asset = next(a for a in document["assets"].values() if "address-points" in a["roles"])
    del asset["address_index:row_groups"]
    assert errors(document)


def test_an_index_asset_needs_its_sort():
    document = copy.deepcopy(EXAMPLE)
    asset = next(a for a in document["assets"].values() if "address-streets" in a["roles"])
    del asset["address_index:sort"]
    assert errors(document)


def test_only_collections():
    document = copy.deepcopy(EXAMPLE)
    document["type"] = "Feature"
    assert errors(document)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
