"""
Custom crawler for kids-in-lux.com — the community-maintained directory
of Luxembourg playgrounds, indoor playgrounds, and family excursions.

The site follows a two-level structure:
  Index page ("/spielplätze/", "/ausflüge/", "/schlechtes-wetter/indoor-spielplätze/")
    ├── /spielplätze/<slug>/
    ├── /spielplätze/<slug>/
    ├── …

Each detail page exposes clean OpenGraph metadata (og:title, og:description,
og:image) that we harvest and upsert into `events` (as always-open venues).

Politeness:
  - every request goes through crawler_utils.polite_get_sync, which reads
    robots.txt and refuses disallowed paths
  - waits the longer of our 2s baseline and the site's Crawl-delay. This site
    asks for 5s; the old hard-coded 1s pause ignored that, because nothing ever
    read the file
  - short 6s timeout

Run:
    cd /app/backend && python crawlers/kids_in_lux.py
"""
import os
import re
import sys
import html as html_lib
import urllib.parse as up
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Iterable

import httpx
from dotenv import load_dotenv
from pymongo import MongoClient

from crawler_utils import RobotsBlocked, describe_exception, polite_get_sync

# Allow running as `python crawlers/kids_in_lux.py` from /app/backend.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

BASE       = "https://www.kids-in-lux.com"

# Kids-in-lux commune hints — the og:title usually follows the form
# "Spielplatz X (Commune - Locality)". When there is no parenthetical, the
# title is searched for a commune name instead. Nothing falls back to
# "Luxembourg" any more: that used to put lakes in the north on the capital,
# and a wrong location is worse than an admitted unknown one.
from geocode_lookup import COMMUNE_COORDS, CANTON_FALLBACK   # noqa: E402
from town_names import find_town_in_text                     # noqa: E402
from age_hints import read_age                               # noqa: E402
from price_hints import read_price                           # noqa: E402

COMMUNE_CANTON: dict[str, str] = {
    "Bambesch": "Luxembourg", "Belair": "Luxembourg", "Bofferdange": "Mersch",
    "Bonnevoie": "Luxembourg", "Cents": "Luxembourg", "Contern": "Luxembourg",
    "Dudelange": "Esch-sur-Alzette", "Echternach": "Echternach",
    "Berdorf": "Echternach", "Consdorf": "Echternach",
    "Kirchberg": "Luxembourg", "Limpertsberg": "Luxembourg",
    "Merl": "Luxembourg", "Gasperich": "Luxembourg",
    "Bertrange": "Luxembourg", "Strassen": "Luxembourg",
    "Hesperange": "Luxembourg", "Roeser": "Esch-sur-Alzette",
    "Rumelange": "Esch-sur-Alzette", "Wiltz": "Wiltz",
    "Vianden": "Vianden", "Clervaux": "Clervaux",
    "Diekirch": "Diekirch", "Mersch": "Mersch",
    "Grevenmacher": "Grevenmacher", "Remich": "Remich",
    "Ettelbruck": "Diekirch", "Redange": "Redange",
    "Steinfort": "Capellen", "Capellen": "Capellen",
    "Esch-sur-Alzette": "Esch-sur-Alzette", "Esch-Alzette": "Esch-sur-Alzette",
    "Foetz": "Esch-sur-Alzette", "Kayl": "Esch-sur-Alzette",
    "Bettembourg": "Esch-sur-Alzette",
    "Bous": "Remich", "Wormeldange": "Grevenmacher",
    "Crauthem": "Esch-sur-Alzette",
    "Munshausen": "Clervaux",
}


class Extractor(HTMLParser):
    """Collects <a href> plus OpenGraph meta into a bag."""
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: set[str] = set()
        self.meta:  dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs) -> None:
        d = dict(attrs)
        if tag == "a" and d.get("href"):
            self.links.add(d["href"])
        elif tag == "meta":
            key = (d.get("property") or d.get("name") or "").lower()
            if key.startswith("og:") and d.get("content"):
                self.meta[key] = d["content"].strip()


