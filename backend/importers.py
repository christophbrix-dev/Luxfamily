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
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser
from icalendar import Calendar

from crawler_utils import RobotsBlocked, polite_get

logger = logging.getLogger("lux-backend.importers")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_localized(value: str) -> Dict[str, str]:
    return {"en": value, "de": value, "fr": value}


def _to_iso_date(value: Any) -> Optional[str]:
    """Coerce various date formats to a YYYY-MM-DD string. Understands ISO,
    German (24. Juni 2026 / 24.06.2026), French (24 juin 2026 / 24/06/2026),
    plain timestamps and `datetime` objects."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    # Fast path: already ISO.
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    # dateutil handles FR/DE month names and slash/dot separators.
    try:
        # dayfirst=True so 06/07/2026 is 6 July (LU/FR/DE convention).
        parsed = dateutil_parser.parse(s, dayfirst=True, fuzzy=True)
        return parsed.date().isoformat()
    except (ValueError, dateutil_parser.ParserError, OverflowError):
        return None


def _extract_time_range(value: str) -> str:
    """Best-effort time-range extractor: pulls '14h30' or '14:30' patterns."""
    if not value:
        return ""
    hits = re.findall(r"\b(\d{1,2})[:h](\d{2})\b", value)
    if not hits:
        return ""
    times = [f"{int(h):02d}:{m}" for h, m in hits[:2]]
    return " - ".join(times) if len(times) == 2 else times[0]


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
        "published": True,   # crawler results auto-publish per user request
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
    """Polite fetch: obeys robots.txt and per-host rate limit."""
    resp = await polite_get(url, timeout=timeout)
    return resp.content


async def _fetch_text(url: str, timeout: float = 30.0) -> str:
    resp = await polite_get(url, timeout=timeout)
    return resp.text


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
    "json_ld": None,       # filled in below after the function is declared
    "kids_in_lux": None,   # filled in below after the function is declared
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


# ---------------------------------------------------------------------------
# JSON-LD (schema.org/Event) importer
# ---------------------------------------------------------------------------
async def _import_json_ld(source: Dict[str, Any], db) -> Tuple[int, int]:
    """Extract schema.org Event objects from JSON-LD blocks on a page.

    Most modern venue and ticketing sites (Philharmonie, Rockhal, Mudam,
    Ticket-Régie, EventBrite, etc.) embed one or more
    ``<script type="application/ld+json">`` blocks describing their events
    in structured schema.org format. This importer parses those and yields
    much cleaner data than CSS scraping.

    The source ``selectors`` field can optionally include:
      - ``list_url``: if the URL is a listing page whose JSON-LD only lists
        ItemList/Event links, we visit each event page.
    """
    html = await _fetch_text(source["url"])
    events = _extract_jsonld_events(html, base_url=source["url"])
    # If nothing found on the listing page itself, try to enumerate linked
    # event pages via schema.org ItemList and follow up to 20 of them.
    if not events:
        links = _extract_event_links(html, base_url=source["url"])
        for link in links[:20]:
            try:
                sub_html = await _fetch_text(link)
                events.extend(_extract_jsonld_events(sub_html, base_url=link))
            except RobotsBlocked as rb:
                logger.info("Skipping %s: %s", link, rb)
            except Exception as exc:
                logger.warning("Sub-page %s failed: %s", link, exc)

    inserted = 0
    skipped = 0
    today = datetime.now(timezone.utc).date()

    for ev in events:
        external_id = ev.get("@id") or ev.get("url") or ev.get("identifier") or ""
        title = ev.get("name") or "Event"
        if isinstance(title, list):
            title = title[0] if title else "Event"
        start_iso = _to_iso_date(ev.get("startDate"))
        if not start_iso or not title:
            skipped += 1
            continue
        if datetime.fromisoformat(start_iso).date() < today - timedelta(days=1):
            skipped += 1
            continue

        # Coerce id fallback if missing.
        if not external_id:
            external_id = f"{source['id']}:{start_iso}:{str(title)[:60]}"

        existing = await db.events.find_one(
            {"source_id": source["id"], "external_id": external_id}, {"_id": 0, "id": 1}
        )
        if existing:
            skipped += 1
            continue

        end_iso = _to_iso_date(ev.get("endDate"))
        description = ev.get("description") or ""
        if isinstance(description, list):
            description = description[0] if description else ""

        # Location handling
        loc = ev.get("location") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        town = source.get("town_default", "Luxembourg")
        lat = float(source.get("lat_default", 49.6116))
        lng = float(source.get("lng_default", 6.1319))
        if isinstance(loc, dict):
            addr = loc.get("address") or {}
            if isinstance(addr, dict):
                town = addr.get("addressLocality") or town
            geo = loc.get("geo") or {}
            if isinstance(geo, dict):
                try:
                    lat = float(geo.get("latitude", lat))
                    lng = float(geo.get("longitude", lng))
                except (TypeError, ValueError):
                    pass

        # Image handling — may be str, list, or {url: ...}
        image_val = ev.get("image") or ""
        if isinstance(image_val, list):
            image_val = image_val[0] if image_val else ""
        if isinstance(image_val, dict):
            image_val = image_val.get("url", "")
        image = _abs_url(source["url"], str(image_val))

        # Time handling
        time_str = ""
        try:
            sdt = ev.get("startDate")
            if isinstance(sdt, str) and "T" in sdt:
                dt = dateutil_parser.parse(sdt)
                time_str = dt.strftime("%H:%M")
                edt = ev.get("endDate")
                if isinstance(edt, str) and "T" in edt:
                    time_str += " - " + dateutil_parser.parse(edt).strftime("%H:%M")
        except Exception:
            pass

        doc = _build_event_doc(
            source=source,
            external_id=str(external_id),
            title=str(title),
            description=str(description),
            start_date=start_iso,
            end_date=end_iso,
            time_str=time_str,
            town=str(town),
            lat=lat,
            lng=lng,
            image=image,
        )
        await db.events.insert_one(doc)
        inserted += 1

    return inserted, skipped


def _extract_jsonld_events(html: str, *, base_url: str) -> List[Dict[str, Any]]:
    """Parse all <script type=application/ld+json> blocks and yield Event objects."""
    soup = BeautifulSoup(html, "lxml")
    out: List[Dict[str, Any]] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            raw = tag.string or tag.get_text() or ""
            if not raw.strip():
                continue
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        _collect_events(data, out)
    return out


def _collect_events(node: Any, out: List[Dict[str, Any]]) -> None:
    """Recursively walk JSON-LD tree, collecting Event nodes."""
    if isinstance(node, dict):
        node_type = node.get("@type") or node.get("type")
        types = [node_type] if isinstance(node_type, str) else (node_type or [])
        if any(t and "Event" in t for t in types):
            out.append(node)
        # Descend into @graph / itemListElement / arrays
        for key in ("@graph", "itemListElement", "item", "subEvent", "workPerformed"):
            if key in node:
                _collect_events(node[key], out)
    elif isinstance(node, list):
        for item in node:
            _collect_events(item, out)


def _extract_event_links(html: str, *, base_url: str) -> List[str]:
    """Fallback: pull URLs from ItemList JSON-LD or from anchor tags that
    plausibly link to an event detail page."""
    soup = BeautifulSoup(html, "lxml")
    urls: List[str] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except Exception:
            continue
        _collect_urls(data, urls)
    # Also try anchor tags with event-ish paths.
    if not urls:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(seg in href.lower() for seg in ("/event", "/agenda", "/manifestation", "/veranstaltung")):
                urls.append(_abs_url(base_url, href))
    # Dedup, keep order
    seen = set()
    unique = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def _collect_urls(node: Any, out: List[str]) -> None:
    if isinstance(node, dict):
        url = node.get("url")
        if isinstance(url, str) and url.startswith("http"):
            out.append(url)
        for v in node.values():
            _collect_urls(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_urls(v, out)


IMPORTERS["json_ld"] = _import_json_ld


# ---------------------------------------------------------------------------
# Sitemap importer — for domain-wide event discovery
# ---------------------------------------------------------------------------
_SITEMAP_EVENT_PATTERNS = re.compile(
    r"/(events?|agenda|manifestations?|veranstaltungen?|programme?|programm"
    r"|expo|expositions?|kalender|calendar|whats?[-_]on"
    r"|actualit(e|é)s?|ateliers?|workshops?"
    r"|concerts?|spectacles?|festivals?|kids?|jeunesse|jeunes|enfants?"
    r"|familles?|familien?)([/_-]|$)",
    re.IGNORECASE,
)


async def _import_sitemap(source: Dict[str, Any], db) -> Tuple[int, int]:
    """Read a domain's sitemap.xml, filter for event-like URLs, then extract
    JSON-LD Event objects from each candidate page.

    Great fit for communes and small venues that don't expose a clean event
    feed but do have sitemap entries for each event page.

    ``source.url`` may point to /sitemap.xml directly, or to any URL on the
    domain (we auto-discover the sitemap via /robots.txt or /sitemap.xml).
    Optional ``selectors.max_pages`` (default 40) caps sub-page fetches.
    """
    from urllib.parse import urlparse, urljoin

    selectors = source.get("selectors") or {}
    max_pages = int(selectors.get("max_pages") or 20)

    parsed = urlparse(source["url"])
    origin = f"{parsed.scheme}://{parsed.netloc}"

    # Resolve the actual sitemap URL
    sitemap_url = source["url"] if source["url"].endswith(".xml") else None
    if not sitemap_url:
        # Try robots.txt first (sites often list all sitemaps there)
        try:
            robots = await _fetch_text(origin + "/robots.txt")
            for line in robots.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    break
        except Exception:
            pass
    if not sitemap_url:
        sitemap_url = origin + "/sitemap.xml"

    # Fetch sitemap (may be a sitemap index containing more sitemaps)
    try:
        xml = await _fetch_text(sitemap_url)
    except Exception as exc:
        raise RuntimeError(f"Could not fetch sitemap {sitemap_url}: {exc}")

    all_urls = _collect_sitemap_urls(xml, base=origin)

    # Recursively expand sitemap indexes (one level deep). We recurse when
    # a URL looks like another sitemap: ends with .xml OR the path contains
    # "sitemap" (e.g. paginated sitemap indexes like ?page=1).
    def _looks_like_sitemap(u: str) -> bool:
        low = u.lower()
        return low.endswith(".xml") or "sitemap" in low

    nested = [u for u in all_urls if _looks_like_sitemap(u)]
    if nested and len(all_urls) < 30:
        expanded: List[str] = []
        for nested_url in nested[:10]:
            try:
                sub_xml = await _fetch_text(nested_url)
                expanded.extend(_collect_sitemap_urls(sub_xml, base=origin))
            except Exception as e:
                logger.info("nested sitemap %s failed: %s", nested_url, e)
        # Replace originals with what we found inside them
        all_urls = expanded or all_urls

    # Filter to event-like paths, dedup, cap
    candidates: List[str] = []
    seen = set()
    for u in all_urls:
        if _SITEMAP_EVENT_PATTERNS.search(u) and u not in seen:
            seen.add(u)
            candidates.append(u)
        if len(candidates) >= max_pages:
            break

    logger.info(
        "[sitemap] %s → %d total sitemap URLs, %d event-like candidates",
        source["name"], len(all_urls), len(candidates),
    )
    if not candidates and all_urls:
        # Log a few examples of what IS in the sitemap so admin can adjust patterns
        logger.info("[sitemap] sample non-matching URLs: %s", all_urls[:5])

    inserted = 0
    skipped = 0
    today = datetime.now(timezone.utc).date()

    for page_url in candidates:
        try:
            html = await _fetch_text(page_url)
        except RobotsBlocked:
            skipped += 1
            continue
        except Exception as exc:
            logger.info("skip %s: %s", page_url, exc)
            skipped += 1
            continue

        events = _extract_jsonld_events(html, base_url=page_url)
        if not events:
            # Fallback: try OpenGraph metadata as a "lite" event record
            og = _extract_open_graph_event(html, page_url=page_url)
            if og:
                events = [og]
        for ev in events:
            title = ev.get("name") or ""
            if isinstance(title, list):
                title = title[0] if title else ""
            start_iso = _to_iso_date(ev.get("startDate"))
            if not (title and start_iso):
                skipped += 1
                continue
            if datetime.fromisoformat(start_iso).date() < today - timedelta(days=1):
                skipped += 1
                continue

            external_id = ev.get("@id") or ev.get("url") or page_url
            existing = await db.events.find_one(
                {"source_id": source["id"], "external_id": external_id}, {"_id": 0, "id": 1}
            )
            if existing:
                skipped += 1
                continue

            end_iso = _to_iso_date(ev.get("endDate"))
            desc = ev.get("description") or ""
            if isinstance(desc, list):
                desc = desc[0] if desc else ""

            loc = ev.get("location") or {}
            if isinstance(loc, list):
                loc = loc[0] if loc else {}
            town = source.get("town_default", "Luxembourg")
            lat = float(source.get("lat_default", 49.6116))
            lng = float(source.get("lng_default", 6.1319))
            if isinstance(loc, dict):
                addr = loc.get("address") or {}
                if isinstance(addr, dict):
                    town = addr.get("addressLocality") or town
                geo = loc.get("geo") or {}
                if isinstance(geo, dict):
                    try:
                        lat = float(geo.get("latitude", lat))
                        lng = float(geo.get("longitude", lng))
                    except (TypeError, ValueError):
                        pass

            image_val = ev.get("image") or ""
            if isinstance(image_val, list):
                image_val = image_val[0] if image_val else ""
            if isinstance(image_val, dict):
                image_val = image_val.get("url", "")
            image = _abs_url(page_url, str(image_val))

            time_str = ""
            try:
                sdt = ev.get("startDate")
                if isinstance(sdt, str) and "T" in sdt:
                    time_str = dateutil_parser.parse(sdt).strftime("%H:%M")
                    edt = ev.get("endDate")
                    if isinstance(edt, str) and "T" in edt:
                        time_str += " - " + dateutil_parser.parse(edt).strftime("%H:%M")
            except Exception:
                pass

            doc = _build_event_doc(
                source=source,
                external_id=str(external_id),
                title=str(title),
                description=str(desc),
                start_date=start_iso,
                end_date=end_iso,
                time_str=time_str,
                town=str(town),
                lat=lat,
                lng=lng,
                image=image,
            )
            await db.events.insert_one(doc)
            inserted += 1

    return inserted, skipped


def _collect_sitemap_urls(xml_text: str, *, base: str) -> List[str]:
    """Extract every <loc> URL from a sitemap or sitemap-index XML string."""
    urls: List[str] = []
    try:
        soup = BeautifulSoup(xml_text, "lxml-xml")
    except Exception:
        soup = BeautifulSoup(xml_text, "lxml")
    for loc in soup.find_all("loc"):
        text = (loc.get_text() or "").strip()
        if text:
            urls.append(text)
    return urls


def _extract_open_graph_event(html: str, *, page_url: str) -> Optional[Dict[str, Any]]:
    """Best-effort: if a page is clearly an event page but lacks JSON-LD,
    return a minimal Event dict from OpenGraph + <time> tags + URL-slug
    date parsing. Returns None if we can't confidently detect a date."""
    soup = BeautifulSoup(html, "lxml")

    def og(prop: str) -> str:
        t = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        return (t.get("content") if t else "") or ""

    title = og("og:title") or (soup.title.get_text(strip=True) if soup.title else "")
    desc = og("og:description")
    image = og("og:image")

    # 1. URL-slug date parsing (Mudam etc. embed date in slug — most reliable
    #    for our LU sources because <time> tags often only contain a time-of-day)
    start = _extract_date_from_url(page_url)

    # 2. <time datetime="..."> tags (require a value that includes a year)
    if not start:
        for tag in soup.find_all("time"):
            dt = tag.get("datetime") or tag.get_text(strip=True)
            iso = _to_iso_date(dt) if dt else None
            if iso and iso.startswith(("19", "20")):
                start = iso
                break

    # 3. Meta tags (some CMSes)
    if not start:
        for prop in ("event:start_time", "article:published_time",
                      "event:start_date", "startDate"):
            dt = og(prop)
            iso = _to_iso_date(dt) if dt else None
            if iso and iso.startswith(("19", "20")):
                start = iso
                break

    # 4. Last resort: date-like strings in the visible page text
    if not start:
        text_blob = soup.get_text(" ")[:5000]
        date_match = re.search(
            r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}"
            r"|\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December"
            r"|Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember"
            r"|janvier|février|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre)"
            r"\s+\d{4})\b",
            text_blob, re.IGNORECASE,
        )
        if date_match and _to_iso_date(date_match.group(1)):
            start = date_match.group(1)

    if not start or not title:
        return None

    return {
        "@id": page_url,
        "name": title,
        "description": desc,
        "startDate": start,
        "image": image,
    }


