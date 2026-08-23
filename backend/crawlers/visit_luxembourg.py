"""
Custom crawler for visitluxembourg.com — the official tourism board's
"Discovery Tours for Families" collection (currently 31 curated
treasure-hunt-style adventure tours across all cantons).

We harvest each detail page's OpenGraph metadata (title, description, image)
which is uniformly present on visitluxembourg.com's TYPO3-generated pages.

Politeness:
  - every request goes through crawler_utils.polite_get_sync, which reads
    robots.txt and refuses disallowed paths. The site disallows a number of
    parameter URLs (?cHash=, ?L=0, /typo3/ ...) that were previously fetched
    regardless, because nothing read the file
  - 1.2s between requests
  - respects User-Agent header

Run:
    cd /app/backend && python crawlers/visit_luxembourg.py
"""
import os
import sys
import urllib.parse as up
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Iterable

import httpx
from dotenv import load_dotenv
from pymongo import MongoClient

from crawler_utils import RobotsBlocked, polite_get_sync

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

BASE       = "https://www.visitluxembourg.com"

# Sitemap of pages — visitluxembourg exposes their full page tree as an XML
# sitemap. We only care about the /discovery-tours-for-families/ tree.
PAGES_SITEMAP = (
    f"{BASE}/sitemap.xml?sitemap=pages&cHash=504a98d79fa5ec7675c0e1f7f08058fc"
)
DETAIL_PREFIX = "/discovery-tours-for-families/"

from geocode_lookup import COMMUNE_COORDS, CANTON_FALLBACK   # noqa: E402

# Best-effort commune → canton lookup for the slug's final path segment.
# Most tour URLs end with "-<commune>" (e.g. "riddle-in-ansembourg" →
# Ansembourg). We match against COMMUNE_COORDS keys case-insensitively.
COMMUNE_CANTON_HINTS: dict[str, str] = {
    "beefort":       "Echternach",   # Beaufort
    "ansembourg":    "Mersch",
    "kahler":        "Capellen",
    "koerich":       "Capellen",
    "mamer":         "Capellen",
    "pettingen":     "Mersch",
    "septfontaines": "Capellen",
    "steinfort":     "Capellen",
    "bech":          "Echternach",
    "berdorf":       "Echternach",
    "consdorf":      "Echternach",
    "echternach":    "Echternach",
    "fischbach":     "Mersch",
    "beaufort":      "Echternach",
    "wollefswee":    "Wiltz",
    "martelange":    "Redange",
    "grevenmacher":  "Grevenmacher",
    "wormeldange":   "Grevenmacher",
    "vianden":       "Vianden",
    "clervaux":      "Clervaux",
    "esch":          "Esch-sur-Alzette",
    "differdange":   "Esch-sur-Alzette",
    "dudelange":     "Esch-sur-Alzette",
    "bettembourg":   "Esch-sur-Alzette",
    "remich":        "Remich",
    "wiltz":         "Wiltz",
    "diekirch":      "Diekirch",
    "larochette":    "Diekirch",
}


class MetaCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs) -> None:
        d = dict(attrs)
        if tag == "meta":
            key = (d.get("property") or d.get("name") or "").lower()
            if key.startswith("og:") and d.get("content"):
                self.meta.setdefault(key, d["content"].strip())


class SitemapLinks(HTMLParser):
    """Very small XML-aware harvester — pulls out <loc> text nodes."""
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_loc = False
        self._buf: list[str] = []
        self.locs: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "loc":
            self._in_loc = True
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "loc":
            self._in_loc = False
            self.locs.append("".join(self._buf).strip())

    def handle_data(self, data: str) -> None:
        if self._in_loc:
            self._buf.append(data)


def fetch(url: str, client: httpx.Client) -> str | None:
    """Fetch one page through the politeness layer.

    This used to call client.get() directly, so the "respects robots.txt" claim
    in the module docstring was never true: no rules were read, and the fixed
    pause ignored any Crawl-delay the site asked for. polite_get_sync() reads
    robots.txt, raises RobotsBlocked for disallowed paths, and waits the longer
    of our baseline and the site's requested delay.
    """
    try:
        return polite_get_sync(url, client=client, timeout=8.0).text
    except RobotsBlocked as e:
        print(f"  [robots] skipping {url}: {e}")
        return None
    except Exception as e:
        print(f"  [fetch] {url}: {type(e).__name__}: {e}")
        return None


def list_detail_urls(client: httpx.Client) -> Iterable[str]:
    xml = fetch(PAGES_SITEMAP, client)
    if not xml:
        return []
    ex = SitemapLinks()
    ex.feed(xml)
    return sorted({
        u for u in ex.locs
        if up.urlparse(u).path.startswith(DETAIL_PREFIX)
        # Exclude the index page itself and any sub-collections
        and up.urlparse(u).path.rstrip("/") != DETAIL_PREFIX.rstrip("/")
    })


