"""Placing city quarters and venues, without repeating an old mistake.

27 events sat on a canton centroid, all of them in Luxembourg City, and all
three distinct "towns" among them were not communes: Kirchberg, a quarter, and
two venue names. The address service returns nothing for any of them on its
own, and returns the right answer when the town is appended.

Appending is exactly what build_address_query stopped doing, because every
commune was collapsing onto its cantonal seat — Luxembourg names its cantons
after their main town, and the service latched onto the part it recognised.
Measured again against the live service while writing this:

    "Bech"              49.75255, 6.36256   the village itself
    "Bech, Echternach"  49.80967, 6.42048   Echternach, 7km away

So the narrowed query is restricted to towns that are not communes. Bech is a
commune and never reaches it. A quarter never appears in any commune list, so
it always does.
"""
import pytest

from geocode_events import build_address_query, narrowed_address_query


def ev(town, canton="Luxembourg"):
    return {"town": town, "canton": canton}


class TestCommunesAreLeftAlone:
    """The half that protects the earlier fix."""

    @pytest.mark.parametrize(
        "town", ["Bech", "Boulaide", "Bettendorf", "Esch-sur-Alzette", "Wiltz"]
    )
    def test_no_narrowed_query_is_produced(self, town):
        assert narrowed_address_query(ev(town, "Echternach")) == ""

    def test_the_bare_query_is_unchanged(self):
        assert build_address_query(ev("Bech", "Echternach")) == "Bech"

    def test_spelling_variants_still_count_as_communes(self):
        assert narrowed_address_query(ev("Suessem", "Esch-sur-Alzette")) == ""


class TestQuartersAndVenues:
    def test_a_quarter_gets_its_town(self):
        assert narrowed_address_query(ev("Kirchberg")) == "Kirchberg, Luxembourg"

    def test_a_venue_gets_its_town(self):
        assert (
            narrowed_address_query(ev("Théâtre des Capucins"))
            == "Théâtre des Capucins, Luxembourg"
        )

    def test_other_quarters_too(self):
        assert narrowed_address_query(ev("Clausen")) == "Clausen, Luxembourg"


class TestEdges:
    def test_no_town_produces_nothing(self):
        assert narrowed_address_query(ev("")) == ""

    def test_no_canton_produces_nothing(self):
        """Appending an empty canton would just repeat the query that failed."""
        assert narrowed_address_query(ev("Kirchberg", "")) == ""

    def test_a_parenthesised_town_is_unwrapped_first(self):
        """clean_town turns "Luxembourg-Stadt (Kirchberg)" into "Kirchberg"."""
        assert (
            narrowed_address_query(ev("Luxembourg-Stadt (Kirchberg)"))
            == "Kirchberg, Luxembourg"
        )
