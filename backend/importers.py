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

import asyncio
import html as html_lib
import json
import logging
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser
from icalendar import Calendar

import content_filter
from town_names import canonical_town
from crawler_utils import RobotsBlocked, polite_get

logger = logging.getLogger("lux-backend.importers")

# How many sources we crawl at once, and how long a single source may take
# before we give up on it and move on to the next.
MAX_CONCURRENT_SOURCES = 4
SOURCE_TIMEOUT_SECONDS = 180


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


# WordPress page builders leave their layout markup in the fields a feed
# exposes, so a description arrives as 700 characters of
# `[et_pb_section fb_built="1" _builder_version="4.24.2" …]` wrapped around two
# sentences of actual text. 51 of 354 events in the live database read that way
# — every one of them from a commune running Divi.
#
# Only the known builder prefixes are removed, not every bracketed word:
# "[Sold out]" and "[FR]" are things a human wrote and has to survive.
_PAGE_BUILDER = re.compile(
    r"\[/?(?:et_pb_|vc_|fusion_|av_|dt_|mk_)[a-z0-9_]*(?:\s[^\]]*)?\]"
    r"|\[/?(?:caption|gallery|embed|audio|video|playlist|vc_row|vc_column)"
    r"(?:\s[^\]]*)?\]",
    re.I,
)


def _strip_page_builder(text: str) -> str:
    """Remove page-builder shortcodes, keeping the text they wrapped."""
    if not text or "[" not in text:
        return text
    return re.sub(r"\s{2,}", " ", _PAGE_BUILDER.sub(" ", text)).strip()


# Where a sitemap lives when it is not at /sitemap.xml. Yoast SEO — which most
# Luxembourg commune sites run — publishes /sitemap_index.xml, and WordPress
# 5.5 and later serves /wp-sitemap.xml.
SITEMAP_FALLBACKS = ("/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap.xml")


def _sitemaps_from_robots(robots_txt: str) -> List[str]:
    """The Sitemap: lines of a robots.txt, in the order they appear."""
    found = []
    for line in robots_txt.splitlines():
        if line.lower().lstrip().startswith("sitemap:"):
            value = line.split(":", 1)[1].strip()
            if value:
                found.append(value)
    return found


