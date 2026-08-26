#!/usr/bin/env python3
"""Bring already-stored events onto one spelling per town.

The importers normalise from now on, but the events imported before that keep
whatever their source wrote. The live database held five names for the capital
alone. This rewrites the existing ones.

    python3 normalise_towns.py            # show what would change
    python3 normalise_towns.py --write    # change it

Only `town` is touched, and only where canonical_town returns something
different — a venue name or a city quarter is left exactly as it is. Safe to
run twice: the second run reports nothing to do.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import logging

from motor.motor_asyncio import AsyncIOMotorClient

from db_config import mongo_settings
from pymongo import UpdateOne

from town_names import canonical_town

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("normalise_towns")

# See db_config: reads backend/.env and refuses when DB_NAME is missing.

COLLECTIONS = ("events", "places")


async def run(write: bool) -> int:
    mongo_url, db_name = mongo_settings()
    mongo = AsyncIOMotorClient(mongo_url)
    db = mongo[db_name]
    total_changed = 0
    try:
        for name in COLLECTIONS:
            coll = db[name]
            ops, moves = [], collections.Counter()
            # The canton comes along because "Esch" names two communes and
            # only the canton distinguishes them; without it the name is left
            # alone rather than guessed at.
            async for doc in coll.find({}, {"_id": 1, "town": 1, "canton": 1}):
                old = (doc.get("town") or "").strip()
                new = canonical_town(old, doc.get("canton"))
                if new and new != old:
                    moves[(old, new)] += 1
                    ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"town": new}}))

            if not ops:
                log.info("%s: nothing to change", name)
                continue

            log.info("%s: %d documents across %d spellings", name, len(ops), len(moves))
            for (old, new), n in moves.most_common(20):
                log.info("   %-24s -> %-20s %d", old, new, n)

            total_changed += len(ops)
            if write:
                res = await coll.bulk_write(ops, ordered=False)
                log.info("   written: %d modified", res.modified_count)
    finally:
        mongo.close()

    if not write:
        log.info("\nPreview only. %d documents would change. Re-run with --write.",
                 total_changed)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply the changes")
    return asyncio.run(run(ap.parse_args().write))


if __name__ == "__main__":
    raise SystemExit(main())
