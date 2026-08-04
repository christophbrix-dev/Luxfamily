"""
Add 13 additional crawler seed sources uploaded by user 2026-08-04.
These are inserted with `active=False` because most require custom parsers
(paginated_directory, map_app, open_data_geojson, ...) that go beyond the
current json_ld / sitemap / html_scraper / ical importers. They will appear
in the admin dashboard so we can activate them one by one after adding the
right parser.

Idempotent — upsert by URL.

Run:
    cd /app/backend && python seed_extra_crawler_sources.py [/path/to/crawler_seeds.json]
"""
import json
import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# type_from_user_json → internal `kind` (best guess — the actual parser
# will still need custom work per source, but this keeps the field valid).
KIND_MAP = {
    "paginated_directory": "html_scraper",
    "map_app":             "html_scraper",
    "open_data_geojson":   "html_scraper",
    "open_data_portal":    "html_scraper",
    "directory":           "html_scraper",
    "regional_directory":  "html_scraper",
    "business_directory":  "html_scraper",
}

# Region hint → default canton for the source (used when the importer
# produces events without an explicit canton).
REGION_DEFAULT_CANTON = {
    "Éislek":         "Wiltz",
    "Eislek":         "Wiltz",
    "Minett":         "Esch-sur-Alzette",
    "Moselle":        "Grevenmacher",
    "Mullerthal":     "Echternach",
    "Ville de Luxembourg": "Luxembourg",
    "Luxembourg City":     "Luxembourg",
}


def guess_canton(name: str) -> str:
    lower = name.lower()
    if "eislek" in lower or "éislek" in lower or "eislëk" in lower:
        return "Wiltz"
    if "minett" in lower:
        return "Esch-sur-Alzette"
    if "moselle" in lower:
        return "Grevenmacher"
    if "mullerthal" in lower:
        return "Echternach"
    if "ville de luxembourg" in lower or "vdl" in lower or "spillplaz" in lower:
        return "Luxembourg"
    return "Luxembourg"


def seed(path: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    sources = payload.get("sources", [])

    client = MongoClient(os.environ["MONGO_URL"])
    db     = client[os.environ["DB_NAME"]]

    inserted = updated = 0
    now = datetime.now(timezone.utc).isoformat()

    for src in sources:
        url  = src.get("url", "").strip()
        name = src.get("source_name", "").strip()
        if not url or not name:
            continue

        kind   = KIND_MAP.get(src.get("type", ""), "html_scraper")
        canton = guess_canton(name)
        doc = {
            "name":    name,
            "kind":    kind,
            "url":     url,
            "active":  False,  # ← manual review + parser needed first
            "image_default": "",
            "selectors": None,
            "canton_default":   canton,
            "town_default":     "",
            "category_default": ["Culture"],
            "age_min_default":  0,
            "age_max_default":  99,
            "lat_default":      49.61,
            "lng_default":      6.13,
            "notes":            src.get("notes", ""),
            "source_kind":      src.get("type", ""),  # keep the original type
            "last_status":      "queued_for_review",
            "last_error":       "",
            "last_imported_count": 0,
            "last_run_at":      None,
            "updated_at":       now,
        }
        existing = db.sources.find_one({"url": url})
        if existing:
            doc["id"] = existing.get("id")
            doc["created_at"] = existing.get("created_at", now)
            db.sources.update_one({"url": url}, {"$set": doc})
            updated += 1
        else:
            doc["id"] = str(uuid.uuid4())
            doc["created_at"] = now
            db.sources.insert_one(doc)
            inserted += 1

    total = db.sources.count_documents({})
    print(f"[seed_extra_sources] inserted={inserted} updated={updated}")
    print(f"[seed_extra_sources] total sources in DB now: {total}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/crawler_seeds.json"
    seed(path)
