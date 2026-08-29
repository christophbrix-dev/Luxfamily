"""A concert in October, filed under the morning it was crawled.

"Le coin des mini monstres | 24.10.2026 13:15" sat in the app three times over
with `start_date: 2026-08-25` — the crawl day. The real date was in its own
title, and in the very next tag on the page.

The Philharmonie's pages carry `<time>` tags in this order:

    ['13:15', '24/10/2026', '10/24/2026 12:00:00 AM', ...]

The first is the start time. The importer took it, and
`dateutil.parse("13:15")` returns *today* at 13:15 — it fills the half the text
does not state from a default, without saying so. The check downstream only
asked whether the result began with "20", which it did.

Parsing twice with defaults that share no field separates the two exactly: what
the text really contains comes out the same both times.

Looking for that turned up an older, quieter fault. dateutil knows English
month names only, and its fuzzy mode drops words it cannot place rather than
objecting. "24. Juni 2026" had been parsing as day 24, year 2026 and *this
month* for as long as the importer existed — while the docstring claimed German
was understood.
"""
from datetime import date, datetime

import pytest

from importers import _to_iso_date


class TestATimeIsNotADate:
    @pytest.mark.parametrize("text", [
        "13:15", "20:00", "20:00 Uhr", "Ab 18:30", "18h30", "8 PM", "14.30 h",
    ])
    def test_a_bare_time_yields_nothing(self, text):
        assert _to_iso_date(text) is None

    def test_it_does_not_quietly_become_today(self):
        """The exact failure: today's date, wearing a wrong event's clothes."""
        assert _to_iso_date("13:15") != date.today().isoformat()

    def test_the_tag_right_after_it_still_works(self):
        """Rejecting the time is only useful if the real date is still read."""
        assert _to_iso_date("24/10/2026") == "2026-10-24"
        assert _to_iso_date("10/24/2026 12:00:00 AM") == "2026-10-24"

    def test_a_date_with_a_time_keeps_the_date(self):
        assert _to_iso_date("24.10.2026 13:15") == "2026-10-24"
        assert _to_iso_date("2026-10-24T13:15:00") == "2026-10-24"


class TestTheFourLanguagesLuxembourgWritesIn:
    @pytest.mark.parametrize("text,expected", [
        ("24. Juni 2026", "2026-06-24"),
        ("24 June 2026", "2026-06-24"),
        ("24 juin 2026", "2026-06-24"),
        ("24. Dezember 2026", "2026-12-24"),
        ("24 décembre 2026", "2026-12-24"),
        ("2. Mäerz 2027", "2027-03-02"),
        ("1. Abrëll 2027", "2027-04-01"),
        ("15 août 2026", "2026-08-15"),
        ("15. März 2027", "2027-03-15"),
    ])
    def test_month_names_are_read_not_guessed(self, text, expected):
        assert _to_iso_date(text) == expected

    def test_the_month_is_not_taken_from_today(self):
        """What the old behaviour actually did.

        Without month names dateutil dropped the word and filled the month from
        its default, so a June date became whatever month the crawl ran in —
        right day, right year, wrong month, and nothing to show for it.
        """
        assert _to_iso_date("24. Juni 2026") == "2026-06-24"
        assert not _to_iso_date("24. Juni 2026").startswith(
            f"2026-{datetime.now().month:02d}"
        ) or datetime.now().month == 6


class TestNothingElseBroke:
    @pytest.mark.parametrize("text,expected", [
        ("2026-10-24", "2026-10-24"),
        ("24.10.2026", "2026-10-24"),
        ("06/07/2026", "2026-07-06"),        # day first, LU/FR/DE convention
        ("2026-10-24T20:00:00+02:00", "2026-10-24"),
    ])
    def test_the_formats_that_already_worked_still_do(self, text, expected):
        assert _to_iso_date(text) == expected

    def test_datetime_objects_are_untouched(self):
        assert _to_iso_date(datetime(2026, 10, 24, 13, 15)) == "2026-10-24"

    @pytest.mark.parametrize("text", ["", "   ", "Termin folgt", "à confirmer", None])
    def test_nothing_readable_is_still_nothing(self, text):
        assert _to_iso_date(text) is None

    def test_the_implausible_year_guard_still_bites(self):
        """Both rules apply: a real date, and one somebody could have meant."""
        assert _to_iso_date("26.09.2926") is None
