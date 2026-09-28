"""Distance on the ground, and the box that finds it quickly.

`/api/places` already took `near_lat`, `near_lng` and `radius_km`, and none of
the three meant what the name said. Measured against the 7,856 places we hold,
asked from the Gare in Luxembourg City with `radius_km=10`:

* 14 of the 200 returned were further away than 10 km, the worst of them
  13.2 km. The filter was a *square* — the corner of a 10 km box is 14.1 km
  from its centre — sold under the word "radius".
* 1,654 places sat in that box and 200 came back, ordered by `family_score`.
  So "near me" answered with the best-scored places in the region: a playground
  200 m away lost to a park 10 km away because the park scored higher. The one
  thing the parameter was named for, nearness, never reached the ordering at
  all.

The fix keeps the box, because the box is what the `(lat, lng)` index can walk
— an IXSCAN over 6,945 rows costs 7 ms, and a database-side geo index would
mean a second coordinate field to write and keep in step. The box is now only a
*prefilter*: everything it returns is measured properly afterwards, and
anything outside the real circle is dropped.

Two-step is deliberate for large collections: rank on `{id, lat, lng}`
(412 KB for a 50 km box) and fetch whole documents only for the page that is
actually returned (5,483 KB if fetched for the whole box).
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Luxembourg is 82 km from end to end. A hundred covers the country and the
# border towns families actually drive to, and stops a caller asking for a box
# that is the whole collection plus a sort over it.
MAX_RADIUS_KM = 100.0

_EARTH_RADIUS_KM = 6371.0
# One degree of latitude, anywhere. Longitude shrinks towards the poles and is
# computed per call — at Luxembourg's 49.6° a degree of longitude is 72 km, not
# 111, so a box built without that correction is a third too narrow.
_KM_PER_DEGREE_LAT = 111.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres.

    The same formula the app uses in `useUserLocation.distanceKm`, so a
    distance shown on a card and a distance used to filter agree. Treating the
    earth as a sphere is accurate to a few metres across Luxembourg — far below
    the accuracy of the position a phone reports.
    """
    to_rad = math.radians
    d_lat = to_rad(lat2 - lat1)
    d_lng = to_rad(lng2 - lng1)
    h = (
        math.sin(d_lat / 2) ** 2
        + math.sin(d_lng / 2) ** 2 * math.cos(to_rad(lat1)) * math.cos(to_rad(lat2))
    )
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def bounding_box(lat: float, lng: float, radius_km: float) -> Dict[str, Any]:
    """The Mongo filter fragment for the square that encloses the circle.

    Encloses, never clips: the returned set is always a superset of the circle,
    so `within_radius` can only ever remove rows the caller did not ask for. A
    box that was too small would silently hide places that really are in range,
    which is the harder bug to notice.

    Near the poles `cos(lat)` goes to zero and the longitude span would explode;
    Luxembourg is nowhere near that, but the clamp means the function cannot
    return a nonsense box for a coordinate that arrived by accident.
    """
    d_lat = radius_km / _KM_PER_DEGREE_LAT
    cos_lat = max(math.cos(math.radians(lat)), 0.01)
    d_lng = radius_km / (_KM_PER_DEGREE_LAT * cos_lat)
    return {
        "lat": {"$gte": lat - d_lat, "$lte": lat + d_lat},
        "lng": {"$gte": lng - d_lng, "$lte": lng + d_lng},
    }


def distance_to_path_km(
    lat: float,
    lng: float,
    parts: Iterable[Iterable[Iterable[float]]],
) -> Optional[float]:
    """Distance to the nearest point *on* a line, not to a point standing in for it.

    871 of our places are hiking and cycle routes. A route is a line — the
    Mosel-Radweg runs the length of the country — and the obvious repair, a pin
    somewhere in the middle, would be the same invented precision as an age of
    "0": it would answer "12 km" to somebody the route passes two kilometres
    from, and "12 km" again to somebody sixty kilometres from its far end.

    So the distance is measured to the nearest point of the nearest *segment*,
    which is the only number that is true. Nearest *vertex* would have been
    less code and wrong by up to half a segment: simplification leaves a
    straight five-kilometre stretch as two points, and a walker standing beside
    the middle of it would be told two and a half kilometres.

    `parts` is a list of polylines, one per member way, rather than one long
    line: a route's ways are not necessarily contiguous or in order, and
    joining them would invent a segment across whatever lies between.
    """
    best: Optional[float] = None
    for part in parts:
        points = [(float(p[0]), float(p[1])) for p in part if len(p) >= 2]
        if not points:
            continue
        if len(points) == 1:
            d = haversine_km(lat, lng, points[0][0], points[0][1])
            best = d if best is None else min(best, d)
            continue
        for a, b in zip(points, points[1:]):
            d = _distance_to_segment_km(lat, lng, a, b)
            if best is None or d < best:
                best = d
    return best