INDEX_URLS = [
    (f"{BASE}/spielplätze/",                          ["Playgrounds"], "Outdoor"),
    (f"{BASE}/schlechtes-wetter/indoor-spielplätze/", ["Playgrounds", "Indoor"], "Indoor"),
    (f"{BASE}/ausflüge/",                             ["Nature", "Culture"], "Outdoor"),
]


def fetch(url: str, client: httpx.Client) -> str | None:
    """Fetch one page through the politeness layer.

    This used to call client.get() directly, so the "respects robots.txt" claim
    in the module docstring was never true: no rules were read, and the fixed
    pause ignored any Crawl-delay the site asked for. polite_get_sync() reads
    robots.txt, raises RobotsBlocked for disallowed paths, and waits the longer
    of our baseline and the site's requested delay.
    """
    try:
        return polite_get_sync(url, client=client, timeout=6.0).text
    except RobotsBlocked as e:
        print(f"  [robots] skipping {url}: {e}")
        return None
    except Exception as e:
        print(f"  [fetch] {url}: {describe_exception(e)}")
        return None


def list_detail_urls(index_url: str, client: httpx.Client) -> Iterable[str]:
    html = fetch(index_url, client)
    if not html:
        return []
    ex = Extractor()
    ex.feed(html)
    parent_path = up.urlparse(index_url).path
    out: set[str] = set()
    for href in ex.links:
        abs_url = up.urljoin(index_url, href)
        parsed  = up.urlparse(abs_url)
        # Only keep links from the same host…
        if parsed.netloc and parsed.netloc != up.urlparse(BASE).netloc:
            continue
        # …under the index path…
        if not parsed.path.startswith(parent_path):
            continue
        # …with exactly one more path segment (the slug) than the index.
        remainder = parsed.path[len(parent_path):].strip("/")
        if remainder and "/" not in remainder and remainder != "-":
            out.add(f"{BASE}{parent_path}{remainder}/")
    return sorted(out)


# Luxembourg's bounding box, generously drawn. Coordinates lifted from a page
# have to land inside the country: an embedded map can point anywhere, and a
# pin in Belgium is worse than no pin at all.
LU_BOUNDS = (49.40, 50.20, 5.70, 6.55)   # lat_min, lat_max, lng_min, lng_max


def coords_from_map_embed(html: str) -> tuple[float, float] | None:
    """The pin a page puts on its own embedded map.

    kids-in-lux builds every entry around a Google Maps iframe:

        .../maps/embed/v1/place?key=…&q=49.8995%2C5.8670&center=49.9059%2C5.8994

    `q` is the marker, `center` only the viewport, so `q` comes first. This is
    the page telling us where the place is, to the metre — far better than the
    commune name we were guessing at, and it needs no lookup.

    The key in that URL is Google's business and theirs; nothing here reads or
    keeps it. Only the two numbers.
    """
    for match in re.finditer(r"google\.com/maps/embed[^\"'\s>]*", html, re.I):
        url = up.unquote(html_lib.unescape(match.group(0)))
        for field in ("q", "center"):
            pair = re.search(rf"[?&]{field}=(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)", url)
            if not pair:
                continue
            lat, lng = float(pair.group(1)), float(pair.group(2))
            lo_lat, hi_lat, lo_lng, hi_lng = LU_BOUNDS
            if lo_lat <= lat <= hi_lat and lo_lng <= lng <= hi_lng:
                return lat, lng
    return None


