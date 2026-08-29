"""Three sources, three index pages — not three copies of the same crawl.

The kids-in-lux importer read the module's INDEX_URLS and ignored the `url` on
the source record entirely, so each of the three sources walked all three index
pages. On a site that asks for five seconds between requests that is 252
fetches a run where 84 would do, and it repeats three times a day.

It also explains a measurement that looked like data and was an artefact. The
three sources hold 81, 1 and 0 events. That is not three differently sized
listings: they crawl the same pages and `upsert_event` stamps its own
`source_id` on every update, so whichever source ran last owns almost
everything.

The source records point at three genuinely different pages — one of them at
`/spielplätze/highlight-spielplätze/`, which sits below an index rather than
being one. That is why matching falls back to a prefix.
"""
import pytest

from importers import _index_for_source

BASE = "https://www.kids-in-lux.com"
INDEX_URLS = [
    (f"{BASE}/spielplätze/", ["Playgrounds"], "Outdoor"),
    (f"{BASE}/schlechtes-wetter/indoor-spielplätze/", ["Playgrounds", "Indoor"], "Indoor"),
    (f"{BASE}/ausflüge/", ["Nature", "Culture"], "Outdoor"),
]


def _src(url):
    return {"id": "s1", "name": "Test", "url": url}


class TestMatching:
    def test_an_exact_index_url_matches_itself(self):
        entry = _index_for_source(_src(f"{BASE}/ausflüge/"), INDEX_URLS)
        assert entry[0] == f"{BASE}/ausflüge/"
        assert entry[1] == ["Nature", "Culture"]

    def test_a_trailing_slash_makes_no_difference(self):
        assert _index_for_source(_src(f"{BASE}/ausflüge"), INDEX_URLS)[0] == f"{BASE}/ausflüge/"

    def test_a_page_below_an_index_belongs_to_that_index(self):
        """The real source record: /spielplätze/highlight-spielplätze/."""
        entry = _index_for_source(
            _src(f"{BASE}/spielplätze/highlight-spielplätze/"), INDEX_URLS
        )
        assert entry[0] == f"{BASE}/spielplätze/"

    def test_the_three_real_sources_land_on_three_different_pages(self):
        """The claim the whole change rests on."""
        urls = [
            f"{BASE}/spielplätze/highlight-spielplätze/",
            f"{BASE}/schlechtes-wetter/indoor-spielplätze/",
            f"{BASE}/ausflüge/",
        ]
        chosen = [_index_for_source(_src(u), INDEX_URLS)[0] for u in urls]
        assert len(set(chosen)) == 3, f"still overlapping: {chosen}"

    def test_the_indoor_page_is_not_swallowed_by_the_playground_index(self):
        """`/schlechtes-wetter/indoor-spielplätze/` contains "spielplätze".

        A looser match — substring instead of prefix — would hand it to the
        outdoor index and give indoor playgrounds the wrong categories.
        """
        entry = _index_for_source(
            _src(f"{BASE}/schlechtes-wetter/indoor-spielplätze/"), INDEX_URLS
        )
        assert entry[1] == ["Playgrounds", "Indoor"]


class TestWhenNothingMatches:
    def test_it_raises_rather_than_crawling_everything(self):
        """Quietly crawling all three is exactly how this started."""
        with pytest.raises(RuntimeError) as exc:
            _index_for_source(_src("https://example.invalid/other/"), INDEX_URLS)
        assert "matches no known index page" in str(exc.value)

    def test_the_message_names_both_sides(self):
        with pytest.raises(RuntimeError) as exc:
            _index_for_source(_src("https://example.invalid/other/"), INDEX_URLS)
        text = str(exc.value)
        assert "example.invalid/other" in text
        assert "ausflüge" in text

    @pytest.mark.parametrize("url", [None, "", "   "])
    def test_a_source_without_a_url_is_an_error_too(self, url):
        with pytest.raises(RuntimeError):
            _index_for_source({"id": "s", "url": url}, INDEX_URLS)

    def test_a_near_miss_is_not_accepted(self):
        """`/spielplätzen/` is a different path, not a sub-page."""
        with pytest.raises(RuntimeError):
            _index_for_source(_src(f"{BASE}/spielplätzen/"), INDEX_URLS)
