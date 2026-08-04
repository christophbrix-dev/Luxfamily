"""Diagnostic tool: for each candidate URL, probe what our importer would find.

Reports per URL:
  - robots.txt: allowed/blocked, crawl delay
  - HTTP status
  - Number of JSON-LD Event blocks (any depth)
  - Presence of RSS/Atom links
  - Presence of iCal (.ics) links
  - Presence of schema.org ItemList (linked event pages)
  - Anchor tags that look like event detail pages

Usage: python probe_sources.py
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
import sys
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from crawler_utils import polite_get, robots_check, RobotsBlocked
from importers import _collect_events, _collect_urls

logging.getLogger().setLevel(logging.WARNING)  # quieter

CANDIDATES = [
    # Try alternate URLs for the tricky ones too
    ("Philharmonie — season",       "https://www.philharmonie.lu/en/programme/season"),
    ("Philharmonie — root agenda",  "https://www.philharmonie.lu/en/programme"),
    ("Philharmonie — root",         "https://www.philharmonie.lu/en"),
    ("Rockhal agenda /en",          "https://www.rockhal.lu/en/agenda/"),
    ("Rockhal agenda root",         "https://www.rockhal.lu/agenda/"),
    ("Rockhal root",                "https://www.rockhal.lu/"),
    ("Mudam programme",             "https://www.mudam.com/programme"),
    ("Mudam events",                "https://www.mudam.com/events"),
    ("Mudam root",                  "https://www.mudam.com/"),
    ("Visit LU — agenda",           "https://www.visitluxembourg.com/agenda"),
    ("Visit LU — events",           "https://www.visitluxembourg.com/en/agenda"),
    ("VdL whats-on",                "https://www.vdl.lu/en/visiting/whats-on"),
    ("VdL fr",                      "https://www.vdl.lu/fr/visiter/agenda-culturel"),
    ("Echo.lu",                     "https://www.echo.lu/en/"),
    ("Echo.lu — agenda",            "https://www.echo.lu/en/agenda"),
    ("KHN Niederanven",             "https://www.khn.lu/agenda/"),
    ("KHN root",                    "https://www.khn.lu/"),
    ("Naturmusée",                  "https://www.mnhn.lu/"),
    ("Naturmusée — agenda",         "https://www.mnhn.lu/agenda/"),
    ("Naturmusée — expositions",    "https://www.mnhn.lu/expositions/"),
    # extra: agendalux + more
    ("Agenda.lu",                   "https://www.agenda.lu/"),
    ("Kulturkanner (kids)",         "https://www.kulturkanner.lu/"),
    ("Kulturkanner agenda",         "https://www.kulturkanner.lu/en/programme/"),
]


async def probe_one(name: str, url: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"name": name, "url": url}
    try:
        rc = await robots_check(url)
        result["robots_allowed"] = rc["allowed"]
        result["crawl_delay"] = rc["crawl_delay_seconds"]
        if not rc["allowed"]:
            result["status"] = "blocked_by_robots"
            return result
    except Exception as e:
        result["status"] = f"robots-check-fail: {e}"
        return result

    try:
        resp = await polite_get(url, timeout=15.0)
    except RobotsBlocked as rb:
        result["status"] = f"blocked_by_robots: {rb}"
        return result
    except Exception as e:
        result["status"] = f"fetch-fail: {type(e).__name__}: {str(e)[:120]}"
        return result

    result["http"] = resp.status_code
    text = resp.text

    soup = BeautifulSoup(text, "lxml")

    # JSON-LD blocks + Event nodes
    ld_blocks = 0
    ld_events: List[Dict[str, Any]] = []
    ld_urls: List[str] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        ld_blocks += 1
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except Exception:
            continue
        _collect_events(data, ld_events)
        _collect_urls(data, ld_urls)

    result["jsonld_blocks"] = ld_blocks
    result["jsonld_events"] = len(ld_events)
    result["jsonld_urls_first5"] = ld_urls[:5]

    # RSS/Atom link tags
    rss = [
        (l.get("href") or "").strip()
        for l in soup.find_all("link", attrs={"type": re.compile("rss|atom", re.I)})
        if l.get("href")
    ]
    result["rss_links"] = rss[:3]

    # iCal-ish links
    ics = []
    for a in soup.find_all("a", href=True):
        h = a["href"].lower()
        if ".ics" in h or "webcal://" in h:
            ics.append(a["href"])
    result["ical_links"] = ics[:3]

    # Event-detail anchors (heuristic)
    events_anchors = 0
    for a in soup.find_all("a", href=True):
        h = a["href"].lower()
        if any(seg in h for seg in ("/event", "/agenda", "/manifestation", "/veranstaltung", "/expositions/")):
            events_anchors += 1
    result["event_anchors"] = events_anchors

    result["status"] = "ok"
    return result


async def main() -> None:
    print(f"{'STATUS':<20}{'HTTP':>6}{'JLD':>5}{'EVT':>5}{'RSS':>5}{'ICS':>5}{'A':>6}  URL")
    for name, url in CANDIDATES:
        r = await probe_one(name, url)
        status = r.get("status", "?")
        http = r.get("http", "-")
        jld = r.get("jsonld_blocks", "-")
        evt = r.get("jsonld_events", "-")
        rss = len(r.get("rss_links") or [])
        ics = len(r.get("ical_links") or [])
        a   = r.get("event_anchors", "-")
        print(f"{str(status)[:20]:<20}{str(http):>6}{str(jld):>5}{str(evt):>5}{str(rss):>5}{str(ics):>5}{str(a):>6}  {name}  →  {url}")


if __name__ == "__main__":
    asyncio.run(main())