# Match date fragments in URL slugs: "28-aug-2026", "2-sept-2026",
# "8-ao%C3%BBt-2026" (URL-encoded "août"), "2026-08-28", "28-08-2026".
_URL_DATE_MONTHS = {
    "jan": 1, "januar": 1, "january": 1, "janvier": 1,
    "feb": 2, "februar": 2, "february": 2, "fevrier": 2, "février": 2, "fév": 2,
    "mar": 3, "märz": 3, "marz": 3, "march": 3, "mars": 3,
    "apr": 4, "april": 4, "avril": 4, "avr": 4,
    "mai": 5, "may": 5,
    "jun": 6, "juni": 6, "june": 6, "juin": 6,
    "jul": 7, "juli": 7, "july": 7, "juillet": 7, "juil": 7,
    "aug": 8, "august": 8, "aout": 8, "août": 8,
    "sep": 9, "sept": 9, "september": 9, "septembre": 9,
    "oct": 10, "okt": 10, "october": 10, "oktober": 10, "octobre": 10,
    "nov": 11, "november": 11, "novembre": 11,
    "dec": 12, "dez": 12, "december": 12, "dezember": 12, "décembre": 12, "déc": 12,
}


def _extract_date_from_url(url: str) -> str:
    """Look for date-like patterns in the last segment(s) of a URL slug."""
    from urllib.parse import unquote
    slug = unquote(url).lower()

    # Pattern 1: YYYY-MM-DD anywhere
    m = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", slug)
    if m:
        y, mo, d = m.groups()
        try:
            return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        except ValueError:
            pass

    # Pattern 2: DD-MMM-YYYY (e.g. "28-aug-2026", "2-sept-2026")
    m = re.search(r"\b(\d{1,2})[-_ ]([a-zàâçéèêëîïôûùüÿñæœ]+)[-_ ](20\d{2})\b", slug)
    if m:
        d, mon_name, y = m.groups()
        mon = _URL_DATE_MONTHS.get(mon_name[:5]) or _URL_DATE_MONTHS.get(mon_name[:4]) or _URL_DATE_MONTHS.get(mon_name[:3])
        if mon:
            try:
                return f"{int(y):04d}-{mon:02d}-{int(d):02d}"
            except ValueError:
                pass

    # Pattern 3: DD-MM-YYYY (numeric)
    m = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b", slug)
    if m:
        d, mo, y = m.groups()
        try:
            return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        except ValueError:
            pass

    return ""


