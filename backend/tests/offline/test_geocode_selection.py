# Which events the geocoder picks up.
#
# geocode_events.py looked for lat == 0, a missing lat or a null one. No
# imported event has any of those: every importer writes the source's
# lat_default. So the query matched nothing, the script printed "0 events to
# geocode" and stopped — and 122 of 304 events sat on 49.6117, 6.1319, the
# generic point for Luxembourg City, with 92% of all events sharing a
# coordinate with another. On a map that is a handful of pins where there
# should be hundreds.

import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]


def selection_clause():
    """The $or list geocode_events.main() selects with."""
    src = (BACKEND / "geocode_events.py").read_text(encoding="utf-8")
    block = src.split("todo = list(db.events.find(", 1)[1].split("))", 1)[0]
    return block


def matches(clause, event):
    """Whether this event would be picked up. A small stand-in for Mongo."""
    if '{"lat": 0}' in clause and event.get("lat") == 0:
        return True
    if '{"lat": {"$exists": False}}' in clause and "lat" not in event:
        return True
    if '{"lat": None}' in clause and event.get("lat") is None:
        return True
    if '"geocode_precision": {"$exists": False}' in clause and "geocode_precision" not in event:
        return True
    m = re.search(r'"geocode_precision": \{"\$in": \[([^\]]*)\]\}', clause)
    if m:
        wanted = {v.strip().strip('"') for v in m.group(1).split(",")}
        wanted.discard("None")
        if event.get("geocode_precision") in wanted:
            return True
        if None in {None} and event.get("geocode_precision") is None and "None" in m.group(1):
            return True
    return False


@pytest.fixture
def clause():
    return selection_clause()


class TestImportedEventsArePickedUp:
    def test_the_shape_an_importer_writes(self, clause):
        """The case that was missed: a real coordinate, from the source."""
        assert matches(clause, {
            "lat": 49.6117, "lng": 6.1319,
            "geocode_precision": "source_default",
        })

    def test_a_commune_centroid(self, clause):
        assert matches(clause, {"lat": 49.5, "lng": 6.0, "geocode_precision": "commune"})

    def test_a_canton_centroid(self, clause):
        assert matches(clause, {"lat": 49.5, "lng": 6.0, "geocode_precision": "canton"})

    def test_an_event_never_geocoded(self, clause):
        assert matches(clause, {"lat": 49.5, "lng": 6.0})

    def test_the_old_cases_still_work(self, clause):
        assert matches(clause, {"lat": 0})
        assert matches(clause, {"lat": None})
        assert matches(clause, {})


class TestGoodCoordinatesAreLeftAlone:
    def test_an_exact_address(self, clause):
        assert not matches(clause, {"lat": 49.61, "lng": 6.13, "geocode_precision": "exact"})

    def test_a_matched_venue(self, clause):
        assert not matches(clause, {"lat": 49.61, "lng": 6.13, "geocode_precision": "place"})


class TestImportersSayWhereTheCoordinateCameFrom:
    def test_the_event_document_records_it(self, importers):
        doc = importers._build_event_doc(
            source={"id": "s1", "name": "T", "lat_default": 49.6, "lng_default": 6.1},
            external_id="x", title="Fest", description="",
            start_date="2026-09-01", end_date=None, time_str="",
            town="Mamer", lat=49.6, lng=6.1,
        )
        assert doc["geocode_precision"] == "source_default"

    def test_that_value_is_one_the_geocoder_looks_for(self, importers, clause):
        """The two must agree, or imported events go unnoticed again."""
        assert matches(clause, {"lat": 49.6, "geocode_precision": "source_default"})


@pytest.fixture
def importers(app_module):
    import importers as mod

    return mod
