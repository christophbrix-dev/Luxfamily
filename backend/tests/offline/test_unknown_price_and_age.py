"""Serving an event whose price and age were never stated.

This file exists because of a gap, not a feature. Storing None in price_adult
made both response models reject every row — they declared `price_adult:
float = 0.0` — and /api/events returned 500. The offline suite, which is what
CI runs, stayed green throughout: every fixture in it sets a price of 0.0, so
no test ever handed the endpoints the value the database now actually holds.

The endpoints also had to start carrying age_source, price_free and
price_source. Without them the "no age given" note in the app has nothing to
read and would silently never appear — the kind of failure that looks like a
design decision rather than a bug.

Both are asserted here through the real routes, so the next change to those
models has to keep them true.
"""
from datetime import datetime, timedelta, timezone

TODAY = datetime.now(timezone.utc).date()


def make_event(**over):
    """An event as the importers write one when the page stated nothing."""
    text = {"en": "Concert", "de": "Konzert", "fr": "Concert"}
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": "ev-unknown", "title": text, "short": text, "description": text,
        "type": "Event", "canton": "Luxembourg", "town": "Luxembourg",
        "category": ["Culture"],
        "age_min": 0, "age_max": 99, "age_source": "unknown",
        "start_date": (TODAY + timedelta(days=3)).isoformat(),
        "end_date": None, "time": "20:00",
        "price_adult": None, "price_child": None,
        "price_free": False, "price_source": "unknown",
        "price_label": {"en": "Price not stated", "de": "Kein Preis angegeben",
                        "fr": "Prix non indiqué"},
        "accessibility": text, "weather_fit": text,
        "image": "", "lat": 49.6, "lng": 6.1,
        "bookable": False, "published": True, "rating": 4.5,
        "featured": False, "featured_until": None, "view_count": 0,
        "website_url": "", "payment_methods": [],
        "sensory_notes": text, "parking": text, "food_onsite": text,
        "preparation_tips": text, "opening_hours": text, "peak_hours": text,
        "accessibility_wheelchair": False, "sensory_friendly": False,
        "free_parking": False, "food_allowed": True, "changing_facilities": False,
        "restrooms": True, "source_name": "Feed A",
        "created_at": now, "updated_at": now, "created_by": None,
    }
    doc.update(over)
    return doc


def seed(app_module, run, **over):
    run(app_module.db.events.insert_one(make_event(**over)))


def get(client, run, path):
    async def _go():
        async with client as c:
            return await c.get(path)
    return run(_go())


class TestTheListSurvivesAnUnknownPrice:
    def test_it_answers_at_all(self, app_module, client, run):
        """This is the request that returned 500."""
        seed(app_module, run)
        assert get(client, run, "/api/events").status_code == 200

    def test_the_price_comes_back_as_null_not_zero(self, app_module, client, run):
        seed(app_module, run)
        row = get(client, run, "/api/events").json()[0]
        assert row["price_adult"] is None
        assert row["price_child"] is None

    def test_a_stated_price_still_arrives(self, app_module, client, run):
        seed(app_module, run, price_adult=14.0, price_source="event")
        assert get(client, run, "/api/events").json()[0]["price_adult"] == 14.0

    def test_free_is_distinguishable_from_unknown(self, app_module, client, run):
        """Zero means free; null means nobody said. They were the same value."""
        seed(app_module, run, price_adult=0.0, price_free=True, price_source="event")
        row = get(client, run, "/api/events").json()[0]
        assert row["price_adult"] == 0.0 and row["price_free"] is True


class TestTheAppCanTellTheNoteToShow:
    def test_age_source_reaches_the_list(self, app_module, client, run):
        """Without it the "no age given" note can never appear."""
        seed(app_module, run)
        assert get(client, run, "/api/events").json()[0]["age_source"] == "unknown"

    def test_price_source_reaches_the_list(self, app_module, client, run):
        seed(app_module, run)
        assert get(client, run, "/api/events").json()[0]["price_source"] == "unknown"

    def test_a_stated_age_is_marked_as_stated(self, app_module, client, run):
        seed(app_module, run, age_min=6, age_max=12, age_source="event")
        row = get(client, run, "/api/events").json()[0]
        assert row["age_source"] == "event" and row["age_min"] == 6


class TestTheDetailEndpointToo:
    def test_it_answers(self, app_module, client, run):
        seed(app_module, run)
        assert get(client, run, "/api/events/ev-unknown").status_code == 200

    def test_it_carries_the_same_markers(self, app_module, client, run):
        seed(app_module, run)
        body = get(client, run, "/api/events/ev-unknown").json()
        assert body["age_source"] == "unknown"
        assert body["price_adult"] is None

    def test_price_label_uses_only_the_languages_the_model_accepts(
        self, app_module, client, run
    ):
        """A fourth key here returned 500 on every detail request.

        The backend's LocalizedString takes en/de/fr; the frontend requires lb
        and gets it from its own strings. A backfill wrote all four into
        price_label and broke the endpoint on a key nobody had declared.
        """
        seed(app_module, run)
        label = get(client, run, "/api/events/ev-unknown").json()["price_label"]
        assert set(label) <= {"en", "de", "fr"}
