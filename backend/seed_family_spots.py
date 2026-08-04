"""
Seed 102 curated Luxembourg family spots into the events collection.
Idempotent — uses upsert keyed on `external_id` so re-running is safe.

Data source: /tmp/seed_data.json (uploaded by user 2026-08-04).
Each item is converted to the internal Event schema (see server.py::EventBase).

Run:
    cd /app/backend && python seed_family_spots.py [/path/to/seed.json]
"""
import json
import os
import re
import sys
import uuid
from datetime import datetime

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

# ---------------------------------------------------------------------------
# Mapping tables
# ---------------------------------------------------------------------------
# Luxembourg commune → canton. Covers every commune present in seed_data.json
# (with a few extras for future-proofing). Cross-border entries fall back to
# the closest Luxembourg canton.
COMMUNE_TO_CANTON = {
    "Ansembourg": "Mersch",
    "Bech": "Echternach",
    "Berdorf": "Echternach",
    "Bertrange": "Luxembourg",
    "Bettembourg": "Esch-sur-Alzette",
    "Bourscheid": "Diekirch",
    "Bous": "Remich",
    "Clervaux": "Clervaux",
    "Consdorf": "Echternach",
    "Contern": "Luxembourg",
    "Deiffelt": "Clervaux",
    "Differdange": "Esch-sur-Alzette",
    "Dudelange": "Esch-sur-Alzette",
    "Echternach": "Echternach",
    "Esch-sur-Alzette": "Esch-sur-Alzette",
    "Esch-sur-Sûre": "Wiltz",
    "Eschweiler": "Wiltz",
    "Foetz": "Esch-sur-Alzette",
    "Grevenmacher": "Grevenmacher",
    "Heiderscheid": "Wiltz",
    "Hesperange": "Luxembourg",
    "Hollenfels": "Mersch",
    "Hoscheid": "Clervaux",
    "Härebierg": "Diekirch",
    "Insenborn": "Wiltz",
    "Kayl": "Esch-sur-Alzette",
    "Kockelscheuer": "Esch-sur-Alzette",
    "Koerich": "Capellen",
    "Lorentzweiler": "Mersch",
    "Luxembourg-Stadt": "Luxembourg",
    "Luxemburg-Stadt": "Luxembourg",
    "Luxemburg": "Luxembourg",
    "Marienthal": "Mersch",
    "Medernach": "Diekirch",
    "Mersch": "Mersch",
    "Munshausen": "Clervaux",
    "Niederanven": "Luxembourg",
    "Niederkorn": "Esch-sur-Alzette",
    "Peppange": "Esch-sur-Alzette",
    "Remerschen": "Remich",
    "Remich": "Remich",
    "Roeser": "Esch-sur-Alzette",
    "Rosport": "Echternach",
    "Rumelange": "Esch-sur-Alzette",
    "Sandweiler": "Luxembourg",
    "Schoenfels": "Mersch",
    "Steinfort": "Capellen",
    "Strassen": "Luxembourg",
    "Useldange": "Redange",
    "Vianden": "Vianden",
    "Wasserbillig": "Grevenmacher",
    "Weiswampach": "Clervaux",
    "Wiltz": "Wiltz",
    "Wormeldange": "Grevenmacher",
}

# Fallback: region → primary canton (used when the commune lookup fails).
REGION_TO_CANTON = {
    "Luxembourg City": "Luxembourg",
    "Guttland":        "Mersch",
    "Minett":          "Esch-sur-Alzette",
    "Mullerthal":      "Echternach",
    "Moselle":         "Grevenmacher",
    "Éislek":          "Wiltz",
    "Landesweit":      "Luxembourg",
}

CATEGORY_MAP = {
    "playground":         ["Playgrounds"],
    "indoor_playground":  ["Playgrounds", "Indoor"],
    "hiking":             ["Nature"],
    "water":              ["Nature", "Sports"],
    "culture":            ["Culture"],
    "animals":            ["Animals"],
    "adventure":          ["Sports", "Nature"],
    "sports":             ["Sports"],
}

TYPE_MAP = {
    "indoor":  "Indoor",
    "outdoor": "Outdoor",
    "both":    "Outdoor",
}


def parse_commune(raw: str) -> str:
    """
    Reduce "Esch-sur-Alzette (Gaalgebierg)" → "Esch-sur-Alzette" and
    "Deiffelt (BE, Grenze)" → "Deiffelt". Returns the trimmed head so the
    COMMUNE_TO_CANTON lookup works.
    """
    if not raw:
        return ""
    head = re.split(r"[\(/]", raw, maxsplit=1)[0].strip()
    return head


