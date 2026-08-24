"""Find candidate event sources among Luxembourg's communes — with evidence.

This proposes; it never enables anything. Every candidate lands in a CSV with
what was actually observed, so a human decides what gets crawled.

Why a starting list rather than open-ended discovery: crawling the web at large
to look for event pages would mean fetching from sites that never invited us.
The 100 Luxembourg communes are a public, finite, verifiable set, and each one
publishes its own address. That is a real search — just one with a source.

Per commune, in order, stopping at the first that answers:

1. robots.txt — is crawling allowed at all, what delay is asked for, and does it
   declare a Sitemap? A declared sitemap beats guessing /sitemap.xml.
2. The sitemap, including nested ones, filtered to event-looking paths.
3. A short list of conventional event paths, only if no sitemap turned up.
4. The page itself, checked for JSON-LD Event markup — the cleanest thing to
   import when it exists.

Everything goes through crawler_utils, so robots.txt is obeyed and each host
gets the delay it asks for. That makes a full pass slow by design: roughly 100
communes at several seconds each. Results are cached, so it can be interrupted
and resumed.

Run:
    cd /app/backend && python discover_sources.py            # full pass
    cd /app/backend && python discover_sources.py --limit 5  # quick look
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx

from crawler_utils import USER_AGENT, RobotsBlocked, _load_robots_sync, polite_get_sync

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path("/tmp/discover_sources_cache.json")

# Wikidata: every Luxembourg commune (Q2919801) with its official website.
# Official, public, and answerable in one query — no guessing at domains.
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
COMMUNE_QUERY = """
SELECT ?communeLabel ?website WHERE {
  ?commune wdt:P31 wd:Q2919801 .
  OPTIONAL { ?commune wdt:P856 ?website }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "de,fr,lb,en" }
} ORDER BY ?communeLabel
"""

# Paths worth trying when a site publishes no sitemap. Deliberately short: each
# entry is a request to someone else's server.
FALLBACK_PATHS = [
    "/agenda", "/events", "/evenements", "/manifestations",
    "/veranstaltungen", "/actualites", "/aktuelles", "/kalender",
]

EVENTISH = re.compile(
    r"event|agenda|manifestation|veranstalt|actualit|aktuell|kalend|termin",
    re.I,
)

# Paths that contain an event word but are not event listings. A commune site
# will happily serve a "photo-events" gallery or an event *category* archive,
# and proposing those as a source wastes the reviewer's time.
NOT_EVENTISH = re.compile(
    r"photo|galerie|gallery|/tag/|/category/|/author/|\.jpe?g|\.png|feed",
    re.I,
)


def fetch_communes() -> List[Dict[str, str]]:
    """The commune list from Wikidata, cached after the first call."""
    if CACHE.exists():
        cached = json.loads(CACHE.read_text(encoding="utf-8"))
        if cached.get("communes"):
            return cached["communes"]

    resp = httpx.get(
        WIKIDATA_SPARQL,
        params={"query": COMMUNE_QUERY},
        headers={"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT},
        timeout=60.0,
    )
    resp.raise_for_status()
    rows = resp.json()["results"]["bindings"]
    communes = [
        {"name": r["communeLabel"]["value"], "website": r["website"]["value"]}
        for r in rows
        if r.get("website")
    ]
    _save_cache({"communes": communes})
    return communes


def _load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_cache(update: dict) -> None:
    data = _load_cache()
    data.update(update)
    CACHE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def sitemap_urls_from_robots(robots_text: str) -> List[str]:
    return re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots_text or "")


# Sections that really are calendars, as whole path segments. Matching these
# as substrings is what put a shop page forward as Casino Luxembourg's example:
# "atelier" appears in an exhibition-catalogue title too.
_STRONG_SECTION = re.compile(
    r"/(agenda|events?|evenements|manifestations?|veranstaltungen|programme?"
    r"|expositions?|ausstellungen|kalender|termine)(/|$)",
    re.I,
)

# Pages that carry an event word without being an event: a shop selling the
# catalogue, a video archive, a press release about last year.
_NOT_A_LISTING = re.compile(
    r"/(shop|boutique|store|channel|video|presse?|press|blog|news|archiv\w*)(/|$)",
    re.I,
)


def _event_url_rank(url: str) -> tuple:
    """Best example first: a real calendar section, shallow, not a shop."""
    path = urlparse(url).path
    return (
        0 if _STRONG_SECTION.search(path) else 1,
        1 if _NOT_A_LISTING.search(path) else 0,
        path.count("/"),
        len(path),
    )


def _looks_like_sitemap(url: str) -> bool:
    """A nested sitemap, even when a query string follows the extension.

    casino-luxembourg.lu splits its index into sitemap.xml?page=1 through 4.
    Testing url.endswith(".xml"), as this used to, files those as content
    pages, so the index is never opened and the site reports no events at all.
    """
    return urlparse(url).path.lower().endswith((".xml", ".xml.gz"))


def read_sitemap(url: str, depth: int = 0) -> List[str]:
    """URLs from a sitemap, following one level of nested sitemaps."""
    if depth > 1:
        return []
    try:
        text = polite_get_sync(url, timeout=25.0).text
    except (RobotsBlocked, Exception):
        return []

    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)
    nested = [u for u in locs if _looks_like_sitemap(u)]
    plain = [u for u in locs if not _looks_like_sitemap(u)]

    # A <sitemapindex> holds nothing but other sitemaps, so there is no content
    # to filter and the event-word test below rejects every child over a name
    # it never had: "sitemap.xml?page=2" says nothing about what is inside it.
    # A <urlset> that happens to link to other sitemaps is the other case —
    # there the name is the only clue, and a commune site can carry dozens.
    if re.search(r"<sitemapindex", text, re.I):
        children = nested[:5]
    else:
        children = [u for u in nested
                    if EVENTISH.search(u) and not NOT_EVENTISH.search(u)][:3]

    for child in children:
        plain.extend(read_sitemap(child, depth + 1))
    return plain


def has_event_markup(url: str) -> bool:
    """Whether a page carries schema.org Event data in JSON-LD."""
    try:
        html = polite_get_sync(url, timeout=20.0).text
    except Exception:
        return False
    for block in re.findall(
        r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I
    ):
        if re.search(r'"@type"\s*:\s*"?\[?\s*"?Event', block, re.I):
            return True
    return False


def probe(
    name: str,
    website: str,
    *,
    eventish: "re.Pattern[str]" = None,
    fallback_paths: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Everything observed about one site.

    The vocabulary is injectable because a commune and a museum do not use the
    same words. A commune publishes an *agenda*; Casino Luxembourg publishes a
    *programme* of *expositions*. Probing a museum with the commune word list
    finds nothing and reports "NICHTS GEFUNDEN", which reads as "this venue has
    no events" — the opposite of the truth.

    Defaults are the commune list, so existing callers and the cached
    candidates.csv are unaffected.
    """
    eventish = eventish or EVENTISH
    fallback_paths = fallback_paths or FALLBACK_PATHS
    row = {
        "Status": "OFFEN", "Gemeinde": name, "Website": website,
        "robots": "", "Crawl-Delay": "", "Sitemap": "",
        "Veranstaltungsseiten": "", "Beispiel-URL": "", "JSON-LD": "", "Hinweis": "",
    }
    host = f"{urlparse(website).scheme or 'https'}://{urlparse(website).netloc}"
    if not urlparse(website).netloc:
        row.update(Status="FEHLER", Hinweis="unbrauchbare Adresse")
        return row

    try:
        entry = _load_robots_sync(host)
    except Exception as exc:
        row.update(Status="FEHLER", Hinweis=f"robots.txt: {type(exc).__name__}")
        return row

    if not entry.parser.can_fetch(USER_AGENT, website):
        row.update(Status="GESPERRT", robots="verbietet", Hinweis="robots.txt untersagt das Crawlen")
        return row
    row["robots"] = "erlaubt"
    row["Crawl-Delay"] = str(entry.crawl_delay or "")

    # A declared sitemap beats guessing at /sitemap.xml.
    declared: List[str] = []
    try:
        robots_txt = httpx.get(
            host.rstrip("/") + "/robots.txt",
            headers={"User-Agent": USER_AGENT}, timeout=15.0, follow_redirects=True,
        ).text
        declared = sitemap_urls_from_robots(robots_txt)
    except Exception:
        pass
    candidates = declared or [urljoin(host + "/", "sitemap.xml")]

    urls: List[str] = []
    used = ""
    for sm in candidates[:2]:
        found = read_sitemap(sm)
        if found:
            urls, used = found, sm
            break
    row["Sitemap"] = used

    event_urls = [u for u in urls if eventish.search(u) and not NOT_EVENTISH.search(u)]
    event_urls.sort(key=_event_url_rank)
    if not event_urls and not urls:
        # No sitemap at all — try a few conventional paths instead.
        for path in FALLBACK_PATHS:
            candidate = urljoin(host + "/", path.lstrip("/"))
            try:
                resp = polite_get_sync(candidate, timeout=15.0)
            except RobotsBlocked:
                continue
            except Exception:
                continue
            if resp.status_code == 200:
                event_urls = [str(resp.url)]
                row["Hinweis"] = "keine Sitemap, Pfad geraten"
                break

    row["Veranstaltungsseiten"] = str(len(event_urls))
    if event_urls:
        # Try the three best rather than only the first. A big site can have
        # thousands of matching URLs, and judging the whole venue on whichever
        # one happened to sort first is how Casino Luxembourg — which does
        # publish its programme — got written off on the strength of a shop
        # page. Three requests, and it stops at the first that answers.
        row["Beispiel-URL"] = event_urls[0]
        row["JSON-LD"] = "nein"
        for candidate in event_urls[:3]:
            if has_event_markup(candidate):
                row["Beispiel-URL"] = candidate
                row["JSON-LD"] = "ja"
                break
        row["Status"] = "KANDIDAT"
    else:
        row["Status"] = "NICHTS GEFUNDEN"
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="only probe the first N communes")
    ap.add_argument("--out", type=Path, default=ROOT / "sources" / "candidates.csv")
    args = ap.parse_args()

    communes = fetch_communes()
    if args.limit:
        communes = communes[: args.limit]
    print(f"[discover] {len(communes)} communes to probe")

    done = _load_cache().get("results", {})
    rows: List[Dict[str, str]] = []
    for i, c in enumerate(communes, 1):
        key = c["website"]
        if key in done:
            rows.append(done[key])
            print(f"[{i}/{len(communes)}] {c['name']:24} (aus dem Zwischenspeicher)")
            continue
        row = probe(c["name"], c["website"])
        done[key] = row
        rows.append(row)
        _save_cache({"results": done})
        print(f"[{i}/{len(communes)}] {c['name']:24} {row['Status']:16} "
              f"{row['Veranstaltungsseiten']:>4} Seiten  JSON-LD={row['JSON-LD'] or '-'}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    from collections import Counter
    tally = Counter(r["Status"] for r in rows)
    print("\n" + "  ".join(f"{k}={v}" for k, v in tally.most_common()))
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
