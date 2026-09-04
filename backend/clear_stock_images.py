#!/usr/bin/env python3
"""Remove stock photographs from events, so the app can say it has none.

This file used to do the opposite. It filled every event without an image
with a category-generic Unsplash photo, and the one chosen for "Culture" is
the Taj Mahal — which is how a commune event in Kayl came to be illustrated
with an Indian mausoleum. Its docstring claimed it only touched the curated
seed; the query had no such filter and took every event without an image,
crawled ones included.

A photograph is the loudest claim on a card. The app now draws a plain panel
with a category icon when a record has no picture of its own, which is honest
and looks deliberate. That only works if the field is actually empty, so this
undoes what the old script wrote.

    python3 clear_stock_images.py            # show what would change
    python3 clear_stock_images.py --write    # empty those fields

Only images served from a stock library are touched. Anything a source
published about itself — an og:image, a venue's own photo — is left alone.
Safe to run twice.
"""
from __future__ import annotations

import argparse
import collections
import logging
from urllib.parse import urlparse

from motor.motor_asyncio import AsyncIOMotorClient

from db_config import mongo_settings
import asyncio

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("clear_stock_images")

# See db_config: reads backend/.env and refuses when DB_NAME is missing.

# Kept in step with frontend/src/utils/photo.ts, which decides the same thing
# at display time. Both lists exist because a record can reach the screen
# without passing through here.
STOCK_HOSTS = {
    "images.unsplash.com",
    "source.unsplash.com",
    "images.pexels.com",
    "cdn.pixabay.com",
    "via.placeholder.com",
    "placehold.co",
    "picsum.photos",
}


def is_stock(url: str) -> bool:
    host = urlparse((url or "").strip()).netloc.lower()
    return any(host == s or host.endswith(f".{s}") for s in STOCK_HOSTS)


async def run(write: bool) -> int:
    mongo_url, db_name = mongo_settings()
    mongo = AsyncIOMotorClient(mongo_url)
    db = mongo[db_name]
    try:
        hosts: collections.Counter = collections.Counter()
        ids = []
        async for ev in db.events.find({"image": {"$nin": ["", None]}}, {"_id": 1, "image": 1}):
            if is_stock(ev.get("image", "")):
                hosts[urlparse(ev["image"]).netloc.lower()] += 1
                ids.append(ev["_id"])

        log.info("%d events carry a stock photograph", len(ids))
        for host, n in hosts.most_common():
            log.info("   %-28s %d", host, n)

        if not ids:
            return 0
        if not write:
            log.info("\nPreview only. Re-run with --write to empty those fields.")
            return 0

        res = await db.events.update_many({"_id": {"$in": ids}}, {"$set": {"image": ""}})
        log.info("\ncleared: %d", res.modified_count)
    finally:
        mongo.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply the change")
    return asyncio.run(run(ap.parse_args().write))


if __name__ == "__main__":
    raise SystemExit(main())
