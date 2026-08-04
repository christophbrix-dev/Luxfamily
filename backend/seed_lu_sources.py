"""Seeds a starter set of Luxembourg event sources.

All entries are inserted with ``active=False`` — admins must review each one
in the admin UI, run a robots-check, and enable them explicitly. This is
intentional: we never crawl a site without an explicit go-ahead.

Usage:
    cd /app/backend && python seed_lu_sources.py

Idempotent: upserts by (name, url).
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger("seed-lu-sources")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


# Curated list of publicly-reachable Luxembourg event listing pages.
# Note: each entry is INACTIVE by default. An admin must:
#   1. Open the Sources page in /admin/sources
#   2. Click "Robots check" → confirm we may crawl
#   3. Toggle "Active" and "Run now"
# We prefer json_ld sources when known to embed schema.org/Event microdata,
# fall back to html_scraper with sensible selectors otherwise.
SOURCES = [
    {
        "name": "Philharmonie Luxembourg — Agenda",
        "kind": "json_ld",
        "url": "https://www.philharmonie.lu/en/programme/season",
        "canton_default": "Luxembourg",
        "town_default": "Luxembourg City",
        "category_default": ["Culture", "Workshops"],
        "age_min_default": 6, "age_max_default": 99,
        "lat_default": 49.6197, "lng_default": 6.1421,
    },
    {
        "name": "Rockhal — Concerts & Events",
        "kind": "json_ld",
        "url": "https://www.rockhal.lu/en/agenda/",
        "canton_default": "Esch-sur-Alzette",
        "town_default": "Esch-Belval",
        "category_default": ["Culture", "Festivals"],
        "age_min_default": 8, "age_max_default": 99,
        "lat_default": 49.4998, "lng_default": 5.9475,
    },
    {
        "name": "Mudam Luxembourg — Programme",
        "kind": "json_ld",
        "url": "https://www.mudam.com/programme",
        "canton_default": "Luxembourg",
        "town_default": "Luxembourg City",
        "category_default": ["Culture", "Workshops"],
        "age_min_default": 4, "age_max_default": 99,
        "lat_default": 49.6411, "lng_default": 6.1417,
    },
    {
        "name": "Visit Luxembourg — Events (agenda)",
        "kind": "html_scraper",
        "url": "https://www.visitluxembourg.com/agenda",
        "canton_default": "Luxembourg",
        "town_default": "Luxembourg City",
        "category_default": ["Culture", "Festivals"],
        "age_min_default": 0, "age_max_default": 99,
        "lat_default": 49.6116, "lng_default": 6.1319,
        "selectors": {
            "item": "article.event, .agenda-item, li.event-teaser",
            "title": "h2, h3, .title",
            "date": "time",
            "date_attr": "datetime",
            "location": ".place, .venue, .location",
            "description": "p, .description",
            "image": "img",
            "link": "a"
        },
    },
    {
        "name": "Ville de Luxembourg — Agenda culturel",
        "kind": "html_scraper",
        "url": "https://www.vdl.lu/en/visiting/whats-on",
        "canton_default": "Luxembourg",
        "town_default": "Luxembourg City",
        "category_default": ["Culture"],
        "age_min_default": 0, "age_max_default": 99,
        "lat_default": 49.6116, "lng_default": 6.1319,
        "selectors": {
            "item": ".event-item, article",
            "title": "h2, h3",
            "date": "time",
            "date_attr": "datetime",
            "location": ".location",
            "description": "p",
            "image": "img",
            "link": "a"
        },
    },
    {
        "name": "Echo.lu — Event Agenda (LU)",
        "kind": "json_ld",
        "url": "https://www.echo.lu/en/",
        "canton_default": "Luxembourg",
        "town_default": "Luxembourg City",
        "category_default": ["Culture", "Festivals"],
        "age_min_default": 0, "age_max_default": 99,
        "lat_default": 49.6116, "lng_default": 6.1319,
    },
    {
        "name": "Kulturhaus Niederanven — Events",
        "kind": "html_scraper",
        "url": "https://www.khn.lu/agenda/",
        "canton_default": "Luxembourg",
        "town_default": "Niederanven",
        "category_default": ["Culture", "Workshops"],
        "age_min_default": 3, "age_max_default": 99,
        "lat_default": 49.6558, "lng_default": 6.2467,
        "selectors": {
            "item": ".event, article",
            "title": "h2, h3",
            "date": "time",
            "date_attr": "datetime",
            "description": "p",
            "image": "img",
            "link": "a"
        },
    },
    {
        "name": "Naturmusée — Events",
        "kind": "json_ld",
        "url": "https://www.mnhn.lu/",
        "canton_default": "Luxembourg",
        "town_default": "Luxembourg City",
        "category_default": ["Culture", "Nature"],
        "age_min_default": 4, "age_max_default": 99,
        "lat_default": 49.6126, "lng_default": 6.1399,
    },
]


async def main() -> None:
    log.info("Connecting to %s/%s", MONGO_URL, DB_NAME)
    mongo = AsyncIOMotorClient(MONGO_URL)
    db = mongo[DB_NAME]

    inserted = 0
    updated = 0
    for src in SOURCES:
        existing = await db.sources.find_one({"name": src["name"], "url": src["url"]}, {"_id": 0})
        if existing:
            await db.sources.update_one(
                {"id": existing["id"]},
                {"$set": {**src, "active": False}},
            )
            updated += 1
            log.info("↻ updated %s", src["name"])
        else:
            doc = {
                "id": str(uuid.uuid4()),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "active": False,           # <— always start disabled
                "image_default": "",
                "selectors": None,
                **src,
            }
            await db.sources.insert_one(doc)
            inserted += 1
            log.info("＋ inserted %s", src["name"])

    total = await db.sources.count_documents({})
    log.info("Done. inserted=%d, updated=%d, total_sources_in_db=%d", inserted, updated, total)
    log.info("All new sources are INACTIVE. Go to /admin/sources to review and enable them.")
    mongo.close()


if __name__ == "__main__":
    asyncio.run(main())
