"""The two name foldings of the geocoding index.

A client finds a name by folding what the user typed the same way the index
folded its names, so these functions are a contract: the cases in
geocoding/normalization-vectors.json pin them, and the JavaScript package
checks itself against the same file.

- nfd-strip-marks-lower/1 is the folding of the Portolan gazetteer extension,
  used for the comuni so that @cngeo/geocoder-core can read our gazetteer. It
  follows that client's normalizeName (packages/spec/src/normalize.js in
  cholmes/cng-map-widgets): characters outside letters, digits, space, ' and -
  are dropped, not turned into spaces, so "Bolzano/Bozen" is "bolzanobozen".
- anncsu-odonimo/1 is ours, for street names. ANNCSU writes accented letters
  as a trailing apostrophe ("LIBERTA'") and elides with one ("D'ANNUNZIO"),
  so every apostrophe becomes a space: "LIBERTA'" and a typed "libertà" both
  fold to "liberta". Other punctuation becomes a space too, so that
  "G.MARCONI" can be found by typing "marconi".
"""

import unicodedata

NAME_NORMALIZATION = "nfd-strip-marks-lower/1"
STREET_NORMALIZATION = "anncsu-odonimo/1"


def _fold(text: str, keep: str, other: str) -> str:
    # Python's re has no \p{L}, so the categories are checked one by one.
    decomposed = unicodedata.normalize("NFD", text)
    unmarked = "".join(
        c for c in decomposed if not unicodedata.category(c).startswith("M")
    )
    kept = "".join(
        c if unicodedata.category(c)[0] in "LN" or c in keep else other
        for c in unmarked.lower()
    )
    return " ".join(kept.split())


def fold_name(text: str) -> str:
    """Fold a place name: NFD, no marks, lowercase, keep letters, digits, space, ' and -."""
    return _fold(text, " '-", "")


def fold_street(text: str) -> str:
    """Fold a street name: like fold_name, but apostrophes and other punctuation become spaces."""
    return _fold(text, " -", " ")
