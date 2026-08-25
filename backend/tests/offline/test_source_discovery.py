# Reading a sitemap, and picking which page to judge a site by.
#
# Both of these decided, silently, that some of the largest venues in the
# country had no events. Nothing errored; the report simply said
# "NICHTS GEFUNDEN" and the site was never looked at again.

import discover_sources as ds


class TestNestedSitemapDetection:
    """A query string after .xml does not stop it being a sitemap."""

    def test_plain_sitemap(self):
        assert ds._looks_like_sitemap("https://x.invalid/sitemap.xml")

    def test_paginated_index(self):
        # casino-luxembourg.lu splits its index this way. Tested with
        # endswith(".xml"), as this used to be, these look like content pages,
        # the index is never opened, and the site reports nothing at all.
        assert ds._looks_like_sitemap("https://x.invalid/sitemap.xml?page=2")

    def test_gzipped(self):
        assert ds._looks_like_sitemap("https://x.invalid/sitemap.xml.gz")

    def test_an_ordinary_page_is_not_one(self):
        assert not ds._looks_like_sitemap("https://x.invalid/agenda/")
        assert not ds._looks_like_sitemap("https://x.invalid/events/fest-2026/")


class TestExampleUrlRanking:
    """Which page gets fetched to decide whether a venue publishes events."""

    def rank(self, *urls):
        return sorted(urls, key=ds._event_url_rank)

    def test_a_real_calendar_beats_a_deep_page(self):
        best = self.rank(
            "https://x.invalid/de/shop/lhomme-gris-ausstellungskatalog",
            "https://x.invalid/fr/agenda",
        )[0]
        assert best.endswith("/fr/agenda")

    def test_a_shop_selling_the_catalogue_is_not_the_programme(self):
        # The failure this was written for: Casino Luxembourg does publish its
        # programme, and was written off on the strength of a shop page whose
        # title contains "atelier".
        urls = self.rank(
            "https://x.invalid/shop/atelier-katalog",
            "https://x.invalid/programme/",
        )
        assert urls[0].endswith("/programme/")

    def test_shallow_before_deep(self):
        urls = self.rank(
            "https://x.invalid/agenda/2026/03/12/fest/",
            "https://x.invalid/agenda/",
        )
        assert urls[0].endswith("/agenda/")

    def test_a_word_inside_a_slug_is_not_a_section(self):
        # "das-studentenprogramm" contains "programm" but is not a programme.
        urls = self.rank(
            "https://x.invalid/das-studentenprogramm/",
            "https://x.invalid/veranstaltungen/",
        )
        assert urls[0].endswith("/veranstaltungen/")


class TestSitemapIndexIsFollowed:
    """A <sitemapindex> has no content of its own, so its children must be read."""

    def test_children_of_an_index_are_followed_whatever_they_are_called(self, monkeypatch):
        index = """<sitemapindex><sitemap><loc>https://x.invalid/sitemap.xml?page=1</loc></sitemap></sitemapindex>"""
        page = """<urlset><url><loc>https://x.invalid/agenda/fest/</loc></url></urlset>"""

        pages = {"https://x.invalid/sitemap.xml": index,
                 "https://x.invalid/sitemap.xml?page=1": page}

        class Resp:
            def __init__(self, text): self.text = text

        monkeypatch.setattr(ds, "polite_get_sync", lambda url, **kw: Resp(pages[url]))

        found = ds.read_sitemap("https://x.invalid/sitemap.xml")
        assert "https://x.invalid/agenda/fest/" in found

    def test_a_urlset_only_follows_event_shaped_children(self, monkeypatch):
        """Not an index: the name is the only clue, and sites carry dozens."""
        urlset = (
            "<urlset>"
            "<url><loc>https://x.invalid/sitemap-events.xml</loc></url>"
            "<url><loc>https://x.invalid/sitemap-products.xml</loc></url>"
            "</urlset>"
        )
        asked = []

        class Resp:
            def __init__(self, text): self.text = text

        def fake(url, **kw):
            asked.append(url)
            return Resp(urlset if url.endswith("/sitemap.xml") else "<urlset></urlset>")

        monkeypatch.setattr(ds, "polite_get_sync", fake)
        ds.read_sitemap("https://x.invalid/sitemap.xml")
        assert "https://x.invalid/sitemap-events.xml" in asked
        assert "https://x.invalid/sitemap-products.xml" not in asked


class TestSingularAndAccentedSections:
    """/evenement/ is a calendar; /actualites/ is a news page.

    kaerjeng.lu files each event under /evenement/<slug> — singular, no accent.
    The first version of the ranking listed only "evenements", so that path
    scored no better than /actualites/, lost on depth, and the commune went
    from usable to not. It was the only source the rewrite cost, and it cost it
    to a missing letter.
    """

    def rank(self, *urls):
        return sorted(urls, key=ds._event_url_rank)

    def test_singular_french(self):
        assert self.rank(
            "https://x.invalid/actualites/",
            "https://x.invalid/evenement/themendag/",
        )[0].endswith("/evenement/themendag/")

    def test_accented(self):
        assert self.rank(
            "https://x.invalid/actualites/",
            "https://x.invalid/événements/fest/",
        )[0].endswith("/événements/fest/")

    def test_news_is_still_not_a_calendar(self):
        assert self.rank(
            "https://x.invalid/agenda/",
            "https://x.invalid/actualites/",
        )[0].endswith("/agenda/")
