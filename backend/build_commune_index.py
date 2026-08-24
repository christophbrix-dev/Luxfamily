#!/usr/bin/env python3
"""Build the commune -> canton index from OpenStreetMap boundary data.

Every source we import needs a canton: it is what the app's "browse by canton"
filter runs on, and an event filed under the wrong one is worse than an event
with none. Luxembourg's 100 communes and 12 cantons are a fixed administrative
fact, but writing the mapping out by hand invites exactly the kind of quiet
error nobody notices — so it is derived here from official boundary geometry
and written to communes_lu.json.

Why not Wikidata, which already gave us the commune list? query.wikidata.org
disallows our user agent in robots.txt, and crawler_utils refuses the request.
The Geofabrik extract we already use for the POI ingest carries the same
boundaries and is published for download, so it answers the question without
asking anyone for something they have not offered.

Why not the geoportal geocoder? It returns coordinates and a locality, but no
canton — checked both the forward and the reverse endpoint.

    python3 build_commune_index.py            # rebuild communes_lu.json

Roughly a minute, most of it the first PBF download.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import osmium

from osm_ingest import ensure_pbf

logger = logging.getLogger("commune_index")

OUT = Path(__file__).resolve().parent / "communes_lu.json"

# Luxembourg tags cantons at admin_level 6 and communes at 8.
CANTON_LEVEL = "6"
COMMUNE_LEVEL = "8"

# The twelve cantons, spelled as the rest of the codebase spells them. OSM
# prefixes them ("Canton Vianden") and uses several language forms, so the name
# is stripped and looked up here. Anything outside this map is not a Luxembourg
# canton and is dropped rather than guessed at — level 6 also carries the
# Luxembourg–Germany condominium on the Moselle, which is not a canton.
CANTON_NAMES = {
    "Capellen": "Capellen",
    "Clervaux": "Clervaux",
    "Clerf": "Clervaux",
    "Diekirch": "Diekirch",
    "Echternach": "Echternach",
    "Esch-sur-Alzette": "Esch-sur-Alzette",
    "Esch-Uelzecht": "Esch-sur-Alzette",
    "Grevenmacher": "Grevenmacher",
    "Luxembourg": "Luxembourg",
    "Luxemburg": "Luxembourg",
    "Lëtzebuerg": "Luxembourg",
    "Mersch": "Mersch",
    "Redange": "Redange",
    "Redingen": "Redange",
    "Remich": "Remich",
    "Vianden": "Vianden",
    "Wiltz": "Wiltz",
}

Ring = List[Tuple[float, float]]


def _strip_canton_prefix(name: str) -> str:
    """"Canton Vianden" -> "Vianden". OSM labels the level-6 areas that way."""
    for prefix in ("Canton ", "Kanton ", "Kanton vun ", "Canton de ", "Canton d'"):
        if name.startswith(prefix):
            return name[len(prefix):].strip()
    return name.strip()


def point_in_ring(lon: float, lat: float, ring: Ring) -> bool:
    """Ray casting: does a horizontal ray from the point cross the ring oddly?

    Standard even-odd test. A point exactly on an edge is undefined and may
    fall either way — irrelevant here, where the points are town centres well
    inside their own canton.
    """
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        # Does the edge straddle the point's latitude?
        if (y1 > lat) != (y2 > lat):
            # Longitude where the edge crosses that latitude.
            x_at = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if x_at > lon:
                inside = not inside
    return inside


class _BoundaryHandler(osmium.SimpleHandler):
    """Collect canton polygons and commune centroids in one pass."""

    def __init__(self) -> None:
        super().__init__()
        self.cantons: List[Tuple[str, List[Ring]]] = []
        self.communes: List[Dict] = []

    def area(self, a) -> None:
        tags = {t.k: t.v for t in a.tags}
        if tags.get("boundary") != "administrative":
            return
        level = tags.get("admin_level")
        if level not in (CANTON_LEVEL, COMMUNE_LEVEL):
            return

        try:
            rings = [
                [(n.lon, n.lat) for n in ring]
                for ring in a.outer_rings()
            ]
        except osmium.InvalidLocationError:
            return
        rings = [r for r in rings if len(r) >= 3]
        if not rings:
            return

        if level == CANTON_LEVEL:
            name = CANTON_NAMES.get(_strip_canton_prefix(tags.get("name", "")))
            if name:
                self.cantons.append((name, rings))
            return

        # The Geofabrik extract is a bounding box, not the country: it carries
        # the German and French municipalities along the border too. Waldhof-
        # Falkenstein sits opposite Vianden across the Our, and the centroid of
        # its boundary vertices lands on the Luxembourg bank — so a point test
        # alone files a German village under canton Vianden. Luxembourg
        # communes carry ref:lau2, their neighbours carry national keys
        # instead, and that is what actually separates them.
        if "ref:lau2" not in tags:
            return

        # A commune: keep every spelling it publishes, plus its own website.
        names = {
            tags.get(k, "").strip()
            for k in ("name", "name:de", "name:fr", "name:lb", "official_name")
        }
        names.discard("")
        if not names:
            return
        pts = [p for ring in rings for p in ring]
        self.communes.append({
            "names": sorted(names),
            "website": (tags.get("website") or tags.get("contact:website") or "").strip(),
            # Centroid of the boundary vertices — good enough to sit inside the
            # canton, which is all it is used for.
            "lng": round(sum(p[0] for p in pts) / len(pts), 6),
            "lat": round(sum(p[1] for p in pts) / len(pts), 6),
        })


def canton_for(lon: float, lat: float, cantons) -> Optional[str]:
    for name, rings in cantons:
        if any(point_in_ring(lon, lat, ring) for ring in rings):
            return name
    return None


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    pbf = asyncio.run(ensure_pbf())

    handler = _BoundaryHandler()
    logger.info("Reading boundaries from %s", pbf)
    handler.apply_file(str(pbf), locations=True, idx="flex_mem")
    logger.info("  %d cantons, %d communes", len(handler.cantons), len(handler.communes))

    out, unplaced = [], []
    for c in handler.communes:
        canton = canton_for(c["lng"], c["lat"], handler.cantons)
        if not canton:
            unplaced.append(c["names"][0])
            continue
        out.append({**c, "canton": canton})

    out.sort(key=lambda c: c["names"][0])
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("Wrote %d communes to %s", len(out), OUT.name)
    if unplaced:
        # Not fatal: a boundary that lands in no canton is simply left out
        # rather than filed under a guess.
        logger.warning("  %d outside every canton, skipped: %s",
                       len(unplaced), ", ".join(unplaced[:8]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
