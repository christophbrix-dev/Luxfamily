"""Importer behaviour: batched dedup, idempotency, concurrency, isolation."""
import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest

TODAY = datetime.now(timezone.utc).date()

BASE_SOURCE = {
    "id": "src-1", "name": "Test source", "kind": "ical", "active": True,
    "url": "https://example.invalid/feed.ics",
    "canton_default": "Luxembourg", "town_default": "Luxembourg",
    "category_default": ["Culture"], "lat_default": 49.6, "lng_default": 6.1,
}


@pytest.fixture
def importers(app_module):
    import importers as mod

    return mod


@pytest.fixture
def db(app_module):
    return app_module.db


def feed(payload):
    """Stub _fetch so no test ever touches the network."""

    async def _fetch(url, timeout=30.0):
        return payload

    return _fetch


def make_ics(n, uid=lambda i: f"uid-{i}", start=lambda i: TODAY + timedelta(days=i + 1)):
    parts = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//test//EN"]
    for i in range(n):
        parts += [
            "BEGIN:VEVENT",
            f"UID:{uid(i)}",
            f"DTSTART:{start(i):%Y%m%d}T100000Z",
            f"DTEND:{start(i):%Y%m%d}T120000Z",
            f"SUMMARY:Concert {i}",
            f"DESCRIPTION:About concert {i}",
            "LOCATION:Luxembourg City",
            "END:VEVENT",
        ]
    parts.append("END:VCALENDAR")
    return "\r\n".join(parts).encode()


def test_ical_import_maps_fields(importers, db, run, monkeypatch):
    monkeypatch.setattr(importers, "_fetch", feed(make_ics(20)))
    inserted, _ = run(importers._import_ical(BASE_SOURCE, db))
    assert inserted == 20

    doc = run(db.events.find_one({"external_id": "uid-3"}))
    assert doc["title"]["en"] == "Concert 3"
    assert doc["time"] == "10:00 - 12:00"
    assert doc["source_id"] == "src-1"


def test_reimporting_the_same_feed_changes_nothing(importers, db, run, monkeypatch):
    monkeypatch.setattr(importers, "_fetch", feed(make_ics(20)))
    run(importers._import_ical(BASE_SOURCE, db))
    inserted, skipped = run(importers._import_ical(BASE_SOURCE, db))

    assert inserted == 0
    assert skipped == 20
    assert run(db.events.count_documents({})) == 20


def test_dedup_costs_one_query_not_one_per_row(importers, db, run, monkeypatch):
    """The old importer ran a find_one per candidate — 500 for a 500-row feed."""
    monkeypatch.setattr(importers, "_fetch", feed(make_ics(50)))

    calls = {"n": 0}
    original = db.events.find_one

    async def counting(*a, **k):
        calls["n"] += 1
        return await original(*a, **k)

    monkeypatch.setattr(db.events, "find_one", counting)
    run(importers._import_ical(BASE_SOURCE, db))
    assert calls["n"] == 0


def test_duplicate_ids_within_one_feed_collapse(importers, db, run, monkeypatch):
    monkeypatch.setattr(importers, "_fetch", feed(make_ics(6, uid=lambda i: "same")))
    inserted, skipped = run(importers._import_ical(BASE_SOURCE, db))
    assert inserted == 1
    assert skipped == 5


def test_dedup_is_scoped_to_one_source(importers, db, run, monkeypatch):
    """Two sources may legitimately carry the same external id."""
    monkeypatch.setattr(importers, "_fetch", feed(make_ics(5)))
    run(importers._import_ical(BASE_SOURCE, db))
    inserted, _ = run(importers._import_ical({**BASE_SOURCE, "id": "src-2"}, db))
    assert inserted == 5


def test_past_events_are_skipped(importers, db, run, monkeypatch):
    old = make_ics(3, start=lambda i: TODAY - timedelta(days=30 + i))
    monkeypatch.setattr(importers, "_fetch", feed(old))
    inserted, skipped = run(importers._import_ical(BASE_SOURCE, db))
    assert inserted == 0
    assert skipped == 3


def test_sources_are_crawled_concurrently(importers, db, run, monkeypatch):
    async def slow(url, timeout=30.0):
        await asyncio.sleep(0.3)
        return make_ics(1)

    monkeypatch.setattr(importers, "_fetch", slow)

    async def _go():
        await db.sources.insert_many(
            [{**BASE_SOURCE, "id": f"s{i}", "name": f"S{i}"} for i in range(4)]
        )
        started = time.monotonic()
        results = await importers.run_all_active(db)
        return results, time.monotonic() - started

    results, elapsed = run(_go())
    assert len(results) == 4
    assert elapsed < 1.0, f"ran sequentially ({elapsed:.2f}s for 4x0.3s)"


def test_one_failing_source_does_not_abort_the_run(importers, db, run, monkeypatch):
    async def boom(url, timeout=30.0):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(importers, "_fetch", boom)

    async def _go():
        await db.sources.insert_many(
            [{**BASE_SOURCE, "id": f"s{i}", "name": f"S{i}"} for i in range(3)]
        )
        results = await importers.run_all_active(db)
        return results, await db.sources.find_one({"id": "s1"})

    results, stored = run(_go())
    assert len(results) == 3
    assert all(r["last_status"] == "error" for r in results)
    assert "connection refused" in stored["last_error"]


def test_only_one_worker_may_hold_the_importer_lease(app_module, run):
    """Every uvicorn worker starts its own scheduler; only one may crawl."""

    async def _go():
        first = await app_module._acquire_importer_lease(app_module.db)
        second = await app_module._acquire_importer_lease(app_module.db)
        await app_module._release_importer_lease(app_module.db)
        third = await app_module._acquire_importer_lease(app_module.db)
        return first, second, third

    assert run(_go()) == (True, False, True)


def test_run_all_returns_immediately(app_module, client, run, admin_headers):
    """Inline it could take minutes and trip the gateway timeout."""
    r = run(client.post("/api/admin/sources/run-all", headers=admin_headers))
    assert r.status_code == 202
    assert r.json()["status"] == "started"
