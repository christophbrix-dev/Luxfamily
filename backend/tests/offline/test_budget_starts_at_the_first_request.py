# The fetch budget has to cover everything the source costs.
#
# `_import_sitemap` created its deadline after the candidate list existed, so
# the clock covered the loop over the pages and nothing before it. Two things
# happen before it, and both make requests under whatever crawl delay the site
# asks for:
#
#   _find_sitemap        up to five — the configured URL, robots.txt, and three
#                        guessed paths
#   the index expansion  up to ten sub-sitemaps
#
# Ville de Luxembourg spent about ten minutes in those two, against a budget
# meant to cap a source at 160 seconds. The source was not misbehaving and the
# budget was not wrong; it simply had not started yet.

import time

import pytest

@pytest.fixture
def importers(app_module):
    import importers as mod

    return mod


@pytest.fixture
def db(app_module):
    return app_module.db


SOURCE = {
    "id": "s-budget",
    "name": "Budget probe",
    "kind": "sitemap",
    "url": "https://example.invalid/sitemap.xml",
    "town_default": "Luxembourg",
    "lat_default": 49.61,
    "lng_default": 6.13,
}


class FakeClock:
    """A clock that only moves when a fetch happens.

    Real time would make this a race; here every request costs a fixed,
    declared amount, which is what a crawl delay is.
    """

    def __init__(self, cost: float) -> None:
        self.now = 1000.0
        self.cost = cost
        self.fetches: list[str] = []

    def tick(self, url: str) -> None:
        self.fetches.append(url)
        self.now += self.cost


@pytest.fixture
def clock(importers, monkeypatch):
    # 60 s a fetch: three exhaust a 160 s budget outright. 40 would have hit
    # it exactly on the fourth, and the check is "past the deadline", not "at".
    c = FakeClock(cost=60.0)
    monkeypatch.setattr(importers, "_monotonic", lambda: c.now)
    return c


def _sitemap_of(urls: list[str]) -> str:
    body = "".join(f"<url><loc>{u}</loc><lastmod>2026-08-20</lastmod></url>" for u in urls)
    return f'<?xml version="1.0"?><urlset>{body}</urlset>'


# ---------------------------------------------------------------------------
# Finding the file
# ---------------------------------------------------------------------------

def test_looking_for_the_sitemap_stops_when_the_budget_is_gone(
    importers, db, run, monkeypatch, clock,
):
    """The part that used to run before any clock existed.

    Every attempt fails, so the function walks its whole candidate list. With
    the budget reaching it, it gives up part-way instead.
    """
    async def never_answers(url, timeout=30.0):
        clock.tick(url)
        raise RuntimeError("404")

    monkeypatch.setattr(importers, "_fetch_text", never_answers)

    with pytest.raises(RuntimeError) as failure:
        run(importers._find_sitemap(
            SOURCE["url"], "https://example.invalid",
            clock.now + importers.SOURCE_FETCH_BUDGET_SECONDS,
        ))

    assert "budget" in str(failure.value).lower()
    # Five candidates exist; the budget is gone after three fetches.
    assert len(clock.fetches) <= 4, clock.fetches


def test_without_a_budget_it_still_tries_everything(
    importers, db, run, monkeypatch, clock,
):
    """The argument is optional, and probe_sources.py passes nothing.

    A tool whose whole job is to report what a site publishes should not be
    cut short by a budget meant for a scheduled crawl.
    """
    async def never_answers(url, timeout=30.0):
        clock.tick(url)
        raise RuntimeError("404")

    monkeypatch.setattr(importers, "_fetch_text", never_answers)

    with pytest.raises(RuntimeError) as failure:
        run(importers._find_sitemap(SOURCE["url"], "https://example.invalid"))

    assert "No sitemap found" in str(failure.value)
    assert "budget" not in str(failure.value).lower()


# ---------------------------------------------------------------------------
# Expanding an index of sub-sitemaps
# ---------------------------------------------------------------------------

def test_an_index_of_sub_sitemaps_is_not_walked_forever(
    importers, db, run, monkeypatch, clock,
):
    """vdl.lu's own shape: a sitemap.xml that lists further sitemaps.

    Ten of them are followed, each a request. Under a crawl delay that alone
    can outlast the budget the source was given.
    """
    index = _sitemap_of([f"https://example.invalid/sitemap-{i}.xml" for i in range(10)])

    async def pages(url, timeout=30.0):
        clock.tick(url)
        if url.endswith(".xml"):
            return _sitemap_of([f"https://example.invalid/events/{url[-5]}"])
        return "<html></html>"

    async def find(source_url, origin, deadline=None):
        return "https://example.invalid/sitemap.xml", index

    monkeypatch.setattr(importers, "_find_sitemap", find)
    monkeypatch.setattr(importers, "_fetch_text", pages)

    run(importers._import_sitemap(SOURCE, db))

    # Ten sub-sitemaps at 60 s each would be 600 s against a 160 s budget. The
    # allowance is one fetch: the deadline is checked before each, so the one
    # that crosses it has already been paid for.
    spent = clock.now - 1000.0
    assert spent <= importers.SOURCE_FETCH_BUDGET_SECONDS + 60, (
        f"spent {spent}s of a {importers.SOURCE_FETCH_BUDGET_SECONDS}s budget "
        f"over {len(clock.fetches)} fetches"
    )


def test_a_source_that_answers_quickly_is_not_cut_short(
    importers, db, run, monkeypatch,
):
    """The other half of the promise.

    A budget that stops a slow source is only worth having if it leaves a fast
    one alone — otherwise every source looks like it has fewer events than it
    does.
    """
    urls = [f"https://example.invalid/events/{i}" for i in range(6)]

    async def pages(url, timeout=30.0):
        if url.endswith(".xml"):
            return _sitemap_of(urls)
        return (
            '<html><head><script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"Event",'
            '"name":"Atelier","startDate":"2026-12-01",'
            '"description":"Fir Kanner","url":"' + url + '"}'
            "</script></head><body></body></html>"
        )

    async def find(source_url, origin, deadline=None):
        return "https://example.invalid/sitemap.xml", _sitemap_of(urls)

    monkeypatch.setattr(importers, "_find_sitemap", find)
    monkeypatch.setattr(importers, "_fetch_text", pages)
    # Real monotonic time: six instant fetches cannot exhaust 160 seconds.
    monkeypatch.setattr(importers, "_monotonic", time.monotonic)

    inserted, skipped, blocked = run(importers._import_sitemap(SOURCE, db))
    assert inserted == 6, "a fast source keeps every page it offered"
