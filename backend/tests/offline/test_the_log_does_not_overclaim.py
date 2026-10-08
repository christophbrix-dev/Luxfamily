"""Three numbers and one label that said more than they knew.

All four came out of the first week of unattended launchd runs, and none of
them was a crash — each was a healthy system describing itself wrongly, which
is the failure this project keeps meeting. A wrong number nobody can check
costs more than a missing one: it sends somebody looking for a problem that is
not there, or stops them looking for one that is.

  - a duration that counted the laptop's sleep as work (5.8 to 241.9 minutes,
    and the long ones were all the 05:00 and 18:00 slots)
  - a run that was killed mid-crawl and left no trace at all
  - "blocked_by_robots" on two communes whose robots.txt had merely timed out
"""
import pytest

import crawler_utils
import importer_run
import run_importers


class TestADurationSaysWhichKindOfTimeItIs:
    def test_an_uninterrupted_run_reads_plainly(self):
        """No parenthesis when there is nothing to explain."""
        assert run_importers._duration(372.0, 371.6) == "6.2 min"

    def test_rounding_between_the_clocks_is_not_reported_as_sleep(self):
        """The two clocks are read a few statements apart, never identical."""
        assert "asleep" not in run_importers._duration(372.0, 371.0)

    def test_a_run_through_a_sleep_reports_both(self):
        """The case that made this necessary: 6 minutes of work, 4 hours of clock."""
        text = run_importers._duration(14_514.0, 372.0)
        assert "6.2 min of work" in text
        assert "241.9 min wall clock" in text
        assert "236 min asleep" in text

    def test_the_work_figure_is_the_one_in_front(self):
        """It is the answer to "was this run slow?" — the other number is context."""
        text = run_importers._duration(14_514.0, 372.0)
        assert text.index("of work") < text.index("wall clock")

    def test_a_long_run_that_never_slept_is_not_excused(self):
        """A genuinely slow run must still look slow."""
        text = run_importers._duration(5_400.0, 5_399.0)
        assert text == "90.0 min"


class TestAKilledRunIsNoticed:
    """The only moment this is knowable is when the next run takes the lease."""

    def test_a_predecessor_that_finished_says_nothing(self, caplog):
        importer_run._note_if_predecessor_died({"released": True, "acquired_at": "2026-10-02"})
        assert caplog.records == []

    def test_a_first_ever_run_says_nothing(self, caplog):
        """No lock document yet, and no predecessor to report on."""
        importer_run._note_if_predecessor_died(None)
        assert caplog.records == []

    def test_an_old_document_without_the_field_says_nothing(self, caplog):
        """The field did not exist before 2026-10-09; absence is not a death."""
        importer_run._note_if_predecessor_died({"acquired_at": "2026-10-02"})
        assert caplog.records == []

    def test_a_predecessor_that_never_released_is_reported(self, caplog):
        importer_run._note_if_predecessor_died({"released": False, "acquired_at": "2026-10-02"})
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

    def test_the_warning_names_when_it_started(self, caplog):
        """Without the time it cannot be matched to anything in the log."""
        importer_run._note_if_predecessor_died({"released": False, "acquired_at": "2026-10-02T12:00:25"})
        assert "2026-10-02T12:00:25" in caplog.text

    def test_the_warning_says_nothing_is_stuck(self, caplog):
        """A warning that leaves a reader wondering if they must clear a lock
        by hand has created work rather than removed it."""
        importer_run._note_if_predecessor_died({"released": False, "acquired_at": "x"})
        assert "nothing is stuck" in caplog.text


class TestTheLeaseRecordsWhetherItFinished:
    def test_releasing_marks_it_released(self):
        import inspect
        src = inspect.getsource(importer_run.release_lease)
        assert '"released": True' in src

    def test_taking_it_marks_it_unreleased(self):
        import inspect
        src = inspect.getsource(importer_run.acquire_lease)
        assert '"released": False' in src

    def test_both_happen_in_the_same_write_as_the_lease_itself(self):
        """A crash between freeing the lease and marking it would look exactly
        like the thing this detects."""
        import inspect
        for fn in (importer_run.acquire_lease, importer_run.release_lease):
            src = inspect.getsource(fn)
            assert src.count("update_one") == 1, fn.__name__
            assert "lease_until" in src and "released" in src


class TestRobotsRefusedAndRobotsUnreachableAreDifferent:
    """Not crawling is right in both cases. What a person should do is not."""

    def test_a_refusal_is_not_marked_unreadable(self):
        assert crawler_utils.RobotsBlocked("robots.txt disallows x").unreadable is False

    def test_an_unreadable_file_is(self):
        assert crawler_utils.RobotsBlocked("could not read", unreadable=True).unreadable is True

    @pytest.mark.parametrize("unreadable,expected", [
        (False, "blocked_by_robots"),
        (True, "robots_unreadable"),
    ])
    def test_the_stored_status_follows_the_flag(self, unreadable, expected):
        """The status is the only place that can carry the distinction into the
        admin screen, which rendered both as "robots.txt says no"."""
        import inspect

        import importers
        src = inspect.getsource(importers.run_source)
        assert f'"{expected}"' in src
        assert "rb.unreadable" in src

    def test_the_check_passes_the_flag_when_it_could_not_read_the_file(self):
        import inspect
        src = inspect.getsource(crawler_utils._check_allowed)
        before_disallow = src[: src.index("can_fetch")]
        assert "unreadable=True" in before_disallow
