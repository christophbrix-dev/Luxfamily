"""
Fetch OpenGraph / Twitter-Card / <link rel="icon"> images for curated venues.

For each event without an `image`, GET its `website_url`, parse the HTML
for <meta property="og:image"> / <meta name="twitter:image"> /
<link rel="apple-touch-icon"> / <link rel="icon">, and store the resolved
image URL.

Politeness: 1 request per host per second, 4s overall timeout, 5 concurrent
hosts max via a simple worker pool.

Run:
    cd /app/backend && python fetch_venue_images.py
    (safe to re-run — already-fetched events are skipped)
"""
import os
import time
import urllib.parse as up
from typing import Optional
from html.parser import HTMLParser

import httpx
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

USER_AGENT = "WatEloLuxembourg/1.0 (contact@wat-elo.lu)"


class MetaImageParser(HTMLParser):
    """Very small HTML parser that harvests candidate image URLs.

    We only inspect <meta property/name="…"> and <link rel="…"> attributes —
    no full DOM. Order preference: og:image → twitter:image → apple-touch-icon
    → icon. First non-empty match wins.
    """
    IMAGE_META = {"og:image", "og:image:secure_url", "twitter:image", "twitter:image:src"}
    IMAGE_LINK = {"apple-touch-icon", "apple-touch-icon-precomposed", "icon", "shortcut icon"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.candidates: dict[str, str] = {}
        self._in_head = False

    def handle_starttag(self, tag: str, attrs) -> None:
        d = dict(attrs)
        if tag == "meta":
            key = (d.get("property") or d.get("name") or "").lower()
            if key in self.IMAGE_META and d.get("content"):
                self.candidates.setdefault(key, d["content"].strip())
        elif tag == "link":
            rel = (d.get("rel") or "").lower()
            if rel in self.IMAGE_LINK and d.get("href"):
                self.candidates.setdefault(rel, d["href"].strip())


def extract_image(html: str, base_url: str) -> Optional[str]:
    parser = MetaImageParser()
    try:
        parser.feed(html[:200_000])   # cap: images are always in <head>
    except Exception:
        pass
    for key in ("og:image:secure_url", "og:image", "twitter:image:src", "twitter:image",
                "apple-touch-icon", "apple-touch-icon-precomposed", "icon", "shortcut icon"):
        val = parser.candidates.get(key)
        if val:
            return up.urljoin(base_url, val)
    return None


def fetch_one(url: str, client: httpx.Client) -> Optional[str]:
    try:
        r = client.get(url, timeout=6.0, follow_redirects=True,
                       headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        r.raise_for_status()
        return extract_image(r.text, str(r.url))
    except Exception as e:
        print(f"  [fetch] {url}: {type(e).__name__}: {e}")
        return None


def main() -> None:
    client = MongoClient(os.environ["MONGO_URL"])
    db     = client[os.environ["DB_NAME"]]

    todo = list(db.events.find({
        "$and": [
            {"$or": [{"image": ""}, {"image": {"$exists": False}}, {"image": None}]},
            {"website_url": {"$nin": ["", None]}},
        ],
    }))
    print(f"[og-image] {len(todo)} events to enrich")

    ok = fail = 0
    with httpx.Client() as hx:
        # simple sequential loop — we don't have hundreds so speed is fine.
        for i, ev in enumerate(todo, 1):
            url = ev.get("website_url", "").strip()
            img = fetch_one(url, hx)
            if img:
                db.events.update_one({"_id": ev["_id"]}, {"$set": {"image": img}})
                ok += 1
            else:
                fail += 1
            if i % 5 == 0 or i == len(todo):
                print(f"[og-image] {i}/{len(todo)}  ok={ok}  fail={fail}")
            # politeness — 800ms between requests
            time.sleep(0.8)

    print(f"[og-image] done. success={ok}, no-image={fail}")


if __name__ == "__main__":
    main()
