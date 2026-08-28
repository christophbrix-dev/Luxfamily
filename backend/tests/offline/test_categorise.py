"""Giving the category filter something to separate.

437 of 528 events carried "Culture, Festivals", so choosing "Festivals"
returned nearly everything and choosing "Playgrounds" returned one row.

The most important test in this file is the last one. A category the frontend
does not know is not a category — it is an event no filter will ever return —
and one source is configured with "Sports", which is not in the app's list.
Nothing caught that until it was looked for by hand.
"""
import re
from pathlib import Path

import pytest

from categorise import CATEGORIES, categorise

FRONTEND_PLACES = (
    Path(__file__).resolve().parents[3] / "frontend" / "src" / "data" / "places.ts"
)


class TestSignals:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Kachcours fir Kanner", "Workshops"),
            ("Atelier créatif", "Workshops"),
            ("Duerffest zu Bech", "Festivals"),
            ("Braderie annuelle", "Festivals"),
            ("Floumoart um Parking", "Festivals"),
            ("Besuch am Déierepark", "Animals"),
            ("Ferme pédagogique ouverte", "Animals"),
            ("Schwammbad zu Réiden", "Water"),
            ("Stand-up-Paddle um Stau", "Water"),
            ("Geführte Wanderung am Naturschutzgebiet", "Nature"),
            ("Promenade guidée au jardin", "Nature"),
            ("Spillplaz-Aweiung", "Playgrounds"),
            ("Konzert vun der Musek", "Culture"),
            ("Vernissage der Ausstellung", "Culture"),
        ],
    )
    def test_recognised(self, text, expected):
        assert expected in categorise(text)


class TestFallback:
    def test_no_signal_keeps_the_source_default(self):
        assert categorise("Gemeinderatssitzung", default=["Nature"]) == ["Nature"]

    def test_no_signal_and_no_default_is_culture(self):
        """The neutral bucket, not a claim that it is a festival."""
        assert categorise("Collecte Superdreckskescht") == ["Culture"]

    def test_empty_text_uses_the_default(self):
        assert categorise("", default=["Animals"]) == ["Animals"]


class TestPickingBetweenSignals:
    def test_the_more_specific_one_wins_the_first_slot(self):
        assert categorise("Kannerfest um Spillplaz")[0] == "Playgrounds"

    def test_at_most_two_are_returned(self):
        """A row of chips saying everything says nothing."""
        text = "Festival mat Concert, Atelier, Wanderung a Schwammbad"
        assert len(categorise(text)) <= 2

    def test_a_walk_is_nature_not_generic_culture(self):
        assert categorise("Geführte Wanderung duerch de Bësch")[0] == "Nature"


class TestVocabulary:
    def test_every_signal_names_a_real_category(self):
        from categorise import SIGNALS
        assert set(SIGNALS) <= set(CATEGORIES)

    def test_nothing_outside_the_vocabulary_is_ever_returned(self):
        for text in ("Konzert", "Duerffest", "Atelier", "Wanderung", "irgendwas"):
            assert set(categorise(text)) <= set(CATEGORIES)

    def test_the_backend_and_the_app_agree(self):
        """The check that would have caught "Sports".

        A category the frontend does not know cannot be filtered on, so an
        event carrying one silently disappears from every view. The two lists
        are in different languages in different files; only a test keeps them
        in step.
        """
        source = FRONTEND_PLACES.read_text(encoding="utf-8")
        block = re.search(r"export const CATEGORIES = \[(.*?)\] as const;", source, re.S)
        assert block, "CATEGORIES not found in places.ts — did it move?"
        frontend = tuple(re.findall(r'"([^"]+)"', block.group(1)))
        assert frontend == CATEGORIES


class TestCuratedDefaultsWin:
    """A keyword beats a placeholder, never a decision somebody made.

    The first version of this module overrode every default with whatever the
    text suggested. The Parc Merveilleux source is configured as Animals,
    Nature, Playgrounds; one of its events mentions a concert, and the app's
    only Playgrounds event became a generic "Culture".
    """

    def test_a_specific_default_is_kept_despite_a_signal(self):
        assert categorise(
            "Konzert am Park", default=["Animals", "Nature", "Playgrounds"]
        ) == ["Animals", "Nature", "Playgrounds"]

    def test_a_generic_default_gives_way_to_the_text(self):
        assert categorise("Duerffest", default=["Culture", "Festivals"]) == ["Festivals"]

    def test_culture_alone_counts_as_generic(self):
        assert categorise("Kachcours", default=["Culture"]) == ["Workshops"]

    def test_a_partly_specific_default_is_kept_whole(self):
        assert categorise("Konzert", default=["Culture", "Water"]) == ["Culture", "Water"]
