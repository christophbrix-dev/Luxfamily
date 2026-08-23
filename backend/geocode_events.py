"""
Batch-geocode all Wat Elo? events that still have lat=0, lng=0.
Uses Nominatim (OpenStreetMap's free geocoder) — no API key needed, but we
respect the 1-request-per-second usage policy and cache results per query.

Run:
    cd /app/backend && python geocode_events.py &

The script writes progress to stdout every 10 records. It is idempotent —
already-geocoded events are skipped, so you can safely re-run it.
"""
import os
import re
import time
import json
from typing import Optional, Tuple

import httpx
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

NOMINATIM_URL   = "https://nominatim.openstreetmap.org/search"
from crawler_utils import USER_AGENT  # one identity for the whole project
REQUEST_PAUSE_S = 1.1   # be nice to Nominatim (>= 1s policy)

# Rough fallback centroids per Luxembourg canton — used when Nominatim can't
# resolve the address, so an event still lands somewhere plausible on the map.
CANTON_FALLBACK: dict[str, Tuple[float, float]] = {
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


def geocode(query: str, cache: dict[str, dict]) -> Optional[Tuple[float, float]]:
    if not query:
        return None
    if query in cache:
        hit = cache[query]
        return (hit["lat"], hit["lng"]) if hit else None

    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "lu,de,be,fr",   # Luxembourg + border-region fallback
        "accept-language": "de,fr,en",
    }
    try:
        r = httpx.get(
            NOMINATIM_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=10.0,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  [nominatim] error for {query!r}: {e}")
        cache[query] = None      # type: ignore[assignment]
        return None

    if not data:
        cache[query] = None      # type: ignore[assignment]
        return None
    hit = data[0]
    lat = float(hit["lat"])
    lng = float(hit["lon"])
    cache[query] = {"lat": lat, "lng": lng, "display": hit.get("display_name", "")}
    return lat, lng


def build_query(ev: dict) -> str:
    """Produce a Nominatim query from the event's town/canton/title fields."""
    title = ev.get("title", {}).get("en") or ev.get("title", {}).get("de") or ""
    # Strip common noise ("MIGO — Minigolf …" → "MIGO Minigolf …")
    title = re.split(r" [—\-–|]", title)[0].strip()
    town   = ev.get("town", "").strip()
    canton = ev.get("canton", "").strip()

    # Reduce town noise: "Luxembourg-Stadt (Kirchberg)" → "Kirchberg"
    if "(" in town and ")" in town:
        m = re.search(r"\(([^)]+)\)", town)
        if m:
            town = m.group(1).strip()

    parts = [p for p in [title, town, canton, "Luxembourg"] if p]
    return ", ".join(parts)


def main() -> None:
    mongo_url = os.environ["MONGO_URL"]
    db_name   = os.environ["DB_NAME"]
    client    = MongoClient(mongo_url)
    db        = client[db_name]

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

    ok = fb = skipped = 0
    for i, ev in enumerate(todo, 1):
        q = build_query(ev)
        result = geocode(q, cache)

        if result is None:
            # Try a lighter query — town + canton only
            q2 = ", ".join([p for p in [ev.get("town", "").split("(")[0].strip(),
                                        ev.get("canton", ""), "Luxembourg"] if p])
            if q2 != q:
                result = geocode(q2, cache)

        if result:
            lat, lng = result
            ok += 1
        else:
            # Canton centroid fallback so the marker still shows up somewhere.
            lat, lng = CANTON_FALLBACK.get(ev.get("canton", ""), (49.61, 6.13))
            fb += 1

        db.events.update_one(
            {"_id": ev["_id"]},
            {"$set": {"lat": lat, "lng": lng}},
        )

        if i % 10 == 0 or i == len(todo):
            print(f"[geocode] {i}/{len(todo)}  ok={ok}  fallback={fb}  skipped={skipped}")
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)

        # Only sleep when we actually hit the network (cache miss).
        if q not in cache or cache.get(q) is None:
            time.sleep(REQUEST_PAUSE_S)

    print(f"[geocode] done. exact={ok}, fallback={fb}")


if __name__ == "__main__":
    main()
