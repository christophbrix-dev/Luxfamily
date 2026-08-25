"""One spelling per town.

The database arrived at five names for the capital — Luxembourg, Luxemburg,
Luxembourg City, Luxembourg-Stadt, Luxemburg-Stadt — because each source writes
it in its own language and every one of them is correct. To the app they are
five different places: five entries in a list, five groups in a filter, and a
search for one that misses the other four.

The mapping is not written out by hand. communes_lu.json already carries every
commune with all four of its official spellings, derived from OpenStreetMap
boundary data, so the table builds itself and stays right when a commune is
renamed or merged. Two communes did merge in 2023; a hand-written list would
still have the old names in it.

What this deliberately does *not* do is touch anything it does not recognise.
Kirchberg, Belval and Clausen are quarters, not communes: they match no entry
and pass through untouched. Collapsing them into "Luxembourg" would throw away
the more useful answer to "where is this?".
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

COMMUNES = Path(__file__).resolve().parent / "communes_lu.json"

# Suffixes that mark the town rather than name it. "Luxembourg-Stadt" is the
# capital; so is "Luxembourg City". Stripped before matching, never after —
# no commune's real name ends in one of these.
_SUFFIX = re.compile(
    r"[\s,-]*(stadt|city|ville|stad|centre|zentrum)\s*$",
    re.IGNORECASE,
)


def _fold(s: str) -> str:
    """Lowercase, strip accents, keep letters. Péiteng and peiteng agree."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s)


@lru_cache(maxsize=1)
def _index() -> Dict[str, str]:
    """Every known spelling -> the name to display."""
    if not COMMUNES.exists():
        return {}
    table: Dict[str, str] = {}
    for c in json.loads(COMMUNES.read_text(encoding="utf-8")):
        display = c["name"]
        spellings = set(c.get("names") or [])
        spellings.update(
            c.get(k, "") for k in ("name", "name_lb", "name_fr", "name_de")
        )
        for s in spellings:
            if s:
                table[_fold(s)] = display
    return table


# Short forms no commune list contains, because they are not names — they are
# what a writer uses when the full one is obvious from context.
_ALIASES = {
    "lux": "Luxembourg",
    "luxbg": "Luxembourg",
}

# Short forms that name more than one commune, and the canton that settles it.
# "Esch" means Esch-sur-Alzette to almost everyone — the country's second city,
# and where both the Rockhal and the Kulturfabrik file their events — but
# Esch-sur-Sûre exists too, and mapping blindly would move its events 50km into
# the wrong half of the country. Without a canton the input is left alone: an
# inconsistent spelling is a smaller problem than a confident wrong answer.
_AMBIGUOUS = {
    "esch": {
        "eschsuralzette": "Esch-sur-Alzette",
        "wiltz": "Esch-sur-Sûre",
    },
}


def canonical_town(town: Optional[str], canton: Optional[str] = None) -> str:
    """The one spelling for this town, or the input unchanged.

    Unchanged is the common case and the safe one: venue names, quarters and
    foreign towns all arrive here too, and guessing at them would be worse than
    leaving them alone.

    `canton` is consulted only for short forms that genuinely name more than
    one commune. It never overrides a name the commune list already knows.
    """
    raw = (town or "").strip()
    if not raw:
        return ""

    index = _index()
    folded = _fold(raw)
    hit = index.get(folded)
    if hit:
        return hit

    if folded in _ALIASES:
        return _ALIASES[folded]

    choices = _AMBIGUOUS.get(folded)
    if choices:
        # No canton, or one we do not recognise: leave it, do not guess.
        return choices.get(_fold(canton or ""), raw)

    # "Luxembourg-Stadt" -> "Luxembourg". Only if the remainder is a commune;
    # otherwise "Belval Centre" would lose a word for nothing.
    stripped = _SUFFIX.sub("", raw).strip(" ,-")
    if stripped and stripped != raw:
        hit = index.get(_fold(stripped))
        if hit:
            return hit

    return raw
