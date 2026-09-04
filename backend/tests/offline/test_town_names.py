# One spelling per town.
#
# The live database held five names for the capital — Luxembourg, Luxemburg,
# Luxembourg City, Luxembourg-Stadt, Luxemburg-Stadt — because every source
# writes it in its own language and each of them is right. To a filter they are
# five different places.

from town_names import canonical_town


class TestTheCapital:
    """The five spellings actually observed in the live data."""

    def test_all_five_collapse_to_one(self):
        seen = [
            "Luxembourg", "Luxemburg", "Luxembourg City",
            "Luxembourg-Stadt", "Luxemburg-Stadt",
        ]
        assert {canonical_town(t) for t in seen} == {"Luxembourg"}

    def test_the_luxembourgish_name_too(self):
        assert canonical_town("Lëtzebuerg") == "Luxembourg"


class TestOtherCommunes:
    def test_german_exonyms_become_the_official_name(self):
        assert canonical_town("Petingen") == "Pétange"
        assert canonical_town("Rümelingen") == "Rumelange"

    def test_luxembourgish_names_too(self):
        assert canonical_town("Péiteng") == "Pétange"
        assert canonical_town("Rëmeleng") == "Rumelange"

    def test_accents_and_case_do_not_matter(self):
        assert canonical_town("petange") == "Pétange"
        assert canonical_town("  PÉTANGE  ") == "Pétange"


class TestItLeavesAloneWhatItDoesNotKnow:
    """The important half. Guessing is worse than passing through."""

    def test_quarters_are_not_swallowed_by_the_capital(self):
        # Kirchberg is in Luxembourg City, but "Kirchberg" is the more useful
        # answer to "where is this?" — collapsing it loses information.
        for quarter in ("Kirchberg", "Belval", "Clausen", "Gasperich"):
            assert canonical_town(quarter) == quarter

    def test_venue_names_pass_through(self):
        for venue in ("Centre sportif Bim Diederich", "Rodange, Sportshal"):
            assert canonical_town(venue) == venue

    def test_foreign_towns_pass_through(self):
        for town in ("Trier", "Arlon", "Thionville"):
            assert canonical_town(town) == town

    def test_a_suffix_alone_is_not_enough(self):
        # "Belval Centre" must keep its word: the remainder is not a commune.
        assert canonical_town("Belval Centre") == "Belval Centre"

    def test_empty_stays_empty(self):
        assert canonical_town("") == ""
        assert canonical_town(None) == ""


class TestItIsIdempotent:
    def test_running_twice_changes_nothing(self):
        for t in ("Luxemburg-Stadt", "Petingen", "Kirchberg", "Trier"):
            once = canonical_town(t)
            assert canonical_town(once) == once


class TestShortForms:
    """Abbreviations, and the one that names two different places.

    134 events arrived from eleven newly enabled sources carrying both "Esch"
    and "Esch-sur-Alzette" — one town, two entries in every list and filter,
    and a search for one that misses the other. The Rockhal and the
    Kulturfabrik both write the short form.
    """

    def test_lux_is_the_capital(self):
        assert canonical_town("Lux") == "Luxembourg"

    def test_esch_with_its_canton_resolves(self):
        assert canonical_town("Esch", "Esch-sur-Alzette") == "Esch-sur-Alzette"

    def test_the_other_esch_also_resolves(self):
        """Esch-sur-Sûre is 50km away and is not the obvious reading."""
        assert canonical_town("Esch", "Wiltz") == "Esch-sur-Sûre"

    def test_esch_without_a_canton_is_left_alone(self):
        """An inconsistent spelling beats a confident wrong answer."""
        assert canonical_town("Esch") == "Esch"

    def test_an_unknown_canton_does_not_force_a_guess(self):
        assert canonical_town("Esch", "Gutland") == "Esch"

    def test_case_and_accents_still_do_not_matter(self):
        assert canonical_town("ESCH", "esch-sur-alzette") == "Esch-sur-Alzette"

    def test_a_known_commune_ignores_the_canton(self):
        """The canton resolves short forms; it never overrides a real name."""
        assert canonical_town("Echternach", "Wiltz") == "Echternach"

    def test_quarters_are_still_untouched(self):
        assert canonical_town("Kirchberg", "Luxembourg") == "Kirchberg"
