"""Keep NSFW content out of a family app.

Christoph's requirement, and it is the right one: an app parents hand to their
children cannot show pornographic or adult-entertainment content even once. A
single slip costs trust that no apology recovers.

What this refuses is narrow on purpose: brothels, strip clubs, sex parties,
pornography. That is the whole list.

What it deliberately does NOT refuse is the more important half, and it was
Christoph who drew the line:

    "bars oder restaurants können 18+ sein, das ist in ordnung […] nur weil in
     restaurants alkohol angeboten wird, soll es nicht rausfliegen"
    "sonst müsste ja auch die Schueberfouer raus"

He is right, and the Schueberfouer settles it. The country's biggest annual
funfair has beer tents and late nights that are plainly not for small children,
and it is also the family event of the year. An "over 18" marker is not a
reason to hide something; a young adult who wants to turn night into day should
find those events here too. Age belongs in a filter the user controls, not in a
rule that deletes things before anyone sees them.

So there is exactly one category — "explicit" — and no age gate at all.

The remaining difficulty is that every word on the list hides inside an
innocent one, and the innocent one is usually the likelier reading in
Luxembourg:

    "Sextett"           a sextet, six musicians
    "Kartoffelpuffer"   a potato pancake, sold at the Schueberfouer
    "Hardcore-Punk"     a music genre, booked at the Rockhal
    "Ford Escort"       a car, at any oldtimer meet
    "XXX. Editioun"     the thirtieth edition, in Roman numerals
    "Nacktschnecke"     a slug, on a children's nature walk
    "Comic-Strip"       a drawing workshop

Each of those cost a term its place on the list or forced it to carry context.
Where the two readings collide, the innocent one wins: a wrongly shown event
can be reported and removed, a wrongly hidden village festival is never
noticed by anyone.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# Adult entertainment and explicit material, in the languages events arrive in.
#
# Several obvious-looking terms are missing on purpose, each one because of a
# real Luxembourg event it would have caught:
#
#   "puff"      Kartoffelpuffer, Puffreis, puff pastry
#   "hardcore"  a music genre before it is anything else
#   "xxx"       Roman thirty; only kept with film/cinema context
#   "escort"    a Ford; only kept as "escort service"
#
# Sex- and adult-venue words are required to carry their context word rather
# than standing alone, for the same reason.
EXPLICIT = [
    r"porno\w*", r"pornogra\w+", r"pornhub",
    r"erotik(?:film|kino|messe|shop|markt|show)\w*",
    r"salon[- ]?[ée]rotique", r"foire[- ]?[ée]rotique",
    r"sex[- ]?(?:shop|kino|club|party|partys|parties|messe|arbeit|kaufen)",
    r"sexuelle dienstleistung\w*",
    r"strip[- ]?club\w*", r"stripclub\w*", r"strip[- ]?tease\w*", r"striptease\w*",
    r"table[- ]?dance", r"lap[- ]?dance", r"pole[- ]?dance[- ]?show",
    r"bordell\w*", r"brothel\w*", r"maison[- ]close", r"laufhaus",
    r"eros[- ]?center", r"rotlicht\w*", r"red[- ]?light[- ]?district",
    r"escort[- ]?(?:service|agentur|agency|girl|boy)", r"callgirl\w*", r"callboy\w*",
    r"swingerclub\w*", r"swinger[- ]club\w*", r"club[- ]?[ée]changiste",
    r"fetisch[- ]?(?:party|club|markt|messe)", r"fetish[- ]?(?:party|club|market)",
    r"bdsm", r"sm[- ]?studio", r"dominastudio",
    r"nackt(?:bar|club|tanz|party)\w*", r"nudisten?\w*", r"fkk[- ]?(?:club|party)",
    r"peep[- ]?show\w*", r"burlesque[- ]?(?:show|night|revue)",
    r"xxx[- ]?(?:film|kino|movie|cinema)\w*", r"pornokino\w*",
    r"onlyfans",
    # How these places name themselves on their own signage, which is not how
    # a swear-word list names them. "Club libertin" is simply what a swinger
    # club is called in French and in Luxembourg, and the first draft of this
    # file would have let one straight through.
    r"club[- ]libertin\w*", r"soir[ée]e[- ]libertine", r"partouze\w*",
    r"maison de passe", r"salon de massage [ée]rotique", r"erotikmassage\w*",
    r"prostitu\w+", r"prostitutie", r"freudenhaus\w*",
    r"saunaclub\w*", r"sauna[- ]club\w*",      # not a plain sauna, which is a spa
    r"animierbar\w*", r"nachtbar\w*", r"bumslokal\w*",
    r"begleitservice\w*", r"hostessen[- ]?(?:service|agentur)",
    r"modelwohnung\w*", r"terminwohnung\w*",
    r"gogo[- ]?bar\w*", r"go[- ]go[- ]bar\w*",
    r"adult[- ]shop\w*", r"erotikshop\w*", r"erotic[- ]shop\w*",
    r"bordeel\w*", r"seksclub\w*",
]

# Compounds that contain a flagged fragment and mean something else entirely.
# Removed from the text first, so the word inside them cannot trigger a match.
ALLOWED = [
    r"sextett\w*", r"sextet\w*", r"sexta\b", r"sextant\w*",
    r"\w*essex\b", r"middlesex", r"sussex", r"wessex",
    r"nacktschnecke\w*", r"nacktsamer\w*", r"nacktmull\w*",
    r"comic[- ]?strip\w*", r"strip[- ]?art\w*", r"filmstrip\w*",
    r"stripe\w*", r"streifen\w*",
]

_EXPLICIT_RE = re.compile(r"(?<!\w)(?:" + "|".join(EXPLICIT) + r")(?!\w)", re.I)
_ALLOWED_RE = re.compile(r"(?<!\w)(?:" + "|".join(ALLOWED) + r")(?!\w)", re.I)


def assess(*parts: Optional[str]) -> Optional[Tuple[str, str]]:
    """(reason, the matching words) when this must not be shown, else None.

    Takes title, description, categories — whatever the importer has. Any one
    of them is enough: a harmless title over an explicit description is still
    an explicit event.
    """
    text = " ".join(p for p in parts if p)
    if not text.strip():
        return None

    # Take the innocent compounds out first, so "Sextett" cannot leave a "sex"
    # behind for the pattern below to find.
    cleaned = _ALLOWED_RE.sub(" ", text)

    hit = _EXPLICIT_RE.search(cleaned)
    return ("explicit", hit.group(0)) if hit else None


def is_family_safe(*parts: Optional[str]) -> bool:
    """Convenience for callers that only need yes or no."""
    return assess(*parts) is None
