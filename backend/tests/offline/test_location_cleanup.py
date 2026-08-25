# Two ways a venue got lost between the page and the map.
#
# Both showed up the first time the whole chain ran against a real database:
# 28 events on 3 distinct points, several of them filed under a town called
# "Cinéma Pour tous publics".

import geocode_events
import importers


class TestALabelledFieldKeepsOnlyItsValue:
    """vdl.lu writes "Lieu | Théâtre des Capucins" inside one element."""

    def test_the_label_is_dropped(self):
        assert importers._clean_location("Lieu | Théâtre des Capucins") == "Théâtre des Capucins"

    def test_an_unlabelled_venue_is_untouched(self):
        assert importers._clean_location("Rodange, Sportshal") == "Rodange, Sportshal"

    def test_a_dash_is_not_a_label(self):
        """Only the pipe means "label | value" here."""
        assert importers._clean_location("Centre sportif Bim-Diederich") == "Centre sportif Bim-Diederich"

    def test_whitespace_goes(self):
        assert importers._clean_location("  Lieu |  Mudam  ") == "Mudam"

    def test_nothing_stays_nothing(self):
        assert importers._clean_location("") == ""
        assert importers._clean_location(None) == ""


class TestTheVenueIsLookedUpBeforeTheTitle:
    """An event is rarely named after the building it happens in.

    "Museum Break : Layers of summer" matches nothing in our places; its town
    field holds "Lëtzebuerg City Museum", which is in there with a coordinate.
    Searching only by title sent both museum events to the city centre.
    """

    def test_a_venue_in_our_places_is_found(self):
        calls = []

        class FakeDB:
            class places:
                @staticmethod
                def find_one(query, projection=None):
                    calls.append(query)
                    # re.escape backslashes the spaces, so compare on a word.
                    pattern = query.get("name", {}).get("$regex", "")
                    if "Museum" in pattern and "Break" not in pattern:
                        return {"lat": 49.61, "lng": 6.1336, "name": "Lëtzebuerg City Museum"}
                    return None

        ev = {
            "title": {"de": "Museum Break : Layers of summer"},
            "town": "Lëtzebuerg City Museum",
            "canton": "Luxembourg",
        }
        result = geocode_events.resolve(FakeDB, ev, {})
        assert result.source == "places"
        assert result.lat == 49.61
        # The venue was tried first, so the title never had to be.
        assert "City" in calls[0]["name"]["$regex"]

    def test_a_commune_name_costs_one_lookup_and_moves_on(self):
        """Commune sources write a commune there, which matches no place."""
        tried = []

        class FakeDB:
            class places:
                @staticmethod
                def find_one(query, projection=None):
                    tried.append(query)
                    return None

        ev = {"title": {"de": "Grouss Botz"}, "town": "Mamer", "canton": "Capellen"}
        geocode_events.lookup_local_place(FakeDB, ev["town"], "")
        assert len(tried) >= 1