def parse_detail(url: str, html: str) -> dict | None:
    ex = Extractor()
    ex.feed(html[:200_000])
    title_raw = ex.meta.get("og:title", "").strip()
    desc      = ex.meta.get("og:description", "").strip()
    image     = ex.meta.get("og:image:secure_url") or ex.meta.get("og:image") or ""
    if not title_raw:
        return None

    # Extract commune from the "Xxxx (Commune - Locality)" pattern.
    commune = ""
    m = re.search(r"\(([^)]+)\)", title_raw)
    if m:
        inside = m.group(1)
        # "Luxembourg Stadt - Limpertsberg" → pick the more specific right side.
        parts = [p.strip() for p in re.split(r"[-–—/,]", inside) if p.strip()]
        # Try right-most first, then left.
        for cand in reversed(parts):
            if cand in COMMUNE_CANTON or cand in COMMUNE_COORDS:
                commune = cand
                break
        if not commune and parts:
            commune = parts[-1]
    # Clean title — strip parenthetical location.
    title = re.sub(r"\s*\([^)]*\)\s*$", "", title_raw).strip()

    # The parenthetical is the reliable source, and the outings mostly have
    # none — but the title still names the place: "Esch sur Sure und
    # Obersauerstausee". That used to fall through to canton "Luxembourg" and a
    # pin on the capital, fifty kilometres from the lake, and nothing
    # downstream could tell that apart from a real answer.
    if not commune:
        commune = find_town_in_text(title_raw)

    canton = COMMUNE_CANTON.get(commune, "")

    # The page's own map pin, first and best. Every entry checked carries one,
    # and it is exact — the lake at Esch-sur-Sûre comes back as 49.8996 /
    # 5.8671 rather than as the centre of a commune, let alone of a canton.
    # Guessing a commune from the title was yesterday's improvement on guessing
    # the capital; this is the page simply telling us.
    coord = coords_from_map_embed(html)
    precision = "address" if coord else ""

    if coord is None:
        coord = COMMUNE_COORDS.get(commune)
        precision = "commune" if coord else ""
    if coord is None and canton:
        coord = CANTON_FALLBACK.get(canton)
        precision = "fallback"
    if coord is None:
        # Nothing recognised at all. The centre of the country is a
        # placeholder, not an answer, and the precision says so — the geocoder
        # picks the record up instead of taking a wrong pin for a resolved one.
        coord = (49.8153, 6.1296)
        precision = "fallback"

    return {
        "title":    title,
        "desc":     desc,
        "image":    image,
        "commune":  commune,
        "canton":   canton,
        "located":  precision in ("address", "commune"),
        "precision": precision,
        "url":      url,
        "lat":      coord[0],
        "lng":      coord[1],
    }


