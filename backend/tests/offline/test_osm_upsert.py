# Writing the OSM ingest to MongoDB.
#
# The ingest produces around 8,000 places. Sent one at a time that is 8,000
# sequential round trips, each waiting for the last — so the test that matters
# here counts round trips, not just rows. Correctness alone would pass just as
# happily against the slow version.

import pytest


def make(n, start=0):
    return [
        {
            "id": f"node/{i}",
            "name": f"Spillplaz {i}",
            "kind": "playground",
            "group": "play",
            "lat": 49.6 + i / 10000,
            "lng": 6.1 + i / 10000,
            "family_score": 50,
            "updated_at": "2026-08-24T10:00:00+00:00",
        }
        for i in range(start, start + n)
    ]


class CountingCollection:
    """Wraps a mongomock collection and counts the calls that cross the wire."""

    def __init__(self, inner):
        self._inner = inner
        self.bulk_writes = 0
        self.update_ones = 0

    async def bulk_write(self, ops, **kw):
        self.bulk_writes += 1
        return await self._inner.bulk_write(ops, **kw)

    async def update_one(self, *a, **kw):
        self.update_ones += 1
        return await self._inner.update_one(*a, **kw)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class CountingDB:
    def __init__(self, db):
        self.places = CountingCollection(db.places)


@pytest.fixture
def osm(app_module):
    """The ingest module. Imported through app_module so sys.path is set up."""
    import osm_ingest

    return osm_ingest


@pytest.fixture
def counting(app_module):
    return CountingDB(app_module.db)


class TestItWrites:
    def test_every_record_lands(self, osm, counting, run):
        written, skipped = run(osm.upsert_places(counting, make(20)))
        assert (written, skipped) == (20, 0)
        assert run(counting.places.count_documents({})) == 20

    def test_fields_survive_the_round_trip(self, osm, counting, run):
        run(osm.upsert_places(counting, make(1)))
        doc = run(counting.places.find_one({"id": "node/0"}))
        assert doc["name"] == "Spillplaz 0"
        assert doc["kind"] == "playground"
        assert doc["created_at"] == "2026-08-24T10:00:00+00:00"

    def test_rerunning_the_same_ingest_writes_nothing_new(self, osm, counting, run):
        run(osm.upsert_places(counting, make(10)))
        written, skipped = run(osm.upsert_places(counting, make(10)))
        assert (written, skipped) == (0, 10)
        assert run(counting.places.count_documents({})) == 10

    def test_a_changed_place_is_updated_not_duplicated(self, osm, counting, run):
        run(osm.upsert_places(counting, make(3)))
        changed = make(3)
        changed[1]["name"] = "Spillplaz mat Rutsch"
        written, skipped = run(osm.upsert_places(counting, changed))
        assert (written, skipped) == (1, 2)
        assert run(counting.places.count_documents({})) == 3
        doc = run(counting.places.find_one({"id": "node/1"}))
        assert doc["name"] == "Spillplaz mat Rutsch"

    def test_created_at_is_not_overwritten_on_reimport(self, osm, counting, run):
        run(osm.upsert_places(counting, make(1)))
        later = make(1)
        later[0]["updated_at"] = "2026-12-01T00:00:00+00:00"
        run(osm.upsert_places(counting, later))
        doc = run(counting.places.find_one({"id": "node/0"}))
        assert doc["created_at"] == "2026-08-24T10:00:00+00:00"
        assert doc["updated_at"] == "2026-12-01T00:00:00+00:00"


class TestItDoesNotGoOneAtATime:
    """The point of the change. Without this, a revert passes unnoticed."""

    def test_one_round_trip_for_a_small_batch(self, osm, counting, run):
        run(osm.upsert_places(counting, make(200)))
        assert counting.places.bulk_writes == 1
        assert counting.places.update_ones == 0

    def test_a_large_ingest_costs_round_trips_in_the_dozens(self, osm, counting, run):
        # The real ingest is 8,138 places, which the in-memory MongoDB takes
        # half a minute to chew through — too slow to pay for on every push.
        # 2,500 makes the same point: the call count scales with chunks, not
        # with rows. At the real size this is 17 round trips instead of 8,138.
        run(osm.upsert_places(counting, make(2500)))
        assert counting.places.update_ones == 0
        assert counting.places.bulk_writes == 5
        assert run(counting.places.count_documents({})) == 2500

    def test_chunks_stay_under_the_command_limit(self, osm, counting, run):
        # MongoDB caps a single command at 16 MB; the chunk size is what keeps
        # a tag-laden ingest under it.
        assert osm.BULK_CHUNK <= 1000
        run(osm.upsert_places(counting, make(osm.BULK_CHUNK + 1)))
        assert counting.places.bulk_writes == 2


class TestFailureIsSurvivable:
    def test_a_broken_batch_is_counted_not_raised(self, osm, counting, run):
        """A partial import beats no import — and beats a crashed job."""

        async def boom(ops, **kw):
            raise RuntimeError("connection reset")

        counting.places.bulk_write = boom
        written, skipped = run(osm.upsert_places(counting, make(30)))
        assert (written, skipped) == (0, 30)

    def test_an_empty_batch_does_nothing_quietly(self, osm, counting, run):
        assert run(osm.upsert_places(counting, [])) == (0, 0)
        assert counting.places.bulk_writes == 0