async def _find_sitemap(source_url: str, origin: str) -> Tuple[str, str]:
    """(url, xml) of the first sitemap that answers. Raises when none does.

    A configured URL is tried first and usually wins. It is not trusted to be
    right, though, and that is the point of this function: every one of these
    sources was seeded with `<domain>/sitemap.xml` appended, so the configured
    URL always ended in .xml, which satisfied the old "is it already a sitemap"
    check — and skipped the robots.txt lookup underneath it. The discovery code
    existed and was unreachable for exactly the sources that needed it. 22 of
    45 inactive sources failed with 404, and robots.txt named the real address
    on several of them.

    robots.txt comes next because a site declaring its own sitemap there is
    telling us the answer, and we already fetch that file for politeness. The
    guessed paths come last.
    """
    tried: List[str] = []
    errors: List[str] = []

    async def attempt(url: str):
        """The sitemap at `url`, or None. Never asks the same host twice."""
        if not url or url in tried:
            return None
        tried.append(url)
        try:
            return await _fetch_text(url)
        except Exception as exc:
            errors.append(f"{url} ({type(exc).__name__})")
            return None

    # The configured URL first, and nothing else when it works. Building the
    # whole candidate list up front would fetch robots.txt from every site on
    # every run, including the ones already pointing at the right file — an
    # extra request per source, and under a crawl delay an extra wait too.
    if source_url.endswith(".xml"):
        xml = await attempt(source_url)
        if xml is not None:
            return source_url, xml

    try:
        declared = _sitemaps_from_robots(await _fetch_text(origin + "/robots.txt"))
    except Exception:
        # No robots.txt, or the host is unreachable. polite_get already refuses
        # the host in the second case, so the guesses below fail too and the
        # error the caller sees will say so.
        declared = []

    for url in [*declared, *(origin + path for path in SITEMAP_FALLBACKS)]:
        xml = await attempt(url)
        if xml is not None:
            return url, xml

    raise RuntimeError("No sitemap found. Tried: " + "; ".join(errors))


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
) -> Optional[Dict[str, Any]]:
    """Build the stored event, or None when it does not belong in a family app.

    The check sits here because this is the one place all five feed importers
    pass through, so nothing explicit can reach the database by way of an
    importer that forgot to ask. Refusal happens before the document exists:
    Christoph asked that this content never be "eingespielt", and the cheapest
    way to keep that promise is to never write it down.

    What is refused is only NSFW material — see content_filter for why an
    over-18 marker is deliberately not enough. Bars, wine tastings and the
    Schueberfouer stay.
    """
    # Clean before filtering and before storing: markup must not hide a word
    # the filter looks for, and it must never reach a reader either. Some of
    # these descriptions are markup end to end, and an empty description is
    # more honest than a wall of shortcodes — the title carries the meaning.
    description = _strip_page_builder(description) or title

    verdict = content_filter.assess(title, description)
    if verdict:
        reason, matched = verdict
        # The matched term and the id, not the text: enough to audit the rule
        # and find the page again, without copying the content into the log.
        logger.warning(
            "Refused %s event from %s (%r matched %s)",
            reason, source.get("name", "?"), matched, external_id[:120],
        )
        return None

    now = _now_iso()
    return {
        "id": str(uuid.uuid4()),
        "title": _default_localized(title),
        "short": _default_localized(description[:120]),
        "description": _default_localized(description),
        "type": "Event",
        "canton": source.get("canton_default") or "Luxembourg",
        "town": canonical_town(town or source.get("town_default") or "Luxembourg"),
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
        # Where this coordinate came from. Every importer falls back to the
        # source's lat_default, which is a commune centroid or a venue's front
        # door — never the event's own address. Saying so lets geocode_events
        # find these again; inferring it from a missing field is how they were
        # missed, since lat is always set to something.
        "geocode_precision": "source_default",
        "geocode_source": "source",
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
async def _known_external_ids(source: Dict[str, Any], db) -> set:
    """Every external_id we already hold for this source, fetched in one query.

    Each importer used to run a find_one per candidate row, so a 500-entry feed
    meant 500 sequential round-trips just to answer "do we have this already?".
    Loading the set once replaces all of them. Callers add to it as they insert,
    so duplicate ids inside a single feed still collapse.
    """
    rows = await db.events.find(
        {"source_id": source["id"]}, {"_id": 0, "external_id": 1}
    ).to_list(length=None)
    return {r["external_id"] for r in rows if r.get("external_id")}


async def _import_ical(source: Dict[str, Any], db) -> Tuple[int, int]:
    """Returns (inserted, skipped)."""
    raw = await _fetch(source["url"])
    cal = Calendar.from_ical(raw)

    known_ids = await _known_external_ids(source, db)
    inserted = 0
    skipped = 0
    blocked = 0   # refused by content_filter, never stored
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

        # Dedup on (source_id, external_id), against the set loaded up front.
        if uid in known_ids:
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
            town=canonical_town(location or source.get("town_default") or "Luxembourg"),
            lat=lat,
            lng=lng,
            image=source.get("image_default", ""),
        )
        if doc is None:
            blocked += 1
            continue
        await db.events.insert_one(doc)
        known_ids.add(doc["external_id"])
        inserted += 1

    return inserted, skipped, blocked


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

    known_ids = await _known_external_ids(source, db)
    inserted = 0
    skipped = 0
    blocked = 0   # refused by content_filter, never stored
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

        if external_id in known_ids:
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
            town=canonical_town(str(town)),
            lat=lat,
            lng=lng,
            image=str(image) if image else "",
        )
        if doc is None:
            blocked += 1
            continue
        await db.events.insert_one(doc)
        known_ids.add(doc["external_id"])
        inserted += 1

    return inserted, skipped, blocked


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


