# "Near me" has to mean near me.
#
# /api/places already took near_lat, near_lng and radius_km, and not one of the
# three did what its name said. Measured against the 7,856 places we hold, asked
# from the Gare in Luxembourg City with radius_km=10:
#
#   * 1,654 places sat inside the filter and 200 came back, ordered by
#     family_score. A playground 200 m away (score 79) lost to a park 10 km away
#     (score 100). Nearness reached the filter and never reached the ordering,
#     so "near me" answered with the best-scored places in the region.
#   * 14 of those 200 were further away than the 10 km asked for, the worst
#     13.2 km. The filter was a square, and a square's corner is 41 % further
#     from the centre than its edge.
#
# Both are tested here against a seeded collection where every distance is known
# in advance, so a regression fails rather than merely looking plausible.

import math

import pytest

from geo import bounding_box, haversine_km, within_radius

# Luxembourg City, Gare. Every seeded coordinate below is placed relative to it.
ME = (49.6000, 6.1333)


def at_offset(km_north: float, km_east: float) -> tuple:
    """A coordinate a given number of kilometres from ME.

    East uses cos(latitude): at 49.6° a degree of longitude is 72 km, not 111.
    Getting this wrong in the fixture would hide exactly the bug being tested.
    """
    lat = ME[0] + km_north / 111.0
    lng = ME[1] + km_east / (111.0 * math.cos(math.radians(ME[0])))
    return lat, lng


# ---------------------------------------------------------------------------
# The measurement itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, a, b", [
    ("Luxembourg City to Esch-sur-Alzette", (49.6116, 6.1319), (49.4958, 5.9806)),
    ("Luxembourg City to Ettelbruck", (49.6116, 6.1319), (49.8476, 6.1039)),
    ("Luxembourg City to Vianden", (49.6116, 6.1319), (49.9347, 6.2064)),
    ("one degree of longitude at the equator", (0.0, 0.0), (0.0, 1.0)),
    ("one degree of latitude", (0.0, 0.0), (1.0, 0.0)),
])
def test_haversine_agrees_with_an_independent_formula(name, a, b):
    """Checked against the spherical law of cosines, not against a guess.

    Writing this test the first time with a remembered "about 15 km" for
    Esch failed — the answer is 16.9 km and the code was right. A second
    formula on the same sphere is a real check; a half-recalled number is not.
    """
    def law_of_cosines(lat1, lng1, lat2, lng2):
        p = math.pi / 180
        return 6371.0 * math.acos(
            math.sin(lat1 * p) * math.sin(lat2 * p)
            + math.cos(lat1 * p) * math.cos(lat2 * p) * math.cos((lng2 - lng1) * p)
        )

    assert haversine_km(*a, *b) == pytest.approx(law_of_cosines(*a, *b), abs=0.001)


def test_a_degree_is_the_length_everybody_quotes():
    """111 km, the constant the bounding box is built from."""
    assert haversine_km(0.0, 0.0, 1.0, 0.0) == pytest.approx(111.19, abs=0.01)


def test_a_point_is_no_distance_from_itself():
    assert haversine_km(*ME, *ME) == pytest.approx(0.0, abs=1e-9)


def test_the_offset_helper_is_itself_correct():
    # If this drifts, every fixture below is measuring something else.
    assert haversine_km(*ME, *at_offset(10, 0)) == pytest.approx(10.0, abs=0.05)
    assert haversine_km(*ME, *at_offset(0, 10)) == pytest.approx(10.0, abs=0.05)


def test_the_box_encloses_the_circle_rather_than_clipping_it():
    """A superset, never a subset.

    A box that was too small would silently hide places that really are in
    range — the harder bug to notice, because the list still looks full.
    """
    box = bounding_box(*ME, 10.0)
    for bearing in range(0, 360, 5):
        rad = math.radians(bearing)
        point = at_offset(10.0 * math.cos(rad), 10.0 * math.sin(rad))
        assert box["lat"]["$gte"] <= point[0] <= box["lat"]["$lte"], bearing
        assert box["lng"]["$gte"] <= point[1] <= box["lng"]["$lte"], bearing


def test_the_box_alone_is_not_good_enough():
    """The corner of the box, which is what used to come back as "within 10 km"."""
    corner = at_offset(10.0, 10.0)
    box = bounding_box(*ME, 10.0)
    assert box["lat"]["$gte"] <= corner[0] <= box["lat"]["$lte"]
    assert box["lng"]["$gte"] <= corner[1] <= box["lng"]["$lte"]
    assert haversine_km(*ME, *corner) > 14.0          # in the box
    assert within_radius([{"lat": corner[0], "lng": corner[1]}], *ME, 10.0) == []


