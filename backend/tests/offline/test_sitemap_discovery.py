"""Finding the sitemap when it is not where we assumed.

A trial run over the 45 inactive sources returned 404 for 22 of them, all on
`<domain>/sitemap.xml`. That looked like 22 broken commune websites. It was one
bug here: every source had been seeded with "/sitemap.xml" appended, the code
asked "does the configured URL already end in .xml?", the answer was always
yes, and the robots.txt lookup written directly underneath was never reached.

robots.txt named the real address — /sitemap_index.xml, which is what Yoast SEO
publishes — on several of those domains, in a file we were already downloading
for the politeness check.
"""
import pytest

pytest.importorskip("mongomock_motor", reason="pip install -r requirements-dev.txt")

import importers
from importers import _find_sitemap, _sitemaps_from_robots

EMPTY = '<?xml version="1.0"?><urlset></urlset>'


@pytest.fixture
def serve(monkeypatch):
    """Pretend the web is a dict; everything absent raises like a 404 would."""
    def _install(pages: dict):
        calls = []

        async def fake_fetch(url, timeout=30.0):
            calls.append(url)
            if url not in pages:
                raise RuntimeError(f"404 for {url}")
            return pages[url]

        monkeypatch.setattr(importers, "_fetch_text", fake_fetch)
        return calls
    return _install


class TestTheConfiguredUrlWins:
    def test_used_when_it_answers(self, serve, run):
        calls = serve({"https://x.lu/sitemap.xml": EMPTY})
        url, xml = run(_find_sitemap("https://x.lu/sitemap.xml", "https://x.lu"))
        assert url == "https://x.lu/sitemap.xml"
        assert xml == EMPTY
        assert calls == ["https://x.lu/sitemap.xml"], "should not look further"

    def test_robots_is_not_fetched_when_it_already_worked(self, serve, run):
        calls = serve({"https://x.lu/sitemap.xml": EMPTY})
        run(_find_sitemap("https://x.lu/sitemap.xml", "https://x.lu"))
        assert not any("robots" in c for c in calls)


class TestRobotsNamesTheRealOne:
    """The case that cost us 22 sources."""

    def test_sitemap_index_from_robots(self, serve, run):
        serve({
            "https://x.lu/robots.txt": "User-agent: *\nSitemap: https://x.lu/sitemap_index.xml\n",
            "https://x.lu/sitemap_index.xml": EMPTY,
        })
        url, _ = run(_find_sitemap("https://x.lu/sitemap.xml", "https://x.lu"))
        assert url == "https://x.lu/sitemap_index.xml"

    def test_the_configured_url_is_tried_first_and_then_abandoned(self, serve, run):
        calls = serve({
            "https://x.lu/robots.txt": "Sitemap: https://x.lu/other.xml\n",
            "https://x.lu/other.xml": EMPTY,
        })
        run(_find_sitemap("https://x.lu/sitemap.xml", "https://x.lu"))
        assert calls[0] == "https://x.lu/sitemap.xml"

    def test_several_sitemap_lines_are_all_candidates(self, serve, run):
        serve({
            "https://x.lu/robots.txt": (
                "Sitemap: https://x.lu/gone.xml\nSitemap: https://x.lu/real.xml\n"
            ),
            "https://x.lu/real.xml": EMPTY,
        })
        url, _ = run(_find_sitemap("https://x.lu/nope.xml", "https://x.lu"))
        assert url == "https://x.lu/real.xml"


class TestParsingRobots:
    def test_reads_the_sitemap_lines(self):
        assert _sitemaps_from_robots(
            "User-agent: *\nDisallow: /admin\nSitemap: https://x.lu/a.xml\n"
        ) == ["https://x.lu/a.xml"]

    def test_case_and_leading_space_do_not_matter(self):
        assert _sitemaps_from_robots("  SITEMAP:  https://x.lu/a.xml  ") == [
            "https://x.lu/a.xml"
        ]

    def test_https_in_the_value_survives_the_split(self):
        """Splitting on every colon would cut the URL's own scheme in half."""
        assert _sitemaps_from_robots("Sitemap: https://x.lu:8443/a.xml") == [
            "https://x.lu:8443/a.xml"
        ]

    def test_no_sitemap_line_is_not_an_error(self):
        assert _sitemaps_from_robots("User-agent: *\nDisallow:\n") == []


class TestFallbacks:
    def test_yoast_path_is_guessed(self, serve, run):
        serve({"https://x.lu/sitemap_index.xml": EMPTY})
        url, _ = run(_find_sitemap("https://x.lu/", "https://x.lu"))
        assert url == "https://x.lu/sitemap_index.xml"

    def test_wordpress_core_path_is_guessed(self, serve, run):
        serve({"https://x.lu/wp-sitemap.xml": EMPTY})
        url, _ = run(_find_sitemap("https://x.lu/", "https://x.lu"))
        assert url == "https://x.lu/wp-sitemap.xml"

    def test_nothing_anywhere_reports_what_was_tried(self, serve, run):
        """A source with no sitemap needs a different importer, and the person
        reading the error has to be able to tell that from a typo."""
        serve({})
        with pytest.raises(RuntimeError) as exc:
            run(_find_sitemap("https://x.lu/sitemap.xml", "https://x.lu"))
        message = str(exc.value)
        assert "sitemap_index.xml" in message
        assert "wp-sitemap.xml" in message

    def test_a_url_is_never_fetched_twice(self, serve, run):
        """The configured URL and the last fallback are both /sitemap.xml."""
        calls = serve({})
        with pytest.raises(RuntimeError):
            run(_find_sitemap("https://x.lu/sitemap.xml", "https://x.lu"))
        assert calls.count("https://x.lu/sitemap.xml") == 1
