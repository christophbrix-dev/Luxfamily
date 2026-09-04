# Which events the geocoder picks up, and when it runs.
#
# geocode_events.py looked for lat == 0, a missing lat or a null one. No
# imported event has any of those: every importer writes the source's
# lat_default. So the query matched nothing, the script printed "0 events to
# geocode" and stopped — and 122 of 304 events sat on 49.6117, 6.1319, the
# generic point for Luxembourg City, with 92% of all events sharing a
# coordinate with another. On a map that is a handful of pins where there
# should be hundreds.
#
# The selection is checked by handing it to the database rather than by
# re-implementing it here: a test that reasons about the query separately can
# agree with itself while disagreeing with Mongo.

import pytest

from geocode_events import pending_query, SCHEDULED_BATCH


@pytest.fixture
def importers(app_module):
    import importers as mod

    return mod


@pytest.fixture
def picked(app_module, run):
    """Whether the database itself would select this event."""
    def check(event):
        async def call():
            await app_module.db.events.delete_many({})
            await app_module.db.events.insert_one({"id": "e1", **event})
            return await app_module.db.events.find_one(pending_query())
        return run(call()) is not None
    return check


def imported_event(importers):
    """Exactly what an importer stores, so the test cannot drift from it."""
    return importers._build_event_doc(
        source={"id": "s1", "name": "T", "lat_default": 49.6117, "lng_default": 6.1319},
        external_id="x", title="Fest", description="",
        start_date="2026-09-01", end_date=None, time_str="",
        town="Mamer", lat=49.6117, lng=6.1319,
    )


class TestImportedEventsArePickedUp:
    def test_the_shape_an_importer_writes(self, picked, importers):
        """The case that was missed: a real coordinate, from the source."""
        assert picked(imported_event(importers))

    def test_a_commune_centroid(self, picked):
        assert picked({"lat": 49.5, "lng": 6.0, "geocode_precision": "commune"})

    def test_a_canton_centroid(self, picked):
        assert picked({"lat": 49.5, "lng": 6.0, "geocode_precision": "canton"})

    def test_an_event_never_geocoded(self, picked):
        assert picked({"lat": 49.5, "lng": 6.0})

    def test_the_original_cases_still_work(self, picked):
        assert picked({"lat": 0, "lng": 0})
        assert picked({"lat": None, "lng": None})
        assert picked({})


class TestGoodCoordinatesAreLeftAlone:
    def test_an_exact_address(self, picked):
        assert not picked({"lat": 49.61, "lng": 6.13, "geocode_precision": "exact"})

    def test_a_matched_venue(self, picked):
        assert not picked({"lat": 49.61, "lng": 6.13, "geocode_precision": "place"})


class TestImportersSayWhereTheCoordinateCameFrom:
    def test_the_event_document_records_it(self, importers):
        assert imported_event(importers)["geocode_precision"] == "source_default"

    def test_the_two_files_agree(self, importers, picked):
        """The importer writes it, the geocoder looks for it, and they live in
        different files — drifting apart is what caused this."""
        assert picked(imported_event(importers))


class TestItRunsAfterEveryImport:
    def test_the_scheduled_job_geocodes(self):
        """Left as a manual script it was never run at all."""
        import inspect

        import server
        src = inspect.getsource(server._run_importers_once)
        assert "geocode_pending" in src
        # After the crawl: geocoding has nothing to do until something arrives.
        assert src.index("run_all_active") < src.index("geocode_pending")

    def test_it_holds_the_same_lease_as_the_import(self):
        """Two workers must not resolve the same events at once."""
        import inspect

        import server
        src = inspect.getsource(server._run_importers_once)
        assert src.index("_acquire_importer_lease") < src.index("geocode_pending")
        assert src.index("geocode_pending") < src.index("_release_importer_lease")


class TestTheScheduledBatch:
    def test_it_is_capped(self):
        """Each unresolved event may cost a request to somebody else's service."""
        assert 0 < SCHEDULED_BATCH <= 500

    def test_three_passes_a_day_clear_a_backlog_in_days_not_months(self):
        assert SCHEDULED_BATCH * 3 >= 300


class TestRetryCooldown:
    """Imprecise results are retried — but not on every single run.

    "canton" and "commune" stay in the pending set on purpose: a later pass may
    do better once a town spelling is corrected or new places are ingested.
    With no cooldown, "later" meant "every run": four consecutive passes each
    re-resolved the same 69 events and each re-asked the geoportal the same
    questions that had never worked once.
    """

    def _match(self, doc):
        import mongomock
        db = mongomock.MongoClient()["g"]
        db.events.insert_one(doc)
        return db.events.find_one(pending_query()) is not None

    def test_a_never_attempted_event_is_pending(self):
        assert self._match({"lat": 0, "geocode_precision": "source_default"})

    def test_a_fresh_canton_result_waits(self):
        from datetime import datetime, timezone
        assert not self._match({
            "lat": 49.6, "geocode_precision": "canton",
            "geocoded_at": datetime.now(timezone.utc).isoformat(),
        })

    def test_a_fresh_commune_result_waits(self):
        from datetime import datetime, timezone
        assert not self._match({
            "lat": 49.6, "geocode_precision": "commune",
            "geocoded_at": datetime.now(timezone.utc).isoformat(),
        })

    def test_an_old_canton_result_is_retried(self):
        from datetime import datetime, timedelta, timezone
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        assert self._match({"lat": 49.6, "geocode_precision": "canton", "geocoded_at": old})

    def test_a_precise_result_is_never_pending(self):
        """Not even after the cooldown — there is nothing better to find."""
        from datetime import datetime, timedelta, timezone
        old = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        assert not self._match({
            "lat": 49.6, "geocode_precision": "address", "geocoded_at": old,
        })