def _clean_location(text: str) -> str:
    """The venue out of a labelled field.

    Sites label these in the markup rather than around it: vdl.lu writes
    "Lieu | Théâtre des Capucins" inside one element. Stored whole, the label
    travels with the value into the town field and into the geocoder, which
    then has to make sense of the word "Lieu".

    Only a labelled separator is trimmed. A venue that legitimately contains a
    dash or a comma keeps it.
    """
    value = (text or "").strip()
    if "|" in value:
        value = value.rsplit("|", 1)[-1].strip()
    return value


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

    known_ids = await _known_external_ids(source, db)
    inserted = 0
    skipped = 0
    blocked = 0   # refused by content_filter, never stored
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
        town = _clean_location(_pick(el, selectors.get("location"))) \
            or source.get("town_default", "Luxembourg")
        image_src = _pick(el, selectors.get("image"), attr="src")
        link = _pick(el, selectors.get("link"), attr="href")
        image = _abs_url(source["url"], image_src) if image_src else source.get("image_default", "")
        external_id = link or f"{source['id']}:{start_iso}:{title[:60]}"

        if external_id in known_ids:
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
            town=canonical_town(town),
            lat=float(source.get("lat_default", 49.6116)),
            lng=float(source.get("lng_default", 6.1319)),
            image=image,
        )
        if doc is None:
            blocked += 1
            continue
        await db.events.insert_one(doc)
        known_ids.add(doc["external_id"])
        inserted += 1

    return inserted, skipped, blocked


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

    if not events:
        # The listing holds nothing and links to nothing we can follow, which
        # is what a page that builds its list in the browser looks like from
        # here: echternach.lu loads its events through admin-ajax, so the HTML
        # arrives with a heading and no events at all. Switched on for the
        # first time, it came back "no_events".
        #
        # Its sitemap does list them and the individual pages do carry
        # JSON-LD — that is how the site cleared discovery. So walk it.
        #
        # Decided here rather than when the source is registered, because
        # registration cannot tell: whether a listing works is a property of
        # the page, and reading it is the only way to know. Guessing from the
        # discovered URL sent Mamer down this path too, and Mamer's listing
        # works perfectly well.
        logger.info("%s: listing carried no events, trying its sitemap",
                    source.get("name"))
        return await _import_sitemap(source, db)

    known_ids = await _known_external_ids(source, db)
    inserted = 0
    skipped = 0
    blocked = 0   # refused by content_filter, never stored
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

        if external_id in known_ids:
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
            town=canonical_town(str(town)),
            lat=lat,
            lng=lng,
            image=image,
        )
        if doc is None:
            blocked += 1
            continue
        await db.events.insert_one(doc)
        known_ids.add(doc["external_id"])
        inserted += 1

    return inserted, skipped, blocked


def _unescape_deep(node: Any) -> Any:
    """Decode HTML entities in every string of a parsed JSON-LD node.

    WordPress — which is what the Luxembourg commune sites run — leaves the
    entities in place inside its JSON-LD, so a title arrives as
    "Fit &#038; Fun &#8211; Zumba". JSON parsing does not touch those: they are
    HTML escapes, not JSON ones. Left alone they reach the database and the
    card in that state.

    The scraped importers never needed this because BeautifulSoup decodes text
    on the way out. Only the JSON-LD path hands us raw markup entities.
    """
    if isinstance(node, str):
        return html_lib.unescape(node)
    if isinstance(node, list):
        return [_unescape_deep(v) for v in node]
    if isinstance(node, dict):
        return {k: _unescape_deep(v) for k, v in node.items()}
    return node


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
    return [_unescape_deep(ev) for ev in out]


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


# Files that are not pages. Fetching one and parsing it as HTML costs a request
# and yields nothing — an 800 KB scaled photo, in the case that prompted this.
_NOT_A_PAGE = re.compile(
    r"\.(jpe?g|png|gif|webp|svg|pdf|zip|mp4|mp3|ics|xml|json)(\?|$)", re.I
)

_EVENTISH_PATH = re.compile(
    r"/(events?|agenda|manifestations?|veranstaltung(en)?|termine?)/", re.I
)


