"""The two hand-written crawlers were making the claims we removed everywhere.

Age and price were taken out of every importer a week ago, because "0–99" in a
family app reads as "newborns welcome" and a zero in a price field reads as
"free" — and neither was ever read off the page. That work went through
`_build_event_doc`, which these two crawlers do not use. They assemble their
own document, so they kept the constants.

kids-in-lux stored every playground as ages 0–99, 0.00 €, "Gratis". The last
one is not merely unknown but wrong for a third of what the source imports:
the indoor playgrounds charge admission. visitluxembourg was narrower still —
every Discovery Tour was stored as being for ages 4 to 12, whatever it is.

Nothing caught it because both crawlers were broken in a different way at the
time (see test_crawl_budget_and_dates.py) and had never stored a single row.
"""
import pytest


class FakeEvents:
    def __init__(self):
        self.stored = []

    def find_one(self, _query):
        return None

    def insert_one(self, doc):
        self.stored.append(doc)


class FakeDB:
    def __init__(self):
        self.events = FakeEvents()


@pytest.fixture
def kids(app_module):
    from crawlers import kids_in_lux

    return kids_in_lux


@pytest.fixture
def visit(app_module):
    from crawlers import visit_luxembourg

    return visit_luxembourg


def _parsed(title="Spillplaz Belair", desc=""):
    return {
        "title": title, "desc": desc, "image": "", "commune": "Belair",
        "canton": "Luxembourg", "url": "https://example.invalid/p/belair/",
        "lat": 49.6, "lng": 6.1,
    }


class TestKidsInLux:
    def _store(self, kids, **kw):
        db = FakeDB()
        kids.upsert_event(db, _parsed(**kw), ["Playgrounds"], "Outdoor", "src-1")
        return db.events.stored[0]

    def test_an_unstated_price_is_not_free(self, kids):
        doc = self._store(kids)
        assert doc["price_adult"] is None
        assert doc["price_free"] is False
        assert doc["price_source"] == "unknown"

    def test_the_label_says_so_in_words(self, kids):
        doc = self._store(kids)
        assert doc["price_label"]["de"] == "Price not stated"

    def test_an_unstated_age_is_marked_unknown(self, kids):
        doc = self._store(kids)
        assert doc["age_source"] == "unknown"

    def test_a_stated_price_is_read(self, kids):
        doc = self._store(kids, desc="Andrang: 8 € pro Persoun.")
        assert doc["price_source"] == "event"
        assert doc["price_adult"] == 8.0

    def test_a_stated_age_is_read(self, kids):
        doc = self._store(kids, desc="Fir Kanner vun 3 bis 12 Joer.")
        assert doc["age_source"] == "event"
        assert (doc["age_min"], doc["age_max"]) == (3, 12)

    def test_free_is_still_free_when_the_page_says_it(self, kids):
        doc = self._store(kids, desc="Entrée gratuite pour tous.")
        assert doc["price_free"] is True
        assert doc["price_label"]["fr"] == "Free entry"


class TestVisitLuxembourg:
    def _store(self, visit, desc=""):
        db = FakeDB()
        visit.upsert_event(db, _parsed(title="Discovery Tour", desc=desc), "src-2")
        return db.events.stored[0]

    def test_it_no_longer_declares_every_tour_a_4_to_12(self, visit):
        doc = self._store(visit)
        assert doc["age_source"] == "unknown"

    def test_an_unstated_price_is_not_free(self, visit):
        doc = self._store(visit)
        assert doc["price_adult"] is None
        assert doc["price_free"] is False


class TestBoth:
    """Whatever they write has to survive the API's response model.

    A previous round of this shipped `price_adult: float = 0.0`, and the first
    document carrying None turned every event request into an HTTP 500.
    """

    def test_the_stored_shape_matches_what_the_api_promises(self, kids, app_module):
        db = FakeDB()
        kids.upsert_event(db, _parsed(), ["Playgrounds"], "Outdoor", "src-1")
        doc = db.events.stored[0]

        fields = app_module.EventBase.model_fields
        for name in ("price_adult", "price_free", "price_source", "age_source"):
            assert name in fields, f"{name} is written but the API drops it"
        app_module.EventBase(**doc)
