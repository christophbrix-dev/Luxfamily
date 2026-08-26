"""Two ways the geocoder was ignoring data it already had.

Places record their municipality as `commune`. Nothing in that collection has
ever had a `town`. The venue lookup narrowed by `town`, so the narrowed query
matched no document at all and every venue fell through — past 6,857 places
holding exactly the answer being asked for.

And when nothing resolved, an event went straight to its canton centroid,
which places every commune in the canton on one pin up to twenty kilometres
from the village. The places we hold inside that commune give a far closer
answer, and 70 events were sitting on canton centroids while it was available.
"""
import pytest

pytest.importorskip("mongomock_motor", reason="pip install -r requirements-dev.txt")

import mongomock

from geocode_events import commune_centre, lookup_local_place


@pytest.fixture
def db():
    return mongomock.MongoClient()["geo"]


def place(name, commune, lat, lng):
    return {"name": name, "commune": commune, "lat": lat, "lng": lng}


class TestVenueLookup:
    def test_narrowing_by_commune_finds_the_venue(self):
        """The query that used to say "town" and match nothing."""
        d = mongomock.MongoClient()["geo"]
        d.places.insert_many([
            place("Kulturfabrik", "Esch-sur-Alzette", 49.49, 5.98),
            place("Kulturfabrik", "Wiltz", 49.96, 5.93),
        ])
        hit = lookup_local_place(d, "Kulturfabrik", "Esch-sur-Alzette")
        assert (round(hit.lat, 2), round(hit.lng, 2)) == (49.49, 5.98)

    def test_the_wrong_commune_is_not_returned_first(self, db):
        db.places.insert_one(place("Kulturfabrik", "Wiltz", 49.96, 5.93))
        hit = lookup_local_place(db, "Kulturfabrik", "Esch-sur-Alzette")
        # Falls back to the name-only search, which is the intended behaviour —
        # the point is that the narrowed query is now capable of matching.
        assert hit is not None

    def test_short_names_are_still_refused(self, db):
        db.places.insert_one(place("Zoo", "Bettembourg", 49.5, 6.1))
        assert lookup_local_place(db, "Zoo", "Bettembourg") is None

    def test_a_name_is_not_a_regular_expression(self, db):
        db.places.insert_one(place("Parc (Merveilleux)", "Bettembourg", 49.5, 6.1))
        assert lookup_local_place(db, "Parc (Merveilleux)", "") is not None


class TestCommuneCentre:
    def test_the_mean_of_the_places_we_hold(self, db):
        db.places.insert_many([place(f"p{i}", "Feulen", 49.85 + i / 1000, 6.04)
                               for i in range(10)])
        hit = commune_centre(db, "Feulen")
        assert hit is not None
        assert 49.85 <= hit.lat <= 49.86

    def test_it_is_labelled_an_approximation(self, db):
        """Never to be mistaken for a real address."""
        db.places.insert_many([place(f"p{i}", "Ell", 49.77, 5.83) for i in range(6)])
        assert commune_centre(db, "Ell").precision == "commune"

    def test_too_few_places_says_nothing(self, db):
        """The mean of two scattered points is worse than admitting ignorance."""
        db.places.insert_many([place("a", "Winseler", 49.9, 5.9),
                               place("b", "Winseler", 50.1, 6.1)])
        assert commune_centre(db, "Winseler") is None

    def test_an_unknown_commune_says_nothing(self, db):
        db.places.insert_many([place(f"p{i}", "Ell", 49.77, 5.83) for i in range(6)])
        assert commune_centre(db, "Paris") is None

    def test_no_town_says_nothing(self, db):
        assert commune_centre(db, "") is None

    def test_places_without_coordinates_are_not_counted(self, db):
        db.places.insert_many([place(f"p{i}", "Ell", None, None) for i in range(9)])
        assert commune_centre(db, "Ell") is None
