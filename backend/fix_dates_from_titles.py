#!/usr/bin/env python3
"""Put the events back on the day their own title names.

Twenty-four stored events sit on the day they were crawled instead of the day
they happen. The importer took a page's first `<time>` tag — "13:15" — and
`dateutil` filled the missing date half from today without saying so. That is
fixed for new imports, but dedup matches on external_id, so an event already
stored is never rewritten: a re-crawl does not repair these. This does.

    python3 fix_dates_from_titles.py            # show what would change
    python3 fix_dates_from_titles.py --write    # change it

Only titles that end in a date after a separator are touched:

    "Le coin des mini monstres | 24.10.2026 13:15"   ->  2026-10-24
    "Lunchtime at Mudam – 4 Sept 2026"               ->  2026-09-04

A date anywhere else in a title is left alone. Parc Merveilleux writes
"…Sommersaison (21/03/2026 – 15/10/2026)", and that first date opens a season
rather than naming a day — moving the event to the first day of summer would
be a different kind of wrong. See `date_from_title` for the rule.

The old value is kept in `date_corrected`, so a wrong correction can be found
and undone rather than merely regretted.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne

from db_config import mongo_settings
from importers import date_from_title

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("fix_dates_from_titles")

LANGS = ("de", "en", "fr")


def _title(ev: dict) -> str:
    field = ev.get("title") or {}
    for lang in LANGS:
        if isinstance(field.get(lang), str) and field[lang].strip():
            return field[lang]
    return ""


async def run(write: bool) -> int:
    mongo_url, db_name = mongo_settings()
    db = AsyncIOMotorClient(mongo_url)[db_name]

    ops, rows = [], []
    async for ev in db.events.find({}, {"title": 1, "start_date": 1, "source_name": 1}):
        stated = date_from_title(_title(ev))
        if not stated or stated == ev.get("start_date"):
            continue
        rows.append((ev.get("start_date"), stated, _title(ev), ev.get("source_name", "")))
        ops.append(UpdateOne(
            {"_id": ev["_id"]},
            {"$set": {
                "start_date": stated,
                "date_corrected": {
                    "was": ev.get("start_date"),
                    "from_title": stated,
                    "at": datetime.now(timezone.utc).isoformat(),
                },
            }},
        ))

    if not ops:
        log.info("No event carries a title date that differs from its start_date.")
        return 0

    log.info("%d event(s) are stored on a different day than their title says:\n", len(ops))
    for was, now, title, source in rows:
        log.info("    %s -> %s   %-44s %s", was, now, title[:44], source[:26])

    by_source: dict[str, int] = {}
    for _, _, _, source in rows:
        by_source[source] = by_source.get(source, 0) + 1
    log.info("")
    for source, count in sorted(by_source.items(), key=lambda kv: -kv[1]):
        log.info("    %3d  %s", count, source)

    if not write:
        log.info("\nDry run. Re-run with --write to apply.")
        return len(ops)

    result = await db.events.bulk_write(ops, ordered=False)
    log.info("\nMoved %d event(s). The old value is in `date_corrected`.",
             result.modified_count)
    return result.modified_count


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply the corrections")
    asyncio.run(run(ap.parse_args().write))


if __name__ == "__main__":
    main()
