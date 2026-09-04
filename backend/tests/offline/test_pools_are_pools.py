"""Seven public swimming pools were filed as splash pads.

Christoph asked whether the app has all of Luxembourg's swimming pools. It held
fourteen of the twenty-four OpenStreetMap knows by name — and seven of the
missing ten were not missing. They were in the database under
`water_playground`: AquaNat'Our, Piscine Piko, Piscine Plein-Air Dudelange,
Remich, Vianden, Freibad Troisvierges, the Réidener Schwämm. Anyone filtering
for "Schwämm" found none of them.

`leisure=water_park` sat in two categories. The first that matches wins, and
`water_playground` came first in the file.

The tag is genuinely ambiguous in Luxembourg: a named water_park is a public
pool, an unnamed one is the paddling area in a village park. So both categories
keep it, `swimming` goes first and declines the unnamed ones — which meant the
ingest also had to stop treating "declined" as "discarded".
"""
import pytest

from osm_taxonomy import CATEGORIES


class TestTheOrderIsLoadBearing:
    def test_swimming_is_asked_before_water_playground(self):
        order = list(CATEGORIES)
        assert order.index("swimming") < order.index("water_playground"), (
            "both claim leisure=water_park; whichever comes first takes the pools"
        )

    def test_both_still_claim_the_tag(self):
        """One alone is not enough: named and unnamed need different homes."""
        for kind in ("swimming", "water_playground"):
            assert '["leisure"="water_park"]' in CATEGORIES[kind]["filters"]

    def test_swimming_declines_the_unnamed_ones(self):
        assert CATEGORIES["swimming"].get("require_name") is True

    def test_a_paid_public_pool_is_not_treated_as_closed(self):
        """`access=customers` on a municipal pool means "pay at the gate"."""
        assert CATEGORIES["swimming"].get("allow_customers") is True


class TestDecliningIsNotDeciding:
    """The ingest used to drop what a category matched and then refused.

    An unnamed `leisure=water_park` was claimed by `swimming`, refused for
    having no name, and never offered to `water_playground` — so putting
    `swimming` first would have deleted the paddling pools instead of sorting
    them. The loop now stops only when a category actually takes the item.
    """

    def test_the_ingest_only_breaks_on_an_accepted_record(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[2] / "osm_ingest.py").read_text(
            encoding="utf-8")
        # Every `break` in the matching loops has to sit under `if rec:`.
        for loop in ("way", "relation"):
            marker = f'self._normalise(kind_key, "{loop}"'
            start = source.index(marker)
            window = source[start:start + 700]
            assert "if rec:" in window
            before_break = window[:window.index("break")]
            assert "if rec:" in before_break, (
                f"the {loop} loop can still break without having stored anything"
            )


class TestTheReclassifierReadsEveryFilterForm:
    """A constraint that cannot be read must not count as met.

    The first version of the re-filing script understood only `["k"="v"]` and
    silently ignored the rest, so
    `["amenity"="shelter"]["shelter_type"~"picnic_shelter|…"]` meant "any
    shelter at all" — and the dry run offered to refile a neolithic house as a
    picnic hut. The dry run is the only reason that never reached the database.
    """

    def _m(self, fragment, tags):
        from recategorise_places import _matches
        return _matches(fragment, tags)

    def test_equality(self):
        assert self._m('["leisure"="water_park"]', {"leisure": "water_park"})
        assert not self._m('["leisure"="water_park"]', {"leisure": "playground"})

    def test_two_clauses_both_have_to_hold(self):
        fragment = '["amenity"="shelter"]["shelter_type"~"picnic_shelter|weather_shelter"]'
        assert self._m(fragment, {"amenity": "shelter", "shelter_type": "picnic_shelter"})
        assert not self._m(fragment, {"amenity": "shelter"}), (
            "the second clause was dropped rather than applied"
        )
        assert not self._m(fragment, {"amenity": "shelter", "shelter_type": "bus_shelter"})

    def test_negated_regex(self):
        fragment = '["leisure"="garden"]["access"!~"^(private|no|customers)$"]'
        assert self._m(fragment, {"leisure": "garden"})
        assert self._m(fragment, {"leisure": "garden", "access": "yes"})
        assert not self._m(fragment, {"leisure": "garden", "access": "private"})

    def test_presence_only(self):
        assert self._m('["man_made"="tower"]["tower:type"]',
                       {"man_made": "tower", "tower:type": "observation"})
        assert not self._m('["man_made"="tower"]["tower:type"]', {"man_made": "tower"})


class TestClassifyingRealTags:
    def _c(self, tags):
        from recategorise_places import classify
        return classify(tags)

    @pytest.mark.parametrize("name", ["Réidener Schwämm", "Piscine de Remich"])
    def test_a_named_water_park_is_a_pool(self, name):
        assert self._c({"leisure": "water_park", "name": name}) == "swimming"

    def test_an_unnamed_one_is_a_water_playground(self):
        """The paddling pools at Biwer and Nommern, which have no OSM name."""
        assert self._c({"leisure": "water_park"}) == "water_playground"

    def test_a_paid_public_pool_survives(self):
        assert self._c({
            "leisure": "water_park", "name": "Piscine ouverte d'Oberkorn",
            "access": "customers",
        }) == "swimming"

    def test_a_genuinely_private_one_does_not(self):
        assert self._c({
            "leisure": "swimming_pool", "name": "Gaart", "access": "private",
        }) is None

    def test_an_unnamed_backyard_pool_is_still_nobody_s_business(self):
        """~1800 of these in OSM Luxembourg."""
        assert self._c({"leisure": "swimming_pool"}) is None