@pytest.mark.parametrize("doc", [
    {},                                  # nothing at all
    {"lat": 49.6},                       # half a position
    {"lat": None, "lng": None},          # written, never filled
    {"lat": 0, "lng": 0},                # Null Island, in the Atlantic
    {"lat": "49.6", "lng": "6.1"},       # a number-shaped string
    {"lat": True, "lng": True},          # bool is an int in Python
])
def test_a_place_without_a_position_is_dropped_not_placed_at_your_feet(doc):
    """911 of our 7,856 places (11.6 %) have no usable coordinates.

    Reading a missing value as 0/0 would put them 5,400 km away in the
    Atlantic; reading it as "here" would make them the first thing on screen.
    Neither is true, so they are left out of a question about distance.
    """
    assert within_radius([doc], *ME, 50.0) == []


# ---------------------------------------------------------------------------
# Places: nearest first
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_places(app_module, run):
    """Four places whose distance and score deliberately disagree.

    `near` is the real-world case: the playground around the corner that the
    old ordering buried under a better-scored park half an hour's drive away.
    """
    places = [
        # id,          km north, km east, score
        ("node/near",       0.2,     0.0, 40),
        ("node/middle",     5.0,     0.0, 60),
        ("node/far",        9.5,     0.0, 100),
        ("node/corner",    10.0,    10.0, 100),   # in the box, 14.1 km away
        ("node/outside",   40.0,     0.0, 100),   # in neither
    ]

    async def fill():
        await app_module.db.places.delete_many({})
        await app_module.db.places.insert_many([
            {
                "id": pid,
                "name": pid.split("/")[1],
                "kind": "playground",
                "group": "play",
                "lat": at_offset(north, east)[0],
                "lng": at_offset(north, east)[1],
                "family_score": score,
                "tags_raw": {"leisure": "playground"},
            }
            for pid, north, east, score in places
        ])
        # One with no position at all, to prove it does not sneak in.
        await app_module.db.places.insert_one({
            "id": "node/nowhere", "name": "Nowhere", "kind": "playground",
            "group": "play", "lat": None, "lng": None, "family_score": 100,
        })
    run(fill())
    return app_module


def fetch(client, run, *queries):
    async def call():
        async with client as c:
            return [await c.get(q) for q in queries]
    return run(call())


def ids(res):
    return [row["id"] for row in res.json()]


def test_without_a_position_the_old_order_is_untouched(seeded_places, client, run):
    """A caller who did not ask about distance must not get a changed answer."""
    res, = fetch(client, run, "/api/places?limit=10")
    scores = [row["family_score"] for row in res.json()]
    assert scores == sorted(scores, reverse=True)
    assert "node/nowhere" in ids(res)          # still listed when nobody asked
    assert all("distance_km" not in row for row in res.json())


def test_the_nearest_really_is_first(seeded_places, client, run):
    res, = fetch(client, run, f"/api/places?near_lat={ME[0]}&near_lng={ME[1]}&radius_km=10")
    assert ids(res) == ["node/near", "node/middle", "node/far"]


def test_a_low_score_next_door_beats_a_perfect_score_ten_kilometres_away(
    seeded_places, client, run,
):
    """The exact inversion found in the live data.

    node/near scores 40 and is 200 m away; node/far scores 100 and is 9.5 km
    away. The old ordering put node/far first.
    """
    res, = fetch(client, run, f"/api/places?near_lat={ME[0]}&near_lng={ME[1]}&radius_km=10")
    rows = res.json()
    assert rows[0]["id"] == "node/near"
    assert rows[0]["family_score"] < rows[-1]["family_score"]


def test_the_corner_of_the_box_is_not_within_the_radius(seeded_places, client, run):
    # Both requests in one fetch: the client fixture is handed over un-entered
    # and a closed httpx client cannot be reopened.
    tight, wide = fetch(
        client, run,
        f"/api/places?near_lat={ME[0]}&near_lng={ME[1]}&radius_km=10",
        f"/api/places?near_lat={ME[0]}&near_lng={ME[1]}&radius_km=20",
    )
    assert "node/corner" not in ids(tight)
    assert "node/corner" in ids(wide)       # reachable once the radius covers it


def test_a_place_with_no_coordinates_is_not_near_anything(seeded_places, client, run):
    res, = fetch(client, run, f"/api/places?near_lat={ME[0]}&near_lng={ME[1]}&radius_km=100")
    assert "node/nowhere" not in ids(res)


