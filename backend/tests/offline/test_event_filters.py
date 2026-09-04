"""The filters the app was applying to whatever it happened to have.

Until now `/api/events` accepted `canton`, `upcoming`, `limit` and `skip`, and
nothing else. Everything else — category, age, indoor/outdoor, the three
family-needs switches, the search box — ran in the app, over the 200 events it
had downloaded out of 479. Choosing "Playgrounds" searched 200 rows; whether
the one Playgrounds event was among them depended on its date.

Worse, FastAPI drops unknown query parameters without a word, so
`?category=Playgrounds` was answered with the unfiltered list. A filter that
silently does nothing is harder to notice than one that errors.

Two of the rules here are easy to build backwards, and both are quiet when
wrong, so they get the most tests: the family-needs switches must only ever
narrow, and ages must overlap rather than be contained.
"""
from datetime import date, timedelta

import pytest

TODAY = date.today()


def _event(n, **over):
    doc = {
        "id": f"e{n}",
        # en/de/fr, no lb: that is the backend's LocalizedString, and no
        # stored event has ever carried a Luxembourgish title. The app
        # translates its own interface; event text stays in the source's
        # language.
        "title": {"en": f"Event {n}", "de": f"Event {n}", "fr": f"Event {n}"},
        "short": {"en": "", "de": "", "fr": ""},
        "type": "Outdoor",
        "canton": "Luxembourg",
        "town": "Luxembourg",
        "category": ["Culture"],
        "age_min": 0, "age_max": 99, "age_source": "unknown",
        "start_date": (TODAY + timedelta(days=n)).isoformat(),
        "end_date": None, "time": "",
        "price_adult": None, "price_child": None,
        "price_free": False, "price_source": "unknown",
        "image": "", "lat": 49.6, "lng": 6.1,
        "featured": False, "published": True, "rating": 4.5, "view_count": 0,
        "accessibility_wheelchair": False,
        "sensory_friendly": False,
        "free_parking": False,
    }
    doc.update(over)
    return doc


@pytest.fixture
def seeded(app_module, run):
    """Twelve events with a deliberate spread across every filter."""
    docs = [
        _event(1, category=["Playgrounds"], town="Esch-sur-Alzette"),
        _event(2, category=["Culture", "Festivals"]),
        _event(3, category=["Workshops"], type="Indoor"),
        _event(4, category=["Nature"], canton="Diekirch"),
        _event(5, age_min=0, age_max=3),
        _event(6, age_min=4, age_max=10),
        _event(7, age_min=12, age_max=99),
        _event(8, accessibility_wheelchair=True),
        _event(9, sensory_friendly=True),
        _event(10, free_parking=True),
        _event(11, title={"en": "Kayak day", "de": "Kajaktag", "fr": "Kayak"}),
        _event(12, town="Wiltz"),
    ]
    run(app_module.db.events.insert_many(docs))
    return app_module.db


async def _ids(client, query=""):
    # Used without `async with`: several tests ask more than once, and the
    # shared client refuses to be entered twice. ASGITransport keeps no
    # connection pool, so there is nothing to open or close.
    r = await client.get(f"/api/events{query}")
    assert r.status_code == 200, r.text
    return {e["id"] for e in r.json()}, r.headers.get("X-Total-Count")


class TestCategory:
    def test_it_is_no_longer_ignored(self, seeded, client, run):
        ids, _ = run(_ids(client, "?category=Playgrounds"))
        assert ids == {"e1"}

    def test_several_categories_are_an_or(self, seeded, client, run):
        ids, _ = run(_ids(client, "?category=Playgrounds&category=Nature"))
        assert ids == {"e1", "e4"}

    def test_an_event_matches_on_any_of_its_own(self, seeded, client, run):
        """e2 is Culture *and* Festivals; asking for either finds it."""
        ids, _ = run(_ids(client, "?category=Festivals"))
        assert "e2" in ids

    def test_a_category_nobody_has_returns_nothing_not_everything(
        self, seeded, client, run
    ):
        """The old behaviour: unknown parameter dropped, full list returned."""
        ids, total = run(_ids(client, "?category=Nonesuch"))
        assert ids == set()
        assert total == "0"


