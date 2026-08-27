"""Re-reading age and price for events stored before the parsers existed.

This writes to live data, which is the reason it is tested rather than just
run once and eyeballed. Most events end up with less stated than before — that
is the intended direction, not a bug: 0–99 and 0.00 were never known, they
were defaults that read as "newborns welcome" and "free".
"""
import pytest

pytest.importorskip("mongomock_motor", reason="pip install -r requirements-dev.txt")

import backfill_age_price as backfill


@pytest.fixture
def db(monkeypatch):
    from mongomock_motor import AsyncMongoMockClient

    client = AsyncMongoMockClient()
    monkeypatch.setattr(backfill, "mongo_settings", lambda: ("mongodb://x", "b"))
    monkeypatch.setattr(backfill, "AsyncIOMotorClient", lambda _u: client)
    return client["b"]


def event(**over):
    doc = {
        "id": "e1",
        "title": {"de": "Kannerfest"},
        "description": {"de": "Am Park."},
        "age_min": 0, "age_max": 99,
        "price_adult": 0.0, "price_child": 0.0,
    }
    doc.update(over)
    return doc


class TestUnstatedBecomesUnknown:
    def test_the_default_age_stops_claiming_0_to_99(self, db, run):
        run(db.events.insert_one(event()))
        run(backfill.run(write=True))
        assert run(db.events.find_one({"id": "e1"}))["age_source"] == "unknown"

    def test_the_default_price_stops_claiming_free(self, db, run):
        run(db.events.insert_one(event()))
        run(backfill.run(write=True))
        stored = run(db.events.find_one({"id": "e1"}))
        assert stored["price_adult"] is None
        assert stored["price_free"] is False
        assert stored["price_source"] == "unknown"


class TestStatedIsRead:
    def test_an_age_in_the_text_is_kept(self, db, run):
        run(db.events.insert_one(event(description={"de": "Fir Kanner ab 6 Joer"})))
        run(backfill.run(write=True))
        stored = run(db.events.find_one({"id": "e1"}))
        assert stored["age_min"] == 6 and stored["age_source"] == "event"

    def test_free_entry_is_kept_as_free(self, db, run):
        run(db.events.insert_one(event(description={"de": "Eintritt frei"})))
        run(backfill.run(write=True))
        stored = run(db.events.find_one({"id": "e1"}))
        assert stored["price_free"] is True and stored["price_adult"] == 0.0

    def test_every_language_is_searched(self, db, run):
        """A French page may state the age the German one omits."""
        run(db.events.insert_one(event(description={"de": "Am Park.", "fr": "à partir de 8 ans"})))
        run(backfill.run(write=True))
        assert run(db.events.find_one({"id": "e1"}))["age_min"] == 8


class TestRunningItTwice:
    def test_the_second_run_changes_nothing(self, db, run):
        run(db.events.insert_one(event(description={"de": "Fir Kanner ab 6 Joer"})))
        run(backfill.run(write=True))
        assert run(backfill.run(write=False)) == 0

    def test_a_dry_run_writes_nothing(self, db, run):
        run(db.events.insert_one(event()))
        run(backfill.run(write=False))
        assert "price_source" not in run(db.events.find_one({"id": "e1"}))
