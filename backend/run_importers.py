#!/usr/bin/env python3
"""One crawl, from the command line — the entry point launchd calls.

Why this exists rather than the scheduler inside the server:

The server's scheduler was switched on correctly on 2026-09-30 and had not run
once by the next morning. Nothing was misconfigured. The scheduler lives in the
server process; on a laptop that process lives only as long as somebody keeps a
terminal open, and the three times of day it waits for — 05:00, 12:00, 18:00 —
are times a laptop is usually asleep or shut.

macOS launchd does not have that problem. A `StartCalendarInterval` job whose
time passes while the machine sleeps is run when the machine wakes, and several
missed times collapse into a single run. So the schedule belongs to launchd and
the work belongs here, in something launchd can call without a server.

    python3 run_importers.py              # crawl, geocode, audit
    python3 run_importers.py --quiet      # only the summary and any warnings

Exit codes, because launchd records them and a log nobody reads is the whole
reason this module has a docstring this long:

    0   the run happened, or another holder was already running (not an error)
    1   the database could not be reached, or .env is incomplete

A failing source is **not** exit 1. Sources break all the time — a site moves,
a certificate lapses — and that belongs in the summary, not in a red light that
makes the next one easy to ignore.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from db_config import mongo_settings
from importer_run import run_once

log = logging.getLogger("run_importers")


# httpx logs every request at INFO. A full crawl makes about a thousand of
# them, and launchd appends to one file forever — so the line that actually
# says what the run achieved ends up buried in a day's worth of
# "HTTP/1.1 200 OK". The requests are not the record; what changed in the
# database is. Raised to WARNING so a failing request still shows up.
NOISY_LOGGERS = ("httpx", "httpcore", "urllib3")


def _setup_logging(quiet: bool) -> None:
    """Timestamps on every line, and the chatter turned down.

    launchd appends stdout to one file forever, so a line that does not say
    when it happened is close to useless: the file is a year of runs with no
    way to tell this morning's from last March's.
    """
    logging.basicConfig(
        level=logging.WARNING if quiet else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


async def _snapshot(db) -> dict[str, int]:
    """The numbers worth comparing before and after.

    Upcoming rather than total: a run that adds fifty events which are all in
    the past has not made the app better, and a total alone cannot show that.
    """
    today = date.today().isoformat()
    return {
        "events": await db.events.count_documents({}),
        "upcoming": await db.events.count_documents(
            {"start_date": {"$gte": today}, "published": True}
        ),
        "without_coordinates": await db.events.count_documents(
            {"$or": [{"lat": None}, {"lat": {"$exists": False}}]}
        ),
    }


KEYS = ("events", "upcoming", "without_coordinates")


def _line(snapshot: dict[str, int]) -> str:
    return ", ".join(f"{k}={snapshot[k]}" for k in KEYS)


def _delta(before: dict[str, int], after: dict[str, int]) -> str:
    """Each number with how far it moved.

    The movement is the part worth reading. "events=1010" says nothing on its
    own; "events=1010 (+6)" says the run did something, and "(±0)" says it
    reached every source and found nothing new — which is also an answer.
    """
    parts = []
    for key in KEYS:
        change = after[key] - before[key]
        parts.append(f"{key}={after[key]} ({change:+d})" if change else f"{key}={after[key]} (±0)")
    return ", ".join(parts)


async def main_async(quiet: bool) -> int:
    url, name = mongo_settings()  # raises SystemExit with advice if DB_NAME is unset
    client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=20_000)
    db = client[name]
    try:
        try:
            await db.command("ping")
        except PyMongoError as exc:
            # Named separately from any other failure: an unreachable database
            # is the one thing that makes the whole run pointless, and on this
            # machine it usually means the laptop has no network yet after a
            # wake. Worth its own exit code so launchd's log says which it was.
            log.error("Database not reachable (%s) — nothing was crawled.", type(exc).__name__)
            return 1

        started = datetime.now(timezone.utc)
        before = await _snapshot(db)
        log.info("Start: %s", _line(before))

        did_run = await run_once(db)

        after = await _snapshot(db)
        minutes = (datetime.now(timezone.utc) - started).total_seconds() / 60
        if did_run:
            log.info("Done in %.1f min: %s", minutes, _delta(before, after))
        else:
            # Normal, not a failure: another machine or an overlapping run has
            # the lease. Saying so plainly keeps it out of the error log.
            log.info("Skipped after %.1f min — another holder has the lease.", minutes)
        return 0
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quiet", action="store_true", help="only the summary and warnings")
    args = parser.parse_args()
    _setup_logging(args.quiet)
    return asyncio.run(main_async(args.quiet))


if __name__ == "__main__":
    sys.exit(main())
