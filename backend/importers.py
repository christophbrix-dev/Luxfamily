"""Event importers for Phase 3/4.

Each importer pulls events from a remote source and writes them to MongoDB
with `published=False` so an admin can review before they go live.

Sources are configured in the `sources` collection so admins can add new
feeds without redeploying. Two source kinds are supported today:

  - "ical":            an iCalendar (.ics) URL — works for venues like
                       Mudam, Philharmonie, Rockhal, museums etc.
  - "data_public_lu":  a CKAN dataset resource URL on data.public.lu
                       (JSON resource). The default canton/category
                       on the source record is applied to every row.

The framework is intentionally tolerant: missing fields fall back to
sensible defaults; rows are deduplicated via (source_id, external_id).
"""

import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from icalendar import Calendar

logger = logging.getLogger("lux-backend.importers")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_localized(value: str) -> Dict[str, str]:
    return {"en": value, "de": value, "fr": value}


def _to_iso_date(value: Any) -> Optional[str]:
    """Coerce an iCal/CKAN date value to a YYYY-MM-DD string."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return value[:10] if len(value) >= 10 else None
    return None


def _build_event_doc(
    *,
    source: Dict[str, Any],
    external_id: str,
    title: str,
    description: str,
    start_date: str,
    end_date: Optional[str],
    time_str: str,
    town: str,
    lat: float,
    lng: float,
    image: str = "",
) -> Dict[str, Any]:
    now = _now_iso()
    return {
        "id": str(uuid.uuid4()),
        "title": _default_localized(title),
        "short": _default_localized(description[:120]),
        "description": _default_localized(description),
        "type": "Event",
        "canton": source.get("canton_default") or "Luxembourg",
        "town": town or source.get("town_default") or "Luxembourg",
        "category": source.get("category_default") or ["Culture"],
        "age_min": source.get("age_min_default", 0),
        "age_max": source.get("age_max_default", 99),
        "start_date": start_date,
        "end_date": end_date,
        "time": time_str,
        "price_adult": 0.0,
        "price_child": 0.0,
        "price_label": _default_localized("See details"),
        "accessibility": _default_localized("See venue"),
        "weather_fit": _default_localized("Any weather"),
        "image": image,
        "lat": lat,
        "lng": lng,
        "bookable": False,
        "published": False,  # admin reviews before publishing
        "rating": 4.5,
        "featured": False,
        "featured_until": None,
        "view_count": 0,
        "source_id": source["id"],
        "source_name": source.get("name", ""),
        "external_id": external_id,
        "created_at": now,
        "updated_at": now,
    }


async def _fetch(url: str, timeout: float = 30.0) -> bytes:
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True, headers={"User-Agent": "FamilyLuxembourg/1.0"}
    ) as cli:
        r = await cli.get(url)
        r.raise_for_status()
        return r.content


# ---------------------------------------------------------------------------
# iCal importer
# ---------------------------------------------------------------------------
async def _import_ical(source: Dict[str, Any], db) -> Tuple[int, int]:
    """Returns (inserted, skipped)."""
    raw = await _fetch(source["url"])
    cal = Calendar.from_ical(raw)

    inserted = 0
    skipped = 0
    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=365)

    for component in cal.walk("VEVENT"):
        uid = str(component.get("UID", "")).strip()
        if not uid:
            continue

        start = component.get("DTSTART")
        if not start:
            continue
        start_val = start.dt

        # Filter out past events older than 1 day to avoid clutter.
        start_iso = _to_iso_date(start_val)
        if not start_iso:
            continue
        if datetime.fromisoformat(start_iso).date() < today - timedelta(days=1):
            skipped += 1
            continue
        if datetime.fromisoformat(start_iso).date() > horizon:
            skipped += 1
            continue

        # Dedup on (source_id, external_id).
        existing = await db.events.find_one(
            {"source_id": source["id"], "external_id": uid}, {"_id": 0, "id": 1}
        )
        if existing:
            skipped += 1
            continue

        end = component.get("DTEND")
        end_iso = _to_iso_date(end.dt) if end else None

        time_str = ""
        if isinstance(start_val, datetime):
            time_str = start_val.strftime("%H:%M")
            if end and isinstance(end.dt, datetime):
                time_str += " - " + end.dt.strftime("%H:%M")

        title = str(component.get("SUMMARY", "Untitled event")).strip()
        description = str(component.get("DESCRIPTION", "")).strip() or title
        location = str(component.get("LOCATION", "")).strip()

        # Best-effort coordinates; venue locations are mostly Luxembourg.
        lat = float(source.get("lat_default", 49.6116))
        lng = float(source.get("lng_default", 6.1319))

        doc = _build_event_doc(
            source=source,
            external_id=uid,
            title=title,
            description=description,
            start_date=start_iso,
            end_date=end_iso,
            time_str=time_str,
            town=location or source.get("town_default") or "Luxembourg",
            lat=lat,
            lng=lng,
            image=source.get("image_default", ""),
        )
        await db.events.insert_one(doc)
        inserted += 1

    return inserted, skipped


# ---------------------------------------------------------------------------
# data.public.lu importer (CKAN JSON resource)
# ---------------------------------------------------------------------------
async def _import_data_public_lu(source: Dict[str, Any], db) -> Tuple[int, int]:
    """Imports a JSON resource from a CKAN portal (data.public.lu / similar)."""
    raw = await _fetch(source["url"])

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError("Source did not return valid JSON")

    rows: List[Dict[str, Any]]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        # Try common CKAN response shapes.
        rows = payload.get("result", {}).get("records") or payload.get("records") or []
    else:
        rows = []

    inserted = 0
    skipped = 0
    today = datetime.now(timezone.utc).date()

    for row in rows:
        if not isinstance(row, dict):
            continue
        external_id = str(row.get("id") or row.get("uid") or row.get("_id") or "")
        if not external_id:
            continue

        title = row.get("title") or row.get("name") or row.get("nom") or "Event"
        description = row.get("description") or row.get("description_long") or title
        start_iso = _to_iso_date(
            row.get("start") or row.get("start_date") or row.get("date") or row.get("date_debut")
        )
        if not start_iso:
            continue
        if datetime.fromisoformat(start_iso).date() < today - timedelta(days=1):
            skipped += 1
            continue

        existing = await db.events.find_one(
            {"source_id": source["id"], "external_id": external_id}, {"_id": 0, "id": 1}
        )
        if existing:
            skipped += 1
            continue

        end_iso = _to_iso_date(row.get("end") or row.get("end_date") or row.get("date_fin"))
        time_str = row.get("time") or row.get("heure") or ""

        # Coordinates: prefer per-row, otherwise fall back to source defaults.
        try:
            lat = float(row.get("lat") or row.get("latitude") or source.get("lat_default") or 49.6116)
            lng = float(row.get("lng") or row.get("lon") or row.get("longitude") or source.get("lng_default") or 6.1319)
        except (TypeError, ValueError):
            lat, lng = 49.6116, 6.1319

        town = row.get("town") or row.get("ville") or row.get("commune") or source.get("town_default") or "Luxembourg"
        image = row.get("image") or row.get("photo") or source.get("image_default", "")

        doc = _build_event_doc(
            source=source,
            external_id=external_id,
            title=str(title),
            description=str(description),
            start_date=start_iso,
            end_date=end_iso,
            time_str=str(time_str),
            town=str(town),
            lat=lat,
            lng=lng,
            image=str(image) if image else "",
        )
        await db.events.insert_one(doc)
        inserted += 1

    return inserted, skipped


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
IMPORTERS = {
    "ical": _import_ical,
    "data_public_lu": _import_data_public_lu,
    "html_scraper": None,  # filled in below after the function is declared
}


def _pick(el, selector: Optional[str], attr: Optional[str] = None) -> str:
    if not selector or not el:
        return ""
    found = el.select_one(selector)
    if not found:
        return ""
    if attr:
        return (found.get(attr) or "").strip()
    return found.get_text(" ", strip=True)


def _abs_url(base: str, href: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        from urllib.parse import urlparse

        parsed = urlparse(base)
        return f"{parsed.scheme}://{parsed.netloc}{href}"
    return href


async def _import_html_scraper(source: Dict[str, Any], db) -> Tuple[int, int]:
    """Generic HTML scraper. Source.selectors must be a dict, e.g.:

      {
        "item":  ".event-card",          # required, matches each event block
        "title": "h3",                   # required, relative within item
        "date":  ".date",                # required, ISO/text parsed loosely
        "location": ".venue",            # optional
        "description": ".excerpt",       # optional
        "image": ".thumb img",           # optional, picks first matching <img src>
        "link": "a",                     # optional, used as external_id basis
        "date_attr": "datetime"          # optional: attr to read date from instead
                                          # of text (e.g. "datetime" on <time>)
      }

    Works for most municipality/venue listing pages without requiring custom code.
    Events created have ``published=False`` so an admin can review them.
    """
    selectors = source.get("selectors") or {}
    item_sel = selectors.get("item")
    title_sel = selectors.get("title")
    date_sel = selectors.get("date")
    if not (item_sel and title_sel and date_sel):
        raise RuntimeError("html_scraper requires item, title and date selectors")

    raw = await _fetch(source["url"])
    soup = BeautifulSoup(raw, "lxml")
    items = soup.select(item_sel)

    inserted = 0
    skipped = 0
    today = datetime.now(timezone.utc).date()

    for el in items:
        title = _pick(el, title_sel)
        if not title:
            skipped += 1
            continue

        date_attr = selectors.get("date_attr")
        raw_date = _pick(el, date_sel, attr=date_attr)
        start_iso = _to_iso_date(raw_date)
        if not start_iso:
            # Best-effort fuzzy parsing for non-ISO date strings.
            try:
                parsed = datetime.strptime(raw_date[:10], "%d.%m.%Y")
                start_iso = parsed.date().isoformat()
            except (ValueError, TypeError):
                skipped += 1
                continue

        if datetime.fromisoformat(start_iso).date() < today - timedelta(days=1):
            skipped += 1
            continue

        description = _pick(el, selectors.get("description")) or title
        town = _pick(el, selectors.get("location")) or source.get("town_default", "Luxembourg")
        image_src = _pick(el, selectors.get("image"), attr="src")
        link = _pick(el, selectors.get("link"), attr="href")
        image = _abs_url(source["url"], image_src) if image_src else source.get("image_default", "")
        external_id = link or f"{source['id']}:{start_iso}:{title[:60]}"

        existing = await db.events.find_one(
            {"source_id": source["id"], "external_id": external_id}, {"_id": 0, "id": 1}
        )
        if existing:
            skipped += 1
            continue

        doc = _build_event_doc(
            source=source,
            external_id=external_id,
            title=title,
            description=description,
            start_date=start_iso,
            end_date=None,
            time_str="",
            town=town,
            lat=float(source.get("lat_default", 49.6116)),
            lng=float(source.get("lng_default", 6.1319)),
            image=image,
        )
        await db.events.insert_one(doc)
        inserted += 1

    return inserted, skipped


IMPORTERS["html_scraper"] = _import_html_scraper


async def run_source(source: Dict[str, Any], db) -> Dict[str, Any]:
    """Run a single source and persist the result on the source record."""
    kind = source.get("kind")
    importer = IMPORTERS.get(kind)
    started = _now_iso()
    if not importer:
        result = {
            "last_run_at": started,
            "last_status": "error",
            "last_error": f"Unknown source kind: {kind}",
            "last_imported_count": 0,
        }
    else:
        try:
            inserted, skipped = await importer(source, db)
            result = {
                "last_run_at": started,
                "last_status": "ok",
                "last_error": None,
                "last_imported_count": inserted,
                "last_skipped_count": skipped,
            }
        except Exception as exc:
            logger.exception("Importer %s failed", source.get("name"))
            result = {
                "last_run_at": started,
                "last_status": "error",
                "last_error": str(exc)[:300],
                "last_imported_count": 0,
            }

    await db.sources.update_one({"id": source["id"]}, {"$set": result})
    return result


async def run_all_active(db) -> List[Dict[str, Any]]:
    cursor = db.sources.find({"active": True}, {"_id": 0})
    sources = await cursor.to_list(length=100)
    out = []
    for s in sources:
        out.append({"source": s["id"], "name": s.get("name"), **(await run_source(s, db))})
    return out
