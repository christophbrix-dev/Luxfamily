#!/usr/bin/env python3
"""Register the verified commune event pages as import sources.

sources/candidates.csv is the output of discover_sources.py: 100 Luxembourg
communes, checked for a robots.txt that permits us, a declared sitemap, an
event section and schema.org JSON-LD. This turns the ones that passed every
check into rows in db.sources, matched to their canton via communes_lu.json.

Sources are created **inactive**. Registering a source and crawling it are
different decisions, and the second one is the owner's:

    python3 seed_commune_sources.py             # preview, writes nothing
    python3 seed_commune_sources.py --write     # create the rows, still off
    python3 seed_commune_sources.py --write --activate

Each source points at the commune's own /events/ listing, which the json_ld
importer reads in a single request — it only follows individual event pages
when the listing itself carries none, and then at most twenty. The sitemaps
hold several hundred event pages per commune; walking those would be tens of
thousands of requests to small municipal servers for the same information.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from motor.motor_asyncio import AsyncIOMotorClient

from db_config import mongo_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("seed_communes")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CANDIDATES = ROOT / "sources" / "candidates.csv"
COMMUNES = HERE / "communes_lu.json"

# Resolved when the script runs, not at import: mongo_settings() stops with a
# message when DB_NAME is missing, and a module-level call would make that a
# stack trace on import instead.

# What a commune actually publishes: markets, concerts, village fêtes, council
# meetings. Culture is the honest umbrella; the importer overrides it whenever
# the JSON-LD names something better.
DEFAULT_CATEGORIES = ["Culture", "Festivals"]


def norm(s: str) -> str:
    """Fold a place name for comparison: lowercase, no accents, letters only."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s)


def load_communes() -> List[Dict]:
    if not COMMUNES.exists():
        raise SystemExit(
            f"{COMMUNES.name} missing — run build_commune_index.py first."
        )
    return json.loads(COMMUNES.read_text(encoding="utf-8"))


def match_commune(name: str, communes: List[Dict]) -> Optional[Dict]:
    """Find the commune a candidate row refers to.

    Exact match on any spelling first. Communes are multilingual here — Petange
    is Petingen is Péiteng — and the CSV uses whichever the discovery run saw.

    Failing that, one containment match, and only if it is unique: the CSV says
    "Reckingen" where OSM says "Reckingen/Mess". Ambiguity returns None so the
    row is reported rather than filed under a guess.
    """
    target = norm(name)
    for c in communes:
        if any(norm(n) == target for n in c["names"]):
            return c

    partial = [
        c for c in communes
        if any(target in norm(n) or norm(n) in target for n in c["names"])
    ]
    return partial[0] if len(partial) == 1 else None


# The path segment a site files its events under. Most use /events/, but not
# all: Käerjeng writes /evenement/ and Ernztal /actualite/agenda/.
_SECTION = re.compile(
    r"^(events?|agenda|[ée]v[ée]nements?|manifestations?|veranstaltungen|actualites?)$",
    re.I,
)


def events_url(website: str, example: str) -> str:
    """The event listing page for a commune.

    The section comes from the URL discovery actually verified rather than
    being assumed. Rebuilding /events/ for everyone gave two 404s on the first
    full crawl — kaerjeng.lu and dippach.lu file theirs under /evenement/, and
    the listing we asked for does not exist.

    The example is one page out of the sitemap: sometimes the listing itself,
    sometimes a single event below it. Either way the section is the part up to
    and including the first event-shaped segment, so /events/marche-au-frais-2/
    and /events/ both give /events/.
    """
    host = urlparse(website or example).netloc
    parts = [p for p in urlparse(example or "").path.split("/") if p]
    # The deepest match, not the first. aerenzdall.lu files its calendar at
    # /actualite/agenda/, and stopping at the first match would hand back
    # /actualite/ — the news section, which is a different page.
    # _SECTION matches a whole segment, so an event slug called "agenda-2026"
    # is not mistaken for one.
    hits = [i for i, part in enumerate(parts) if _SECTION.match(part)]
    if hits:
        return f"https://{host}/" + "/".join(parts[: hits[-1] + 1]) + "/"
    return f"https://{host}/events/"


def build_source(row: Dict[str, str], commune: Dict) -> Dict:
    host = urlparse(row["Website"] or row["Beispiel-URL"]).netloc
    return {
        "name": f"{commune['name']} (Gemeng) — Events",
        "kind": "json_ld",
        "url": events_url(row["Website"], row["Beispiel-URL"]),
        "canton_default": commune["canton"],
        "town_default": commune["name"],
        "category_default": DEFAULT_CATEGORIES,
        "age_min_default": 0,
        "age_max_default": 99,
        # The commune centroid, from the OSM boundary. Events carrying a real
        # address are geocoded properly afterwards; this only decides where a
        # marker sits when the source gives no address at all, and it is
        # recorded as approximate rather than passed off as measured.
        "lat_default": commune["lat"],
        "lng_default": commune["lng"],
        "geocode_precision_default": "commune",
        "selectors": None,
        "homepage": f"https://{host}/",
        "discovered_from": "sources/candidates.csv",
    }


async def seed(write: bool, activate: bool) -> int:
    communes = load_communes()
    rows = [
        r for r in csv.DictReader(CANDIDATES.open(encoding="utf-8-sig"))
        if r["Status"] == "KANDIDAT" and r["JSON-LD"] == "ja"
    ]
    log.info("%d candidates cleared discovery (robots ok, sitemap, JSON-LD)", len(rows))

    sources, unmatched = [], []
    for r in rows:
        c = match_commune(r["Gemeinde"], communes)
        if not c:
            unmatched.append(r["Gemeinde"])
            continue
        sources.append(build_source(r, c))

    if unmatched:
        # Not fatal, but say so: a commune nobody can place is a commune whose
        # events would be filed under the wrong canton.
        log.warning("%d could not be matched to a commune, skipped: %s",
                    len(unmatched), ", ".join(unmatched))

    by_canton: Dict[str, int] = {}
    for s in sources:
        by_canton[s["canton_default"]] = by_canton.get(s["canton_default"], 0) + 1
    log.info("%d sources ready, across %d cantons:", len(sources), len(by_canton))
    for canton, n in sorted(by_canton.items()):
        log.info("   %-18s %d", canton, n)

    if not write:
        log.info("\nPreview only. Re-run with --write to create them.")
        for s in sources[:5]:
            log.info("   %s -> %s", s["name"], s["url"])
        return 0

    mongo_url, db_name = mongo_settings()
    mongo = AsyncIOMotorClient(mongo_url)
    db = mongo[db_name]
    inserted = updated = 0
    try:
        for s in sources:
            # Matched by name, not by URL. The name is derived from the
            # commune or venue and does not change; the URL does — correcting
            # the event section for Käerjeng from /events/ to /evenement/
            # created a second source and left the broken one running.
            existing = await db.sources.find_one({"name": s["name"]}, {"_id": 0})
            if existing:
                # Never flip a source someone has already switched on or off.
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

    log.info("\n%d created, %d updated. Active: %s",
             inserted, updated, "yes" if activate else "no — enable them in the admin console")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="create the rows")
    ap.add_argument("--activate", action="store_true",
                    help="switch new sources on immediately (existing ones keep their state)")
    args = ap.parse_args()
    return asyncio.run(seed(args.write, args.activate))


if __name__ == "__main__":
    raise SystemExit(main())
