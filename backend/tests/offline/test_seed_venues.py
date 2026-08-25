# Registering the venue sources.
#
# Fourteen venues cleared discovery, and four of them sit on a domain a commune
# source already covers — a youth club or a sports hall published on its
# commune's website. Registering both means the importer crawls the same
# /events/ page under two names and files every event twice.

import seed_venue_sources as sv


class TestDomain:
    def test_www_is_not_part_of_the_name(self):
        assert sv.domain("https://www.mamer.lu/events/") == "mamer.lu"
        assert sv.domain("https://mamer.lu/events/") == "mamer.lu"

    def test_case_does_not_matter(self):
        assert sv.domain("https://MAMER.LU/x") == "mamer.lu"

    def test_nothing_stays_nothing(self):
        assert sv.domain("") == ""
        assert sv.domain(None) == ""

    def test_a_subdomain_is_its_own_domain(self):
        """agenda.mamer.lu is not the page the commune source crawls."""
        assert sv.domain("https://agenda.mamer.lu/x") != sv.domain("https://mamer.lu/x")


COMMUNES = [
    {"name": "Veianen", "canton": "Vianden", "lat": 49.9366, "lng": 6.1902},
    {"name": "Esch-sur-Alzette", "canton": "Esch-sur-Alzette", "lat": 49.4959, "lng": 5.9795},
    {"name": "Wiltz", "canton": "Wiltz", "lat": 49.9811, "lng": 5.9378},
]


class TestPlacing:
    def test_a_venue_lands_in_its_own_commune(self):
        # Château de Vianden, from the extract.
        c = sv.place_at(49.935214, 6.202589, COMMUNES)
        assert c["canton"] == "Vianden"

    def test_a_venue_elsewhere_lands_elsewhere(self):
        # Musée national des Mines, in Rumelange.
        c = sv.place_at(49.460774, 6.022864, COMMUNES)
        assert c["canton"] == "Esch-sur-Alzette"

    def test_an_empty_index_places_nothing(self):
        assert sv.place_at(49.5, 6.1, []) is None


class TestBuild:
    def row(self, **over):
        base = {
            "Art": "Musée", "Name": "Musée national des Mines",
            "Website": "https://mnm.lu/", "Beispiel-URL": "https://mnm.lu/events/",
            "lat": "49.460774", "lng": "6.022864",
        }
        base.update(over)
        return base

    def test_it_uses_the_venues_own_position(self):
        """Not the commune centroid — a museum has a front door."""
        s = sv.build(self.row(), COMMUNES[1])
        assert s["lat_default"] == 49.460774
        assert s["geocode_precision_default"] == "venue"

    def test_the_url_is_the_page_discovery_verified(self):
        s = sv.build(self.row(), COMMUNES[1])
        assert s["url"] == "https://mnm.lu/events/"

    def test_categories_follow_the_kind(self):
        assert "Culture" in sv.build(self.row(Art="Theater"), COMMUNES[1])["category_default"]
        assert "Sports" in sv.build(self.row(Art="Sportzentrum"), COMMUNES[1])["category_default"]
        assert "Animals" in sv.build(self.row(Art="Tierpark"), COMMUNES[1])["category_default"]

    def test_an_unknown_kind_still_gets_something(self):
        assert sv.build(self.row(Art="Zirkuszelt"), COMMUNES[1])["category_default"] == ["Culture"]

    def test_every_kind_discovery_can_emit_has_categories(self):
        """A kind without an entry would silently become plain "Culture"."""
        from discover_venue_sources import VENUE_KINDS
        for _, _, label in VENUE_KINDS:
            assert label in sv.CATEGORIES_BY_KIND, label

    def test_sources_are_json_ld(self):
        assert sv.build(self.row(), COMMUNES[1])["kind"] == "json_ld"
