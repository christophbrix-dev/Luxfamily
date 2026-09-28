# How far away is a hiking trail?
#
# 866 of our 7,856 places are hiking and cycle routes — the Mosel-Radweg, the
# Sauer-Radweg, the Piste cyclable Jangeli. Every one has a real name and a
# family score between 60 and 77, and every one was invisible: no coordinate
# meant no map pin and no answer to "what is near me".
#
# The obvious repair is the wrong one. A pin in the middle of a route that runs
# the length of the country answers "12 km" to somebody it passes two
# kilometres from, and "12 km" again to somebody sixty kilometres from its far
# end. That is the same invented precision as an age of "0" — a number the data
# never supplied, shown as though it had been.
#
# So the distance is to the nearest point *on the line*. These tests use
# coordinates whose answers can be worked out by hand.

import pytest

from geo import distance_of, distance_to_path_km, haversine_km, within_radius

# A straight east-west line at 49.6 °N, one whole degree of longitude wide. At
# that latitude a degree of longitude is about 72 km — roughly the length of the
# Mosel-Radweg, and long enough that "beside the middle" and "near an end" are
# very different places. Writing it 0.2° wide the first time made the line 14 km
# long and the test's own point disappeared.
WEST = (49.6, 6.0)
EAST = (49.6, 7.0)
MIDDLE_LNG = 6.5
LINE = [[[WEST[0], WEST[1]], [EAST[0], EAST[1]]]]

def test_a_point_on_the_line_is_no_distance_away():
    assert distance_to_path_km(49.6, MIDDLE_LNG, LINE) == pytest.approx(0.0, abs=0.01)

def test_standing_beside_the_middle_measures_to_the_middle():
    """Not to an endpoint, and not to a stand-in point.

    0.01° of latitude is about 1.11 km due north of the line's midpoint.
    """
    d = distance_to_path_km(49.61, MIDDLE_LNG, LINE)
    assert d == pytest.approx(1.11, abs=0.05)

def test_past_the_end_measures_to_the_end():
    """The nearest point of a segment can only be on the segment.

    Without clamping, the projection would land off the end of the line and
    report a distance to a place the route never reaches.
    """
    d = distance_to_path_km(49.6, 7.1, LINE)         # 0.1° east of the east end
    straight = haversine_km(49.6, 7.1, *EAST)
    assert d == pytest.approx(straight, abs=0.05)

def test_the_nearest_vertex_would_have_been_wrong():
    """The reason segments are measured rather than the points that define them.

    Simplification leaves a long straight stretch as two points. Somebody
    standing beside the middle of it is 1.11 km from the line and roughly 36 km
    from either end — a walker told the larger number would conclude the route
    is nowhere near.
    """
    beside_middle = (49.61, MIDDLE_LNG)
    to_line = distance_to_path_km(*beside_middle, LINE)
    to_nearest_vertex = min(haversine_km(*beside_middle, *WEST),
                            haversine_km(*beside_middle, *EAST))
    assert to_line < 1.2
    assert to_nearest_vertex > 35
    assert to_nearest_vertex / to_line > 30

# ---------------------------------------------------------------------------
# Several polylines: a route's ways are not one continuous line
# ---------------------------------------------------------------------------

def test_the_nearest_of_several_parts_wins():
    far = [[49.9, 6.0], [49.9, 7.0]]
    near = [[49.61, 6.0], [49.61, 7.0]]
    assert distance_to_path_km(49.6, MIDDLE_LNG, [far, near]) == pytest.approx(1.11, abs=0.05)

def test_parts_are_not_joined_across_the_gap_between_them():
    """A route's member ways may be disjoint and out of order.

    Joining them end to end would invent a segment across whatever lies
    between — and that invented segment would happily be somebody's "nearest
    point". Here the two parts sit far north and far south; a joining segment
    would run right past the point in the middle.
    """
    north = [[50.0, 6.1], [50.0, 6.2]]
    south = [[49.2, 6.1], [49.2, 6.2]]
    middle = (49.6, 6.15)
    d = distance_to_path_km(*middle, [north, south])
    # Both parts are about 44 km away; a joining segment would pass through 0.
    assert d > 40

@pytest.mark.parametrize("parts", [[], [[]], [[[49.6]]], None])
def test_a_path_that_says_nothing_yields_nothing(parts):
    """An empty or malformed path is missing, not zero."""
    assert distance_to_path_km(49.6, MIDDLE_LNG, parts or []) is None

# ---------------------------------------------------------------------------
# How a document is measured
# ---------------------------------------------------------------------------

def test_a_document_with_a_path_is_measured_as_a_line():
    doc = {"id": "osm:relation/1", "path_parts": LINE}
    assert distance_of(doc, 49.61, MIDDLE_LNG) == pytest.approx(1.11, abs=0.05)

def test_a_document_with_a_point_is_still_measured_as_a_point():
    doc = {"id": "osm:node/1", "lat": 49.61, "lng": 6.1}
    assert distance_of(doc, 49.6, 6.1) == pytest.approx(1.11, abs=0.05)

def test_a_path_wins_over_a_coordinate_when_both_are_present():
    """If a route ever acquires a representative point as well, the line is
    still the truthful answer."""
    doc = {"path_parts": LINE, "lat": 50.5, "lng": 6.1}
    assert distance_of(doc, 49.61, MIDDLE_LNG) == pytest.approx(1.11, abs=0.05)

def test_neither_is_not_zero():
    assert distance_of({"id": "x"}, 49.6, 6.1) is None
    assert distance_of({"lat": None, "lng": None}, 49.6, 6.1) is None

# ---------------------------------------------------------------------------
# The filter itself
# ---------------------------------------------------------------------------

def test_a_route_that_passes_close_is_inside_a_small_radius():
    route = {"id": "route", "path_parts": LINE}
    assert [d for d, _ in within_radius([route], 49.61, MIDDLE_LNG, 2.0)]

def test_the_same_route_is_outside_it_from_beyond_its_far_end():
    route = {"id": "route", "path_parts": LINE}
    assert within_radius([route], 49.6, 8.0, 2.0) == []

def test_routes_and_points_are_ranked_against_each_other_honestly():
    """A route passing 1.1 km away beats a playground 5 km away, and the list
    says so in order."""
    route = {"id": "route", "path_parts": LINE}
    playground = {"id": "play", "lat": 49.645, "lng": MIDDLE_LNG}   # ~5 km north
    ranked = within_radius([playground, route], 49.61, MIDDLE_LNG, 10.0)
    assert [doc["id"] for _, doc in ranked] == ["route", "play"]

def test_a_document_with_nothing_never_enters_the_list():
    assert within_radius([{"id": "nowhere"}], 49.6, MIDDLE_LNG, 100.0) == []
