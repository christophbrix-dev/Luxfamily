#!/usr/bin/env python3
"""Re-file stored places against the current taxonomy.

Christoph asked whether the app has all of Luxembourg's swimming pools. It had
fourteen of the twenty-four that OpenStreetMap knows by name — and seven of the
missing ten were not missing at all. They were filed as splash pads.

`leisure=water_park` was listed under both `water_playground` and `swimming`.
The first matching category wins, `water_playground` comes first in the file,
and so AquaNat'Our, Piscine Piko, Piscine Plein-Air Dudelange, Remich, Vianden,
Freibad Troisvierges and the Réidener Schwämm all became water playgrounds.
Anyone filtering for "Schwämm" found none of them.

The taxonomy is fixed, but a fixed taxonomy only helps the next ingest, and
that means downloading the country extract again. Every place keeps its
original OSM tags in `tags_raw`, so the same decision can simply be made again
here, against what is already stored.

    python3 recategorise_places.py            # show what would move
    python3 recategorise_places.py --write    # move it

Places whose category does not change are left completely alone. What this
cannot do is *add* anything: a place the old rules rejected outright — the
Piscine ouverte d'Oberkorn, dropped for `access=customers` — is not in the
database to be re-filed. That one needs the ingest to run again.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

from db_config import mongo_settings
from osm_taxonomy import CATEGORIES

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("recategorise_places")


# Every bracket group in a filter fragment, and every form the taxonomy uses:
#   ["k"="v"]   equals        ["k"~"re"]  matches        ["k"!~"re"]  does not
_CLAUSE = re.compile(r'\["([^"]+)"(?:(!?[~=])"([^"]+)")?\]')


def _matches(filter_fragment: str, tags: dict) -> bool:
    """True when an Overpass filter fragment describes these tags.

    Every clause has to be understood *and* satisfied. The first version of
    this read only the `="` form and quietly ignored the rest, which made
    `["amenity"="shelter"]["shelter_type"~"picnic_shelter|…"]` mean "any
    shelter at all" — and the dry run duly offered to refile a neolithic house
    as a picnic hut. A constraint that cannot be read must never count as met.
    """
    clauses = _CLAUSE.findall(filter_fragment)
    if not clauses or len(clauses) != filter_fragment.count("["):
        return False        # something in there we do not understand
    for key, op, value in clauses:
        actual = tags.get(key)
        if not op:                       # ["k"] — the key just has to be there
            if actual is None:
                return False
        elif op == "=":
            if actual != value:
                return False
        elif op == "~":
            if actual is None or not re.search(value, actual):
                return False
        elif op == "!~":
            if actual is not None and re.search(value, actual):
                return False
        else:
            return False
    return True


NAME_KEYS = ("name", "name:lb", "name:de", "name:fr", "name:en")


def classify(tags: dict) -> str | None:
    """The category these tags belong to, decided the way the ingest decides.

    Not merely "first filter that matches": a category can decline what it
    matched, and the item then belongs to the next one. `swimming` matches
    every `leisure=water_park` and declines the unnamed ones, which are the
    paddling pools in village parks. Replicating only the matching half moved
    "Wasserspielplatz, Biwer" into the swimming pools — the dry run caught it.
    """
    for kind, cat in CATEGORIES.items():
        if not any(_matches(f, tags) for f in cat.get("filters", [])):
            continue
        if cat.get("require_name") and not any(tags.get(k) for k in NAME_KEYS):
            continue        # matched, declined; try the next category
        closed = {"private", "no"} if cat.get("allow_customers") else {"private", "no", "customers"}
        if tags.get("access") in closed:
            return None     # closed to the public in every category
        if cat.get("min_area_m2") or cat.get("relations_only"):
            return None     # decided on geometry the ingest has and we do not
        return kind
    return None


async def run(write: bool) -> int:
    mongo_url, db_name = mongo_settings()
    db = AsyncIOMotorClient(mongo_url)[db_name]

    ops, moves = [], []
    async for place in db.places.find(
        {"tags_raw": {"$exists": True}}, {"name": 1, "kind": 1, "tags_raw": 1, "commune": 1}
    ):
        tags = place.get("tags_raw") or {}
        if not isinstance(tags, dict):
            continue
        wanted = classify(tags)
        if not wanted or wanted == place.get("kind"):
            continue
        moves.append((place.get("kind"), wanted, place.get("name", "?"), place.get("commune", "")))
        ops.append(UpdateOne(
            {"_id": place["_id"]},
            {"$set": {"kind": wanted, "group": CATEGORIES[wanted]["group"]}},
        ))

    if not ops:
        log.info("Every place is already filed where the current taxonomy puts it.")
        return 0

    log.info("%d place(s) would move:\n", len(ops))
    for was, now, name, commune in sorted(moves, key=lambda m: (m[0] or "", m[1])):
        log.info("    %-18s -> %-18s %-38s %s", was, now, name[:38], commune[:18])

    counts: dict[tuple, int] = {}
    for was, now, _, _ in moves:
        counts[(was, now)] = counts.get((was, now), 0) + 1
    log.info("")
    for (was, now), count in sorted(counts.items(), key=lambda kv: -kv[1]):
        log.info("    %4d  %s -> %s", count, was, now)

    if not write:
        log.info("\nDry run. Re-run with --write to apply.")
        return len(ops)

    result = await db.places.bulk_write(ops, ordered=False)
    log.info("\nMoved %d place(s).", result.modified_count)
    return result.modified_count


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply the moves")
    asyncio.run(run(ap.parse_args().write))


if __name__ == "__main__":
    main()