def _extract_event_links(html: str, *, base_url: str) -> List[str]:
    """URLs of individual event pages linked from a listing.

    Two things used to go wrong here, and they compounded.

    _collect_urls walked the JSON-LD and took `url` off *any* node. A commune
    site describes itself with a WebSite or Organization block, so what came
    back was the site's own address and a photo — never an event.

    Worse, the anchor scan below ran only `if not urls`. That garbage counted
    as a result, so the scan was skipped. differdange.lu lists 229 event links
    in its markup; this function returned three, none of them an event, one a
    JPEG. Every commune whose listing carries a self-describing JSON-LD block
    but no Event objects — 41 of the 100 checked — looked like a site with no
    events at all.

    Now only Event nodes contribute URLs, the anchor scan runs whenever that
    found nothing, and anything that is not a page is dropped.
    """
    soup = BeautifulSoup(html, "lxml")
    urls: List[str] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except Exception:
            continue
        _collect_event_urls(data, urls)

    if not urls:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if _EVENTISH_PATH.search(href):
                urls.append(_abs_url(base_url, href))

    # The listing links to itself, to its own translations, and to the site
    # root. Fetching those re-parses the page we already have.
    base = base_url.rstrip("/")
    seen, unique = set(), []
    for u in urls:
        if not u or u in seen or _NOT_A_PAGE.search(u):
            continue
        if u.rstrip("/") == base:
            continue
        seen.add(u)
        unique.append(u)

    # A single event first, listing pages last. The caller follows at most
    # twenty of these, and /de/agenda/ is the page we are standing on in
    # another language — spending the budget on those means never reaching an
    # actual event. Ordering rather than dropping: on a site whose listing is
    # paginated the second page is worth having once the events are exhausted.
    unique.sort(key=lambda u: 0 if _has_slug_after_section(u) else 1)
    return unique


def _has_slug_after_section(url: str) -> bool:
    """True for /events/spillfest-2026/, false for /events/ and /de/agenda/."""
    m = _EVENTISH_PATH.search(url)
    return bool(m) and len(url[m.end():].strip("/")) > 0


def _collect_event_urls(node: Any, out: List[str]) -> None:
    """URLs of Event nodes only — not of whatever else the page describes."""
    if isinstance(node, dict):
        node_type = node.get("@type") or node.get("type")
        types = [node_type] if isinstance(node_type, str) else (node_type or [])
        if any(t and "Event" in t for t in types):
            url = node.get("url") or node.get("@id")
            if isinstance(url, str) and url.startswith("http"):
                out.append(url)
        for key in ("@graph", "itemListElement", "item", "subEvent"):
            if key in node:
                _collect_event_urls(node[key], out)
    elif isinstance(node, list):
        for item in node:
            _collect_event_urls(item, out)


def _collect_urls(node: Any, out: List[str]) -> None:
    """Every `url` in a JSON-LD tree, whatever describes it.

    Kept for probe_sources.py, which reports what a site publishes and wants
    the lot. Do not use this to decide what to crawl — that is
    _collect_event_urls, which takes URLs off Event nodes only. Using this one
    is what made a commune's own homepage and a photo look like events.
    """
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
    # "shows" is how the Rockhal names its 998 event pages, and French spells
    # the word with accents that "events?" cannot match.
    r"|shows?|[ée]v[eè]nements?|[ée]v[ée]nements?"
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
    from urllib.parse import urlparse

    selectors = source.get("selectors") or {}
    max_pages = int(selectors.get("max_pages") or 20)

    parsed = urlparse(source["url"])
    origin = f"{parsed.scheme}://{parsed.netloc}"

    sitemap_url, xml = await _find_sitemap(source["url"], origin)

    all_entries = _collect_sitemap_entries(xml, base=origin)
    all_urls = [u for u, _ in all_entries]

    # Recursively expand sitemap indexes (one level deep). We recurse when
    # a URL looks like another sitemap: ends with .xml OR the path contains
    # "sitemap" (e.g. paginated sitemap indexes like ?page=1).
    def _looks_like_sitemap(u: str) -> bool:
        low = u.lower()
        return low.endswith(".xml") or "sitemap" in low

    nested = [u for u in all_urls if _looks_like_sitemap(u)]
    if nested and len(all_urls) < 30:
        expanded: List[Tuple[str, str]] = []
        for nested_url in nested[:10]:
            try:
                sub_xml = await _fetch_text(nested_url)
                expanded.extend(_collect_sitemap_entries(sub_xml, base=origin))
            except Exception as e:
                logger.info("nested sitemap %s failed: %s", nested_url, e)
        # Replace originals with what we found inside them
        if expanded:
            all_entries = expanded
            all_urls = [u for u, _ in all_entries]

    # Filter to event-like paths and dedup, then spend the page budget on the
    # most recently changed pages rather than on whatever the file happens to
    # list first. Without this, Rockhal's 998-entry show archive gave us
    # twenty concerts from 2022 and no import at all.
    matched: List[Tuple[str, str]] = []
    seen = set()
    for u, mod in all_entries:
        if _SITEMAP_EVENT_PATTERNS.search(u) and u not in seen:
            seen.add(u)
            matched.append((u, mod))

    matched.sort(key=lambda pair: pair[1] or "", reverse=True)
    candidates: List[str] = [u for u, _ in matched[:max_pages]]

    logger.info(
        "[sitemap] %s → %d total sitemap URLs, %d event-like candidates",
        source["name"], len(all_urls), len(candidates),
    )
    if not candidates and all_urls:
        # Log a few examples of what IS in the sitemap so admin can adjust patterns
        logger.info("[sitemap] sample non-matching URLs: %s", all_urls[:5])

    known_ids = await _known_external_ids(source, db)
    inserted = 0
    skipped = 0
    blocked = 0   # refused by content_filter, never stored
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
            if external_id in known_ids:
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
                town=canonical_town(str(town)),
                lat=lat,
                lng=lng,
                image=image,
            )
            if doc is None:
                blocked += 1
                continue
            await db.events.insert_one(doc)
            known_ids.add(doc["external_id"])
            inserted += 1

    return inserted, skipped, blocked