def upsert_event(db, parsed: dict, categories: list[str], ev_type: str, source_id: str) -> str:
    """Insert-or-update using `external_id = kids-in-lux:<slug>` as stable key."""
    slug = parsed["url"].rstrip("/").rsplit("/", 1)[-1]
    external_id = f"kids-in-lux:{slug}"

    now_iso = datetime.now(timezone.utc).isoformat()
    empty_i18n = {"en": "", "de": "", "fr": ""}

    # This crawler writes its own document instead of going through
    # _build_event_doc, so the cleanup that removed "0–99" and "0.00 €" from
    # every other importer went past it. It claimed both, plus "Gratis" — and
    # that last one is not merely unknown but wrong for a third of what it
    # imports: the indoor playgrounds charge admission.
    age = read_age(parsed["title"], parsed["desc"])
    price = read_price(parsed["title"], parsed["desc"])
    doc = {
        "external_id": external_id,
        "title":       {"en": parsed["title"], "de": parsed["title"], "fr": parsed["title"]},
        "short":       {"en": parsed["desc"][:180], "de": parsed["desc"][:180], "fr": parsed["desc"][:180]},
        "description": {"en": parsed["desc"], "de": parsed["desc"], "fr": parsed["desc"]},
        "type":        ev_type,
        "canton":      parsed["canton"],
        # No invented town. An empty one is honest and the geocoder can
        # still work from the title; "Luxembourg" would be a wrong answer
        # that looks like a right one.
        "town":        parsed["commune"] or parsed["canton"] or "",
        # Said out loud rather than left unset, so the healthcheck can count
        # what is exact and what is still a placeholder.
        "geocode_precision": parsed.get("precision") or "fallback",
        "category":    categories,
        # See the note in importers._build_event_doc: a one-sided age such
        # as "bis 12 Joer" has a None on the open end, and storing that None
        # made /api/events answer 500 for every event at once.
        "age_min":     (age.minimum or 0) if age.source == "event" else 0,
        "age_max":     (age.maximum or 99) if age.source == "event" else 99,
        "age_source":  age.source,
        "start_date":  datetime.now(timezone.utc).date().isoformat(),
        "end_date":    None,
        "time":        "",
        "price_adult": price.adult,
        "price_child": price.adult if price.is_free else None,
        "price_free":  price.is_free,
        "price_source": price.source,
        "price_label": {
            lang: ("Free entry" if price.is_free
                   else f"{price.adult:.2f} €" if price.adult is not None
                   else "Price not stated")
            for lang in ("en", "de", "fr")
        },
        "accessibility": dict(empty_i18n),
        "weather_fit":   dict(empty_i18n),
        "image":         parsed["image"],
        "lat":           parsed["lat"],
        "lng":           parsed["lng"],
        "bookable":      False,
        "published":     True,
        "rating":        4.5,
        "featured":      False,
        "featured_until": None,
        "view_count":    0,
        "source_id":     source_id,
        "source_name":   "Curated — kids-in-lux.com",
        "website_url":   parsed["url"],
        "accessibility_wheelchair": False,
        "sensory_friendly":         False,
        "free_parking":             False,
        "sensory_notes":     dict(empty_i18n),
        "parking":           dict(empty_i18n),
        "food_allowed":      True,
        "food_onsite":       dict(empty_i18n),
        "preparation_tips":  dict(empty_i18n),
        "payment_methods":   [],
        "opening_hours":     dict(empty_i18n),
        "peak_hours":        dict(empty_i18n),
        "changing_facilities": False,
        "restrooms":         True,
        "updated_at":        now_iso,
    }

    existing = db.events.find_one({"external_id": external_id})
    if existing:
        doc["id"] = existing["id"]
        doc["created_at"] = existing.get("created_at", now_iso)
        db.events.update_one({"external_id": external_id}, {"$set": doc})
        return "updated"
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = now_iso
    db.events.insert_one(doc)
    return "inserted"


def main() -> None:
    client = MongoClient(os.environ["MONGO_URL"])
    db     = client[os.environ["DB_NAME"]]

    # Resolve source record for tracking (kind=html_scraper, active=True).
    src = db.sources.find_one({"url": {"$regex": "kids-in-lux.com", "$options": "i"}})
    source_id = src.get("id") if src else None
    now_iso   = datetime.now(timezone.utc).isoformat()

    inserted = updated = failed = 0
    with httpx.Client() as hx:
        for index_url, cats, ev_type in INDEX_URLS:
            print(f"[kids-in-lux] scanning {index_url}")
            details = list_detail_urls(index_url, hx)
            print(f"  → {len(details)} detail pages")
            for i, url in enumerate(details, 1):
                html = fetch(url, hx)
                if not html:
                    failed += 1
                    continue
                parsed = parse_detail(url, html)
                if not parsed:
                    failed += 1
                    continue
                status = upsert_event(db, parsed, cats, ev_type, source_id)
                if status == "inserted":
                    inserted += 1
                else:
                    updated += 1
                if i % 10 == 0:
                    print(f"  [{i}/{len(details)}] ins={inserted} upd={updated} fail={failed}")

    # Mark every kids-in-lux source row as run + active.
    if src:
        db.sources.update_many(
            {"url": {"$regex": "kids-in-lux.com", "$options": "i"}},
            {"$set": {
                "active":              True,
                "last_status":         "ok",
                "last_run_at":         now_iso,
                "last_imported_count": inserted + updated,
                "last_error":          "",
                "updated_at":          now_iso,
            }},
        )
    print(f"[kids-in-lux] done. inserted={inserted}, updated={updated}, failed={failed}")


if __name__ == "__main__":
    main()
