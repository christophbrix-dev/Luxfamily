#!/usr/bin/env python3
"""Find event sources beyond the communes: museums, theatres, pools, castles.

discover_sources.py checked the 100 communes and found 40 usable feeds. The
places that actually *host* things — Mudam, a commune sports hall, the castle
in Vianden, the local Kulturhaus — were never asked, and between them they
publish far more than a commune's noticeboard.

The list of them is already on disk. The Geofabrik extract used for the POI
ingest tags museums, theatres, libraries, arts centres, sports halls, water
parks and castles, and a good number carry a `website`. No new source of data,
no service to ask permission of: 230 distinct domains fall out of a file we
already download.

Each one is then put through the same probe as the communes — robots.txt
first, and a site that says no is dropped rather than argued with.

    python3 discover_venue_sources.py               # everything, resumable
    python3 discover_venue_sources.py --limit 20    # a taste first

Progress is cached per domain, so a run that is interrupted, or one that hits
a slow site, can be repeated without asking anyone twice.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse

import osmium

from discover_sources import probe
from osm_ingest import PBF_CACHE

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("discover_venues")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sources" / "venue_candidates.csv"
CACHE = Path("/tmp/discover_venues_cache.json")

# Places that put on events, in the order they are worth having. A restaurant
# or a hotel is left out on purpose: they have websites and no public calendar,
# and asking 400 of them for a page that does not exist is rude arithmetic.
VENUE_KINDS: List[Tuple[str, str, str]] = [
    ("tourism", "museum", "Musée"),
    ("amenity", "arts_centre", "Kulturzentrum"),
    ("amenity", "theatre", "Theater"),
    ("amenity", "library", "Bibliothek"),
    ("amenity", "events_venue", "Veranstaltungsort"),
    ("amenity", "community_centre", "Gemeinschaftshaus"),
    ("amenity", "cinema", "Kino"),
    ("tourism", "gallery", "Galerie"),
    ("tourism", "zoo", "Tierpark"),
    ("tourism", "theme_park", "Freizeitpark"),
    ("tourism", "attraction", "Sehenswürdigkeit"),
    ("tourism", "information", "Tourist-Info"),
    ("historic", "castle", "Burg"),
    ("leisure", "sports_centre", "Sportzentrum"),
    ("leisure", "water_park", "Erlebnisbad"),
    ("leisure", "swimming_pool", "Schwimmbad"),
    ("leisure", "nature_reserve", "Naturschutzgebiet"),
]

_LOOKUP = {(k, v): label for k, v, label in VENUE_KINDS}
_ORDER = {(k, v): i for i, (k, v, _) in enumerate(VENUE_KINDS)}

# A commune publishes an "agenda". A museum publishes a "programme" of
# "expositions" and "ateliers", a theatre a "spectacle", a castle "visites
# guidées". Probing venues with the commune vocabulary reports NICHTS GEFUNDEN
# for places that plainly do have events — Casino Luxembourg among them.
VENUE_EVENTISH = re.compile(
    r"event|agenda|manifestation|veranstalt|actualit|aktuell|kalend|termin"
    r"|programm|exposition|ausstellung|activite|activit|atelier|workshop"
    r"|visite|fuehrung|führung|spectacle|concert|konzert|vernissage"
    r"|whats-?on|was-?ist-?los",
    re.I,
)

VENUE_PATHS = [
    "/agenda", "/events", "/evenements", "/programme", "/programm",
    "/expositions", "/ausstellungen", "/activites", "/ateliers",
    "/veranstaltungen", "/manifestations", "/actualites", "/aktuelles",
]


class _VenueHandler(osmium.SimpleHandler):
    """Every tagged venue that publishes a website."""

    def __init__(self) -> None:
        super().__init__()
        self.found: List[Dict[str, str]] = []

    def _take(self, tags: Dict[str, str]) -> None:
        site = (tags.get("website") or tags.get("contact:website") or "").strip()
        if not site.startswith("http"):
            return
        for key, value in _LOOKUP:
            if tags.get(key) == value:
                self.found.append({
                    "kind": _LOOKUP[(key, value)],
                    "order": _ORDER[(key, value)],
                    "name": (tags.get("name") or tags.get("name:lb")
                             or tags.get("name:fr") or "").strip(),
                    "website": site,
                })
                return

    def node(self, n) -> None:
        self._take({t.k: t.v for t in n.tags})

    def way(self, w) -> None:
        self._take({t.k: t.v for t in w.tags})

    def relation(self, r) -> None:
        self._take({t.k: t.v for t in r.tags})


def venues() -> List[Dict[str, str]]:
    """One entry per domain, best-known name kept.

    A museum with three buildings mapped separately is one website, and asking
    it three times is three requests for the same answer.
    """
    if not PBF_CACHE.exists():
        raise SystemExit(
            f"{PBF_CACHE} missing — run build_commune_index.py once to fetch it."
        )
    handler = _VenueHandler()
    handler.apply_file(str(PBF_CACHE))

    by_domain: Dict[str, Dict[str, str]] = {}
    for v in handler.found:
        domain = urlparse(v["website"]).netloc.lower().removeprefix("www.")
        if not domain:
            continue
        keep = by_domain.get(domain)
        # Prefer the more interesting kind, then the one that has a name.
        if (keep is None
                or v["order"] < keep["order"]
                or (v["order"] == keep["order"] and not keep["name"] and v["name"])):
            by_domain[domain] = v

    out = sorted(by_domain.values(), key=lambda v: (v["order"], v["name"]))
    log.info("%d venues with a website, %d distinct domains",
             len(handler.found), len(out))
    return out


def _cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="stop after N venues")
    args = ap.parse_args()

    todo = venues()
    if args.limit:
        todo = todo[:args.limit]

    cache = _cache()
    rows: List[Dict[str, str]] = []
    for i, v in enumerate(todo, 1):
        key = v["website"]
        if key in cache:
            rows.append(cache[key])
            continue
        log.info("[%3d/%d] %s — %s", i, len(todo), v["kind"], v["name"] or key)
        row = probe(v["name"] or urlparse(key).netloc, key,
                    eventish=VENUE_EVENTISH, fallback_paths=VENUE_PATHS)
        # probe() names its subject column "Gemeinde"; these are venues.
        row = {"Art": v["kind"], "Name": row.pop("Gemeinde"), **row}
        rows.append(row)
        cache[key] = row
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    usable = [r for r in rows if r["Status"] == "KANDIDAT" and r["JSON-LD"] == "ja"]
    blocked = [r for r in rows if r["Status"] == "GESPERRT"]
    log.info("\n%d probed -> %d usable (robots ok, sitemap, JSON-LD), %d say no",
             len(rows), len(usable), len(blocked))
    log.info("Written to %s", OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
