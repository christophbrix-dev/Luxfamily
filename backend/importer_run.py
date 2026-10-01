"""One crawl-and-place run, and the lease that keeps it single.

This used to live inside `server.py`, where it was reachable only by starting
the server. That was the whole bug behind this module: the scheduler lives in
the server process, the server process on a laptop lives only as long as
somebody keeps a terminal open, and so a scheduler that was switched on
correctly on 2026-09-30 had still not run a single time by the next morning.
The switch was right; there was simply nothing alive to act on it.

So the run moves out here, where two callers can reach it:

  - `server.py`, for a deployment that genuinely stays up, and
  - `run_importers.py`, a one-shot command that macOS launchd calls three
    times a day — and that launchd *re-runs on wake* if the machine was asleep
    when the time passed. That last property is the reason this exists; an
    in-process cron cannot have it.

Both go through the same lease in Mongo, so it does not matter if a laptop, a
container and a scheduled job all decide to crawl at once: the first takes the
lease, the others step aside.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from pymongo.errors import DuplicateKeyError

from check_family_safe import audit_family_safety
from geocode_events import geocode_pending
from importers import run_all_active

logger = logging.getLogger(__name__)

LOCK_ID = "importers"
LEASE_MINUTES = 60

# One identity per process, so a release can only clear a lease this process
# actually holds. A crashed holder is not blocking: the lease carries an expiry
# and the next caller takes it over once that has passed.
WORKER_ID = str(uuid.uuid4())


async def acquire_lease(db) -> bool:
    """Claim the right to run the importers for the next lease window.

    Uvicorn runs several workers and the deployment may run several replicas —
    each starts its own scheduler, so every scheduled tick crawled every feed
    N times over. This takes a short lease in Mongo so exactly one of them does
    the work; the lease expires on its own if a worker dies mid-run.
    """
    now = datetime.now(timezone.utc)
    try:
        await db.locks.insert_one({"_id": LOCK_ID, "lease_until": now})
    except DuplicateKeyError:
        pass  # lock document already exists, which is the normal case
    result = await db.locks.update_one(
        {"_id": LOCK_ID, "lease_until": {"$lte": now}},
        {
            "$set": {
                "lease_until": now + timedelta(minutes=LEASE_MINUTES),
                "holder": WORKER_ID,
                "acquired_at": now,
            }
        },
    )
    return result.modified_count == 1


async def release_lease(db) -> None:
    await db.locks.update_one(
        {"_id": LOCK_ID, "holder": WORKER_ID},
        {"$set": {"lease_until": datetime.now(timezone.utc)}},
    )


async def run_once(db) -> bool:
    """Crawl every active source, place what arrived, then audit the whole set.

    Returns whether this caller got the lease and did the work — `False` means
    somebody else was already running, which is a normal outcome and not an
    error.

    Geocoding runs here rather than as a separate job because it only has work
    to do once an import has produced some. Left as a manual script it was
    never run at all, and 122 of 304 events sat on the same generic point for
    Luxembourg City.

    It runs under the same lease as the import and after it, so two workers
    cannot both be resolving the same events, and a batch is capped — each
    unresolved event may cost a request to the geoportal, which is somebody
    else's service.

    Each stage catches its own failures. A geocoding failure must not make the
    import look failed: the events are already stored, they simply keep the
    coordinate they arrived with.
    """
    if not await acquire_lease(db):
        logger.info("Importer run skipped — another worker holds the lease")
        return False
    try:
        try:
            results = await run_all_active(db)
            logger.info("Importer run finished for %d sources", len(results))
        except Exception:
            logger.exception("Scheduled importer run failed")

        try:
            # Synchronous, with its own connection: resolve() and the geocoders
            # all work against pymongo. A worker thread is cheaper than teaching
            # two database drivers about each other.
            counts = await asyncio.to_thread(geocode_pending)
            if counts:
                logger.info(
                    "Geocoded %d events (%s)",
                    sum(counts.values()),
                    ", ".join(f"{k}={v}" for k, v in sorted(counts.items())),
                )
        except Exception:
            logger.exception("Scheduled geocoding failed")

        try:
            # Ask the family-safety question of the whole database, not just of
            # what arrived. The import filter cannot see events stored before it
            # existed, or an entry an importer wrote without asking, or a source
            # that changed what it publishes after we first read it.
            #
            # Findings are hidden, never deleted: a hit is a question for a
            # person, and an entry that is gone cannot be looked at to decide
            # whether the rule was right. Nothing is expected to turn up — the
            # point is the day something does.
            hidden = await audit_family_safety(db)
            if hidden:
                logger.warning(
                    "Family-safety audit hid %d stored entr(ies) — review family_flag",
                    hidden,
                )
        except Exception:
            logger.exception("Family-safety audit failed")
    finally:
        await release_lease(db)
    return True
