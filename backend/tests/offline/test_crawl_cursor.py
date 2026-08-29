"""A crawler that reports perfect health and walks in a circle.

Emergent's fifth report had this line, and read it as good news:

    Kids in Luxemburg – Spielplätze: 42 listed, 15 visited
        → 0 new, 15 refreshed, 0 unreadable, 0 refused

Nothing unreadable, nothing refused, everything refreshed. But the fetch budget
cuts a long list short, and the list arrives in the same order every time: the
first 15 pages were being crawled three times a day forever, and pages 16 to 42
had never been fetched once. "0 new" was not a quiet week at the source — it
was a crawler that could not reach the rest of its own list.

Rotating by a stored offset turns the same budget into full coverage. 42 pages,
15 a run, three runs a day is everything inside a day.
"""
import mongomock
import pytest

from importers import _rotate_to_cursor, _save_cursor

SOURCE = {"id": "kil-1", "name": "Kids in Lux – Spielplätze"}
PAGES = [f"p{i}" for i in range(42)]


@pytest.fixture
def db():
    d = mongomock.MongoClient()["test"]
    d.sources.insert_one(dict(SOURCE))
    return d


class TestRotating:
    def test_a_fresh_source_starts_at_the_beginning(self):
        rotated, cursor = _rotate_to_cursor(None, SOURCE, PAGES)
        assert cursor == 0
        assert rotated == PAGES

    def test_it_resumes_where_the_last_run_stopped(self):
        rotated, cursor = _rotate_to_cursor(None, {**SOURCE, "crawl_cursor": 15}, PAGES)
        assert cursor == 15
        assert rotated[0] == "p15"

    def test_nothing_is_dropped_only_reordered(self):
        rotated, _ = _rotate_to_cursor(None, {**SOURCE, "crawl_cursor": 15}, PAGES)
        assert sorted(rotated) == sorted(PAGES)
        assert len(rotated) == len(PAGES)

    def test_it_wraps_round_to_the_front(self):
        rotated, _ = _rotate_to_cursor(None, {**SOURCE, "crawl_cursor": 40}, PAGES)
        assert rotated[:3] == ["p40", "p41", "p0"]

    def test_a_cursor_past_the_end_is_not_an_error(self):
        """The list shrinks when the site removes a page."""
        rotated, cursor = _rotate_to_cursor(None, {**SOURCE, "crawl_cursor": 500}, PAGES)
        assert cursor == 500 % 42
        assert len(rotated) == 42

    def test_an_empty_list_is_left_alone(self):
        assert _rotate_to_cursor(None, SOURCE, []) == ([], 0)


class TestSavingIt:
    def test_the_cursor_moves_on_by_what_was_visited(self, db):
        _save_cursor(db, SOURCE, started_at=0, visited=15, listed=42)
        assert db.sources.find_one({"id": "kil-1"})["crawl_cursor"] == 15

    def test_it_wraps_instead_of_running_off_the_end(self, db):
        _save_cursor(db, SOURCE, started_at=36, visited=15, listed=42)
        assert db.sources.find_one({"id": "kil-1"})["crawl_cursor"] == 9

    def test_an_empty_listing_leaves_the_cursor_alone(self, db):
        """A failed run must not advance past pages it never saw."""
        _save_cursor(db, SOURCE, started_at=15, visited=0, listed=0)
        assert "crawl_cursor" not in db.sources.find_one({"id": "kil-1"})

    def test_a_database_that_will_not_take_it_does_not_fail_the_run(self):
        class Broken:
            class sources:
                @staticmethod
                def update_one(*a, **k):
                    raise RuntimeError("no")

        _save_cursor(Broken, SOURCE, started_at=0, visited=15, listed=42)


class TestTheWholeCircuit:
    def test_three_runs_of_fifteen_cover_all_forty_two(self, db):
        """The claim the fix exists to make.

        Runs the rotation and the save against each other the way the importer
        does, and checks that every page is reached — not that the arithmetic
        looks right in isolation.
        """
        seen, source = set(), dict(SOURCE)
        for _ in range(3):
            rotated, started = _rotate_to_cursor(db, source, PAGES)
            batch = rotated[:15]
            seen.update(batch)
            _save_cursor(db, source, started, len(batch), len(PAGES))
            source = db.sources.find_one({"id": "kil-1"})

        assert len(seen) == 42, f"never reached: {sorted(set(PAGES) - seen)}"

    def test_without_the_cursor_the_tail_is_never_reached(self, db):
        """The old behaviour, so the difference is on the record."""
        seen = set()
        for _ in range(3):
            seen.update(PAGES[:15])
        assert len(seen) == 15
        assert "p41" not in seen
