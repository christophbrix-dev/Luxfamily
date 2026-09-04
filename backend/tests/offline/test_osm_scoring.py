# The family score decides which places surface first, so a rule that never
# fires or fires on the wrong value is invisible: nothing crashes, the ordering
# is just quietly wrong. These tests pin the two things that go wrong most
# easily — a tag key that does not exist, and a rule that ignores the value.

import re

from osm_ingest import compute_family_score
from osm_taxonomy import SCORE_RULES


def score(**tags):
    """Score a place against a base of 0, so the result is the bonus alone."""
    return compute_family_score(tags, 0)


class TestValueBlindRules:
    """A tag whose value is "no" states an absence. It must not earn points."""

    def test_baby_feeding_no_earns_nothing(self):
        assert score(baby_feeding="no") == 0

    def test_baby_feeding_yes_earns_points(self):
        assert score(baby_feeding="yes") > 0

    def test_baby_feeding_room_earns_points(self):
        # OSM also uses room / dedicated_room for this key.
        assert score(baby_feeding="room") > 0

    def test_presence_only_rules_sit_on_free_form_keys(self):
        """A rule with no value check scores the tag whatever it says.

        That is fine for a key whose value is free-form — a name, a URL, an
        age — where merely having the information is the signal. It is wrong
        for a yes/no key, where "no" states the facility is missing and would
        earn the same points as having it. baby_feeding was in the second
        group while being scored like the first.
        """
        free_form = {"name", "website", "opening_hours", "playground:theme", "max_age"}
        for key, pattern, delta in SCORE_RULES:
            if pattern is None and delta > 0:
                assert key in free_form, (
                    f"{key!r} is scored on presence alone. If it can be "
                    f'tagged "no", that absence earns +{delta}. Give it a '
                    "value_regex, or add it to free_form here."
                )


class TestToiletRules:
    """The POI has toilets, or the POI is one. Both should count."""

    def test_place_with_toilets(self):
        assert score(toilets="yes") > 0

    def test_place_that_is_a_toilet(self):
        # OSM spells this amenity=toilets. A key named "amenity:toilets" does
        # not exist; the rule used to look for one and never fired.
        assert score(amenity="toilets") > 0

    def test_toilets_explicitly_absent(self):
        assert score(toilets="no") == 0


class TestRuleTableIsLive:
    """Every rule must be able to fire, and every regex must compile."""

    def test_regexes_compile(self):
        for key, pattern, _ in SCORE_RULES:
            if pattern is not None:
                re.compile(pattern)  # raises if malformed

    def test_no_rule_uses_a_namespaced_key_that_cannot_exist(self):
        """`amenity:toilets` was dead for exactly this reason.

        OSM namespaces keys as prefix:detail (contact:phone, name:lb). A key
        of the form amenity:<value> is a value written where a key belongs,
        and tags.get() on it returns None forever.
        """
        for key, _, _ in SCORE_RULES:
            assert not key.startswith("amenity:"), (
                f"{key!r} looks like amenity=<value> written as a key; "
                "this rule can never fire"
            )


class TestPenalties:
    def test_private_access_is_heavily_penalised(self):
        # A place the public cannot enter should not outrank one it can.
        assert compute_family_score({"access": "private"}, 60) < 60

    def test_score_stays_within_bounds(self):
        assert compute_family_score({"access": "no"}, 10) >= 0
        assert compute_family_score({k: "yes" for k in
                                     ("name", "website", "opening_hours",
                                      "wheelchair", "toilets", "drinking_water",
                                      "shade", "baby_feeding",
                                      "changing_table")}, 100) <= 100