def _collect_sitemap_entries(xml_text: str, *, base: str) -> List[Tuple[str, str]]:
    """Every (url, lastmod) pair in a sitemap or sitemap-index XML string.

    lastmod is kept because the page budget is small and the archive is not:
    rockhal.lu lists 998 shows going back years, and spending 20 fetches on
    whichever 20 happen to come first in the file means fetching 2022 concerts
    and importing nothing. The sitemap already says which entries are fresh.
    Missing lastmod sorts last rather than being dropped — unknown is not old,
    but a dated entry is the better bet.
    """
    entries: List[Tuple[str, str]] = []
    try:
        soup = BeautifulSoup(xml_text, "lxml-xml")
    except Exception:
        soup = BeautifulSoup(xml_text, "lxml")
    for node in soup.find_all(["url", "sitemap"]) or []:
        loc = node.find("loc")
        text = (loc.get_text() or "").strip() if loc else ""
        if not text:
            continue
        mod = node.find("lastmod")
        entries.append((text, (mod.get_text() or "").strip() if mod else ""))
    if not entries:
        # Some sitemaps nest <loc> outside <url>/<sitemap>; fall back to those.
        for loc in soup.find_all("loc"):
            text = (loc.get_text() or "").strip()
            if text:
                entries.append((text, ""))
    return entries


def _collect_sitemap_urls(xml_text: str, *, base: str) -> List[str]:
    """Extract every <loc> URL from a sitemap or sitemap-index XML string."""
    return [u for u, _ in _collect_sitemap_entries(xml_text, base=base)]


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
        import time as _t

        from crawlers import kids_in_lux as k
        from pymongo import MongoClient

        client = MongoClient(os.environ["MONGO_URL"])
        sdb    = client[os.environ["DB_NAME"]]

        inserted = updated = failed = blocked = 0
        try:
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
                        verdict = content_filter.assess(
                            parsed.get("title"), parsed.get("desc"))
                        if verdict:
                            logger.warning(
                                "Refused %s event from %s (%r matched %s)",
                                verdict[0], source.get("name", "?"),
                                verdict[1], url[:120],
                            )
                            blocked += 1
                            continue
                        status = k.upsert_event(sdb, parsed, cats, ev_type, source["id"])
                        if status == "inserted":
                            inserted += 1
                        else:
                            updated += 1
                        _t.sleep(k.PAUSE_S)
        finally:
            client.close()
        return inserted, failed, blocked

    return await asyncio.to_thread(_run_sync)


IMPORTERS["kids_in_lux"] = _import_kids_in_lux


