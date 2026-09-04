"""A lake in the north was pinned on the capital, fifty kilometres away.

Christoph opened "Esch sur Sure und Obersauerstausee" in the app and the map
underneath it showed Luxembourg City. The event said `town: Luxembourg`,
`canton: Luxembourg`, and carried the capital's coordinates.

The kids-in-lux crawler reads its location from a "(Commune - Locality)"
parenthetical in the OpenGraph title. The outings mostly have none, and the
code then did this:

    canton = canton or "Luxembourg"
    coord = COMMUNE_COORDS.get(commune) or CANTON_FALLBACK.get(canton, ...)

An invention that looked exactly like an answer. Nothing downstream could tell
the two apart: the geocoder picks up events with a coarse location, but it was
handed "Luxembourg" as the town and dutifully confirmed the capital.

The name was in the title the whole time, and the coordinates for it were
already in our own table.
"""
import pytest

from town_names import find_town_in_text


class TestFindingAPlaceInATitle:
    @pytest.mark.parametrize("title,expected", [
        ("Esch sur Sure und Obersauerstausee", "Esch-sur-Sûre"),
        ("Wanderung Vianden", "Vianden"),
        ("Naturpark Our bei Clervaux", "Clervaux"),
    ])
    def test_it_reads_the_place_out_of_the_title(self, title, expected):
        assert find_town_in_text(title) == expected

    def test_accents_and_hyphens_do_not_have_to_match(self):
        """The title writes "Esch sur Sure", the commune is "Esch-sur-Sûre"."""
        assert find_town_in_text("Esch sur Sure") == "Esch-sur-Sûre"

    def test_the_longest_match_wins(self):
        """"esch" appears inside "esch-sur-sure".

        Taking the first or shortest match would file a lake in the Ardennes
        under Esch-sur-Alzette in the industrial south.
        """
        assert find_town_in_text("Esch sur Sure und Obersauerstausee") != "Esch-sur-Alzette"

    @pytest.mark.parametrize("title", [
        "Fit & Fun – Zumba", "Konzert am Duerf", "Kachcours fir Kanner", "", None,
    ])
    def test_a_title_without_a_place_yields_nothing(self, title):
        """Silence, not a guess. "" lets the caller admit it does not know."""
        assert find_town_in_text(title) == ""

    def test_very_short_names_are_not_hunted_inside_words(self):
        """Four-letter communes turn up inside ordinary words.

        A wrong town is worse than no town, so the search skips the names too
        short to be sure about.
        """
        assert find_town_in_text("Bechermaschinn a Kachbicher") == ""


class TestTheCrawlerStopsInventing:
    def _parsed(self, title):
        from crawlers import kids_in_lux
        html = (
            f'<html><head><meta property="og:title" content="{title}">'
            '<meta property="og:description" content="">'
            "</head><body></body></html>"
        )
        return kids_in_lux.parse_detail("https://example.invalid/p/x/", html)

    def test_the_case_from_the_screenshot(self):
        parsed = self._parsed("Esch sur Sure und Obersauerstausee")
        assert parsed["commune"] == "Esch-sur-Sûre"
        assert parsed["located"] is True
        # The Obersauer lake, not the capital.
        assert parsed["lat"] == pytest.approx(49.9086, abs=0.01)
        assert parsed["lng"] == pytest.approx(5.9375, abs=0.01)

    def test_it_is_nowhere_near_luxembourg_city(self):
        parsed = self._parsed("Esch sur Sure und Obersauerstausee")
        assert abs(parsed["lat"] - 49.6117) > 0.2, "that is the capital again"

    def test_a_parenthetical_still_wins(self):
        """The structured hint is the better source where it exists."""
        parsed = self._parsed("Spillplaz Um Bierg (Vianden - Zentrum)")
        assert parsed["commune"] == "Vianden"

    def test_an_unrecognisable_title_admits_it(self):
        parsed = self._parsed("Fit &amp; Fun – Zumba")
        assert parsed["commune"] == ""
        assert parsed["canton"] == "", "no invented canton"
        assert parsed["located"] is False


class TestWhatGetsStored:
    def _stored(self, title):
        from crawlers import kids_in_lux

        class FakeEvents:
            def __init__(self): self.stored = []
            def find_one(self, _q): return None
            def insert_one(self, d): self.stored.append(d)

        class FakeDB:
            def __init__(self): self.events = FakeEvents()

        html = (
            f'<html><head><meta property="og:title" content="{title}">'
            '<meta property="og:description" content="">'
            "</head><body></body></html>"
        )
        parsed = kids_in_lux.parse_detail("https://example.invalid/p/x/", html)
        db = FakeDB()
        kids_in_lux.upsert_event(db, parsed, ["Nature"], "Outdoor", "src-1")
        return db.events.stored[0]

    def test_an_unknown_place_is_stored_as_unknown(self):
        doc = self._stored("Fit &amp; Fun – Zumba")
        assert doc["town"] == "", 'not "Luxembourg"'
        assert doc["geocode_precision"] == "fallback"

    def test_a_known_place_is_stored_as_resolved(self):
        doc = self._stored("Esch sur Sure und Obersauerstausee")
        assert doc["town"] == "Esch-sur-Sûre"
        assert doc["geocode_precision"] == "commune"

    def test_the_geocoder_will_pick_up_the_unresolved_one(self):
        """Saying "fallback" out loud is what makes it findable.

        `pending_query` already looks for coarse or missing precision, so the
        placeholder gets a real lookup on the next pass instead of sitting
        there looking finished.
        """
        from geocode_events import pending_query

        doc = self._stored("Fit &amp; Fun – Zumba")
        coarse = pending_query()["$and"][0]["$or"]
        accepted = [c for c in coarse if "geocode_precision" in c]
        assert any(
            doc["geocode_precision"] in (c["geocode_precision"].get("$in") or [])
            for c in accepted
            if isinstance(c["geocode_precision"], dict)
            and "$in" in c["geocode_precision"]
        )
