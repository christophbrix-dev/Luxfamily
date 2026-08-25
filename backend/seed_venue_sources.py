#!/usr/bin/env python3
"""Register the verified venue event pages as import sources.

The companion to seed_commune_sources.py. Where that one registers the
communes, this registers the places that actually host things — Rockhal, the
Musée national des Mines, Château de Vianden, the Echternach tourist office —
found by discover_venue_sources.py in sources/venue_candidates.csv.

There are fourteen, of which four sit on a domain a commune source already
covers: a youth club or a sports hall published on its commune's website. Those
are skipped rather than registered twice, because the importer would crawl the
same /events/ page under two names and file the same event twice.

    python3 seed_venue_sources.py             # preview, writes nothing
    python3 seed_venue_sources.py --write     # create the rows, inactive
    python3 seed_venue_sources.py --write --activate

Sources are created inactive. Registering a source and crawling it are
different decisions, and the second one is the owner's.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from motor.motor_asyncio import AsyncIOMotorClient

from db_config import mongo_settings


logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("seed_venues")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VENUES = ROOT / "sources" / "venue_candidates.csv"
COMMUNES_CSV = ROOT / "sources" / "candidates.csv"
COMMUNES = HERE / "communes_lu.json"

# Resolved when the script runs, not at import: mongo_settings() stops with a
# message when DB_NAME is missing, and a module-level call would make that a
# stack trace on import instead.

# What each sort of venue tends to put on. Broad on purpose: the importer
# overrides these whenever the JSON-LD names something better, and a wrong
# guess here only affects the filter chips, not whether an event appears.
CATEGORIES_BY_KIND: Dict[str, List[str]] = {
    "Musée": ["Culture", "Workshops"],
    "Kulturzentrum": ["Culture", "Workshops"],
    "Theater": ["Culture"],
    "Bibliothek": ["Culture", "Workshops"],
    "Veranstaltungsort": ["Culture", "Festivals"],
    "Gemeinschaftshaus": ["Culture", "Festivals"],
    "Kino": ["Culture"],
    "Galerie": ["Culture"],
    "Tierpark": ["Animals", "Nature"],
    "Freizeitpark": ["Festivals"],
    "Sehenswürdigkeit": ["Culture"],
    "Tourist-Info": ["Culture", "Festivals"],
    "Burg": ["Culture"],
    "Sportzentrum": ["Sports"],
    "Erlebnisbad": ["Sports"],
    "Schwimmbad": ["Sports"],
    "Naturschutzgebiet": ["Nature"],
}


def domain(url: str) -> str:
    return urlparse(url or "").netloc.lower().removeprefix("www.")


def commune_index() -> List[Dict]:
    if not COMMUNES.exists():
        raise SystemExit(f"{COMMUNES.name} missing — run build_commune_index.py first.")
    return json.loads(COMMUNES.read_text(encoding="utf-8"))


def place_at(lat: float, lng: float, communes: List[Dict]) -> Optional[Dict]:
    """The commune containing this point.

    communes_lu.json stores a centroid, not a polygon, so this falls back to
    the nearest one. That is fine for what it decides — the canton — because a
    venue is inside its own commune and its neighbours share the canton far
    more often than not. Where it matters more, the ingest does the real
    point-in-polygon test against the boundaries in the extract.
    """
    best, best_d = None, None
    for c in communes:
        d = (c["lat"] - lat) ** 2 + (c["lng"] - lng) ** 2
        if best_d is None or d < best_d:
            best, best_d = c, d
    return best


def build(row: Dict[str, str], commune: Dict) -> Dict:
    host = domain(row["Website"] or row["Beispiel-URL"])
    return {
        "name": f"{row['Name']} ({row['Art']})",
        "kind": "json_ld",
        "url": row["Beispiel-URL"],
        "canton_default": commune["canton"],
        "town_default": commune["name"],
        "category_default": CATEGORIES_BY_KIND.get(row["Art"], ["Culture"]),
        "age_min_default": 0,
        "age_max_default": 99,
        # The venue's own coordinates, from the OSM extract — not the commune
        # centroid the commune sources fall back to. A museum has a front door.
        "lat_default": float(row["lat"]),
        "lng_default": float(row["lng"]),
        "geocode_precision_default": "venue",
        "selectors": None,
        "homepage": f"https://{host}/",
        "discovered_from": "sources/venue_candidates.csv",
    }


async def seed(write: bool, activate: bool) -> int:
    communes = commune_index()

    covered = {
        domain(r["Website"] or r["Beispiel-URL"])
        for r in csv.DictReader(COMMUNES_CSV.open(encoding="utf-8-sig"))
        if r["Status"] == "KANDIDAT" and r["JSON-LD"] == "ja"
    }

    rows = [
        r for r in csv.DictReader(VENUES.open(encoding="utf-8-sig"))
        if r["Status"] == "KANDIDAT" and r["JSON-LD"] == "ja"
    ]
    log.info("%d venues cleared discovery", len(rows))

    sources, skipped, unplaced = [], [], []
    for r in rows:
        if domain(r["Website"] or r["Beispiel-URL"]) in covered:
            skipped.append(r["Name"])
            continue
        if not r.get("lat") or not r.get("lng"):
            unplaced.append(r["Name"])
            continue
        commune = place_at(float(r["lat"]), float(r["lng"]), communes)
        if not commune:
            unplaced.append(r["Name"])
            continue
        sources.append(build(r, commune))

    if skipped:
        log.info("%d already covered by a commune source, skipped:", len(skipped))
        for name in skipped:
            log.info("   %s", name)
    if unplaced:
        log.warning("%d without a usable position, skipped: %s",
                    len(unplaced), ", ".join(unplaced))

    log.info("\n%d venue sources ready:", len(sources))
    for s in sources:
        log.info("   %-44s %s", s["name"][:44], s["canton_default"])

    if not write:
        log.info("\nPreview only. Re-run with --write to create them.")
        return 0

    mongo_url, db_name = mongo_settings()
    mongo = AsyncIOMotorClient(mongo_url)
    db = mongo[db_name]
    inserted = updated = 0
    try:
        for s in sources:
            existing = await db.sources.find_one({"url": s["url"]}, {"_id": 0})
            if existing:
                await db.sources.update_one(
                    {"id": existing["id"]},
                    {"$set": {**s, "active": existing.get("active", False)}},
                )
                updated += 1
            else:
                await db.sources.insert_one({
                    **s,
                    "id": str(uuid.uuid4()),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "active": bool(activate),
                    "last_run_at": None,
                    "last_status": None,
                    "last_error": None,
                    "last_imported_count": 0,
                })
                inserted += 1
    finally:
        mongo.close()

    log.info("\n%d created, %d updated. Active: %s", inserted, updated,
             "yes" if activate else "no — enable them in the admin console")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="create the rows")
    ap.add_argument("--activate", action="store_true",
                    help="switch new sources on immediately")
    args = ap.parse_args()
    return asyncio.run(seed(args.write, args.activate))


if __name__ == "__main__":
    raise SystemExit(main())