# --- visitluxembourg.com Discovery-Tours crawler -------------------------
async def _import_visit_luxembourg(source: Dict[str, Any], db) -> tuple[int, int]:
    import asyncio

    def _run_sync() -> tuple[int, int]:
        import time as _t

        from crawlers import visit_luxembourg as v
        from pymongo import MongoClient

        client = MongoClient(os.environ["MONGO_URL"])
        sdb    = client[os.environ["DB_NAME"]]
        inserted = updated = failed = blocked = 0
        try:
            with httpx.Client() as hx:
                urls = list(v.list_detail_urls(hx))
                for url in urls:
                    html = v.fetch(url, hx)
                    if not html:
                        failed += 1
                        continue
                    parsed = v.parse_detail(url, html)
                    if not parsed:
                        failed += 1
                        continue
                    verdict = content_filter.assess(
                        parsed.get("title"), parsed.get("desc"))
                    if verdict:
                        logger.warning(
                            "Refused %s event from %s (%r matched %s)",
                            verdict[0], source.get("name", "?"), verdict[1], url[:120],
                        )
                        blocked += 1
                        continue
                    status = v.upsert_event(sdb, parsed, source["id"])
                    if status == "inserted":
                        inserted += 1
                    else:
                        updated += 1
                    _t.sleep(v.PAUSE_S)
        finally:
            client.close()
        return inserted, failed, blocked

    return await asyncio.to_thread(_run_sync)


IMPORTERS["visit_luxembourg"] = _import_visit_luxembourg


# How many runs of nothing at all before it is worth saying out loud. The
# importer runs three times a day, so this is roughly a day of silence — long
# enough that a site being briefly down does not raise it, short enough that a
# commune which redesigned its calendar is noticed the next morning.
EMPTY_RUNS_BEFORE_WARNING = 3


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
            inserted, skipped, blocked = await importer(source, db)
            # inserted + skipped + blocked is what the page actually yielded:
            # skipped counts events that were read and then set aside, usually
            # for being in the past, and blocked counts the ones content_filter
            # refused. Zero of all three means nothing was parsed at all, which
            # is what a redesigned website looks like from here — and under a
            # plain "ok" it looks identical to a quiet week.
            seen = inserted + skipped + blocked
            empty_runs = 0 if seen else int(source.get("empty_runs") or 0) + 1
            result = {
                "last_run_at": started,
                "last_status": "ok" if seen else "no_events",
                "last_error": None,
                "last_imported_count": inserted,
                "last_skipped_count": skipped,
                "last_blocked_count": blocked,
                "last_seen_count": seen,
                "empty_runs": empty_runs,
            }
            if blocked:
                # Visible on the source, not just in the log. A filter whose
                # work nobody can see is a filter nobody can correct — and the
                # cost of a wrong rule here is a village festival that quietly
                # stops appearing.
                logger.warning(
                    "Source %s: %d event(s) refused as not family-safe",
                    source.get("name"), blocked,
                )
            if empty_runs >= EMPTY_RUNS_BEFORE_WARNING:
                logger.warning(
                    "Source %s has parsed nothing %d runs running — check the page",
                    source.get("name"), empty_runs,
                )
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
    """Crawl every active source, a few at a time.

    These runs are almost entirely network wait, so running them one after
    another made a full pass take as long as the sum of every feed. Concurrency
    is capped so we stay polite to the sites we crawl, and each source gets its
    own timeout so one unresponsive host can't stall the whole pass.
    """
    cursor = db.sources.find({"active": True}, {"_id": 0})
    sources = await cursor.to_list(length=100)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SOURCES)

    async def _run_one(s: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            try:
                result = await asyncio.wait_for(
                    run_source(s, db), timeout=SOURCE_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                logger.warning("Importer %s timed out", s.get("name"))
                result = {
                    "last_run_at": _now_iso(),
                    "last_status": "error",
                    "last_error": f"Timed out after {SOURCE_TIMEOUT_SECONDS}s",
                    "last_imported_count": 0,
                }
                await db.sources.update_one({"id": s["id"]}, {"$set": result})
            return {"source": s["id"], "name": s.get("name"), **result}

    return list(await asyncio.gather(*(_run_one(s) for s in sources)))
