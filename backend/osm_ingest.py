"""
OSM POI ingest for Wat Elo? — parses a Geofabrik `.osm.pbf` extract of
Luxembourg locally (no Overpass dependency) and upserts family-friendly
POIs into the `places` MongoDB collection.

Why PBF instead of Overpass?
    - Overpass public mirrors go down often.  Geofabrik is a rock-solid CDN.
    - A single 45 MB PBF ships every category we care about; one file pass
      classifies every POI, so ~30 categories cost the same as 1.
    - Runs in seconds after the first download (cached on disk for 24 h).

Public API (unchanged from the earlier Overpass draft):
    from osm_ingest import ingest_category, ingest_all, JOB_STATE
    result = await ingest_category("playground")
    await ingest_all()                 # every category

CLI:
    python -m osm_ingest all
    python -m osm_ingest playground castle
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
import osmium
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

from osm_taxonomy import (
    CATEGORIES,
    CATEGORY_ORDER,
    NAME_KEYS,
    SCORE_RULES,
)

logger = logging.getLogger("osm_ingest")

# -------- Geofabrik source ------------------------------------------
GEOFABRIK_URL = "https://download.geofabrik.de/europe/luxembourg-latest.osm.pbf"
PBF_CACHE = Path(os.environ.get("OSM_PBF_CACHE", "/tmp/luxembourg-latest.osm.pbf"))
PBF_MAX_AGE_SECONDS = 24 * 3600  # refresh after 24 h

from crawler_utils import USER_AGENT  # one identity for the whole project

LU_BBOX = (49.44, 5.72, 50.19, 6.55)


# -------- Job state (in-memory) -------------------------------------
JOB_STATE: Dict[str, Any] = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "current": None,
    "categories": {},
    "totals": {"raw": 0, "upserted": 0, "skipped": 0, "errors": 0},
    "message": "",
}


# -------- PBF download ----------------------------------------------
async def ensure_pbf() -> Path:
    """Download the Luxembourg PBF unless a fresh copy already exists."""
    if PBF_CACHE.exists():
        age = time.time() - PBF_CACHE.stat().st_mtime
        if age < PBF_MAX_AGE_SECONDS and PBF_CACHE.stat().st_size > 1_000_000:
            return PBF_CACHE

    PBF_CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PBF_CACHE.with_suffix(".pbf.tmp")
    logger.info("Downloading Luxembourg PBF from %s", GEOFABRIK_URL)
    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as cx:
        async with cx.stream("GET", GEOFABRIK_URL, headers={"User-Agent": USER_AGENT}) as r:
            r.raise_for_status()
            with tmp.open("wb") as fh:
                async for chunk in r.aiter_bytes(chunk_size=256 * 1024):
                    fh.write(chunk)
    tmp.replace(PBF_CACHE)
    logger.info("PBF cached at %s (%.1f MB)", PBF_CACHE, PBF_CACHE.stat().st_size / 1e6)
    return PBF_CACHE


# -------- Filter parser ---------------------------------------------
_TAG_RE = re.compile(
    r'\["(?P<key>[^"]+)"(?P<op>!?=|!?~)"(?P<val>[^"]*)"\]'
)


def _compile_filter(filter_str: str) -> Callable[[Dict[str, Any]], bool]:
    """Turn an Overpass QL fragment like ["leisure"="playground"] into a
    Python predicate over an osmium tag dict.  AND semantics between chunks."""
    parts: List[Tuple[str, str, str]] = []
    for m in _TAG_RE.finditer(filter_str):
        parts.append((m.group("key"), m.group("op"), m.group("val")))
    if not parts:
        return lambda _t: False

    def predicate(tags: Dict[str, Any]) -> bool:
        for key, op, val in parts:
            actual = tags.get(key)
            if op == "=":
                if actual != val:
                    return False
            elif op == "!=":
                if actual == val:
                    return False
            elif op == "~":
                if actual is None or not re.search(val, str(actual)):
                    return False
            elif op == "!~":
                if actual is not None and re.search(val, str(actual)):
                    return False
        return True

    return predicate


def _compile_category(kind_key: str) -> Tuple[Callable[[Dict[str, Any]], bool], bool]:
    cat = CATEGORIES[kind_key]
    preds = [_compile_filter(f) for f in cat["filters"]]
    relations_only = cat.get("relations_only", False)

    def match(tags: Dict[str, Any]) -> bool:
        return any(p(tags) for p in preds)

    return match, relations_only


# -------- Normalisation helpers ------------------------------------
def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text or "poi"


def pick_name(tags: Dict[str, Any], fallback_label: str) -> str:
    for k in NAME_KEYS:
        v = tags.get(k)
        if v:
            return v.strip()
    return fallback_label


def compute_family_score(tags: Dict[str, Any], base: int) -> int:
    score = base
    for key, pattern, delta in SCORE_RULES:
        val = tags.get(key)
        if val is None:
            continue
        if pattern is None:
            score += delta
        elif re.search(pattern, str(val), re.IGNORECASE):
            score += delta
    return max(0, min(100, score))


def age_range(tags: Dict[str, Any], kind_key: str) -> Tuple[int, int]:
    try:
        mn = int(tags.get("min_age") or 0)
    except (TypeError, ValueError):
        mn = 0
    try:
        mx = int(tags.get("max_age") or 0)
    except (TypeError, ValueError):
        mx = 0
    if mn or mx:
        return (mn or 0), (mx or 14)
    defaults = {
        "playground": (1, 12), "water_playground": (1, 10), "skatepark": (6, 18),
        "indoor_play": (1, 12), "minigolf": (5, 99), "farm": (2, 12),
        "zoo": (2, 99), "horse": (4, 16), "theme_park": (3, 99),
        "swimming": (1, 99), "ice_rink": (4, 99), "climbing": (5, 99),
    }
    return defaults.get(kind_key, (0, 99))


def extract_localised(tags: Dict[str, Any], prefix: str) -> Dict[str, str]:
    return {
        "lb": tags.get(f"{prefix}:lb") or "",
        "de": tags.get(f"{prefix}:de") or "",
        "fr": tags.get(f"{prefix}:fr") or "",
        "en": tags.get(f"{prefix}:en") or tags.get(prefix) or "",
    }


def _dedupe_key(rec: Dict[str, Any]) -> Tuple[str, int, int]:
    return (rec["name"].lower(), round(rec["lat"], 4), round(rec["lng"], 4))


# -------- Osmium handler --------------------------------------------
class _POIHandler(osmium.SimpleHandler):
    """Runs once over the PBF and classifies every element against ALL
    known categories.  Emits one dict per element into the `.records` list.
    """

    def __init__(self, matchers: Dict[str, Tuple[Callable, bool]]):
        super().__init__()
        self.matchers = matchers  # {kind_key: (predicate, relations_only)}
        self.records: List[Dict[str, Any]] = []
        self.raw_counts: Dict[str, int] = {k: 0 for k in matchers}

    # -- helpers ------------------------------------------------------
    def _tags_to_dict(self, t) -> Dict[str, str]:
        return {tag.k: tag.v for tag in t}

    def _way_centroid(self, w) -> Optional[Tuple[float, float]]:
        # Simple average of node locations; good enough for POI markers.
        lats: List[float] = []
        lons: List[float] = []
        for n in w.nodes:
            try:
                if n.location.valid():
                    lats.append(n.location.lat)
                    lons.append(n.location.lon)
            except Exception:
                continue
        if not lats:
            return None
        return sum(lats) / len(lats), sum(lons) / len(lons)

    # -- osmium callbacks --------------------------------------------
    def node(self, n):
        tags = self._tags_to_dict(n.tags)
        if not tags:
            return
        for kind_key, (match, relations_only) in self.matchers.items():
            if relations_only:
                continue
            if match(tags):
                self.raw_counts[kind_key] += 1
                rec = self._normalise(kind_key, "node", n.id, tags,
                                      n.location.lat, n.location.lon)
                if rec:
                    self.records.append(rec)

    def way(self, w):
        tags = self._tags_to_dict(w.tags)
        if not tags:
            return
        for kind_key, (match, relations_only) in self.matchers.items():
            if relations_only:
                continue
            if match(tags):
                self.raw_counts[kind_key] += 1
                c = self._way_centroid(w)
                if c is None:
                    continue
                rec = self._normalise(kind_key, "way", w.id, tags, c[0], c[1])
                if rec:
                    self.records.append(rec)
                break  # avoid double-counting one way in multiple categories

    def relation(self, r):
        tags = self._tags_to_dict(r.tags)
        if not tags:
            return
        for kind_key, (match, _relations_only) in self.matchers.items():
            if match(tags):
                self.raw_counts[kind_key] += 1
                # Coordinates for relations are hard w/o multipolygon build.
                # For hiking / cycle routes we skip geometry — the UI
                # can link out to OSM for now.  A future pass can use
                # osmium.geom to build centroids from member ways.
                rec = self._normalise(kind_key, "relation", r.id, tags, None, None)
                if rec:
                    self.records.append(rec)
                break

    # -- normalise ---------------------------------------------------
    def _normalise(self, kind_key: str, osm_type: str, osm_id: int,
                   tags: Dict[str, Any], lat: Optional[float],
                   lon: Optional[float]) -> Optional[Dict[str, Any]]:
        cat = CATEGORIES[kind_key]

        if tags.get("access") in {"private", "no", "customers"}:
            return None

        # Require a real name for categories that opt in (e.g. swimming),
        # because private garden pools in OSM lack access tags but have no
        # name either.
        if cat.get("require_name"):
            if not any(tags.get(k) for k in NAME_KEYS):
                return None

        # Bounding box check when we have coords
        if lat is not None and lon is not None:
            s, w_, n_, e_ = LU_BBOX
            if not (s - 0.2 <= lat <= n_ + 0.2 and w_ - 0.2 <= lon <= e_ + 0.2):
                return None

        name = pick_name(tags, cat["label_de"])
        score = compute_family_score(tags, cat["base_score"])
        a_min, a_max = age_range(tags, kind_key)

        title = extract_localised(tags, "name")
        if not any(title.values()):
            title = {lang: name for lang in ("lb", "de", "fr", "en")}
        else:
            for lang in ("lb", "de", "fr", "en"):
                if not title[lang]:
                    title[lang] = name
        description = extract_localised(tags, "description")

        stable_id = f"osm:{osm_type}/{osm_id}"
        return {
            "id": stable_id,
            "slug": f"{slugify(name)}-{osm_type[0]}{osm_id}",
            "kind": kind_key,
            "group": cat["group"],
            "name": name,
            "title": title,
            "description": description,
            "lat": round(float(lat), 6) if lat is not None else None,
            "lng": round(float(lon), 6) if lon is not None else None,
            "age_min": a_min,
            "age_max": a_max,
            "family_score": score,
            "source": "osm",
            "source_license": "ODbL-1.0",
            "source_ref": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
            "osm_type": osm_type,
            "osm_id": osm_id,
            "tags_raw": tags,
            "website_url": tags.get("website") or tags.get("contact:website") or "",
            "phone": tags.get("phone") or tags.get("contact:phone") or "",
            "opening_hours": tags.get("opening_hours") or "",
            "wheelchair": tags.get("wheelchair") in {"yes", "designated"},
            # Either the place has toilets, or the place is one.  The second
            # test used to look for a key "amenity:toilets", which OSM has no
            # such thing as, so only the first half ever worked.
            "toilets": tags.get("toilets") == "yes" or tags.get("amenity") == "toilets",
            "drinking_water": tags.get("drinking_water") == "yes",
            "shade": tags.get("shade") in {"yes", "partial"},
            "fee": tags.get("fee"),
            "wikidata": tags.get("wikidata") or "",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


# -------- Mongo upsert ---------------------------------------------
async def _get_db():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "familyluxembourg")
    client = AsyncIOMotorClient(mongo_url)
    return client[db_name], client


async def ensure_indexes(db):
    await db.places.create_index("id", unique=True)
    await db.places.create_index("kind")
    await db.places.create_index("group")
    await db.places.create_index([("lat", 1), ("lng", 1)])
    await db.places.create_index("family_score")


BULK_CHUNK = 500


async def upsert_places(db, records: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Write a batch of places, in chunks rather than one round trip each.

    The ingest produces around 8,000 records. Sent individually that is 8,000
    sequential round trips to MongoDB, each waiting for the last — the same
    N+1 shape the event importers had. bulk_write sends a chunk in one go.

    `ordered=False` lets the server continue past a rejected document instead
    of abandoning the rest of the chunk, which matters because one malformed
    record should not cost the other 499. Failures are counted and logged, not
    raised: a partial import is worth keeping.

    Chunked rather than one enormous batch because MongoDB caps a command at
    16 MB, and a whole ingest of tag-laden documents can exceed that.
    """
    upserted = 0
    skipped = 0

    for start in range(0, len(records), BULK_CHUNK):
        chunk = records[start:start + BULK_CHUNK]
        ops = [
            UpdateOne(
                {"id": rec["id"]},
                {"$set": rec, "$setOnInsert": {"created_at": rec["updated_at"]}},
                upsert=True,
            )
            for rec in chunk
        ]
        try:
            res = await db.places.bulk_write(ops, ordered=False)
            # A record already stored unchanged is neither upserted nor
            # modified — it counts as skipped, as it did before.
            written = len(res.upserted_ids) + res.modified_count
            upserted += written
            skipped += len(chunk) - written
        except BulkWriteError as bwe:
            # Everything the server did accept still counted.
            details = bwe.details or {}
            written = len(details.get("upserted", [])) + details.get("nModified", 0)
            upserted += written
            skipped += len(chunk) - written
            for err in details.get("writeErrors", [])[:5]:
                logger.error("upsert rejected: %s", err.get("errmsg", err))
        except Exception as e:
            logger.error("bulk upsert failed for %d records: %s", len(chunk), e)
            skipped += len(chunk)

    return upserted, skipped


