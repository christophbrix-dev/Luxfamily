"""The age an event states, and an honest silence when it states none.

Every imported event was stored as `age_min = 0, age_max = 99`. In an app for
families that is not "unknown" — it is "suitable for everyone, newborns
included". A Trivium concert at the Rockhal carried it.

Measured against the live data, 14 of 528 events name an age anywhere in their
text. So this cannot fill the gap, and it is not supposed to: the point is to
read the few that say something and to mark the rest as unstated, so the app
can tell the reader "no age given" instead of implying a toddler is welcome.

Christoph's call on what happens then, and it is the right one: those events
stay visible with a note rather than disappearing. Parents decide — but only
if we admit what we do not know.

The traps are numbers that are not ages. "50 Joer Guiden a Scouten" is an
anniversary. "ab 18:30" is half past six. A year is not an age. So a number
counts only when a word for "years" or "children" stands with it.
"""
from __future__ import annotations

import re
from typing import NamedTuple, Optional

YEARS = r"(?:joer|jahren?|jahre|ans|années?|years?|yrs?)"


class AgeHint(NamedTuple):
    minimum: Optional[int]
    maximum: Optional[int]
    source: str          # "event" when read from the page, else "unknown"


# "von 4 bis 10 Joer", "de 2 à 5 ans", "6-12 Jahre". Ranges first: a range also
# matches the "from N" pattern, and would otherwise lose its upper bound.
_RANGE = re.compile(
    rf"(?:vun|von|de|from|entre)\s*(\d{{1,2}})\s*(?:bis|à|a|to|-|–|et)\s*(\d{{1,2}})\s*{YEARS}"
    rf"|(?<!\d)(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})\s*{YEARS}",
    re.I,
)

# "ab 6 Joer", "à partir de 12 ans", "for children from 3 years"
_FROM = re.compile(
    rf"(?:ab|vun|von|from|à partir de|a partir de|dès)\s*(\d{{1,2}})\s*{YEARS}",
    re.I,
)

# "bis 12 Joer", "jusqu'à 10 ans"
_UPTO = re.compile(
    rf"(?:bis|jusqu'?[aà]|up to|max\.?)\s*(\d{{1,2}})\s*{YEARS}",
    re.I,
)

# Anniversaries and durations wear the same clothes as ages: a number and the
# word "years". Removed before ages are looked for, so "50 Joer Guiden a
# Scouten" cannot become a minimum age of fifty.
_NOT_AN_AGE = re.compile(
    rf"(?:s?[ei]t|zënter|depuis|since)\s*\d{{1,3}}\s*{YEARS}"
    rf"|\d{{1,3}}\s*{YEARS}\s*(?:jubil\w*|bestoen|partnerschaft|anniversaire"
    rf"|guiden|scouten|verein|club|gemeng|commune|du\s+club)",
    re.I,
)


def read_age(*parts: Optional[str]) -> AgeHint:
    """The age range this text states, or an honest "unstated"."""
    text = " ".join(p for p in parts if p)
    if not text.strip():
        return AgeHint(None, None, "unknown")

    # Take the anniversaries out before looking for ages, so "50 Joer Guiden"
    # cannot become a minimum age of fifty.
    cleaned = _NOT_AN_AGE.sub(" ", text)

    match = _RANGE.search(cleaned)
    if match:
        low = match.group(1) or match.group(3)
        high = match.group(2) or match.group(4)
        lo, hi = int(low), int(high)
        if lo > hi or hi > 99:
            # "vun 40 bis 10 Joer" is not a range, it is a typo or a misread.
            # Falling through would let the narrower patterns below read "bis
            # 10 Joer" out of it and return an upper bound of 10 — a confident
            # answer extracted from nonsense. Nothing is the honest reading.
            return AgeHint(None, None, "unknown")
        return AgeHint(lo, hi, "event")

    match = _FROM.search(cleaned)
    if match:
        lo = int(match.group(1))
        if lo <= 99:
            return AgeHint(lo, None, "event")

    match = _UPTO.search(cleaned)
    if match:
        hi = int(match.group(1))
        if hi <= 99:
            return AgeHint(None, hi, "event")

    return AgeHint(None, None, "unknown")