class TestTheFamilyNeedsSwitches:
    """Off must mean "do not care", never "only the ones without"."""

    @pytest.mark.parametrize(
        "param,expected",
        [("wheelchair=true", "e8"), ("sensory=true", "e9"), ("free_parking=true", "e10")],
    )
    def test_on_narrows_to_the_ones_that_have_it(self, seeded, client, run, param, expected):
        ids, _ = run(_ids(client, f"?{param}"))
        assert ids == {expected}

    @pytest.mark.parametrize(
        "param", ["wheelchair=false", "sensory=false", "free_parking=false"]
    )
    def test_off_hides_nothing_at_all(self, seeded, client, run, param):
        """The failure that would be quiet.

        Read as an exclusion, a switch left alone would remove almost the whole
        calendar — and the app's switches are off by default, so it would
        happen on the first screen every user sees.
        """
        ids, _ = run(_ids(client, f"?{param}"))
        assert len(ids) == 12

    def test_absent_is_the_same_as_off(self, seeded, client, run):
        with_flag, _ = run(_ids(client, "?wheelchair=false"))
        without, _ = run(_ids(client, ""))
        assert with_flag == without


class TestAgeOverlaps:
    def test_a_range_meets_a_wider_one(self, seeded, client, run):
        """0–3 must find the 0–99 events, which is most of the database."""
        ids, _ = run(_ids(client, "?age_min=0&age_max=3"))
        assert "e5" in ids and "e1" in ids

    def test_it_does_not_reach_a_range_that_starts_later(self, seeded, client, run):
        ids, _ = run(_ids(client, "?age_min=0&age_max=3"))
        assert "e6" not in ids, "4–10 does not overlap 0–3"
        assert "e7" not in ids, "12–99 does not overlap 0–3"

    def test_the_middle_band_finds_the_middle_event(self, seeded, client, run):
        ids, _ = run(_ids(client, "?age_min=4&age_max=6"))
        assert "e6" in ids
        assert "e5" not in ids and "e7" not in ids

    def test_touching_at_one_year_counts_as_overlapping(self, seeded, client, run):
        ids, _ = run(_ids(client, "?age_min=3&age_max=4"))
        assert "e5" in ids, "0–3 touches 3"
        assert "e6" in ids, "4–10 touches 4"


class TestTheRest:
    def test_indoor_outdoor(self, seeded, client, run):
        ids, _ = run(_ids(client, "?type=Indoor"))
        assert ids == {"e3"}

    def test_canton_still_works(self, seeded, client, run):
        ids, _ = run(_ids(client, "?canton=Diekirch"))
        assert ids == {"e4"}

    def test_the_search_box_covers_title_and_town(self, seeded, client, run):
        by_title, _ = run(_ids(client, "?q=Kajak"))
        by_town, _ = run(_ids(client, "?q=Wiltz"))
        assert by_title == {"e11"}
        assert by_town == {"e12"}

    def test_the_search_is_case_insensitive(self, seeded, client, run):
        ids, _ = run(_ids(client, "?q=wiltz"))
        assert ids == {"e12"}

    def test_a_regex_metacharacter_is_text_and_not_a_pattern(self, seeded, client, run):
        """Caller-supplied text going into a regex.

        Unescaped, "(" is a 500 and ".*" is a way to make the database work
        hard on request.
        """
        ids, _ = run(_ids(client, "?q=(unclosed"))
        assert ids == set()

        dotstar, _ = run(_ids(client, "?q=.%2A"))
        assert dotstar == set(), "a literal '.*' matches no title we hold"

    def test_a_date_window(self, seeded, client, run):
        frm = (TODAY + timedelta(days=2)).isoformat()
        to = (TODAY + timedelta(days=4)).isoformat()
        ids, _ = run(_ids(client, f"?date_from={frm}&date_to={to}"))
        assert ids == {"e2", "e3", "e4"}

    def test_a_malformed_date_is_refused_rather_than_ignored(self, seeded, client, run):
        async def go():
            return await client.get("/api/events?date_from=morgen")
        assert run(go()).status_code == 422

    def test_filters_combine_as_and_not_or(self, seeded, client, run):
        """e4 is the only Nature event and the only one in Diekirch."""
        both, _ = run(_ids(client, "?category=Nature&canton=Diekirch"))
        assert both == {"e4"}

        # Same two filters, one of them now excluding it. An OR would still
        # return e4 here, and a great deal else besides.
        contradictory, _ = run(_ids(client, "?category=Nature&canton=Luxembourg"))
        assert contradictory == set()


class TestPagingIsUsable:
    def test_the_total_counts_the_filtered_set_not_the_page(self, seeded, client, run):
        _, total = run(_ids(client, "?limit=5"))
        assert total == "12", "the header has to describe what is being paged"

    def test_the_total_respects_the_filter(self, seeded, client, run):
        _, total = run(_ids(client, "?category=Playgrounds"))
        assert total == "1"

    def test_pages_do_not_overlap_and_cover_everything(self, seeded, client, run):
        first, _ = run(_ids(client, "?limit=5&skip=0"))
        second, _ = run(_ids(client, "?limit=5&skip=5"))
        third, _ = run(_ids(client, "?limit=5&skip=10"))
        assert not (first & second) and not (second & third)
        assert len(first | second | third) == 12
