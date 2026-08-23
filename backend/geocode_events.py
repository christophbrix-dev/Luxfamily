"""Fill in coordinates for events that still sit at lat=0, lng=0.

Three steps per event, in order, stopping at the first that answers:

1. **Our own places collection.** The OSM ingest already holds thousands of
   Luxembourg parks, playgrounds, museums and zoos with coordinates. A venue
   *name* — "Escher Déierepark", "Parc Merveilleux" — is far more likely to
   match there than in any address service, and it costs no network call.
2. **The country's cadastral geocoder** (see geocoders.py). Good at addresses,
   poor at names, which is why it comes second.
3. **The canton centroid**, so a marker still appears somewhere plausible.

Every record keeps `geocode_precision` and `geocode_source`, because a canton
centroid and a rooftop match are otherwise indistinguishable afterwards — and
the map would present both with the same confidence.

Run:
    cd /app/backend && python geocode_events.py

Idempotent: events that already have coordinates are skipped, so re-running is
safe.
"""
import json
import os
import re
import time
from typing import Dict, Optional, Tuple

from dotenv import load_dotenv
from pymongo import MongoClient

from geocoders import DEFAULT_COUNTRY, GeoResult, geocoder_for

load_dotenv()

REQUEST_PAUSE_S = 0.5  # gentle spacing between calls to the address service

# Rough centroids per Luxembourg canton — last resort, so an event still lands
# somewhere plausible rather than at (0, 0) in the Gulf of Guinea.
CANTON_FALLBACK: Dict[str, Tuple[float, float]] = {
    "Luxembourg":         (49.6117, 6.1319),
    "Esch-sur-Alzette":   (49.4959, 5.9807),
    "Diekirch":           (49.8683, 6.1560),
    "Clervaux":           (50.0546, 6.0289),
    "Wiltz":              (49.9663, 5.9333),
    "Vianden":            (49.9333, 6.2036),
    "Echternach":         (49.7217, 6.4225),
    "Grevenmacher":       (49.6800, 6.4400),
    "Remich":             (49.5453, 6.3667),
    "Mersch":             (49.7500, 6.1067),
    "Capellen":           (49.6461, 5.9906),
    "Redange":            (49.7639, 5.8850),
}


def clean_title(ev: dict) -> str:
    """Venue name without the trailing marketing tail.

    "MIGO — Minigolf & more" becomes "MIGO", which is what a place lookup can
    actually match.
    """
    title = (ev.get("title") or {}).get("de") or (ev.get("title") or {}).get("en") or ""
    return re.split(r" [—\-–|]", title)[0].strip()


def clean_town(ev: dict) -> str:
    """"Luxembourg-Stadt (Kirchberg)" becomes "Kirchberg"."""
    town = (ev.get("town") or "").strip()
    inner = re.search(r"\(([^)]+)\)", town)
    return inner.group(1).strip() if inner else town


def lookup_local_place(db, name: str, town: str) -> Optional[GeoResult]:
    """Search our own OSM places for this venue name.

    Anchored, case-insensitive, and escaped — a venue called "Parc (Merveilleux)"
    must not be read as a regular expression.
    """
    if len(name) < 4:
        return None
    pattern = {"$regex": f"^{re.escape(name)}", "$options": "i"}
    for query in ({"name": pattern, "town": town} if town else None, {"name": pattern}):
        if query is None:
            continue
        hit = db.places.find_one(query, {"_id": 0, "lat": 1, "lng": 1, "name": 1})
        if hit and hit.get("lat") and hit.get("lng"):
            return GeoResult(
                float(hit["lat"]), float(hit["lng"]), "address", "places", hit.get("name", "")
            )
    return None


def build_address_query(ev: dict) -> str:
    """An address-shaped query for the cadastral service.

    The venue name is left out on purpose: address geocoders match streets and
    house numbers, and a name in the query only pulls the result towards an
    unrelated locality. Names are handled by the places lookup instead.
    """
    parts = [p for p in (clean_town(ev), (ev.get("canton") or "").strip()) if p]
    return ", ".join(parts)


def resolve(db, ev: dict, cache: Dict[str, Optional[dict]]) -> GeoResult:
    """Coordinates for one event, best available source first."""
    name, town = clean_title(ev), clean_town(ev)

    local = lookup_local_place(db, name, town)
    if local:
        return local

    country = (ev.get("country") or DEFAULT_COUNTRY).upper()
    geocoder = geocoder_for(country)
    if geocoder:
        query = build_address_query(ev)
        if query:
            if query in cache:
                cached = cache[query]
                if cached:
                    return GeoResult(**cached)
            else:
                hit = geocoder.geocode(query)
                cache[query] = hit._asdict() if hit else None
                time.sleep(REQUEST_PAUSE_S)
                if hit:
                    return hit

    lat, lng = CANTON_FALLBACK.get((ev.get("canton") or "").strip(), (49.61, 6.13))
    return GeoResult(lat, lng, "canton", "fallback")


def main() -> None:
    client = MongoClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    todo = list(db.events.find({
        "$or": [{"lat": 0}, {"lat": {"$exists": False}}, {"lat": None}],
    }))
    print(f"[geocode] {len(todo)} events to geocode")

    cache_path = "/tmp/geocode_cache.json"
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}

    counts: Dict[str, int] = {}
    for i, ev in enumerate(todo, 1):
        result = resolve(db, ev, cache)
        counts[result.source] = counts.get(result.source, 0) + 1

        db.events.update_one(
            {"_id": ev["_id"]},
            {"$set": {
                "lat": result.lat,
                "lng": result.lng,
                "country": (ev.get("country") or DEFAULT_COUNTRY).upper(),
                "geocode_precision": result.precision,
                "geocode_source": result.source,
            }},
        )

        if i % 10 == 0 or i == len(todo):
            summary = "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            print(f"[geocode] {i}/{len(todo)}  {summary}")
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)

    print("[geocode] done. " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    fallbacks = counts.get("fallback", 0)
    if fallbacks:
        print(f"[geocode] {fallbacks} events only have a canton centroid — "
              "find them with geocode_precision='canton' and fix them by hand.")


if __name__ == "__main__":
    main()
