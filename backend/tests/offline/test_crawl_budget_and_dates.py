"""Three things a full production run found that the suite did not.

All three had the same shape: the code was wrong in a way that only shows up
after a real crawl against real sites, and nothing here objected.

1. `importers.py` called `k.PAUSE_S` on two crawler modules that had stopped
   defining it. The pacing had moved into `polite_get_sync`; the constant went
   with it, the two call sites did not. Five sources raised AttributeError
   after their first event and imported nothing for a week.

2. One event arrived with `start_date: 2926-09-26` — a mistyped digit at the
   source. It is a well-formed date, so every check downstream accepted it, and
   it took up residence at the end of every list sorted by date.

3. The Rockhal sitemap has a 200-page budget, the site asks for a 2s
   Crawl-delay, and the watchdog fires at 180s. 400 > 180, so the source could
   not finish, by arithmetic, on any run it ever made.
"""
import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
TODAY = datetime.now(timezone.utc).date()

SITEMAP_SOURCE = {
    "id": "src-sitemap", "name": "Test venue — Sitemap", "kind": "sitemap",
    "active": True, "url": "https://example.invalid/",
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


class TestTheCrawlerModulesHaveWhatTheImporterAsksFor:
    """Reads importers.py and checks every attribute it takes off a crawler.

    The two crawlers are imported inside the function body, so nothing catches
    a missing name until that line runs — which needs a network crawl. This
    walks the syntax tree instead: for each `from crawlers import X as k`, find
    every `k.SOMETHING` and ask the real module whether it has it.

    Written for `PAUSE_S`, but it is the shape of the bug that matters, not the
    name. Anything renamed in a crawler shows up here on the next test run
    instead of in a week of empty imports.
    """

    def _accesses(self):
        tree = ast.parse((BACKEND_DIR / "importers.py").read_text(encoding="utf-8"))
        aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "crawlers":
                for alias in node.names:
                    aliases[alias.asname or alias.name] = alias.name
        assert aliases, "no crawler imports found — did importers.py move them?"

        found = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in aliases
            ):
                found.append((aliases[node.value.id], node.attr, node.lineno))
        return found

    def test_the_import_is_still_written_the_way_this_test_reads_it(self):
        assert self._accesses(), "expected crawler attribute accesses in importers.py"

    def test_every_attribute_exists_on_the_real_module(self):
        import importlib

        missing = []
        for module_name, attr, lineno in self._accesses():
            module = importlib.import_module(f"crawlers.{module_name}")
            if not hasattr(module, attr):
                missing.append(f"importers.py:{lineno} uses {module_name}.{attr}")
        assert not missing, "\n".join(missing)


class TestImplausibleDates:
    def test_a_mistyped_millennium_is_not_a_date(self, importers):
        assert importers._to_iso_date("2926-09-26") is None

    def test_the_year_it_was_meant_to_be_is_fine(self, importers):
        assert importers._to_iso_date("2026-09-26") == "2026-09-26"

    def test_a_season_announced_two_years_out_still_passes(self, importers):
        far = TODAY.replace(year=TODAY.year + 2)
        assert importers._to_iso_date(far.isoformat()) == far.isoformat()

    def test_last_year_still_parses(self, importers):
        """Rejected later for being over, not here for being unreadable.

        Whether a past event is worth keeping is the importer's call — several
        keep yesterday's. This function only refuses dates nobody meant.
        """
        old = TODAY.replace(year=TODAY.year - 1)
        assert importers._to_iso_date(old.isoformat()) == old.isoformat()

    def test_a_far_future_year_is_refused_whatever_the_format(self, importers):
        for value in ("26.09.2926", "26 septembre 2926", "2926-09-26T20:00:00"):
            assert importers._to_iso_date(value) is None, value

    def test_datetime_objects_are_checked_too(self, importers):
        assert importers._to_iso_date(datetime(2926, 9, 26, tzinfo=timezone.utc)) is None

    def test_nothing_readable_is_still_nothing(self, importers):
        assert importers._to_iso_date("Termin folgt") is None