def parse_age_range(raw: str) -> tuple[int, int]:
    """
    "2-12"  -> (2, 12)
    "3+"    -> (3, 99)
    "alle"  -> (0, 99)
    "0-3"   -> (0, 3)
    """
    if not raw or raw.lower() in ("alle", "all", "any"):
        return 0, 99
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)", raw)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^\s*(\d+)\s*\+", raw)
    if m:
        return int(m.group(1)), 99
    return 0, 99


def resolve_canton(commune_raw: str, region: str) -> str:
    commune = parse_commune(commune_raw)
    if commune in COMMUNE_TO_CANTON:
        return COMMUNE_TO_CANTON[commune]
    # Word-level match — handles "Luxembourg-Stadt (Kirchberg)" leftovers.
    lower = commune.lower()
    for key, canton in COMMUNE_TO_CANTON.items():
        if key.lower() == lower:
            return canton
    return REGION_TO_CANTON.get(region, "Luxembourg")


def to_event_doc(item: dict) -> dict:
    """Map a seed_data.json item to an EventBase-shaped MongoDB document."""
    commune_raw = item.get("commune", "")
    region      = item.get("region", "")
    canton      = resolve_canton(commune_raw, region)
    town        = parse_commune(commune_raw) or region or "Luxembourg"

    age_min, age_max = parse_age_range(item.get("age_range", ""))
    categories       = CATEGORY_MAP.get(item.get("category", ""), ["Culture"])
    ev_type          = TYPE_MAP.get(item.get("indoor_outdoor", "outdoor"), "Outdoor")

    desc_de = item.get("description_de", "") or ""
    name    = item.get("name", "").strip()
    external_id = item.get("id") or f"seed-{uuid.uuid4().hex[:8]}"

    empty_i18n = {"en": "", "de": "", "fr": ""}
    doc = {
        "id": str(uuid.uuid4()),
        "external_id": external_id,
        "title": {"en": name, "de": name, "fr": name},
        "short": {"en": desc_de, "de": desc_de, "fr": desc_de},
        "description": {"en": desc_de, "de": desc_de, "fr": desc_de},
        "type": ev_type,
        "canton": canton,
        "town": town,
        "category": categories,
        "age_min": age_min,
        "age_max": age_max,
        "start_date": datetime.utcnow().date().isoformat(),
        "end_date": None,
        "time": "",
        "price_adult": 0.0,
        "price_child": 0.0,
        "price_label": {"en": "Free", "de": "Gratis", "fr": "Gratuit"},
        "accessibility": dict(empty_i18n),
        "weather_fit": dict(empty_i18n),
        "image": item.get("image_url") or "",
        "lat": 0.0,
        "lng": 0.0,
        "bookable": False,
        "published": True,
        "rating": 4.6,
        "featured": False,
        "featured_until": None,
        "view_count": 0,
        "source_id": None,
        "source_name": "Curated — Luxfamily Seed 2026",
        "website_url": item.get("source_url") or "",
        "accessibility_wheelchair": False,
        "sensory_friendly": False,
        "free_parking": False,
        "sensory_notes": dict(empty_i18n),
        "parking": dict(empty_i18n),
        "food_allowed": True,
        "food_onsite": dict(empty_i18n),
        "preparation_tips": dict(empty_i18n),
        "payment_methods": [],
        "opening_hours": dict(empty_i18n),
        "peak_hours": dict(empty_i18n),
        "changing_facilities": False,
        "restrooms": True,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    return doc


def seed(json_path: str) -> None:
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    items = payload.get("items", payload) if isinstance(payload, dict) else payload

    mongo_url = os.environ["MONGO_URL"]
    db_name   = os.environ["DB_NAME"]
    client    = MongoClient(mongo_url)
    db        = client[db_name]

    inserted = updated = 0
    for item in items:
        doc = to_event_doc(item)
        # Upsert on external_id so re-running never duplicates.
        existing = db.events.find_one({"external_id": doc["external_id"]})
        if existing:
            # Preserve the existing UUID `id` and creation timestamp so the
            # foreign keys (favorites, bookings, ...) remain stable.
            doc["id"] = existing.get("id", doc["id"])
            doc["created_at"] = existing.get("created_at", doc["created_at"])
            db.events.update_one({"external_id": doc["external_id"]}, {"$set": doc})
            updated += 1
        else:
            db.events.insert_one(doc)
            inserted += 1

    total = db.events.count_documents({"published": True})
    print(f"[seed_family_spots] inserted={inserted} updated={updated}")
    print(f"[seed_family_spots] published events in DB now: {total}")

    # Canton distribution — helps confirm the North is now well populated.
    from collections import Counter
    dist = Counter(
        e.get("canton", "?") for e in db.events.find({"published": True}, {"canton": 1})
    )
    print("[seed_family_spots] canton distribution:")
    for c, n in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"   {c:<24} {n}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/seed_data.json"
    seed(path)
