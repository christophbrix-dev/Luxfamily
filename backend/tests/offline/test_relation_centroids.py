# Giving relation-backed places a coordinate — and never a route one.
#
# 911 of 7,856 places had no lat/lng, and the number invited the wrong fix.
# 871 of them are hiking and cycle routes: a trail is a line, and a single
# point for it would be invented, not measured. The other 40 are ordinary
# places that happen to be mapped as multipolygons — among them the Piscine
# Municipale de Bonnevoie, the Skatepark Péitruss and Château de Clervaux —
# and those should always have had a centre.
#
# What is tested here is the selection and the guard rails, not osmium: the
# polygon assembly is osmium's job and it has its own tests. What this project
# can get wrong is *which* rows it touches and *which* coordinates it believes.

import pytest

from fix_relation_centroids import LU_BOUNDS, ROUTE_KINDS, plausible, wanted


class FakePlaces:
    """Just enough of a collection for `wanted()` — it runs one find()."""

    def __init__(self, docs):
        self.docs = docs

    def find(self, query, projection=None):
        return [d for d in self.docs if self._matches(d, query)]

    def _matches(self, doc, query):
        for key, cond in query.items():
            if key == "$or":
                if not any(self._matches(doc, c) for c in cond):
                    return False
            elif isinstance(cond, dict):
                if "$nin" in cond and doc.get(key) in cond["$nin"]:
                    return False
                if "$in" in cond and doc.get(key) not in cond["$in"]:
                    return False
                if "$exists" in cond and (key in doc) != cond["$exists"]:
                    return False
            elif doc.get(key) != cond:
                return False
        return True


class FakeDb:
    def __init__(self, docs):
        self.places = FakePlaces(docs)


def place(pid, kind, lat=None, lng=None, osm_type="relation", name="x"):
    doc = {"id": pid, "kind": kind, "osm_type": osm_type, "name": name}
    if lat is not None:
        doc["lat"] = lat
    if lng is not None:
        doc["lng"] = lng
    return doc


# ---------------------------------------------------------------------------
# Which rows are picked
# ---------------------------------------------------------------------------

def test_a_relation_without_a_coordinate_is_picked():
    db = FakeDb([place("osm:relation/1954663", "swimming")])
    assert list(wanted(db)) == [1954663]


@pytest.mark.parametrize("kind", sorted(ROUTE_KINDS))
def test_routes_are_never_picked(kind):
    """A hiking trail is a line. A point for it would be invented.

    Excluded by kind rather than by "has no coordinate", so a route that
    somehow acquires one is still left alone.
    """
    db = FakeDb([place("osm:relation/999", kind)])
    assert wanted(db) == {}


def test_a_relation_that_already_has_a_coordinate_is_left_alone():
    db = FakeDb([place("osm:relation/42", "park", lat=49.6, lng=6.1)])
    assert wanted(db) == {}


@pytest.mark.parametrize("lat, lng", [(0, 0), (None, None), (0, 6.1), (49.6, 0)])
def test_null_island_and_half_a_coordinate_count_as_missing(lat, lng):
    """0,0 is the Atlantic and half a position is no position."""
    db = FakeDb([place("osm:relation/7", "park", lat=lat, lng=lng)])
    assert list(wanted(db)) == [7]


def test_a_way_is_not_a_relation():
    """Ways already come through osm_ingest with their own coordinates."""
    db = FakeDb([place("osm:way/5", "park", osm_type="way")])
    assert wanted(db) == {}


def test_an_id_in_an_unexpected_shape_is_skipped_not_guessed():
    """Better one row left behind than a coordinate written onto the wrong one."""
    db = FakeDb([
        place("relation-1954663", "swimming"),   # no slash
        place("osm:relation/abc", "park"),       # not a number
        place("osm:relation/77", "park"),        # fine
    ])
    assert list(wanted(db)) == [77]


# ---------------------------------------------------------------------------
# Which coordinates are believed
# ---------------------------------------------------------------------------

def test_luxembourg_is_plausible():
    assert plausible(49.6116, 6.1319)      # Luxembourg City
    assert plausible(50.0544, 6.0301)      # Clervaux
    assert plausible(49.4958, 5.9806)      # Esch-sur-Alzette


@pytest.mark.parametrize("lat, lng, what", [
    (0.0, 0.0, "Null Island"),
    (48.8566, 2.3522, "Paris"),
    (52.5200, 13.4050, "Berlin"),
    (-33.8688, 151.2093, "Sydney"),
])
def test_a_centre_outside_the_country_is_refused(lat, lng, what):
    """A wrong coordinate is worse than none: it puts a castle in a field and
    nothing complains."""
    assert not plausible(lat, lng), what


def test_the_bounds_have_a_margin_for_border_parks():
    south, north, west, east = LU_BOUNDS
    # Luxembourg spans roughly 49.45–50.18 N and 5.73–6.53 E. The bounds must
    # be wider, because several nature parks reach into Belgium and Germany.
    assert south < 49.44 and north > 50.19
    assert west < 5.72 and east > 6.54
