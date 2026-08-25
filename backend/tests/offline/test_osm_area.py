# Sizing a polygon, and the category that needs it.
#
# Luxembourg's bathing lakes carry natural=water + water=lake and nothing else
# — no swimming_area, no beach — so the water category never matched one and
# the Lac d'Echternach was missing from an app about family outings in
# Luxembourg. Matching water=lake alone is no better: 3,110 unnamed ponds sit
# inside the country's bounding box. Name plus size is what separates a lake
# people drive to from a storm basin called "A2".

import math

from osm_ingest import polygon_area_m2, _compile_category
from osm_taxonomy import CATEGORIES


def square(lat, lon, metres):
    """A square of the given side, as a lon/lat ring."""
    dlat = metres / 110_540
    dlon = metres / (111_320 * math.cos(math.radians(lat)))
    return [(lon, lat), (lon + dlon, lat), (lon + dlon, lat + dlat), (lon, lat + dlat)]


class TestPolygonArea:
    def test_a_hundred_metre_square_is_a_hectare(self):
        area = polygon_area_m2(square(49.6, 6.1, 100))
        assert abs(area - 10_000) < 100          # within 1%

    def test_winding_direction_does_not_matter(self):
        ring = square(49.6, 6.1, 100)
        assert abs(polygon_area_m2(ring) - polygon_area_m2(ring[::-1])) < 1

    def test_degenerate_rings_are_zero(self):
        assert polygon_area_m2([]) == 0.0
        assert polygon_area_m2([(6.1, 49.6)]) == 0.0
        assert polygon_area_m2([(6.1, 49.6), (6.2, 49.6)]) == 0.0

    def test_it_scales_with_the_square_of_the_side(self):
        small = polygon_area_m2(square(49.6, 6.1, 100))
        large = polygon_area_m2(square(49.6, 6.1, 200))
        assert abs(large / small - 4) < 0.05

    def test_the_threshold_separates_the_real_cases(self):
        """0.4 ha storm basin against a 30 ha lake — not a close call."""
        basin = polygon_area_m2(square(49.6, 6.1, 63))     # ~0.4 ha
        lake = polygon_area_m2(square(49.8, 6.4, 548))     # ~30 ha
        threshold = CATEGORIES["lake"]["min_area_m2"]
        assert basin < threshold < lake


class TestLakeCategory:
    def test_it_demands_a_name_and_a_size(self):
        cat = CATEGORIES["lake"]
        assert cat["require_name"] is True
        assert cat["min_area_m2"] > 0

    def test_reservoirs_stay_out(self):
        """At this size water=reservoir means the fenced basins at Vianden."""
        match, _, _ = _compile_category("lake")
        assert match({"natural": "water", "water": "lake"})
        assert not match({"natural": "water", "water": "reservoir"})
        assert not match({"natural": "water", "water": "pond"})

    def test_a_sized_category_is_recognised_as_one(self):
        _, _, min_area = _compile_category("lake")
        assert min_area == 20_000

    def test_ordinary_categories_carry_no_size(self):
        """way() and relation() must keep handling everything else."""
        for kind in ("playground", "zoo", "museum"):
            if kind in CATEGORIES:
                _, _, min_area = _compile_category(kind)
                assert min_area == 0
