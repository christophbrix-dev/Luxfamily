"""Event endpoints: list projection, pagination, caching, view counting."""
from datetime import datetime, timedelta, timezone

TODAY = datetime.now(timezone.utc).date()

# Every field the list screens read — events.tsx, explore.tsx and the admin
# list. Dropping one of these from EventSummary silently breaks a screen, so the
# set is asserted rather than assumed.
NEEDED_BY_LIST_SCREENS = {
    "accessibility_wheelchair", "age_max", "age_min", "canton", "category",
    "featured", "free_parking", "id", "image", "lat", "lng", "published",
    "sensory_friendly", "short", "source_name", "start_date", "time", "title",
    "town", "type", "view_count",
}

# Long localized prose that belongs only on the detail endpoint — this is the
# bulk of what the list used to carry.
DETAIL_ONLY = (
    "description", "accessibility", "weather_fit", "price_label",
    "preparation_tips", "sensory_notes", "parking", "opening_hours", "website_url",
)


def make_event(i, featured=False, published=True):
    short = {"en": f"Event {i}", "de": f"Termin {i}", "fr": f"Sortie {i}"}
    long = {k: v * 40 for k, v in short.items()}
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": f"ev-{i:03d}", "title": short, "short": short, "description": long,
        "type": "Event", "canton": "Esch" if i % 2 else "Luxembourg", "town": f"Town {i}",
        "category": ["Culture"], "age_min": 0, "age_max": 99,
        "start_date": (TODAY + timedelta(days=i + 1)).isoformat(),
        "end_date": None, "time": "10:00", "price_adult": 0.0, "price_child": 0.0,
        "price_label": short, "accessibility": long, "weather_fit": long,
        "image": "https://example.com/i.jpg", "lat": 49.6, "lng": 6.1,
        "bookable": False, "published": published, "rating": 4.5,
        "featured": featured, "featured_until": None, "view_count": i,
        "website_url": "https://example.com/x", "payment_methods": [],
        "sensory_notes": long, "parking": long, "food_onsite": long,
        "preparation_tips": long, "opening_hours": long, "peak_hours": long,
        "accessibility_wheelchair": False, "sensory_friendly": False,
        "free_parking": True, "food_allowed": True, "changing_facilities": False,
        "restrooms": True, "source_name": "Feed A",
        "created_at": now, "updated_at": now, "created_by": None,
    }


def seed(app_module, run, count=120, drafts=1):
    async def _seed():
        docs = [make_event(i, featured=(i < 3)) for i in range(count)]
        docs += [make_event(900 + n, published=False) for n in range(drafts)]
        await app_module.db.events.insert_many(docs)

    run(_seed())


def get(client, run, path, **kw):
    return run(client.get(path, **kw))


def test_list_carries_every_field_the_screens_read(app_module, client, run):
    seed(app_module, run)
    row = get(client, run, "/api/events").json()[0]
    assert not NEEDED_BY_LIST_SCREENS - set(row)


def test_list_omits_detail_only_prose(app_module, client, run):
    seed(app_module, run)
    row = get(client, run, "/api/events").json()[0]
    assert [f for f in DETAIL_ONLY if f in row] == []


def test_list_is_paginated_and_reports_the_total(app_module, client, run):
    seed(app_module, run)
    r = get(client, run, "/api/events?limit=10&skip=0")
    assert len(r.json()) == 10
    assert r.headers["X-Total-Count"] == "120"
    second = get(client, run, "/api/events?limit=10&skip=10")
    assert {e["id"] for e in r.json()}.isdisjoint({e["id"] for e in second.json()})


def test_limit_is_capped(app_module, client, run):
    # An unbounded limit let one request scan and serialize the collection.
    seed(app_module, run, count=5)
    assert get(client, run, "/api/events?limit=1000000").status_code == 422


def test_unpublished_events_stay_hidden(app_module, client, run):
    seed(app_module, run, count=5, drafts=2)
    listed = get(client, run, "/api/events").json()
    assert all(not e["id"].startswith("ev-9") for e in listed)
    assert get(client, run, "/api/events/ev-900").status_code == 404


def test_featured_events_sort_first(app_module, client, run):
    seed(app_module, run)
    rows = get(client, run, "/api/events?limit=10").json()
    assert [e["featured"] for e in rows[:3]] == [True, True, True]
    assert not rows[3]["featured"]


def test_canton_filter(app_module, client, run):
    seed(app_module, run)
    assert all(e["canton"] == "Esch" for e in get(client, run, "/api/events?canton=Esch").json())


