#!/usr/bin/env python3
"""Re-read age and price for events that were stored before the parsers existed.

The importers ask the two parsers from now on, but the 528 events already in
the database still carry the constants they were written with: age 0–99 and
price 0.00 for every one of them. Re-crawling does not fix that — dedup matches
on external_id, so an event already stored is never rewritten.

    python3 backfill_age_price.py            # show what would change
    python3 backfill_age_price.py --write    # change it

Most events will end up with *less* stated than before, and that is the point.
An event whose page never mentioned an age had 0–99 written into it, which in
a family app reads as "newborns welcome"; after this it reads as "no age
given", which is what was actually known. The same for the price: a zero meant
free, and 528 events were claiming it.

Safe to run twice — the second run reports nothing to do.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import logging
import sys

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

from age_hints import read_age
from db_config import mongo_settings
from price_hints import read_price

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("backfill_age_price")

# The backend's LocalizedString accepts en/de/fr only — unlike the frontend,
# where `lb` is required. Writing a fourth key here made every event detail
# fail validation with a 500; the localized *content* fields follow the
# backend's contract, and Lëtzebuergesch for the interface comes from the
# frontend's own strings.
LANGS = ("en", "de", "fr")


def _text(doc: dict) -> str:
    """Every language of every prose field — the age may be stated in one only."""
    out = []
    for field in ("title", "short", "description"):
        value = doc.get(field)
        if isinstance(value, dict):
            out.extend(v for v in value.values() if isinstance(v, str))
        elif isinstance(value, str):
            out.append(value)
    return " ".join(out)


def _age_label(age) -> str:
    """"ab 12", "bis 10", "4-10" — a stated minimum has no upper bound."""
    if age.minimum is not None and age.maximum is not None:
        return f"{age.minimum}-{age.maximum}"
    if age.minimum is not None:
        return f"ab {age.minimum}"
    return f"bis {age.maximum}"


def _localized(value: str) -> dict:
    return {lang: value for lang in LANGS}


async def run(write: bool) -> int:
    mongo_url, db_name = mongo_settings()
    db = AsyncIOMotorClient(mongo_url)[db_name]

    ops = []
    tally = collections.Counter()
    samples = []

    async for ev in db.events.find(
        {}, {"title": 1, "short": 1, "description": 1,
             "age_min": 1, "age_max": 1, "age_source": 1,
             "price_adult": 1, "price_source": 1}
    ):
        blob = _text(ev)
        age = read_age(blob)
        price = read_price(blob)

        update: dict = {}

        if ev.get("age_source") != age.source or (
            age.source == "event" and ev.get("age_min") != age.minimum
        ):
            update["age_source"] = age.source
            if age.source == "event":
                update["age_min"] = age.minimum if age.minimum is not None else 0
                update["age_max"] = age.maximum if age.maximum is not None else 99
            tally[f"age -> {age.source}"] += 1

        if ev.get("price_source") != price.source or ev.get("price_adult") != price.adult:
            update["price_adult"] = price.adult
            update["price_child"] = price.adult if price.is_free else None
            update["price_free"] = price.is_free
            update["price_source"] = price.source
            update["price_label"] = _localized(
                "Free entry" if price.is_free
                else f"{price.adult:.2f} €" if price.adult is not None
                else "Price not stated"
            )
            tally[f"price -> {'free' if price.is_free else price.source}"] += 1

        if not update:
            continue
        ops.append(UpdateOne({"_id": ev["_id"]}, {"$set": update}))
        if len(samples) < 6 and (age.source == "event" or price.source == "event"):
            samples.append((
                (ev.get("title") or {}).get("de", "")[:34],
                _age_label(age) if age.source == "event" else "—",
                "gratis" if price.is_free else (f"{price.adult:.2f} €" if price.adult else "—"),
            ))

    if not ops:
        log.info("Nothing to change — every event already matches the parsers.")
        return 0

    log.info("%d event(s) would change:\n", len(ops))
    for label, count in sorted(tally.items()):
        log.info("    %-26s %d", label, count)

    if samples:
        log.info("\n  where something was actually stated:")
        for title, age_s, price_s in samples:
            log.info("    %-36s Alter %-8s Preis %s", title, age_s, price_s)

    if not write:
        log.info("\nDry run. Re-run with --write to apply.")
        return len(ops)

    result = await db.events.bulk_write(ops, ordered=False)
    log.info("\nUpdated %d event(s).", result.modified_count)
    return result.modified_count


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply the changes")
    sys.exit(0 if asyncio.run(run(ap.parse_args().write)) >= 0 else 1)


if __name__ == "__main__":
    main()
