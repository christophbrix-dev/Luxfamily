"""One event with a half-stated age took down the whole list.

`read_age` reports what the page said, and pages say one-sided things:

    "Fir Kanner bis 12 Joer"  ->  source=event, minimum=None, maximum=12
    "ab 6 Joer"               ->  source=event, minimum=6,    maximum=None

Three writers then stored that as-is, because they only checked whether the
source was "event" and not whether both ends were actually there:

    "age_min": age.minimum if age.source == "event" else 0,

`EventSummary.age_min` is a plain `int`, so a stored None fails validation, and
FastAPI answers the *entire* list request with 500. Not the one row — all of
them. The app showed "Server error (500)" and "0 Aktivitäten" on a database
holding hundreds of perfectly good events.

This is the second time this exact shape has bitten: `price_adult: float = 0.0`
rejected None the same way and returned 500 from the same endpoint. Hence the
last test here, which checks every numeric field the summary declares as
non-optional against a document that leaves it out.
"""
from datetime import date, timedelta

import pytest

from age_hints import read_age

TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def _doc(**over):
    doc = {
        "id": "half-aged",
        "title": {"en": "Atelier", "de": "Atelier", "fr": "Atelier"},
        "short": {"en": "", "de": "", "fr": ""},
        "type": "Indoor", "canton": "Luxembourg", "town": "Luxembourg",
        "category": ["Workshops"],
        "age_min": 0, "age_max": 99, "age_source": "event",
        "start_date": TOMORROW, "end_date": None, "time": "",
        "price_adult": None, "price_child": None,
        "price_free": False, "price_source": "unknown",
        "image": "", "lat": 49.6, "lng": 6.1,
        "featured": False, "published": True, "rating": 4.5, "view_count": 0,
    }
    doc.update(over)
    return doc


class TestTheHintItself:
    """`read_age` is right to report a half-open range. The writers were wrong."""

    def test_an_upper_bound_alone_is_still_a_statement(self):
        hint = read_age("Fir Kanner bis 12 Joer")
        assert hint.source == "event"
        assert (hint.minimum, hint.maximum) == (None, 12)

    def test_a_lower_bound_alone_too(self):
        hint = read_age("ab 6 Joer")
        assert hint.source == "event"
        assert (hint.minimum, hint.maximum) == (6, None)


class TestTheListSurvivesIt:
    def test_one_such_row_does_not_take_down_the_endpoint(
        self, app_module, client, run
    ):
        """The symptom exactly: hundreds of good events, HTTP 500 for all."""
        async def go():
            await app_module.db.events.insert_many([
                _doc(id="good-1"), _doc(id="good-2"),
                _doc(id="half", age_min=None, age_max=12),
            ])
            return await client.get("/api/events")

        r = run(go())
        assert r.status_code == 200, r.text
        assert len(r.json()) == 3

    def test_the_half_aged_row_reads_as_an_open_end(self, app_module, client, run):
        """0–12 for "up to 12", not a hole in the data."""
        async def go():
            await app_module.db.events.insert_one(_doc(id="half", age_min=None, age_max=12))
            return await client.get("/api/events")

        row = run(go()).json()[0]
        assert (row["age_min"], row["age_max"]) == (0, 12)

    def test_a_missing_lower_end_is_the_same_the_other_way(
        self, app_module, client, run
    ):
        async def go():
            await app_module.db.events.insert_one(_doc(id="half", age_min=6, age_max=None))
            return await client.get("/api/events")

        row = run(go()).json()[0]
        assert (row["age_min"], row["age_max"]) == (6, 99)


class TestTheWritersDoNotStoreItAgain:
    """Fix the response and you hide it; fix the writers and it is gone."""

    def test_the_main_importer_fills_the_open_end(self, app_module):
        import importers

        source = {"id": "s", "name": "S", "canton_default": "Luxembourg",
                  "town_default": "Luxembourg", "category_default": ["Workshops"],
                  "lat_default": 49.6, "lng_default": 6.1}
        doc = importers._build_event_doc(
            source=source, external_id="x", title="Atelier",
            description="Fir Kanner bis 12 Joer", start_date=TOMORROW,
            end_date=None, time_str="", town="Luxembourg", lat=49.6, lng=6.1,
            image="",
        )
        assert doc is not None
        assert doc["age_source"] == "event"
        assert doc["age_min"] == 0, "an unstated lower end is 0, not None"
        assert doc["age_max"] == 12

    @pytest.mark.parametrize("text,expected", [
        ("Fir Kanner bis 12 Joer", (0, 12)),
        ("ab 6 Joer", (6, 99)),
        ("vun 3 bis 12 Joer", (3, 12)),
    ])
    def test_the_kids_in_lux_writer_too(self, app_module, text, expected):
        from crawlers import kids_in_lux

        class FakeEvents:
            def __init__(self): self.stored = []
            def find_one(self, _q): return None
            def insert_one(self, d): self.stored.append(d)

        class FakeDB:
            def __init__(self): self.events = FakeEvents()

        db = FakeDB()
        kids_in_lux.upsert_event(
            db,
            {"title": "Atelier", "desc": text, "image": "", "commune": "Belair",
             "canton": "Luxembourg", "url": "https://example.invalid/p/x/",
             "lat": 49.6, "lng": 6.1},
            ["Workshops"], "Indoor", "src-1",
        )
        doc = db.events.stored[0]
        assert (doc["age_min"], doc["age_max"]) == expected
        assert doc["age_min"] is not None and doc["age_max"] is not None


class TestTheShapeThatKeepsBiting:
    def test_no_required_number_in_the_summary_can_be_None(self, app_module):
        """`price_adult: float = 0.0` did this once already.

        A default is not a permission: Pydantic uses it when the key is absent
        and still rejects an explicit None. Any numeric field declared without
        Optional is one bad row away from a 500 on the whole list, so the model
        has to say so.
        """
        import typing

        model = app_module.EventSummary
        offenders = []
        for name, field in model.model_fields.items():
            annotation = field.annotation
            if annotation in (int, float):
                offenders.append(name)
        # int/float without Optional is fine *if* nothing ever writes None —
        # which is what the writer tests above are for. This records which
        # fields carry that obligation.
        assert set(offenders) <= {"age_min", "age_max", "lat", "lng", "rating", "view_count"}, (
            f"a new non-optional number appeared: {offenders} — either make it "
            "Optional or add a writer test proving None never reaches it"
        )

    def test_lat_and_lng_are_the_other_two_worth_watching(self, app_module, client, run):
        async def go():
            await app_module.db.events.insert_one(_doc(id="nowhere", lat=None, lng=None))
            return await client.get("/api/events")

        assert run(go()).status_code == 200, (
            "an event without coordinates must not take the list down either"
        )