class TestTheSitemapImporterHonoursBothOfThose:
    """The same two rules again, through the importer that met them."""

    def _page(self, start: str, title: str = "Kreative Schreifatelier", url: str = "") -> str:
        payload = {
            "@context": "https://schema.org", "@type": "Event",
            "name": title, "startDate": start,
            "description": "Atelier fir Kanner",
            "url": url or f"https://example.invalid/event/{start}",
        }
        return (
            '<html><head><script type="application/ld+json">'
            + json.dumps(payload)
            + "</script></head><body></body></html>"
        )

    def _sitemap(self, count: int) -> str:
        urls = "".join(
            f"<url><loc>https://example.invalid/event/{i}</loc>"
            f"<lastmod>2026-08-{20 - i % 10:02d}</lastmod></url>"
            for i in range(count)
        )
        return f'<?xml version="1.0"?><urlset>{urls}</urlset>'

    def _wire(self, importers, monkeypatch, *, pages, sitemap_size):
        async def _find(source_url, origin):
            return "https://example.invalid/sitemap.xml", self._sitemap(sitemap_size)

        monkeypatch.setattr(importers, "_find_sitemap", _find)
        monkeypatch.setattr(importers, "_fetch_text", pages)

    def test_the_2926_event_is_skipped_not_stored(self, importers, db, run, monkeypatch):
        async def pages(url, timeout=30.0):
            return self._page("2926-09-26")

        self._wire(importers, monkeypatch, pages=pages, sitemap_size=3)
        inserted, skipped, blocked = run(importers._import_sitemap(SITEMAP_SOURCE, db))

        assert inserted == 0
        assert skipped == 3, "a skip, so the source is not reported as a dead site"
        assert run(db.events.count_documents({})) == 0

    def test_the_same_page_with_the_right_year_is_stored(
        self, importers, db, run, monkeypatch
    ):
        soon = (TODAY + timedelta(days=30)).isoformat()

        async def pages(url, timeout=30.0):
            return self._page(soon, title=f"Atelier {url[-1]}", url=url)

        self._wire(importers, monkeypatch, pages=pages, sitemap_size=3)
        inserted, _, _ = run(importers._import_sitemap(SITEMAP_SOURCE, db))
        assert inserted == 3