IMPORTERS["sitemap"] = _import_sitemap


# --- kids-in-lux.com custom crawler --------------------------------------
# Runs the sync crawler in a worker thread and returns (inserted, skipped) so
# it plugs into the same `run_source` / cron flow as the JSON-LD / sitemap
# importers.
async def _import_kids_in_lux(source: Dict[str, Any], db) -> tuple[int, int]:
    import asyncio

    def _run_sync() -> tuple[int, int]:
        # Late-import to keep the module boot fast when the source isn't used.
        from crawlers import kids_in_lux as k
        from pymongo import MongoClient

        client = MongoClient(os.environ["MONGO_URL"])
        sdb    = client[os.environ["DB_NAME"]]
        src_row = sdb.sources.find_one({"id": source["id"]}) or source

        inserted = updated = failed = 0
        try:
            import httpx
            with httpx.Client() as hx:
                for index_url, cats, ev_type in k.INDEX_URLS:
                    details = k.list_detail_urls(index_url, hx)
                    for url in details:
                        html = k.fetch(url, hx)
                        if not html:
                            failed += 1
                            continue
                        parsed = k.parse_detail(url, html)
                        if not parsed:
                            failed += 1
                            continue
                        status = k.upsert_event(sdb, parsed, cats, ev_type, source["id"])
                        if status == "inserted":
                            inserted += 1
                        else:
                            updated += 1
                        import time as _t
                        _t.sleep(k.PAUSE_S)
        finally:
            client.close()
        return inserted, failed

    return await asyncio.to_thread(_run_sync)


IMPORTERS["kids_in_lux"] = _import_kids_in_lux


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
        except RobotsBlocked as rb:
            logger.warning("Source %s blocked by robots.txt: %s", source.get("name"), rb)
            result = {
                "last_run_at": started,
                "last_status": "blocked_by_robots",
                "last_error": str(rb)[:300],
                "last_imported_count": 0,
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
