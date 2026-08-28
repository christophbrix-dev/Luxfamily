#!/usr/bin/env python3
"""Give the category filter something to separate, on data already stored.

The filter had one bucket: 437 of 528 events carried "Culture, Festivals", so
choosing "Festivals" returned nearly everything and choosing "Playgrounds"
returned a single row.

Two things are corrected.

The source defaults. 52 commune feeds are configured as "Culture, Festivals",
and a commune agenda is not a run of festivals — it carries road closures,
waste collection and council notices next to the village fête. They become the
neutral "Culture", and an event earns "Festivals" from its own text.

Then the stored events, re-read through categorise(). A curated source default
wins outright: the Parc Merveilleux is configured Animals, Nature, Playgrounds
and no keyword in one title should overrule that.

    python3 fix_categories.py            # show what would change
    python3 fix_categories.py --write    # change it

Also reports any category the app cannot filter on. One source is configured
with "Sports", which is not in the frontend's list — an event carrying it
would be returned by no filter at all.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import logging
import sys

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

from categorise import CATEGORIES, categorise
from db_config import mongo_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("fix_categories")

GENERIC_COMMUNE_DEFAULT = ["Culture", "Festivals"]
NEUTRAL = ["Culture"]


def _text(doc: dict) -> str:
    out = []
    for field in ("title", "short"):
        value = doc.get(field)
        if isinstance(value, dict):
            out.extend(v for v in value.values() if isinstance(v, str))
        elif isinstance(value, str):
            out.append(value)
    return " ".join(out)


async def run(write: bool) -> int:
    mongo_url, db_name = mongo_settings()
    db = AsyncIOMotorClient(mongo_url)[db_name]

    # --- sources -----------------------------------------------------------
    unknown = collections.Counter()
    source_ops, defaults = [], {}
    async for src in db.sources.find({}, {"id": 1, "name": 1, "category_default": 1}):
        current = src.get("category_default") or NEUTRAL
        for name in current:
            if name not in CATEGORIES:
                unknown[f"{name} ({src.get('name', '?')[:30]})"] += 1
        new = NEUTRAL if current == GENERIC_COMMUNE_DEFAULT else current
        defaults[src["id"]] = new
        if new != current:
            source_ops.append(UpdateOne({"_id": src["_id"]}, {"$set": {"category_default": new}}))

    if unknown:
        log.warning("Categories the app cannot filter on:")
        for name, _ in unknown.most_common():
            log.warning("    %s", name)
        log.warning("")

    # --- events ------------------------------------------------------------
    event_ops = []
    before, after = collections.Counter(), collections.Counter()
    async for ev in db.events.find({}, {"title": 1, "short": 1, "category": 1, "source_id": 1}):
        old = ev.get("category") or []
        new = categorise(_text(ev), default=defaults.get(ev.get("source_id"), NEUTRAL))
        for name in old:
            before[name] += 1
        for name in new:
            after[name] += 1
        if new != old:
            event_ops.append(UpdateOne({"_id": ev["_id"]}, {"$set": {"category": new}}))

    log.info("%-14s %8s %8s", "Category", "before", "after")
    for name in CATEGORIES:
        log.info("  %-14s %6d   %6d", name, before[name], after[name])
    log.info("\n%d source default(s) and %d event(s) would change.",
             len(source_ops), len(event_ops))

    if not write:
        log.info("Dry run. Re-run with --write to apply.")
        return len(event_ops)

    if source_ops:
        await db.sources.bulk_write(source_ops, ordered=False)
    if event_ops:
        result = await db.events.bulk_write(event_ops, ordered=False)
        log.info("Updated %d event(s).", result.modified_count)
    return len(event_ops)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply the changes")
    sys.exit(0 if asyncio.run(run(ap.parse_args().write)) >= 0 else 1)


if __name__ == "__main__":
    main()
