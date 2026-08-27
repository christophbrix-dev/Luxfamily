"""Reading an age only when the page gives one.

All 528 events were stored as 0–99, which in a family app reads as "newborns
welcome" rather than "we were not told". A Trivium concert carried it.

Only 14 of the 528 state an age anywhere. The value of this module is
therefore mostly in the second class below: numbers that look like ages and
are not. Getting one of those wrong is worse than the silence it replaces —
a parent acting on "ab 50 Joer" would be acting on an anniversary.
"""
import pytest

from age_hints import read_age


class TestStatedAges:
    @pytest.mark.parametrize(
        "text,low,high",
        [
            ("Fir Kanner ab 3 Joer", 3, None),
            ("Ouvert aux jeunes à partir de 12 ans", 12, None),
            ("Für Kinder ab 6 Jahren", 6, None),
            ("For children from 5 years", 5, None),
            ("conçu pour les enfants de 2 à 5 ans", 2, 5),
            ("Kinder (6-12 Jahre) : 11 EUR", 6, 12),
            ("vun 4 bis 10 Joer", 4, 10),
            ("jusqu'à 10 ans", None, 10),
        ],
    )
    def test_read(self, text, low, high):
        hint = read_age(text)
        assert (hint.minimum, hint.maximum) == (low, high)
        assert hint.source == "event"

    def test_a_range_keeps_its_upper_bound(self):
        """A range also matches "from N"; the wider reading must not win."""
        assert read_age("de 2 à 5 ans").maximum == 5


class TestNumbersThatAreNotAges:
    @pytest.mark.parametrize(
        "text",
        [
            # Anniversaries, which is what most standalone numbers are.
            "50 Joer Guiden a Scouten",
            "25 Jahre Partnerschaft mit der Gemeng",
            "100 ans du club",
            "Zënter 30 Joer am Déngscht vun der Gemeng",
            "Seit 40 Jahren im Verein",
            # A time, which cost the family filter a false positive already.
            "Freides, Ab 18:30 am Centre",
            "Treffpunkt um 14:30",
            # A year.
            "Konzert am Joer 2026",
            # A price.
            "D'Plaze kaschten 30 € pro Persoun",
            # Nothing.
            "Kannerfest am Park",
            "",
        ],
    )
    def test_nothing_is_invented(self, text):
        hint = read_age(text)
        assert hint == (None, None, "unknown"), f"invented an age for {text!r}"


class TestInputHandling:
    def test_several_fields_are_searched(self):
        assert read_age("Workshop", None, "Fir Kanner ab 3 Joer").minimum == 3

    def test_an_impossible_range_is_refused(self):
        assert read_age("vun 40 bis 10 Joer").source == "unknown"

    def test_empty_input_is_unknown(self):
        assert read_age().source == "unknown"
        assert read_age("", None, "   ").minimum is None
