# Which commune a place is in, and the name it gets from that.
#
# Four in five places have no name in OSM, so pick_name falls back to the
# category label and the list reads "Spielplatz" forty times over. They are all
# real playgrounds; what is missing is which one. Almost none carry an address
# — of 3,689 unnamed playgrounds, parks and picnic sites, exactly one has
# addr:* — so the commune boundary is what answers it, and it is in the same
# file the ingest already reads.

import osm_ingest


class FakeHandler:
    """A handler with boundaries and records, without touching a PBF."""

    def __init__(self, communes, records):
        self.communes = communes
        self.records = records

    commune_at = osm_ingest._POIHandler.commune_at


def square(minx, miny, size):
    return [(minx, miny), (minx + size, miny), (minx + size, miny + size), (minx, miny + size)]


def commune(name, minx, miny, size=1.0):
    ring = square(minx, miny, size)
    box = (minx, miny, minx + size, miny + size)
    return (name, box, [ring])


def place(lat, lng, name, named):
    return {"lat": lat, "lng": lng, "name": name, "named": named, "commune": ""}


BEETEBUERG = commune("Beetebuerg", 6.0, 49.0)
MAMER = commune("Mamer", 8.0, 49.0)


class TestPointInCommune:
    def test_a_point_inside(self):
        h = FakeHandler([BEETEBUERG], [])
        assert h.commune_at(49.5, 6.5) == "Beetebuerg"

    def test_a_point_outside_every_commune(self):
        h = FakeHandler([BEETEBUERG], [])
        assert h.commune_at(49.5, 7.5) == ""

    def test_the_right_one_of_several(self):
        h = FakeHandler([BEETEBUERG, MAMER], [])
        assert h.commune_at(49.5, 8.5) == "Mamer"

    def test_the_bounding_box_does_not_decide_alone(self):
        """An L-shaped commune: inside the box, outside the polygon."""
        ring = [(6.0, 49.0), (7.0, 49.0), (7.0, 49.5), (6.5, 49.5), (6.5, 50.0), (6.0, 50.0)]
        h = FakeHandler([("L", (6.0, 49.0, 7.0, 50.0), [ring])], [])
        assert h.commune_at(49.2, 6.8) == "L"     # in the foot
        assert h.commune_at(49.8, 6.8) == ""      # in the notch


class TestNaming:
    def run(self, records, communes=(BEETEBUERG,)):
        h = FakeHandler(list(communes), records)
        osm_ingest._assign_communes(h)
        return h.records

    def test_an_unnamed_place_gains_its_commune(self):
        out = self.run([place(49.5, 6.5, "Spillplaz", named=False)])
        assert out[0]["name"] == "Spillplaz, Beetebuerg"
        assert out[0]["commune"] == "Beetebuerg"

    def test_a_named_place_keeps_its_name(self):
        """"Parc Merveilleux" must not become "Parc Merveilleux, Beetebuerg"."""
        out = self.run([place(49.5, 6.5, "Parc Merveilleux", named=True)])
        assert out[0]["name"] == "Parc Merveilleux"
        assert out[0]["commune"] == "Beetebuerg"

    def test_a_place_outside_every_commune_is_left_alone(self):
        out = self.run([place(49.5, 99.0, "Spillplaz", named=False)])
        assert out[0]["name"] == "Spillplaz"
        assert out[0]["commune"] == ""

    def test_records_without_coordinates_survive(self):
        rec = {"lat": None, "lng": None, "name": "Wanderwee", "named": True, "commune": ""}
        out = self.run([rec])
        assert out[0]["name"] == "Wanderwee"

    def test_two_unnamed_places_in_different_communes_differ(self):
        out = self.run(
            [place(49.5, 6.5, "Spillplaz", named=False), place(49.5, 8.5, "Spillplaz", named=False)],
            communes=(BEETEBUERG, MAMER),
        )
        assert {r["name"] for r in out} == {"Spillplaz, Beetebuerg", "Spillplaz, Mamer"}

    def test_no_boundaries_means_no_renaming(self):
        """Better an ambiguous list than "Spillplaz, " with nothing after it."""
        h = FakeHandler([], [place(49.5, 6.5, "Spillplaz", named=False)])
        osm_ingest._assign_communes(h)
        assert h.records[0]["name"] == "Spillplaz"


class TestCategoriesThatNeedAName:
    """Where the name *is* the destination, an unnamed match is a fragment."""

    def test_the_ones_that_demand_one(self):
        from osm_taxonomy import CATEGORIES
        for kind in ("castle", "zoo", "horse", "lake"):
            assert CATEGORIES[kind].get("require_name"), kind

    def test_generic_places_do_not(self):
        # A playground is interchangeable: you go to the nearest one, and the
        # commune plus the distance is enough to tell them apart.
        from osm_taxonomy import CATEGORIES
        for kind in ("playground", "picnic", "park", "bbq"):
            assert not CATEGORIES[kind].get("require_name"), kind

    def test_an_animal_enclosure_is_not_a_zoo(self):
        """attraction=animal tags one exhibit inside an attraction."""
        match, _, _ = osm_ingest._compile_category("zoo")
        assert match({"tourism": "zoo"})
        assert not match({"attraction": "animal", "name": "Molukkenkakadu"})
