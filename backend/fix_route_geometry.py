#!/usr/bin/env python3
"""Give hiking and cycle routes the geometry that makes them findable.

866 of our 7,856 places are routes — the Mosel-Radweg, the Sauer-Radweg, the
Piste cyclable Jangeli. Every one carries a real name and a family score
between 60 and 77, and every one was invisible: `osm_ingest.relation()` skips
geometry for them, so they had no coordinate, so they fell out of every
question about distance and never reached the map.

The obvious repair would be the wrong one. A pin in the middle of a route that
runs the length of the country answers "12 km" to somebody it passes two
kilometres from, and "12 km" again to somebody sixty kilometres from its far
end — the same invented precision as an age of "0".

So a route keeps its shape. This reads the same Geofabrik extract the ingest
reads, walks each route's member ways, simplifies them, and stores the result
as `path_parts`: a list of polylines, one per member way. `geo.distance_of`
then measures to the nearest point *on the line*.

One polyline per way rather than one long line, deliberately: a route's ways
are not necessarily contiguous or in order, and joining them would invent a
segment across whatever lies between — which would then happily be somebody's
"nearest point".

    python3 fix_route_geometry.py            # show what would change
    python3 fix_route_geometry.py --write    # change it
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import math
import sys
from typing import Dict, List, Sequence, Tuple

import osmium
from pymongo import MongoClient

from db_config import mongo_settings
from osm_ingest import ensure_pbf

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("fix_route_geometry")

ROUTE_KINDS = ["hiking_route", "cycle_route"]

# A route is stored at a fidelity that is honest about what it is used for:
# answering "how far is this from me". 25 m is far below the accuracy of a
# phone's position, so simplifying to it costs nothing anybody could notice.
BASE_TOLERANCE_M = 25.0
# …but the Mosel-Radweg has 14,274 points, and a document that large helps
# nobody. The tolerance doubles until the route fits, and the cap is generous
# enough that it is rarely reached.
MAX_POINTS_PER_ROUTE = 200

_KM_PER_DEGREE_LAT = 111.0


def _to_km(points: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """(lat, lng) -> local kilometres, so a tolerance in metres means metres."""
    if not points:
        return []
    lat0 = math.radians(sum(p[0] for p in points) / len(points))
    kx = _KM_PER_DEGREE_LAT * math.cos(lat0)
    return [(p[1] * kx, p[0] * _KM_PER_DEGREE_LAT) for p in points]


def simplify(points: Sequence[Tuple[float, float]], tolerance_m: float) -> List[Tuple[float, float]]:
    """Ramer–Douglas–Peucker, keeping the ends.

    Iterative rather than recursive: one Luxembourg cycle route has 14,274
    points, and the recursive form reaches Python's stack limit on a shape like
    that — which would have shown up as a crash on exactly the longest and most
    interesting routes.
    """
    if len(points) < 3:
        return list(points)

    flat = _to_km(points)
    tol = tolerance_m / 1000.0
    keep = [False] * len(points)
    keep[0] = keep[-1] = True

    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        ax, ay = flat[first]
        bx, by = flat[last]
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy

        worst, worst_at = -1.0, -1
        for i in range(first + 1, last):
            px, py = flat[i]
            if length_sq == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
                d = math.hypot(px - ax - t * dx, py - ay - t * dy)
            if d > worst:
                worst, worst_at = d, i

        if worst > tol:
            keep[worst_at] = True
            stack.append((first, worst_at))
            stack.append((worst_at, last))

    return [p for p, k in zip(points, keep) if k]


class Members(osmium.SimpleHandler):
    """Pass one: which ways belong to which route."""

    def __init__(self, ids: set) -> None:
        super().__init__()
        self.ids = ids
        self.ways_of: Dict[int, List[int]] = {}

    def relation(self, r) -> None:
        if r.id not in self.ids:
            return
        ways = [m.ref for m in r.members if m.type == "w"]
        if ways:
            self.ways_of[r.id] = ways


class Shapes(osmium.SimpleHandler):
    """Pass two: the coordinates of those ways."""

    def __init__(self, wanted: set) -> None:
        super().__init__()
        self.wanted = wanted
        self.points: Dict[int, List[Tuple[float, float]]] = {}

    def way(self, w) -> None:
        if w.id not in self.wanted:
            return
        try:
            pts = [(n.lat, n.lon) for n in w.nodes if n.location.valid()]
        except osmium.InvalidLocationError:
            return
        if len(pts) >= 2:
            self.points[w.id] = pts


def _key(point: Tuple[float, float]) -> Tuple[float, float]:
    """An endpoint, as a value two ways can be compared by.

    The coordinates come from the same OSM node, so they are identical bit for
    bit; rounding is only insurance against a float that took a different route
    through the reader.
    """
    return (round(point[0], 7), round(point[1], 7))


def chain(parts: List[List[Tuple[float, float]]]) -> List[List[Tuple[float, float]]]:
    """Join ways that share an endpoint into longer lines.

    Without this the point budget cannot be met: every way contributes at least
    two points however coarsely it is simplified, and the Europäischer
    Fernwanderweg E3 is made of enough of them that its floor was 3,134 points
    against a cap of 200. Simplification had nothing to bite on, because each
    piece was already as short as a line can be.

    Joining is not inventing: two ways are only joined where they genuinely
    end at the same node. Ways that do not meet stay separate, which is what
    keeps `distance_to_path_km` from measuring to a segment across a gap.
    """
    remaining = {i: list(p) for i, p in enumerate(parts) if len(p) >= 2}
    ends: Dict[Tuple[float, float], List[int]] = {}
    for i, pts in remaining.items():
        ends.setdefault(_key(pts[0]), []).append(i)
        ends.setdefault(_key(pts[-1]), []).append(i)

    def take(at: Tuple[float, float], exclude: int):
        for j in ends.get(at, []):
            if j != exclude and j in remaining:
                return j
        return None

    out: List[List[Tuple[float, float]]] = []
    while remaining:
        i, line = remaining.popitem()
        # Grow at the tail, then at the head, until nothing meets either end.
        while True:
            j = take(_key(line[-1]), i)
            if j is None:
                break
            nxt = remaining.pop(j)
            line += (nxt[1:] if _key(nxt[0]) == _key(line[-1]) else list(reversed(nxt))[1:])
        while True:
            j = take(_key(line[0]), i)
            if j is None:
                break
            prv = remaining.pop(j)
            line = (prv[:-1] if _key(prv[-1]) == _key(line[0]) else list(reversed(prv))[:-1]) + line
        out.append(line)
    return out


def build(ways: Sequence[int], shapes: Dict[int, List[Tuple[float, float]]]) -> List[List[List[float]]]:
    """Simplified polylines for one route, within the point budget."""
    raw = chain([shapes[w] for w in ways if w in shapes])
    if not raw:
        return []
    tolerance = BASE_TOLERANCE_M
    while True:
        parts = [simplify(p, tolerance) for p in raw]
        parts = [p for p in parts if len(p) >= 2]
        total = sum(len(p) for p in parts)
        if total <= MAX_POINTS_PER_ROUTE or tolerance > 2000:
            return [[[round(lat, 6), round(lng, 6)] for lat, lng in p] for p in parts]
        tolerance *= 2


def bounds(parts: Sequence[Sequence[Sequence[float]]]) -> Dict[str, float]:
    """The box the route lies in, so Mongo can rule it out without arithmetic."""
    lats = [p[0] for part in parts for p in part]
    lngs = [p[1] for part in parts for p in part]
    return {
        "bbox_south": min(lats), "bbox_north": max(lats),
        "bbox_west": min(lngs), "bbox_east": max(lngs),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="store the geometry")
    args = ap.parse_args()

    url, name = mongo_settings()
    db = MongoClient(url, serverSelectionTimeoutMS=10_000)[name]

    routes: Dict[int, dict] = {}
    for doc in db.places.find({"kind": {"$in": ROUTE_KINDS}}, {"_id": 0, "id": 1, "name": 1, "kind": 1}):
        try:
            routes[int(str(doc["id"]).rsplit("/", 1)[1])] = doc
        except (IndexError, ValueError):
            log.warning("id in an unexpected shape, skipped: %s", doc.get("id"))
    log.info("%d routes\n", len(routes))
    if not routes:
        return

    pbf = asyncio.run(ensure_pbf())
    log.info("reading %s", pbf)

    members = Members(set(routes))
    members.apply_file(str(pbf))
    log.info("  %d routes have member ways", len(members.ways_of))

    needed = {w for ws in members.ways_of.values() for w in ws}
    shapes = Shapes(needed)
    shapes.apply_file(str(pbf), locations=True, idx="flex_mem")
    log.info("  %d of %d member ways have coordinates\n", len(shapes.points), len(needed))

    done = empty = 0
    points_total = 0
    longest: Tuple[int, str] = (0, "")
    for osm_id, doc in routes.items():
        parts = build(members.ways_of.get(osm_id, []), shapes.points)
        if not parts:
            empty += 1
            continue
        n = sum(len(p) for p in parts)
        points_total += n
        if n > longest[0]:
            longest = (n, str(doc.get("name")))
        done += 1
        if args.write:
            db.places.update_one(
                {"id": doc["id"]},
                {"$set": {"path_parts": parts, "geocode_precision": "route", **bounds(parts)}},
            )

    log.info("%d routes %s geometry", done, "given" if args.write else "would get")
    if empty:
        log.info("%d had no usable ways and stay without", empty)
    log.info("%d points in total, most in one route: %d (%s)", points_total, longest[0], longest[1])
    log.info("roughly %.2f MB stored", points_total * 16 / 1e6)
    if not args.write:
        log.info("\nDry run. Re-run with --write to apply.")


if __name__ == "__main__":
    sys.exit(main())