# -------- Public API -----------------------------------------------
def _parse_pbf(kinds: List[str]) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
    """Run the osmium handler synchronously (blocking, ~5 s for LU)."""
    matchers = {k: _compile_category(k) for k in kinds}
    handler = _POIHandler(matchers)
    handler.apply_file(str(PBF_CACHE), locations=True, idx="flex_mem")
    return handler.raw_counts, handler.records


async def ingest_category(kind_key: str, db=None, dry_run: bool = False) -> Dict[str, Any]:
    if kind_key not in CATEGORIES:
        raise ValueError(f"Unknown category: {kind_key}")
    await ensure_pbf()

    loop = asyncio.get_running_loop()
    raw_counts, records = await loop.run_in_executor(None, _parse_pbf, [kind_key])

    # Dedup within category
    seen: Dict[Tuple, Dict[str, Any]] = {}
    for r in records:
        if r["lat"] is None or r["lng"] is None:
            # Keep relations without coords under a unique key
            key = ("__no_coord__", r["osm_type"], r["osm_id"])
        else:
            key = _dedupe_key(r)
        cur = seen.get(key)
        if cur is None or r["family_score"] > cur["family_score"]:
            seen[key] = r
    deduped = list(seen.values())

    if dry_run:
        return {
            "kind": kind_key,
            "raw": raw_counts.get(kind_key, 0),
            "normalised": len(records),
            "deduped": len(deduped),
            "sample": deduped[:2],
        }

    if db is None:
        db, _client = await _get_db()
    await ensure_indexes(db)
    upserted, skipped = await upsert_places(db, deduped)
    return {
        "kind": kind_key,
        "raw": raw_counts.get(kind_key, 0),
        "normalised": len(records),
        "deduped": len(deduped),
        "upserted": upserted,
        "skipped": skipped,
    }