class TestTheFetchBudget:
    """Stop asking for pages before the watchdog stops the source.

    Time is faked: every page fetch costs a minute of the clock the importer
    reads. Real crawl-delays are 2s, not 60, but the arithmetic being tested is
    the same one Rockhal loses — how many pages fit before the budget is spent.
    """

    def _run_with_clock(self, importers, db, run, monkeypatch, *, pages, seconds_each):
        clock = {"t": 0.0}
        monkeypatch.setattr(importers, "_monotonic", lambda: clock["t"])

        urls = "".join(
            f"<url><loc>https://example.invalid/event/{i}</loc>"
            f"<lastmod>2026-08-{28 - i:02d}</lastmod></url>"
            for i in range(pages)
        )

        async def _find(source_url, origin):
            return "s.xml", f'<?xml version="1.0"?><urlset>{urls}</urlset>'

        fetched = []
        soon = (TODAY + timedelta(days=14)).isoformat()

        async def _fetch(url, timeout=30.0):
            fetched.append(url)
            clock["t"] += seconds_each
            payload = {
                "@context": "https://schema.org", "@type": "Event",
                "name": f"Konzert {len(fetched)}", "startDate": soon,
                "url": url,
            }
            return (
                '<script type="application/ld+json">'
                + json.dumps(payload)
                + "</script>"
            )

        monkeypatch.setattr(importers, "_find_sitemap", _find)
        monkeypatch.setattr(importers, "_fetch_text", _fetch)
        source = {**SITEMAP_SOURCE, "selectors": {"max_pages": pages}}
        result = run(importers._import_sitemap(source, db))
        return result, fetched

    def test_it_stops_when_the_budget_is_spent(self, importers, db, run, monkeypatch):
        budget = importers.SOURCE_FETCH_BUDGET_SECONDS
        (inserted, _, _), fetched = self._run_with_clock(
            importers, db, run, monkeypatch, pages=50, seconds_each=60.0
        )
        assert len(fetched) == int(budget // 60) + 1
        assert inserted == len(fetched), "everything fetched was kept"

    def test_it_returns_normally_rather_than_being_cancelled(
        self, importers, db, run, monkeypatch
    ):
        """The point of the whole fix.

        Before, the watchdog cancelled the source: the events already written
        stayed in the database, but the source record said "error, imported 0".
        A source that is doing its job looked broken, and the count nobody
        could trust was the count used to decide whether a site had died.
        """
        (inserted, _, _), _ = self._run_with_clock(
            importers, db, run, monkeypatch, pages=50, seconds_each=60.0
        )
        assert inserted > 0

    def test_a_budget_that_fits_fetches_everything(self, importers, db, run, monkeypatch):
        (inserted, _, _), fetched = self._run_with_clock(
            importers, db, run, monkeypatch, pages=8, seconds_each=1.0
        )
        assert len(fetched) == 8
        assert inserted == 8

    def test_the_budget_leaves_the_watchdog_room_to_never_fire(self, importers):
        assert importers.SOURCE_FETCH_BUDGET_SECONDS < importers.SOURCE_TIMEOUT_SECONDS


class TestTheCustomCrawlersStopThemselves:
    """The same budget, where it matters more than anywhere else.

    These two crawlers are sync code in a worker thread. Cancelling an
    `asyncio.to_thread` future does not stop the thread: the watchdog stamps
    the source "error, imported 0" and the crawl keeps going in the background,
    still fetching, still writing through its own pymongo client. Stopping
    voluntarily is the only stop there is.

    kids-in-lux asks for a 5s Crawl-delay and the three sources walk about a
    hundred detail pages between them. Until the PAUSE_S fix they crashed on
    their first event, so this never came up; the first run that actually
    crawled hit the watchdog on all three.
    """

    def _fake_crawler(
        self, monkeypatch, clock, *, seconds_each, pages, upsert_returns="inserted"
    ):
        import sys
        import types

        import crawlers
        import importers as importers_mod

        module = types.ModuleType("crawlers.kids_in_lux")
        module.INDEX_URLS = [("https://example.invalid/i", ["Playgrounds"], "venue")]
        module.list_detail_urls = lambda index_url, hx: [
            f"https://example.invalid/p/{i}" for i in range(pages)
        ]
        fetched = []

        def fetch(url, hx):
            fetched.append(url)
            clock["t"] += seconds_each
            return "<html></html>"

        module.fetch = fetch
        module.parse_detail = lambda url, html: {"title": "Spillplaz", "desc": "fir Kanner"}
        module.upsert_event = lambda sdb, parsed, cats, ev_type, sid: upsert_returns

        # Both, and the second one is the one that matters. `from crawlers
        # import kids_in_lux` reads the attribute off the already-imported
        # package, so replacing only the sys.modules entry leaves the real
        # crawler in place — and the first version of this test went out and
        # fetched kids-in-lux.com for real, at the 5s Crawl-delay the site
        # asks for, until it was killed.
        monkeypatch.setitem(sys.modules, "crawlers.kids_in_lux", module)
        monkeypatch.setattr(crawlers, "kids_in_lux", module, raising=False)
        # These tests are about the fetch budget. The cursor writes to the real
        # MongoDB, which the offline guard refuses, and pymongo then spends its
        # server-selection timeout finding that out — 30 seconds per test.
        monkeypatch.setattr(importers_mod, "_save_cursor", lambda *a: None)
        return fetched

    def test_it_stops_instead_of_running_past_the_watchdog(
        self, importers, db, run, monkeypatch
    ):
        clock = {"t": 0.0}
        monkeypatch.setattr(importers, "_monotonic", lambda: clock["t"])
        fetched = self._fake_crawler(monkeypatch, clock, seconds_each=5.0, pages=200)

        source = {"id": "kil", "name": "Kids in Lux – Spielplätze", "kind": "kids_in_lux"}
        inserted, failed, blocked = run(importers._import_kids_in_lux(source, db))

        budget = importers.SOURCE_FETCH_BUDGET_SECONDS
        assert len(fetched) < 200, "it must not walk the whole list"
        assert len(fetched) == int(budget // 5) + 1
        assert inserted == len(fetched)

    def test_a_short_list_is_finished_normally(self, importers, db, run, monkeypatch):
        clock = {"t": 0.0}
        monkeypatch.setattr(importers, "_monotonic", lambda: clock["t"])
        fetched = self._fake_crawler(monkeypatch, clock, seconds_each=5.0, pages=6)

        source = {"id": "kil", "name": "Kids in Lux – Ausflüge", "kind": "kids_in_lux"}
        inserted, _, _ = run(importers._import_kids_in_lux(source, db))
        assert len(fetched) == 6
        assert inserted == 6


class TestASourceThatIsWorkingDoesNotReportItselfDead:
    """`run_source` reads three zeroes as "this website has died".

    These are always-open venues, keyed on a stable external_id, so after the
    first successful run every later pass is an update and nothing is ever
    inserted again. `updated` was counted in a local variable and then left out
    of the return value, so a healthy refresh of thirty venues returned
    (0, 0, 0) — the source was on course to report itself dead forever, and
    `empty_runs` would have kept climbing while it worked perfectly.
    """

    def _wire(self, monkeypatch, *, upsert_returns, links=4):
        import sys
        import types

        import crawlers
        import importers as importers_mod

        module = types.ModuleType("crawlers.kids_in_lux")
        module.INDEX_URLS = [("https://example.invalid/i", ["Playgrounds"], "venue")]
        module.list_detail_urls = lambda index_url, hx: [
            f"https://example.invalid/p/{i}" for i in range(links)
        ]
        module.fetch = lambda url, hx: "<html></html>"
        module.parse_detail = lambda url, html: {"title": "Spillplaz", "desc": ""}
        module.upsert_event = lambda *a: upsert_returns
        monkeypatch.setitem(sys.modules, "crawlers.kids_in_lux", module)
        monkeypatch.setattr(crawlers, "kids_in_lux", module, raising=False)
        monkeypatch.setattr(importers_mod, "_save_cursor", lambda *a: None)

    def _source(self):
        return {"id": "kil", "name": "Kids in Lux – Spielplätze", "kind": "kids_in_lux"}

    def test_a_refresh_of_known_venues_counts_as_seen(
        self, importers, db, run, monkeypatch
    ):
        self._wire(monkeypatch, upsert_returns="updated")
        inserted, skipped, blocked = run(
            importers._import_kids_in_lux(self._source(), db)
        )
        assert inserted == 0, "nothing new, which is correct"
        assert skipped == 4, "but four were seen — not a dead site"
        assert inserted + skipped + blocked > 0

    def test_run_source_calls_that_ok_and_not_no_events(
        self, importers, app_module, run, monkeypatch
    ):
        """The end the counting exists for."""
        self._wire(monkeypatch, upsert_returns="updated")
        db = app_module.db
        run(db.sources.insert_one({**self._source(), "active": True}))

        result = run(importers.run_source(self._source(), db))
        assert result["last_status"] == "ok"
        assert result["empty_runs"] == 0

    def test_an_unreadable_index_page_is_an_error_not_a_quiet_week(
        self, importers, app_module, run, monkeypatch
    ):
        """Two different things had one answer.

        A crawl that read the index and found nothing, and an index page that
        could not be read at all, both came out as `no_events` with three
        zeroes. Only one of them is a site going quiet.
        """
        self._wire(monkeypatch, upsert_returns="inserted", links=0)
        db = app_module.db
        run(db.sources.insert_one({**self._source(), "active": True}))

        result = run(importers.run_source(self._source(), db))
        assert result["last_status"] == "error"
        assert "index page" in (result["last_error"] or "")
