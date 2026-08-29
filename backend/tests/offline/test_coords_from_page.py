"""Reading a place off the map the page already draws.

Locating kids-in-lux entries has now been wrong twice and roundabout once.
First the crawler filled an unknown commune with "Luxembourg" and dropped a pin
on the capital — a lake in the Ardennes fifty kilometres out. Then it looked
for a commune name in the title, which is better but still a guess, and left
eighteen entries with no location at all.

All along, every one of those pages carried the exact position in its own
markup:

    .../maps/embed/v1/place?key=…&q=49.8995%2C5.8670&center=49.9059%2C5.8994

`q` is the marker, `center` only the viewport. Six pages checked by hand, six
with coordinates.

The bounding box is the part worth testing hardest. An embedded map can point
anywhere on earth, and a confident pin in Belgium would be worse than the
honest blank it replaces.
"""
import pytest

from crawlers.kids_in_lux import LU_BOUNDS, coords_from_map_embed

# The real thing, entities and percent-encoding included.
REAL = (
    '<iframe width="100%" height="400" frameborder="0" '
    'data-src="https://www.google.com/maps/embed/v1/place?key=AIzaSyEXAMPLE'
    '&amp;q=49.8995712865%2C5.86709251312'
    '&amp;center=49.9059587611%2C5.89947214035&amp;zoom=14&amp;maptype=roadmap">'
    "</iframe>"
)


class TestTheRealMarkup:
    def test_it_finds_the_marker(self):
        assert coords_from_map_embed(REAL) == (49.8995712865, 5.86709251312)

    def test_the_marker_beats_the_viewport_centre(self):
        """`center` is where the map looks, `q` is where the place is."""
        lat, _ = coords_from_map_embed(REAL)
        assert lat != 49.9059587611

    def test_html_entities_and_percent_encoding_are_handled(self):
        """`&amp;` between parameters and `%2C` for the comma."""
        assert "&amp;" in REAL and "%2C" in REAL
        assert coords_from_map_embed(REAL) is not None

    def test_only_numbers_come_back(self):
        """The API key in that URL is Google's and theirs. Nothing keeps it."""
        result = coords_from_map_embed(REAL)
        assert isinstance(result, tuple) and len(result) == 2
        assert all(isinstance(v, float) for v in result)


class TestTheBoundingBox:
    @pytest.mark.parametrize("lat,lng,where", [
        (48.8566, 2.3522, "Paris"),
        (50.8503, 4.3517, "Brussels"),
        (52.5200, 13.4050, "Berlin"),
        (0.0, 0.0, "the Gulf of Guinea"),
    ])
    def test_a_pin_outside_luxembourg_is_refused(self, lat, lng, where):
        html = f'<iframe src="https://www.google.com/maps/embed/v1/place?q={lat}%2C{lng}">'
        assert coords_from_map_embed(html) is None, f"accepted {where}"

    @pytest.mark.parametrize("lat,lng", [
        (49.6117, 6.1319),      # Luxembourg City
        (49.8996, 5.8671),      # the Obersauer lake
        (49.4958, 5.9806),      # Esch-sur-Alzette, near the southern border
        (50.1450, 6.0300),      # Clervaux, near the northern one
    ])
    def test_places_in_the_country_are_accepted(self, lat, lng):
        html = f'<iframe src="https://www.google.com/maps/embed/v1/place?q={lat}%2C{lng}">'
        assert coords_from_map_embed(html) == (lat, lng)

    def test_the_box_actually_contains_the_country(self):
        lo_lat, hi_lat, lo_lng, hi_lng = LU_BOUNDS
        assert lo_lat < 49.4479 and hi_lat > 50.1820, "misses the north or south tip"
        assert lo_lng < 5.7357 and hi_lng > 6.5309, "misses the east or west edge"

    def test_it_moves_on_to_the_next_embed_rather_than_giving_up(self):
        """A page may hold a decorative map before the real one."""
        html = (
            '<iframe src="https://www.google.com/maps/embed/v1/place?q=48.8566%2C2.3522">'
            '<iframe src="https://www.google.com/maps/embed/v1/place?q=49.8996%2C5.8671">'
        )
        assert coords_from_map_embed(html) == (49.8996, 5.8671)


class TestWhenThereIsNoMap:
    @pytest.mark.parametrize("html", [
        "", "<html><body>Keng Kaart hei</body></html>",
        '<iframe src="https://www.youtube.com/embed/abc"></iframe>',
        '<iframe src="https://www.google.com/maps/embed/v1/place?key=X&amp;zoom=14">',
    ])
    def test_nothing_is_invented(self, html):
        assert coords_from_map_embed(html) is None


class TestWhatParseDetailDoesWithIt:
    def _page(self, title, extra=""):
        return (
            f'<html><head><meta property="og:title" content="{title}">'
            '<meta property="og:description" content=""></head>'
            f"<body>{extra}</body></html>"
        )

    def test_the_map_wins_over_the_commune_table(self):
        """The lake, not the centre of the commune it belongs to."""
        from crawlers.kids_in_lux import parse_detail

        parsed = parse_detail("https://example.invalid/p/x/",
                              self._page("Esch sur Sure und Obersauerstausee", REAL))
        assert parsed["precision"] == "address"
        assert parsed["lat"] == pytest.approx(49.8996, abs=0.001)
        # The commune is still read, because the town label needs a name.
        assert parsed["commune"] == "Esch-sur-Sûre"

    def test_without_a_map_the_commune_still_carries_it(self):
        from crawlers.kids_in_lux import parse_detail

        parsed = parse_detail("https://example.invalid/p/x/",
                              self._page("Esch sur Sure und Obersauerstausee"))
        assert parsed["precision"] == "commune"
        assert parsed["located"] is True

    def test_with_neither_it_says_so(self):
        from crawlers.kids_in_lux import parse_detail

        parsed = parse_detail("https://example.invalid/p/x/", self._page("Fit &amp; Fun"))
        assert parsed["precision"] == "fallback"
        assert parsed["located"] is False