async def ingest_all(categories: Optional[List[str]] = None, db=None) -> Dict[str, Any]:
    # No `global JOB_STATE` needed: it is only ever mutated in place, never
    # rebound, so the declaration was a no-op.
    cats = categories or CATEGORY_ORDER
    JOB_STATE.update(
        status="running",
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=None,
        current="preparing",
        categories={},
        totals={"raw": 0, "upserted": 0, "skipped": 0, "errors": 0},
        message=f"Starting PBF-based ingest of {len(cats)} categories",
    )

    try:
        await ensure_pbf()
    except Exception as e:
        JOB_STATE.update(status="error", message=f"PBF download failed: {e}",
                          finished_at=datetime.now(timezone.utc).isoformat())
        return JOB_STATE

    if db is None:
        db, _client = await _get_db()
    await ensure_indexes(db)

    JOB_STATE["current"] = "parsing_pbf"
    loop = asyncio.get_running_loop()
    raw_counts, records = await loop.run_in_executor(None, _parse_pbf, cats)

    # Group by kind and dedup
    per_kind: Dict[str, List[Dict[str, Any]]] = {k: [] for k in cats}
    for r in records:
        per_kind[r["kind"]].append(r)

    for kind_key in cats:
        JOB_STATE["current"] = kind_key
        recs = per_kind.get(kind_key, [])
        seen: Dict[Tuple, Dict[str, Any]] = {}
        for r in recs:
            if r["lat"] is None or r["lng"] is None:
                key = ("__no_coord__", r["osm_type"], r["osm_id"])
            else:
                key = _dedupe_key(r)
            cur = seen.get(key)
            if cur is None or r["family_score"] > cur["family_score"]:
                seen[key] = r
        deduped = list(seen.values())
        try:
            upserted, skipped = await upsert_places(db, deduped)
            JOB_STATE["categories"][kind_key] = {
                "raw": raw_counts.get(kind_key, 0),
                "deduped": len(deduped),
                "upserted": upserted,
                "skipped": skipped,
            }
            JOB_STATE["totals"]["raw"] += raw_counts.get(kind_key, 0)
            JOB_STATE["totals"]["upserted"] += upserted
            JOB_STATE["totals"]["skipped"] += skipped
        except Exception as e:
            logger.exception("upsert failed for %s", kind_key)
            JOB_STATE["categories"][kind_key] = {"error": str(e)}
            JOB_STATE["totals"]["errors"] += 1

    JOB_STATE.update(
        status="done",
        current=None,
        finished_at=datetime.now(timezone.utc).isoformat(),
        message=(
            f"Ingest complete: {JOB_STATE['totals']['upserted']} POIs updated "
            f"across {len(cats)} categories"
        ),
    )
    return JOB_STATE


# -------- CLI entrypoint --------------------------------------------
async def _cli(argv: List[str]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return
    if argv[0] == "all":
        result = await ingest_all()
        print("Totals:", result["totals"])
        for k, v in result["categories"].items():
            print(f"  {k:22s} raw={v.get('raw','-'):>5}  ok={v.get('upserted','-'):>5}")
    else:
        db, _client = await _get_db()
        for k in argv:
            r = await ingest_category(k, db=db)
            print(f"{k:22s} raw={r['raw']:>5} deduped={r['deduped']:>5} upserted={r['upserted']:>5}")


if __name__ == "__main__":
    import sys
    asyncio.run(_cli(sys.argv[1:]))
