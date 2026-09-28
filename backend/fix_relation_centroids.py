#!/usr/bin/env python3
"""Give the places that are mapped as OSM relations a coordinate.

911 of our 7,856 places have no `lat`/`lng`, and every one of them is an OSM
relation. That number looks alarming and mostly is not: 871 are hiking and
cycle routes, which are lines rather than points. A hiking trail has no single
coordinate, and inventing one would be the same mistake as an age of "0".

The other 40 are ordinary places that happen to be mapped as multipolygons, and
those should always have had a centre:

    Piscine Municipale de Bonnevoie      a public swimming pool
    Kulturfabrik Esch                    one of the larger venues
    Château de Clervaux, Skatepark Péitruss
    12 parks, 9 castles, 8 nature parks, 4 fitness trails, a playground

The cause is a documented gap rather than an accident. `osm_ingest.relation()`
says so itself:

    Coordinates for relations are hard w/o multipolygon build. For hiking /
    cycle routes we skip geometry — the UI can link out to OSM for now. A
    future pass can use osmium.geom to build centroids from member ways.

This is that pass. It reads the same Geofabrik extract the ingest reads — no
new source, nothing fetched that the project does not already fetch — and takes
the centre of the assembled polygon, exactly as `osm_ingest.area()` does for
the categories that carry a minimum size.

    python3 fix_relation_centroids.py            # show what would change
    python3 fix_relation_centroids.py --write    # change it

Routes are never touched, with or without --write.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Dict, Optional, Tuple

import osmium
from pymongo import MongoClient

from db_config import mongo_settings
from osm_ingest import ensure_pbf

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("fix_relation_centroids")

# Lines, not points. Excluded by kind rather than by "has no coordinate", so a
# route that somehow acquires one is still left alone.
ROUTE_KINDS = {"hiking_route", "cycle_route"}


def wanted(db) -> Dict[int, dict]:
    """The relation-backed places that are missing a coordinate, by OSM id."""
    query = {
        "osm_type": "relation",
        "kind": {"$nin": sorted(ROUTE_KINDS)},
        "$or": [
            {"lat": {"$in": [None, 0]}},
            {"lng": {"$in": [None, 0]}},
            {"lat": {"$exists": False}},
            {"lng": {"$exists": False}},
        ],
    }
    out: Dict[int, dict] = {}
    for doc in db.places.find(query, {"_id": 0, "id": 1, "name": 1, "kind": 1}):
        # "osm:relation/12890196" -> 12890196
        try:
            out[int(str(doc["id"]).rsplit("/", 1)[1])] = doc
        except (IndexError, ValueError):
            log.warning("id in an unexpected shape, skipped: %s", doc.get("id"))
    return out


class Centroids(osmium.SimpleHandler):
    """Collect the centre of every wanted relation's assembled polygon.

    osmium hands multipolygon relations to `area()` with the rings already
    built, which is the part `relation()` could not do on its own. `orig_id()`
    gives the relation's own id back, and `from_way()` tells a relation-derived
    area from a closed-way one — only the former is of interest here.
    """

    def __init__(self, ids: set) -> None:
        super().__init__()
        self.ids = ids
        self.found: Dict[int, Tuple[float, float]] = {}

    def area(self, a) -> None:
        if a.from_way():
            return
        osm_id = a.orig_id()
        if osm_id not in self.ids or osm_id in self.found:
            return
        try:
            rings = [[(n.lon, n.lat) for n in ring] for ring in a.outer_rings()]
        except osmium.InvalidLocationError:
            return
        rings = [r for r in rings if len(r) >= 3]
        if not rings:
            return
        pts = [p for r in rings for p in r]
        # The mean of the outer ring's points, the same way osm_ingest.area()
        # does it. Not a true centroid for a crescent-shaped park, but within
        # metres for anything this list holds — and honest about being an
        # approximation, which is why it is written as "relation_centroid".
        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        self.found[osm_id] = (lat, lon)


# Luxembourg and a margin for the border parks. A centroid outside this is a
# sign the polygon was assembled wrong, and a wrong coordinate is worse than
# none: it puts a castle in a field and nothing complains.
LU_BOUNDS = (49.30, 50.30, 5.60, 6.70)


def plausible(lat: float, lng: float) -> bool:
    south, north, west, east = LU_BOUNDS
    return south <= lat <= north and west <= lng <= east


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply the coordinates")
    args = ap.parse_args()

    url, name = mongo_settings()
    db = MongoClient(url, serverSelectionTimeoutMS=10_000)[name]

    todo = wanted(db)
    routes = db.places.count_documents({"osm_type": "relation", "kind": {"$in": sorted(ROUTE_KINDS)}})
    log.info("%d relation-backed places without a coordinate", len(todo))
    log.info("%d routes left alone — a line has no single point\n", routes)
    if not todo:
        return

    pbf = asyncio.run(ensure_pbf())
    log.info("reading %s\n", pbf)

    handler = Centroids(set(todo))
    handler.apply_file(str(pbf), locations=True, idx="flex_mem")

    applied = skipped_missing = skipped_odd = 0
    for osm_id, doc in sorted(todo.items(), key=lambda kv: kv[1].get("kind") or ""):
        point: Optional[Tuple[float, float]] = handler.found.get(osm_id)
        label = f"{str(doc.get('kind')):16} {str(doc.get('name'))[:40]:42}"
        if point is None:
            # Not every relation is a multipolygon: a site or a route master
            # has no rings to assemble, and there is nothing to compute.
            log.info("  %s  no polygon — left without a coordinate", label)
            skipped_missing += 1
            continue
        lat, lng = point
        if not plausible(lat, lng):
            log.info("  %s  centre %.5f,%.5f is outside Luxembourg — refused", label, lat, lng)
            skipped_odd += 1
            continue
        log.info("  %s  %.5f, %.5f", label, lat, lng)
        if args.write:
            db.places.update_one(
                {"id": doc["id"]},
                {"$set": {"lat": lat, "lng": lng, "geocode_precision": "relation_centroid"}},
            )
        applied += 1

    log.info("\n%d would get a coordinate" if not args.write else "\n%d updated", applied)
    if skipped_missing:
        log.info("%d had no polygon to build from", skipped_missing)
    if skipped_odd:
        log.info("%d produced a centre outside Luxembourg and were refused", skipped_odd)
    if not args.write:
        log.info("\nDry run. Re-run with --write to apply.")


if __name__ == "__main__":
    sys.exit(main())