def test_each_row_carries_the_distance_it_was_ranked_by(seeded_places, client, run):
    """The app shows this number; it must be the one the server sorted on.

    Recomputing it in the app from lat/lng would usually agree — and "usually"
    is how a list ends up ordered by one number and labelled with another.
    """
    res, = fetch(client, run, f"/api/places?near_lat={ME[0]}&near_lng={ME[1]}&radius_km=10")
    rows = res.json()
    assert [row["distance_km"] for row in rows] == sorted(row["distance_km"] for row in rows)
    for row in rows:
        assert row["distance_km"] == pytest.approx(
            round(haversine_km(*ME, row["lat"], row["lng"]), 1), abs=0.05
        )


def test_the_total_counts_the_circle_and_not_the_box(seeded_places, client, run):
    """Paging against the box's count would promise rows the circle removed."""
    res, = fetch(client, run, f"/api/places?near_lat={ME[0]}&near_lng={ME[1]}&radius_km=10&limit=1")
    assert res.headers["X-Total-Count"] == "3"
    assert len(res.json()) == 1


def test_paging_a_nearby_list_neither_repeats_nor_drops(seeded_places, client, run):
    first, second, third = fetch(
        client, run,
        *[f"/api/places?near_lat={ME[0]}&near_lng={ME[1]}&radius_km=10&limit=1&skip={n}"
          for n in (0, 1, 2)],
    )
    assert ids(first) + ids(second) + ids(third) == [
        "node/near", "node/middle", "node/far",
    ]


def test_half_a_position_is_no_position(seeded_places, client, run):
    """A latitude without a longitude must not quietly filter by nothing."""
    res, = fetch(client, run, f"/api/places?near_lat={ME[0]}&radius_km=10")
    assert "node/outside" in ids(res)      # unfiltered, as if near were absent


def test_an_absurd_radius_is_refused_rather_than_scanning_everything(
    seeded_places, client, run,
):
    res, = fetch(client, run, f"/api/places?near_lat={ME[0]}&near_lng={ME[1]}&radius_km=99999")
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Events: nearness narrows, the date still leads
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_events(app_module, run):
    """Three events where date order and distance order are opposites.

    Sorting an agenda by distance would put the concert in December two streets
    away above the village fete tomorrow. That is the mistake this fixture is
    built to catch.
    """
    events = [
        # id,        days out, km north
        ("far-soon",        1,     9.0),
        ("near-later",     90,     0.3),
        ("outside",         2,    60.0),
    ]

    async def fill():
        from datetime import date, timedelta
        await app_module.db.events.delete_many({})
        await app_module.db.events.insert_many([
            {
                "id": eid,
                "title": {"en": eid, "de": eid, "fr": eid},
                "short": {"en": "", "de": "", "fr": ""},
                "type": "Event",
                "canton": "Luxembourg",
                "town": "Luxembourg",
                "category": ["Culture"],
                "age_min": 0, "age_max": 99,
                "start_date": (date.today() + timedelta(days=days)).isoformat(),
                "time": "10:00",
                "price_adult": None, "price_child": None,
                "price_label": {"en": "", "de": "", "fr": ""},
                "image": "",
                "lat": at_offset(north, 0.0)[0],
                "lng": at_offset(north, 0.0)[1],
                "published": True, "featured": False,
                "rating": 0, "view_count": 0,
                "accessibility_wheelchair": False,
                "sensory_friendly": False,
                "free_parking": False,
            }
            for eid, days, north in events
        ])
    run(fill())
    return app_module


def test_a_position_narrows_the_event_list(seeded_events, client, run):
    res, = fetch(client, run, f"/api/events?near_lat={ME[0]}&near_lng={ME[1]}&radius_km=10")
    assert ids(res) == ["far-soon", "near-later"]


def test_the_date_still_leads_when_a_position_is_given(seeded_events, client, run):
    """far-soon is 9 km away and tomorrow; near-later is 300 m away and in
    three months. Tomorrow wins."""
    res, = fetch(client, run, f"/api/events?near_lat={ME[0]}&near_lng={ME[1]}&radius_km=10")
    dates = [row["start_date"] for row in res.json()]
    assert dates == sorted(dates)
    assert ids(res)[0] == "far-soon"


def test_the_event_total_counts_the_circle(seeded_events, client, run):
    res, = fetch(client, run, f"/api/events?near_lat={ME[0]}&near_lng={ME[1]}&radius_km=10&limit=1")
    assert res.headers["X-Total-Count"] == "2"


def test_nearness_combines_with_the_other_filters(seeded_events, client, run):
    """The radius must narrow what the category left, not replace it."""
    res, = fetch(
        client, run,
        f"/api/events?near_lat={ME[0]}&near_lng={ME[1]}&radius_km=10&category=Nature",
    )
    assert ids(res) == []


def test_without_a_position_every_event_is_still_offered(seeded_events, client, run):
    res, = fetch(client, run, "/api/events")
    assert set(ids(res)) == {"far-soon", "near-later", "outside"}
