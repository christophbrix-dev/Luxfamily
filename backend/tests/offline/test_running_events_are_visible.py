"""An event is over when it ends, not the day after it begins.

`upcoming` meant `start_date >= today`. For a concert that is the same thing.
For the 135 multi-day entries it is not, and the ones it got wrong were exactly
the ones a family planning a weekend wants: "Mount vum Bongert 2026" runs the
whole of October, the Actionbound trail in Reisdorf likewise, "Rollblitzverleih"
from the end of August to the end of October. On the day this was written nine
events were running in Luxembourg and the app showed none of them — one had
been invisible since August.

Nothing failed when the rule changed, because `upcoming` had no test at all.
It was named once, in a docstring, in a file about other filters. These are
that missing coverage, written against the rule rather than the implementation:
a reader should be able to check each case against a calendar.

The second rule here is the honest one. 299 of 1,435 events carry a start date
and nothing else, so for those "has it finished?" cannot be answered from the
data — only guessed. Three days is the guess, and it is a separate clause
rather than a fudge inside the comparison, so it can be found and changed.
"""
from datetime import date, timedelta

import pytest

import server

TODAY = date.today()


def _d(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _matches(doc: dict) -> bool:
    """Evaluate the clause the way Mongo would, on one document.

    Hand-evaluated rather than run through mongomock so the test states the
    rule in the open: anyone reading it can see what is being asked of a
    document, instead of trusting a second database engine to agree with the
    first.
    """
    clause = server._still_current(TODAY.isoformat())
    for alternative in clause["$or"]:
        if all(_field_matches(doc, field, cond) for field, cond in alternative.items()):
            return True
    return False


def _field_matches(doc: dict, field: str, cond) -> bool:
    value = doc.get(field)
    if cond is None:
        return value is None
    return value is not None and value >= cond["$gte"]


class TestSomethingWithAStatedEnd:
    def test_a_future_event_is_shown(self):
        assert _matches({"start_date": _d(5), "end_date": _d(5)})

    def test_an_event_running_today_is_shown(self):
        """The case the old rule got wrong: began before today, ends later."""
        assert _matches({"start_date": _d(-2), "end_date": _d(1)})

    def test_a_month_long_event_is_shown_on_its_last_day(self):
        """Mount vum Bongert: 1–31 October, invisible for 30 of its 31 days."""
        assert _matches({"start_date": _d(-30), "end_date": _d(0)})

    def test_one_that_started_in_august_and_runs_into_november_is_shown(self):
        """Rollblitzverleih. The longest-standing of the nine."""
        assert _matches({"start_date": _d(-75), "end_date": _d(20)})

    def test_one_that_ended_yesterday_is_gone(self):
        """No grace here. We were told when it ends, so there is nothing to be
        unsure about — and a parent cannot go to it any more."""
        assert not _matches({"start_date": _d(-4), "end_date": _d(-1)})

    def test_one_that_ended_last_week_is_gone(self):
        assert not _matches({"start_date": _d(-10), "end_date": _d(-8)})

    def test_the_last_day_is_the_last_day_it_shows(self):
        assert _matches({"start_date": _d(-9), "end_date": _d(0)})

    def test_the_grace_does_not_reach_a_stated_end(self):
        """Granting these the same three days put 106 finished events back in
        the list — one row in seven. The window is for uncertainty, not for
        the past."""
        assert not _matches({"start_date": _d(-9), "end_date": _d(-1)})
        assert not _matches({"start_date": _d(-9), "end_date": _d(-server.GRACE_DAYS)})


class TestSomethingWithNoStatedEnd:
    """299 events are in this shape. Nothing here can be known, only assumed."""

    def test_a_future_event_is_shown(self):
        assert _matches({"start_date": _d(3), "end_date": None})

    def test_todays_event_is_shown(self):
        assert _matches({"start_date": _d(0), "end_date": None})

    def test_one_from_two_days_ago_is_shown(self):
        """What was asked for: on day 3 you can still see it started on day 1."""
        assert _matches({"start_date": _d(-2), "end_date": None})

    def test_the_grace_boundary_is_included(self):
        assert _matches({"start_date": _d(-server.GRACE_DAYS), "end_date": None})

    def test_one_day_past_the_boundary_is_not(self):
        assert not _matches({"start_date": _d(-server.GRACE_DAYS - 1), "end_date": None})

    def test_a_missing_field_counts_as_no_end(self):
        """Mongo treats a null equality as matching an absent field, and so
        must this — otherwise an older document falls out of the list for a
        reason that has nothing to do with its dates."""
        assert _matches({"start_date": _d(-1)})


class TestTheGraceIsNamedAndShort:
    def test_it_is_three_days(self):
        assert server.GRACE_DAYS == 3

    def test_it_is_a_separate_clause_not_a_fudge_in_the_comparison(self):
        """So that it can be found, read and changed — the end-date rule is
        knowledge, this one is an assumption, and they should not look alike."""
        alternatives = server._still_current(TODAY.isoformat())["$or"]
        assert len(alternatives) == 2
        assert sum("end_date" in a and a["end_date"] is None for a in alternatives) == 1


class TestThroughTheEndpoint:
    @pytest.fixture
    def seeded(self, app_module, run):
        def ev(n, start, end):
            return {
                "id": n,
                "title": {"en": n, "de": n, "fr": n},
                "short": {"en": "", "de": "", "fr": ""},
                "type": "Outdoor", "canton": "Luxembourg", "town": "Luxembourg",
                "category": ["Culture"], "age_min": 0, "age_max": 99,
                "age_source": "unknown", "start_date": start, "end_date": end,
                "time": "", "price_adult": None, "price_child": None,
                "price_free": False, "price_source": "unknown", "image": "",
                "lat": 49.6, "lng": 6.1, "featured": False, "published": True,
                "rating": 4.5, "view_count": 0,
                "accessibility_wheelchair": False, "sensory_friendly": False,
                "free_parking": False,
            }
        run(app_module.db.events.insert_many([
            ev("future",      _d(5),   _d(5)),
            ev("running",     _d(-20), _d(10)),
            ev("just_ended",  _d(-6),  _d(-1)),
            ev("long_over",   _d(-30), _d(-20)),
            ev("no_end_new",  _d(-1),  None),
            ev("no_end_old",  _d(-9),  None),
        ]))
        return app_module.db

    async def _ids(self, client, query=""):
        r = await client.get(f"/api/events{query}")
        assert r.status_code == 200, r.text
        return {e["id"] for e in r.json()}

    def test_the_default_list_shows_what_has_not_finished(self, seeded, client, run):
        assert run(self._ids(client)) == {"future", "running", "no_end_new"}

    def test_one_whose_stated_end_has_passed_is_not_there(self, seeded, client, run):
        """`just_ended` finished yesterday and says so."""
        assert "just_ended" not in run(self._ids(client))

    def test_the_running_one_is_there(self, seeded, client, run):
        """The whole point. It started 20 days ago and runs for 10 more."""
        assert "running" in run(self._ids(client))

    def test_the_long_finished_one_is_not(self, seeded, client, run):
        assert "long_over" not in run(self._ids(client))

    def test_an_explicit_window_still_reaches_the_past(self, seeded, client, run):
        """A date range is somebody asking on purpose; it must not be overruled
        by "not over yet"."""
        ids = run(self._ids(client, f"?date_from={_d(-40)}&date_to={_d(-25)}"))
        assert ids == {"long_over"}

    def test_upcoming_false_still_shows_everything(self, seeded, client, run):
        assert len(run(self._ids(client, "?upcoming=false"))) == 6

    def test_the_total_count_agrees_with_the_rows(self, seeded, client, run):
        """X-Total-Count is counted with the same query, not estimated."""
        r = run(client.get("/api/events"))
        assert int(r.headers["X-Total-Count"]) == len(r.json())


class TestTheOrderOfTheList:
    """Letting running events in broke the order, and nothing would have said so.

    A thing that has been running since 31 August carries the earliest start
    date in the database. Sorted by start_date it therefore leads the list, and
    the app opened on an August date with today's events nine rows below. The
    sort key is now the first day an entry is still relevant seen from today.
    """

    @pytest.fixture
    def seeded(self, app_module, run):
        def ev(n, start, end, featured=False):
            return {
                "id": n,
                "title": {"en": n, "de": n, "fr": n},
                "short": {"en": "", "de": "", "fr": ""},
                "type": "Outdoor", "canton": "Luxembourg", "town": "Luxembourg",
                "category": ["Culture"], "age_min": 0, "age_max": 99,
                "age_source": "unknown", "start_date": start, "end_date": end,
                "time": "", "price_adult": None, "price_child": None,
                "price_free": False, "price_source": "unknown", "image": "",
                "lat": 49.6, "lng": 6.1, "featured": featured, "published": True,
                "rating": 4.5, "view_count": 0,
                "accessibility_wheelchair": False, "sensory_friendly": False,
                "free_parking": False,
            }
        run(app_module.db.events.insert_many([
            ev("in_a_week",   _d(7),   _d(7)),
            ev("since_august", _d(-44), _d(17)),
            ev("today",       _d(0),   _d(0)),
            ev("tomorrow",    _d(1),   _d(1)),
        ]))
        return app_module.db

    async def _order(self, client, query=""):
        r = await client.get(f"/api/events{query}")
        assert r.status_code == 200, r.text
        return [e["id"] for e in r.json()]

    def test_a_long_running_event_does_not_lead_the_list(self, seeded, client, run):
        """It is relevant today, not in August — so it sorts as today."""
        order = run(self._order(client))
        assert order.index("since_august") < order.index("tomorrow")
        assert order.index("today") < order.index("tomorrow")

    def test_what_starts_today_comes_before_what_has_run_for_weeks(self, seeded, client, run):
        """Both are on today; the new one is the news. Sorting the other way
        put an August date at row one, which is the complaint that started
        all this."""
        order = run(self._order(client))
        assert order.index("today") < order.index("since_august")

    def test_tomorrow_comes_before_next_week(self, seeded, client, run):
        order = run(self._order(client))
        assert order.index("tomorrow") < order.index("in_a_week")

    def test_featured_still_leads(self, seeded, client, run, app_module):
        run(app_module.db.events.update_one({"id": "in_a_week"}, {"$set": {"featured": True}}))
        assert run(self._order(client))[0] == "in_a_week"

    def test_the_sort_key_does_not_reach_the_client(self, seeded, client, run):
        """It is a pipeline detail; $project drops it."""
        r = run(client.get("/api/events"))
        assert all("_relevant_from" not in row for row in r.json())

    def test_paging_does_not_repeat_or_skip(self, seeded, client, run):
        """A changed sort is the classic way to break paging."""
        first = run(self._order(client, "?limit=2&skip=0"))
        second = run(self._order(client, "?limit=2&skip=2"))
        assert len(first) == 2 and len(second) == 2
        assert set(first) | set(second) == {"in_a_week", "since_august", "today", "tomorrow"}


class TestTheDayIsLuxembourgsDay:
    """Two clocks answering one question is one clock too many.

    "Today" was UTC on the server and the device's own calendar in the app.
    Between midnight and 01:00 or 02:00 Luxembourg time those are different
    days: the list still held yesterday's events while the app had already
    moved on, and labelled them as having started yesterday. Both answers were
    defensible; that is exactly what makes the disagreement hard to spot.
    """

    def test_the_list_uses_the_luxembourg_calendar(self):
        assert str(server.LOCAL_TZ) == "Europe/Luxembourg"

    def test_it_is_the_same_clock_the_importer_runs_on(self):
        """The scheduler has used Europe/Luxembourg since it was written."""
        import inspect
        assert "Europe/Luxembourg" in inspect.getsource(server.lifespan)

    def test_today_here_returns_a_plain_date(self):
        value = server.today_here()
        assert len(value) == 10 and value[4] == "-" and value[7] == "-"

    def test_nothing_in_the_list_path_still_reaches_for_utc(self):
        """The two call sites were replaced; this is what stops a third."""
        import inspect
        src = inspect.getsource(server.list_events)
        assert "timezone.utc" not in src
        assert "today_here()" in src
