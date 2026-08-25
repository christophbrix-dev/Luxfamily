# What we ask the geocoder, and why the canton must not be part of it.
#
# Luxembourg names its cantons after their main town, and the cadastral service
# latches onto whichever part of a query it recognises. Asking for
# "Bech, Echternach" returned Echternach; "Boulaide, Wiltz" returned Wiltz;
# "Bettendorf, Diekirch" returned Diekirch. Every commune in a canton collapsed
# onto its cantonal seat, and the guard against a bad locality could not see it:
# the address that came back did echo a word from the query, just the wrong one.
#
# Nothing errored. 200 events sat on 24 points instead of 39, and on a map that
# reads as a country with very little going on.

import geocode_events
from geocoders import LuxembourgGeocoder

# Cantons that are also the name of a town. Nine of the twelve.
CANTON_TOWNS = [
    "Echternach", "Wiltz", "Diekirch", "Remich", "Mersch",
    "Clervaux", "Vianden", "Capellen", "Grevenmacher",
]


class TestTheQueryIsTheTownAlone:
    def test_the_canton_is_not_appended(self):
        ev = {"town": "Bech", "canton": "Echternach"}
        assert geocode_events.build_address_query(ev) == "Bech"

    def test_no_canton_name_survives_into_the_query(self):
        """The whole class of failure, not the three that were noticed."""
        for canton in CANTON_TOWNS:
            q = geocode_events.build_address_query({"town": "Iergendwou", "canton": canton})
            assert canton.lower() not in q.lower(), f"{canton} would capture the match"

    def test_a_venue_is_asked_for_by_itself(self):
        ev = {"town": "Théâtre des Capucins", "canton": "Luxembourg"}
        assert geocode_events.build_address_query(ev) == "Théâtre des Capucins"

    def test_a_parenthetical_is_still_unwrapped(self):
        """clean_town keeps working: "Luxembourg-Stadt (Kirchberg)" is Kirchberg."""
        ev = {"town": "Luxembourg-Stadt (Kirchberg)", "canton": "Luxembourg"}
        assert geocode_events.build_address_query(ev) == "Kirchberg"

    def test_no_town_means_no_question(self):
        assert geocode_events.build_address_query({"town": "", "canton": "Wiltz"}) == ""


class TestTheGuardAgainstAWrongPlace:
    """The service answers with its closest guess rather than nothing."""

    def test_a_real_match_is_accepted(self):
        assert LuxembourgGeocoder._answers_the_question("Bech", "bech,Luxembourg")

    def test_an_unrelated_guess_is_rejected(self):
        assert not LuxembourgGeocoder._answers_the_question("Käerjeng", "eltz,Luxembourg")

    def test_the_capital_is_not_an_answer_to_a_commune(self):
        assert not LuxembourgGeocoder._answers_the_question("Contern", "luxembourg,Luxembourg")

    def test_with_the_canton_attached_the_guard_was_blind(self):
        """Why this went unnoticed. The old query carried the word that matched.

        "Bech, Echternach" against "echternach,Luxembourg" shares a token, so
        the answer looked verified while pointing at the wrong town.
        """
        assert LuxembourgGeocoder._answers_the_question("Bech, Echternach", "echternach,Luxembourg")
        assert not LuxembourgGeocoder._answers_the_question("Bech", "echternach,Luxembourg")
