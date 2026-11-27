# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
# ]
# ///
"""Tests for geocoding_normalize.py, the name foldings of the geocoding index.

Usage:
    uv run scripts/test_geocoding_normalize.py

The cases live in geocoding/normalization-vectors.json, which the JavaScript
package reads too: a change on one side fails the other side's tests.
"""

import json
from pathlib import Path

import pytest

from geocoding_normalize import (
    NAME_NORMALIZATION,
    STREET_NORMALIZATION,
    fold_name,
    fold_street,
)

VECTORS = json.loads(
    (Path(__file__).resolve().parent.parent / "geocoding" / "normalization-vectors.json").read_text(
        encoding="utf-8"
    )
)
FOLDS = {NAME_NORMALIZATION: fold_name, STREET_NORMALIZATION: fold_street}
CASES = [
    (normalization, source, expected)
    for normalization, cases in VECTORS.items()
    for source, expected in cases
]


def test_every_normalization_in_the_vectors_has_a_function():
    assert set(VECTORS) == set(FOLDS)


@pytest.mark.parametrize("normalization,source,expected", CASES)
def test_vectors(normalization, source, expected):
    assert FOLDS[normalization](source) == expected


@pytest.mark.parametrize("normalization,source,expected", CASES)
def test_idempotent(normalization, source, expected):
    fold = FOLDS[normalization]
    assert fold(fold(source)) == fold(source)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
