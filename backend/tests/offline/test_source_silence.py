# A source that stops working without failing.
#
# run_source recorded "ok" whenever the importer returned without raising, so a
# commune that redesigned its calendar — the page still loads, the markup no
# longer matches — showed a green tick and "0 imported" in the admin console.
# That is exactly what a quiet week looks like. The difference is whether
# anything was parsed at all.

import pytest


@pytest.fixture
def importers(app_module):
    import importers as mod

    return mod


@pytest.fixture
def db(app_module):
    return app_module.db


BASE = {
    "id": "src-quiet", "name": "Gemeng Iergendwou", "kind": "ical", "active": True,
    "url": "https://example.invalid/feed.ics",
    "canton_default": "Luxembourg", "town_default": "Luxembourg",
    "category_default": ["Culture"], "lat_default": 49.6, "lng_default": 6.1,
}


@pytest.fixture
def stub(importers, monkeypatch):
    """Replace the importer with one returning whatever a test asks for."""
    def yielding(inserted, skipped):
        async def fake(source, db):
            return inserted, skipped
        monkeypatch.setitem(importers.IMPORTERS, "ical", fake)
    return yielding


def run_once(importers, db, run, source=None):
    async def call():
        src = dict(source or BASE)
        await db.sources.replace_one({"id": src["id"]}, src, upsert=True)
        await importers.run_source(src, db)
        return await db.sources.find_one({"id": src["id"]}, {"_id": 0})
    return run(call())


class TestSomethingWasParsed:
    def test_events_imported_is_ok(self, importers, db, run, stub):
        stub(5, 0)
        assert run_once(importers, db, run)["last_status"] == "ok"

    def test_everything_skipped_is_still_ok(self, importers, db, run, stub):
        """A page full of last month's events parsed fine. Nothing is wrong."""
        stub(0, 12)
        row = run_once(importers, db, run)
        assert row["last_status"] == "ok"
        assert row["last_seen_count"] == 12


class TestNothingWasParsed:
    def test_it_is_not_reported_as_ok(self, importers, db, run, stub):
        stub(0, 0)
        assert run_once(importers, db, run)["last_status"] == "no_events"

    def test_the_run_is_counted(self, importers, db, run, stub):
        stub(0, 0)
        assert run_once(importers, db, run)["empty_runs"] == 1

    def test_consecutive_runs_accumulate(self, importers, db, run, stub):
        stub(0, 0)
        src = dict(BASE)
        for expected in (1, 2, 3):
            row = run_once(importers, db, run, src)
            assert row["empty_runs"] == expected
            src = row

    def test_one_event_clears_the_streak(self, importers, db, run, stub):
        """A site that was merely down for a day must not stay flagged."""
        stub(0, 0)
        src = run_once(importers, db, run, dict(BASE))
        src = run_once(importers, db, run, src)
        assert src["empty_runs"] == 2

        stub(1, 0)
        row = run_once(importers, db, run, src)
        assert row["empty_runs"] == 0
        assert row["last_status"] == "ok"


class TestFailuresAreStillFailures:
    def test_an_exception_is_an_error_not_silence(self, importers, db, run, monkeypatch):
        async def boom(source, db):
            raise RuntimeError("connection reset")
        monkeypatch.setitem(importers.IMPORTERS, "ical", boom)
        row = run_once(importers, db, run)
        assert row["last_status"] == "error"
        assert "connection reset" in row["last_error"]

    def test_robots_refusal_keeps_its_own_status(self, importers, db, run, monkeypatch):
        async def blocked(source, db):
            raise importers.RobotsBlocked("robots.txt disallows this")
        monkeypatch.setitem(importers.IMPORTERS, "ical", blocked)
        assert run_once(importers, db, run)["last_status"] == "blocked_by_robots"


class TestTheThreshold:
    def test_it_is_about_a_day_of_runs(self, importers):
        """The importer runs three times a day; one bad afternoon is not news."""
        assert 2 <= importers.EMPTY_RUNS_BEFORE_WARNING <= 6
