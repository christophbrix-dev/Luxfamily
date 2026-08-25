"""Spending a small page budget on the right pages.

A sitemap importer fetches at most `max_pages` candidate pages — 20 by default
— because each one is a request to somebody else's server. Which 20 it picks
decides whether anything is imported at all.

It used to take whichever came first in the file. rockhal.lu lists 998 shows
going back years, so the budget went on concerts from 2022, every one of them
long past, and the source imported nothing while looking like it had worked.
The sitemap says which entries are fresh; we were discarding that.
"""
import pytest

from importers import _collect_sitemap_entries, _collect_sitemap_urls, _SITEMAP_EVENT_PATTERNS


def sitemap(*pairs):
    body = "".join(
        f"<url><loc>{u}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "") + "</url>"
        for u, m in pairs
    )
    return f'<?xml version="1.0"?><urlset>{body}</urlset>'


class TestKeepingLastmod:
    def test_pairs_url_with_its_date(self):
        xml = sitemap(("https://x.lu/events/a", "2026-08-25"))
        assert _collect_sitemap_entries(xml, base="https://x.lu") == [
            ("https://x.lu/events/a", "2026-08-25")
        ]

    def test_a_missing_lastmod_is_empty_not_dropped(self):
        """Unknown is not old — the entry still deserves consideration."""
        xml = sitemap(("https://x.lu/events/a", None))
        assert _collect_sitemap_entries(xml, base="https://x.lu") == [
            ("https://x.lu/events/a", "")
        ]

    def test_the_url_only_helper_still_works(self):
        """Existing callers and their tests must not notice this change."""
        xml = sitemap(("https://x.lu/a", "2026-01-01"), ("https://x.lu/b", None))
        assert _collect_sitemap_urls(xml, base="https://x.lu") == [
            "https://x.lu/a", "https://x.lu/b"
        ]

    def test_loose_loc_tags_are_still_read(self):
        """Some sitemaps put <loc> outside <url>; those must not vanish."""
        xml = '<?xml version="1.0"?><urlset><loc>https://x.lu/a</loc></urlset>'
        assert _collect_sitemap_urls(xml, base="https://x.lu") == ["https://x.lu/a"]

    def test_sitemap_index_entries_are_read_too(self):
        xml = (
            '<?xml version="1.0"?><sitemapindex><sitemap>'
            "<loc>https://x.lu/sub.xml</loc><lastmod>2026-08-01</lastmod>"
            "</sitemap></sitemapindex>"
        )
        assert _collect_sitemap_entries(xml, base="https://x.lu") == [
            ("https://x.lu/sub.xml", "2026-08-01")
        ]


class TestNewestFirst:
    """The ordering the page budget depends on."""

    def sorted_urls(self, entries):
        matched = [(u, m) for u, m in entries if _SITEMAP_EVENT_PATTERNS.search(u)]
        matched.sort(key=lambda pair: pair[1] or "", reverse=True)
        return [u for u, _ in matched]

    def test_the_2022_archive_loses_to_this_week(self):
        entries = [
            ("https://rockhal.lu/shows/old-concert", "2022-02-18"),
            ("https://rockhal.lu/shows/lorde", "2026-08-25"),
            ("https://rockhal.lu/shows/mid", "2024-06-01"),
        ]
        assert self.sorted_urls(entries)[0] == "https://rockhal.lu/shows/lorde"

    def test_undated_entries_sort_last(self):
        entries = [
            ("https://x.lu/events/undated", ""),
            ("https://x.lu/events/dated", "2020-01-01"),
        ]
        assert self.sorted_urls(entries)[-1] == "https://x.lu/events/undated"


class TestUrlPattern:
    @pytest.mark.parametrize(
        "url",
        [
            "https://rockhal.lu/shows/lorde/",          # 998 pages, none matched before
            "https://x.lu/show/something/",
            "https://x.lu/évènements/fete/",            # French, accented
            "https://x.lu/evenements/fete/",
            "https://x.lu/événements/fete/",
            "https://x.lu/events/a",
            "https://x.lu/agenda/a",
            "https://x.lu/kids/a",
        ],
    )
    def test_recognised(self, url):
        assert _SITEMAP_EVENT_PATTERNS.search(url), url

    @pytest.mark.parametrize(
        "url",
        [
            "https://x.lu/wp-content/uploads/2026/photo.jpg",
            "https://x.lu/contact/",
            "https://x.lu/verwaltung/",
            "https://x.lu/showroom-partner/",   # not an event page
        ],
    )
    def test_not_recognised(self, url):
        assert not _SITEMAP_EVENT_PATTERNS.search(url), url
