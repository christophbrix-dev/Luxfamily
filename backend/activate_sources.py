#!/usr/bin/env python3
"""Switch on the sources that were shown to work, and only those.

Every source starts disabled, which is the right default: nothing is crawled
until a person says so. Turning them on is therefore a deliberate act, and this
records which ones and why rather than leaving it as a click in a console that
nobody can review later.

The list below is not a guess. Each name produced events in a trial run against
a scratch database, through the real importer path, with the results checked
for being in the future and for carrying a correct town.

    python3 activate_sources.py            # show what would change
    python3 activate_sources.py --write    # change it

This touches the database named in backend/.env — the local one during
development. Production runs its own database and needs this run against it
too; activating here does not activate there.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from motor.motor_asyncio import AsyncIOMotorClient

from db_config import mongo_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("activate_sources")

# Exact source name -> what the trial run returned.
#
# Exact, not a fragment, and that is the whole point. A first version matched
# on substrings and picked the wrong source three times out of eleven:
# "Rockhal" also matches "Rockhal (Theater)", "Dudelange" also matches
# "opderschmelz Dudelange" — which failed with 404 in the trial — and
# "Echternach" also matches "Echternach (Gemeng)". Every one of those would
# have switched on a source nobody had tested, under a note claiming it had
# been.
WORKING = {
    "Rockhal — Sitemap":                    "20 events — hit the page cap, more available",
    "Philharmonie Luxembourg — Sitemap":    "19 events",
    "Sanem — Sitemap":                      "13 events",
    "Mudam Luxembourg — Sitemap":           "6 events",
    "Park Sënnesräich — Sitemap":           "2 events",
    "Visit Luxembourg — Sitemap":           "1 event",
    "Parc Merveilleux — Sitemap":           "1 event",
    "Neimënster Cultural Centre — Sitemap": "1 event",
    "Kulturfabrik Esch — Sitemap":          "1 event",
    "Echternach — Sitemap":                 "1 event",
    "Dudelange — Sitemap":                  "1 event",
}

# Rockhal returned exactly the default budget of 20, which means the cap bound
# and not the source: its sitemap holds 1165 event pages. Raised for this one
# source only, and to a number that was measured rather than picked.
#
# 60 pages gave 50 events, 200 gave 90 — and all 90 fall in the future, so the
# freshness ordering is spending the budget on the live calendar rather than on
# the archive. Going deeper buys little: the remaining pages are past shows.
# Rockhal declares no crawl delay, so our own two-second minimum applies and
# 200 pages costs about seven minutes against their server. That is the trade
# this number represents.
PAGE_BUDGET = {"Rockhal — Sitemap": 200}


async def run(write: bool) -> int:
    mongo_url, db_name = mongo_settings()
    db = AsyncIOMotorClient(mongo_url)[db_name]

    log.info("Database: %s\n", db_name)
    changed = missing = already = 0

    for name, note in WORKING.items():
        source = await db.sources.find_one(
            {"name": name},
            {"_id": 1, "name": 1, "active": 1, "selectors": 1},
        )
        if not source:
            log.warning("    ?  %-34s no source with this exact name", name[:34])
            missing += 1
            continue

        update: dict = {}
        if not source.get("active"):
            update["active"] = True
        budget = PAGE_BUDGET.get(name)
        if budget and (source.get("selectors") or {}).get("max_pages") != budget:
            update["selectors"] = {**(source.get("selectors") or {}), "max_pages": budget}

        if not update:
            log.info("    =  %-22s already on", source["name"][:34])
            already += 1
            continue

        extra = f", max_pages={budget}" if "selectors" in update else ""
        log.info("    +  %-34s %s%s", source["name"][:34], note, extra)
        changed += 1
        if write:
            await db.sources.update_one({"_id": source["_id"]}, {"$set": update})

    log.info("\n%d to change, %d already on, %d not found.", changed, already, missing)
    if changed and not write:
        log.info("Dry run. Re-run with --write to apply.")
    elif changed:
        total = await db.sources.count_documents({"active": True})
        log.info("Applied. %d sources are now active.", total)
    return 1 if missing else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply the changes")
    sys.exit(asyncio.run(run(ap.parse_args().write)))


if __name__ == "__main__":
    main()
