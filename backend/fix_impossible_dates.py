#!/usr/bin/env python3
"""Find events dated in a year nobody meant, and take them out of the lists.

One event arrived as "Kreative Schreifatelier", start_date 2926-09-26 — a
single mistyped digit at the source. It is a well-formed date, so nothing
objected: not the importer, not the API, not the app. It simply sat at the far
end of every list sorted by date, a thousand years out, forever.

The importer refuses these now (see `_plausible_year` in importers.py), but
dedup matches on external_id, so an event already stored is never rewritten. A
re-crawl does not clean this up. This does.

    python3 fix_impossible_dates.py            # show what would change
    python3 fix_impossible_dates.py --write    # change it

Hidden, not deleted — `published: False` plus a `date_flag` saying why, the
same treatment check_family_safe.py gives its findings. The event is probably
real; only its date is wrong, and guessing which digit was meant is not
something a script should do. Clear `date_flag` and set `published` to publish
it again once the date is corrected by hand.
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorClient

from db_config import mongo_settings
from importers import YEARS_AHEAD, YEARS_BACK, _plausible_year

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("fix_impossible_dates")

FIELDS = ("start_date", "end_date")


def _bad_fields(ev: dict) -> list[tuple[str, str]]:
    out = []
    for field in FIELDS:
        value = ev.get(field)
        if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
            if not _plausible_year(value):
                out.append((field, value))
    return out


async def run(write: bool) -> int:
    mongo_url, db_name = mongo_settings()
    db = AsyncIOMotorClient(mongo_url)[db_name]

    findings = []
    async for ev in db.events.find(
        {}, {"title": 1, "start_date": 1, "end_date": 1, "source_id": 1}
    ):
        bad = _bad_fields(ev)
        if bad:
            findings.append((ev, bad))

    if not findings:
        log.info(
            "No event is dated outside %d years back or %d ahead.",
            YEARS_BACK, YEARS_AHEAD,
        )
        return 0

    log.info("%d event(s) carry an impossible date:", len(findings))
    for ev, bad in findings:
        title = (ev.get("title") or {}).get("de") or (ev.get("title") or {}).get("en") or "?"
        for field, value in bad:
            log.info("    %-44s %s = %s", title[:44], field, value)

    if not write:
        log.info("\nDry run. Re-run with --write to hide them.")
        return len(findings)

    hidden = 0
    for ev, bad in findings:
        result = await db.events.update_one(
            {"_id": ev["_id"]},
            {"$set": {
                "published": False,
                "date_flag": {field: value for field, value in bad},
            }},
        )
        hidden += result.modified_count

    log.info("\nHid %d event(s). Clear `date_flag` to publish again.", hidden)
    return hidden


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="hide what was found")
    asyncio.run(run(ap.parse_args().write))


if __name__ == "__main__":
    main()
