"""Which of the app's categories an event actually belongs to.

The filter had one bucket. 437 of 528 events carried "Culture, Festivals",
because that is the default on the 52 commune sources and almost nothing ever
overrode it — so choosing "Festivals" returned nearly everything and choosing
"Playgrounds" returned one row. A filter that cannot separate is not a filter.

"Festivals" on a commune feed is also a claim, and mostly a wrong one: those
feeds carry road closures, waste collection and council notices alongside the
village fête. The default is therefore the neutral "Culture", and an event is
promoted out of it only when its own text says something.

What this can reach is limited by what there is to read. Measured across the
live database, 189 of 528 events carry a recognisable signal in their title or
short text — the descriptions add nothing, because the median description is
17 characters and 213 events have none at all. So roughly a third gets a real
category and the rest keeps the default, which is an honest improvement rather
than a complete one.

The vocabulary is fixed by the app: a category the frontend does not know is
not a category, it is an event that no filter will ever return. One source is
configured with "Sports", which is not in the list — see test_categorise for
the check that keeps the two in step.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Exactly the frontend's CATEGORIES in src/data/places.ts. Kept in the same
# order so a diff between the two files is readable.
CATEGORIES: Tuple[str, ...] = (
    "Animals",
    "Culture",
    "Playgrounds",
    "Water",
    "Nature",
    "Workshops",
    "Festivals",
)

# Signals in the four languages events arrive in. Deliberately narrow: a word
# that only sometimes indicates the category is worse than no signal, because
# a wrong category is invisible — the event simply stops appearing under the
# right one and starts appearing under a wrong one.
SIGNALS: Dict[str, str] = {
    "Workshops": (
        r"workshop|atelier(?!s? de r[ée]paration)|coursen?\b|kachcours|"
        r"kurs\b|kursus|stage\s+(?:d'|de\s)|formatioun|initiation"
    ),
    "Festivals": (
        r"f[eê]te|festival|kirmes|kiermes|fouer|foire|braderie|"
        r"maart\b|march[ée]\b|market\b|floumoart|brocante|"
        r"duerffest|dorffest|schueberfouer|karneval|kavalkad|f[ée]st\b"
    ),
    "Animals": (
        r"d[ée]ierepark|tierpark|zoo\b|ferme p[ée]dagogique|"
        r"bauerenhaff|streichelzoo|aquarium|volière|päerd|chevaux"
    ),
    "Water": (
        r"schwamm|piscine|swimming|baden\b|bued\b|"
        r"plage\b|strand\b|kayak|kanu|cano[eë]|stand[- ]?up[- ]?paddle|pedalo"
    ),
    "Nature": (
        r"wanderung|randonn[ée]e|naturpad|naturlehrpfad|bësch\b|forêt|"
        r"jardin|gaart\b|arboretum|botanique|vogelkundlech|"
        r"promenade guid[ée]e|geführte wanderung|naturschutz"
    ),
    "Playgrounds": (
        r"spillplaz|spielplatz|aire de jeux|playground|"
        r"spillfest|kannerspillplaz"
    ),
    # Culture is the fallback, so its signal only has to catch the cases where
    # a source default is something else and the event is plainly cultural.
    "Culture": (
        r"konzert|concert|musek\b|musique\b|theater|théâtre|spectacle|"
        r"exposition|ausstellung|vernissage|mus[ée]e|kino|cinéma|"
        r"lesung|conf[ée]rence|opér|ballet"
    ),
}

_COMPILED = {name: re.compile(pattern, re.I) for name, pattern in SIGNALS.items()}

# Checked most-specific first: a "Kannerfest am Spillplaz" is a festival, and
# a guided walk through a park is Nature rather than a generic outing. Culture
# comes last because it is also the fallback.
ORDER = ("Playgrounds", "Animals", "Water", "Workshops", "Festivals", "Nature", "Culture")

FALLBACK = ["Culture"]

# A default made only of these says nothing in particular: it is what every
# commune feed carries because somebody had to put something. Anything else was
# chosen for that source — the Parc Merveilleux is configured as Animals,
# Nature, Playgrounds — and a keyword in one event's title is a worse answer
# than that. A first version overrode it anyway and lost the app's only
# Playgrounds event to a generic "Culture".
GENERIC = {"Culture", "Festivals"}


def categorise(*parts: str, default: List[str] | None = None) -> List[str]:
    """The categories this event belongs to.

    A curated source default wins outright. Otherwise the event's own text
    decides, and failing that the default stands.

    Returns at most two: more than that reads as "everything" in a row of
    filter chips, and the second is already the weaker guess.
    """
    fallback = list(default or FALLBACK)
    if default and not set(default) <= GENERIC:
        return fallback

    text = " ".join(p for p in parts if p)
    if not text.strip():
        return fallback

    found = [name for name in ORDER if _COMPILED[name].search(text)]
    return found[:2] if found else fallback