def test_etag_lets_clients_revalidate_cheaply(app_module, client, run):
    seed(app_module, run, count=20)

    async def _go():
        first = await client.get("/api/events")
        again = await client.get(
            "/api/events", headers={"If-None-Match": first.headers["ETag"]}
        )
        stale = await client.get("/api/events", headers={"If-None-Match": '"nope"'})
        return first, again, stale

    first, again, stale = run(_go())
    assert first.headers["ETag"]
    assert again.status_code == 304 and again.content == b""
    assert stale.status_code == 200


def test_etag_is_stable_across_content_encodings(app_module, client, run):
    """ETag hashes the raw JSON, so gzip and identity clients agree on it."""
    seed(app_module, run, count=20)

    async def _go():
        gz = await client.get("/api/events", headers={"Accept-Encoding": "gzip"})
        plain = await client.get("/api/events", headers={"Accept-Encoding": "identity"})
        return gz, plain

    gz, plain = run(_go())
    assert gz.headers.get("content-encoding") == "gzip"
    assert not plain.headers.get("content-encoding")
    assert gz.headers["ETag"] == plain.headers["ETag"]


def test_detail_still_carries_the_full_document(app_module, client, run):
    seed(app_module, run, count=5)
    body = get(client, run, "/api/events/ev-002").json()
    assert all(f in body for f in DETAIL_ONLY)


def test_repeated_views_from_one_ip_count_once(app_module, client, run):
    seed(app_module, run, count=5)

    async def _go():
        for _ in range(6):
            await client.post("/api/events/ev-002/view")
        return (await app_module.db.events.find_one({"id": "ev-002"}),
                await app_module.db.event_views.count_documents({}))

    doc, logged = run(_go())
    assert doc["view_count"] == 3  # seeded at 2, +1 for the whole deduped burst
    assert logged == 1


def test_concurrent_views_do_not_double_count(app_module, client, run):
    import asyncio

    seed(app_module, run, count=5)

    async def _go():
        await app_module.db.events.update_one({"id": "ev-003"}, {"$set": {"view_count": 0}})
        await asyncio.gather(*[client.post("/api/events/ev-003/view") for _ in range(10)])
        return await app_module.db.events.find_one({"id": "ev-003"})

    # find-then-insert let two concurrent requests both pass the check.
    assert run(_go())["view_count"] == 1


def test_view_log_row_is_ttl_able_and_pseudonymous(app_module, client, run):
    seed(app_module, run, count=5)

    async def _go():
        await client.post("/api/events/ev-001/view")
        return await app_module.db.event_views.find_one({})

    row = run(_go())
    # A TTL index only expires real date fields, never ISO strings.
    assert isinstance(row["viewed_at"], datetime)
    # sha256 prefix, not Python's per-process-salted hash().
    assert len(row["ip_hash"]) == 16


def test_views_for_unknown_events_are_not_logged(app_module, client, run):
    seed(app_module, run, count=3)

    async def _go():
        await client.post("/api/events/no-such-event/view")
        return await app_module.db.event_views.count_documents({})

    assert run(_go()) == 0


def test_admin_list_is_summaries_and_paginated(app_module, client, run, admin_headers):
    seed(app_module, run, count=30)
    r = get(client, run, "/api/admin/events", headers=admin_headers)
    assert r.status_code == 200
    assert "description" not in r.json()[0]
    assert r.headers["X-Total-Count"] == "31"


def test_admin_detail_endpoint_returns_the_full_document(
    app_module, client, run, admin_headers
):
    seed(app_module, run, count=5)
    r = get(client, run, "/api/admin/events/ev-002", headers=admin_headers)
    assert r.status_code == 200
    assert all(f in r.json() for f in DETAIL_ONLY)


def test_admin_endpoints_require_auth(app_module, client, run):
    seed(app_module, run, count=3)
    for path in ("/api/admin/events", "/api/admin/events/ev-001",
                 "/api/admin/analytics/overview", "/api/admin/sources"):
        assert get(client, run, path).status_code == 401, path


def test_analytics_counts_match(app_module, client, run, admin_headers):
    seed(app_module, run, count=20, drafts=3)
    a = get(client, run, "/api/admin/analytics/overview", headers=admin_headers).json()
    assert a["total_events"] == 23
    assert a["published"] == 20
    assert a["drafts"] == 3
    assert a["featured"] == 3
    assert len(a["top_events"]) == 5