def parse_detail(url: str, html: str) -> dict | None:
    ex = MetaCollector()
    ex.feed(html[:200_000])
    title = ex.meta.get("og:title", "").strip()
    desc  = ex.meta.get("og:description", "").strip()
    image = ex.meta.get("og:image:secure_url") or ex.meta.get("og:image", "")
    if not title:
        return None

    # Extract the last slug fragment: "riddle-in-ansembourg" → "ansembourg"
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    slug_tail = slug.rsplit("-", 1)[-1] if "-" in slug else slug
    canton = COMMUNE_CANTON_HINTS.get(slug_tail, "")

    # Try full commune match if the tail matched a lookup name (case-insensitive).
    commune_key = ""
    for key in COMMUNE_COORDS:
        if key.lower() == slug_tail.lower():
            commune_key = key
            break
    if not canton and commune_key:
        # If we have coords but no canton hint, still use Luxembourg
        canton = "Luxembourg"
    if not canton:
        canton = "Luxembourg"
    coord = COMMUNE_COORDS.get(commune_key) or CANTON_FALLBACK.get(canton, (49.61, 6.13))

    return {
        "title":   title,
        "desc":    desc,
        "image":   image,
        "commune": commune_key or slug_tail.title(),
        "canton":  canton,
        "url":     url,
        "lat":     coord[0],
        "lng":     coord[1],
    }


def upsert_event(db, parsed: dict, source_id) -> str:
    slug = parsed["url"].rstrip("/").rsplit("/", 1)[-1]
    external_id = f"visit-lu-dtff:{slug}"
    now_iso = datetime.now(timezone.utc).isoformat()
    empty_i18n = {"en": "", "de": "", "fr": ""}

    doc = {
        "external_id": external_id,
        "title":       {"en": parsed["title"], "de": parsed["title"], "fr": parsed["title"]},
        "short":       {"en": parsed["desc"][:180], "de": parsed["desc"][:180], "fr": parsed["desc"][:180]},
        "description": {"en": parsed["desc"], "de": parsed["desc"], "fr": parsed["desc"]},
        "type":        "Outdoor",
        "canton":      parsed["canton"],
        "town":        parsed["commune"],
        "category":    ["Nature", "Culture", "Workshops"],
        "age_min":     4,
        "age_max":     12,
        "start_date":  datetime.utcnow().date().isoformat(),
        "end_date":    None,
        "time":        "",
        "price_adult": 0.0,
        "price_child": 0.0,
        "price_label": {"en": "Free", "de": "Gratis", "fr": "Gratuit"},
        "accessibility":         dict(empty_i18n),
        "weather_fit":           dict(empty_i18n),
        "image":                 parsed["image"],
        "lat":                   parsed["lat"],
        "lng":                   parsed["lng"],
        "bookable":              False,
        "published":             True,
        "rating":                4.6,
        "featured":              False,
        "featured_until":        None,
        "view_count":            0,
        "source_id":             source_id,
        "source_name":           "Curated — Visit Luxembourg (Discovery Tours)",
        "website_url":           parsed["url"],
        "accessibility_wheelchair": False,
        "sensory_friendly":         False,
        "free_parking":             False,
        "sensory_notes":  dict(empty_i18n),
        "parking":        dict(empty_i18n),
        "food_allowed":   True,
        "food_onsite":    dict(empty_i18n),
        "preparation_tips": dict(empty_i18n),
        "payment_methods": [],
        "opening_hours":  dict(empty_i18n),
        "peak_hours":     dict(empty_i18n),
        "changing_facilities": False,
        "restrooms":      True,
        "updated_at":     now_iso,
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

    src = db.sources.find_one({"url": {"$regex": "visitluxembourg", "$options": "i"}})
    source_id = src.get("id") if src else None

    inserted = updated = failed = 0
    with httpx.Client() as hx:
        urls = list(list_detail_urls(hx))
        print(f"[visit-lu] {len(urls)} discovery-tour pages")
        for i, url in enumerate(urls, 1):
            html = fetch(url, hx)
            if not html:
                failed += 1
                continue
            parsed = parse_detail(url, html)
            if not parsed:
                failed += 1
                continue
            status = upsert_event(db, parsed, source_id)
            if status == "inserted":
                inserted += 1
            else:
                updated += 1
            if i % 10 == 0:
                print(f"  [{i}/{len(urls)}] ins={inserted} upd={updated} fail={failed}")

    now_iso = datetime.now(timezone.utc).isoformat()
    if src:
        db.sources.update_many(
            {"url": {"$regex": "visitluxembourg", "$options": "i"}},
            {"$set": {
                "kind": "visit_luxembourg",
                "active": True,
                "last_status": "ok",
                "last_run_at": now_iso,
                "last_imported_count": inserted + updated,
                "last_error": "",
                "updated_at": now_iso,
            }},
        )
    print(f"[visit-lu] done. inserted={inserted}, updated={updated}, failed={failed}")


if __name__ == "__main__":
    main()