def _distance_to_segment_km(
    lat: float, lng: float,
    a: Tuple[float, float], b: Tuple[float, float],
) -> float:
    """Distance from a point to a segment, on a flat local approximation.

    Over a segment of a few hundred metres in Luxembourg the earth's curvature
    is far below the accuracy of anything we hold, so the projection is done in
    kilometres on a local plane — longitude scaled by cos(latitude), the same
    correction `bounding_box` makes. The result is then a plain 2-D distance,
    and the caller never sees the difference.
    """
    lat0 = math.radians((a[0] + b[0]) / 2)
    kx = _KM_PER_DEGREE_LAT * math.cos(lat0)
    ky = _KM_PER_DEGREE_LAT

    px, py = (lng - a[1]) * kx, (lat - a[0]) * ky
    bx, by = (b[1] - a[1]) * kx, (b[0] - a[0]) * ky

    length_sq = bx * bx + by * by
    if length_sq == 0:
        return math.hypot(px, py)

    # How far along the segment the closest point lies, clamped to its ends:
    # without the clamp the "nearest point" could sit off the end of the line.
    t = max(0.0, min(1.0, (px * bx + py * by) / length_sq))
    return math.hypot(px - t * bx, py - t * by)


def near_query(lat: float, lng: float, radius_km: float) -> Dict[str, Any]:
    """The Mongo fragment that finds both points and lines near here.

    `bounding_box` alone looks at `lat`/`lng`, which a route does not have: 865
    of our places are lines, and they fell through the prefilter before they
    ever reached the arithmetic. A route matches when the box it lies in
    overlaps the box we are searching — two boxes overlap unless one is
    entirely past an edge of the other, which is four plain comparisons and
    something Mongo can answer from an index.

    Still a prefilter, and still generous: a route whose box overlaps may yet
    be outside the circle, and `within_radius` is what decides.
    """
    box = bounding_box(lat, lng, radius_km)
    south, north = box["lat"]["$gte"], box["lat"]["$lte"]
    west, east = box["lng"]["$gte"], box["lng"]["$lte"]
    return {
        "$or": [
            box,
            {
                "bbox_south": {"$lte": north},
                "bbox_north": {"$gte": south},
                "bbox_west": {"$lte": east},
                "bbox_east": {"$gte": west},
            },
        ]
    }


def within_radius(
    docs: Iterable[Dict[str, Any]],
    lat: float,
    lng: float,
    radius_km: float,
    *,
    sort: bool = True,
) -> List[Tuple[float, Dict[str, Any]]]:
    """`(distance_km, doc)` for the documents genuinely inside the circle.

    Nearest first unless `sort=False`, which the event list uses: there the
    date leads and nearness is only a filter. A concert three months away two
    streets from the door does not belong above tomorrow's village fete.

    A document carrying `path_parts` is a line rather than a point — a hiking
    or cycle route — and is measured to its nearest point. 866 of our places
    are these, and until they had geometry they fell out of every question
    about distance: named, well scored, and invisible on any map.

    A document with neither a coordinate nor a path is dropped rather than
    placed at zero distance. Putting it at the user's feet would make it the
    first thing on the screen, which is the loudest possible way to be wrong.
    """
    out: List[Tuple[float, Dict[str, Any]]] = []
    for doc in docs:
        distance = distance_of(doc, lat, lng)
        if distance is not None and distance <= radius_km:
            out.append((distance, doc))
    if sort:
        out.sort(key=lambda pair: pair[0])
    return out


def distance_of(doc: Dict[str, Any], lat: float, lng: float) -> Optional[float]:
    """How far this document is, whether it is a point or a line.

    None when it is neither — which is not the same as zero, and the caller
    must keep the two apart.
    """
    parts = doc.get("path_parts")
    if parts:
        return distance_to_path_km(lat, lng, parts)
    point = _coords(doc)
    if point is None:
        return None
    return haversine_km(lat, lng, point[0], point[1])


def _coords(doc: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """A document's position, or None when it has not really got one.

    `0, 0` is Null Island in the Atlantic, and it is what an importer writes
    when it found nothing. Reading it as a coordinate puts the place 5,400 km
    from Luxembourg, which at least sorts last — but it is a missing value
    wearing a number, and it is treated as missing.
    """
    lat, lng = doc.get("lat"), doc.get("lng")
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        return None
    if isinstance(lat, bool) or isinstance(lng, bool):
        return None
    if lat == 0 and lng == 0:
        return None
    return float(lat), float(lng)
