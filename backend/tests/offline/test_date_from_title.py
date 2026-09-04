"""Reading the date a venue put in its own page title.

The importer had been taking a page's first `<time>` tag, which on the
Philharmonie's pages is "13:15" — the start time. dateutil filled the missing
date from today, and an October programme was filed under an August morning.

The title said so all along: "Le coin des mini monstres | 24.10.2026 13:15".

The rule is deliberately narrow. The date has to be the *last* thing in the
title, after a separator, because the same-looking string appears in titles
where it means something else entirely:

    "Parc Merveilleux Sommersaison (21/03/2026 – 15/10/2026)"

That first date opens a season. Taking it would move the event to the first day
of summer, which is a different kind of wrong from the one being fixed — and
the more embarrassing kind, because it would look deliberate.
"""
import pytest

from importers import date_from_title


class TestTheTitlesThisWasBuiltFor:
    @pytest.mark.parametrize("title,expected", [
        ("Le coin des mini monstres | 24.10.2026 13:15", "2026-10-24"),
        ("La fabrique à monstres | 25.10.2026 10:00", "2026-10-25"),
        ("Dräi luusseg, muusseg Monsteren | 24.10.2026 11:00", "2026-10-24"),
        ("Lunchtime at Mudam – 4 Sept 2026", "2026-09-04"),
        ("Mudamini 360° – 13 Aug 2026", "2026-08-13"),
        ("Lunchtime at Mudam – 27 Nov 2026", "2026-11-27"),
    ])
    def test_it_reads_the_date_at_the_end(self, title, expected):
        assert date_from_title(title) == expected

    @pytest.mark.parametrize("separator", ["|", "–", "—", "-"])
    def test_every_separator_the_venues_use(self, separator):
        assert date_from_title(f"Konzert {separator} 24.10.2026") == "2026-10-24"

    def test_a_trailing_time_does_not_get_in_the_way(self):
        assert date_from_title("Konzert | 24.10.2026 13:15") == "2026-10-24"
        assert date_from_title("Konzert | 24.10.2026 13.15") == "2026-10-24"


class TestWhatItRefuses:
    def test_a_season_range_in_brackets(self):
        """The one title in the database that must not be touched."""
        title = "Parc Merveilleux Sommersaison (21/03/2026 – 15/10/2026)"
        assert date_from_title(title) is None

    def test_a_closing_date(self):
        """"until 31.12." is not a start date."""
        assert date_from_title("Ausstellung bis 31.12.2026") is None

    def test_a_date_in_the_middle_of_a_title(self):
        assert date_from_title("Rückblick 24.10.2026 und was danach kam") is None

    @pytest.mark.parametrize("title", [
        "Konzert ohne Datum", "", None, "Mudamini 360°", "Fit & Fun – Zumba",
    ])
    def test_a_title_with_no_date_yields_nothing(self, title):
        assert date_from_title(title) is None

    def test_a_year_nobody_meant_is_still_refused(self):
        """The plausibility window applies here too."""
        assert date_from_title("Schreifatelier | 26.09.2926") is None

    def test_a_bare_time_after_a_separator_is_not_a_date(self):
        """The original bug, arriving from the other side."""
        assert date_from_title("Konzert | 13:15") is None


class TestTheImporterPrefersIt:
    def test_the_title_beats_a_misleading_time_tag(self):
        """End to end, on the shape of page that caused this.

        The first `<time>` tag is the start time, exactly as the Philharmonie
        writes it. Before, that decided the date.
        """
        from importers import _extract_open_graph_event

        html = (
            '<html><head>'
            '<meta property="og:title" content="Le coin des mini monstres | 24.10.2026 13:15">'
            '<meta property="og:description" content="Fir Kanner">'
            '</head><body>'
            '<time>13:15</time><time datetime="24/10/2026">24/10/2026</time>'
            '</body></html>'
        )
        event = _extract_open_graph_event(html, page_url="https://example.invalid/e/1")
        assert event is not None
        assert event["startDate"] == "2026-10-24"

    def test_a_page_without_a_title_date_still_uses_its_time_tags(self):
        from importers import _extract_open_graph_event

        html = (
            '<html><head><meta property="og:title" content="Konzert am Duerf">'
            '</head><body><time datetime="24/10/2026">24 October</time></body></html>'
        )
        event = _extract_open_graph_event(html, page_url="https://example.invalid/e/2")
        assert event is not None
        assert event["startDate"] == "2026-10-24"

    def test_a_page_with_neither_is_not_invented(self):
        from importers import _extract_open_graph_event

        html = (
            '<html><head><meta property="og:title" content="Konzert am Duerf">'
            '</head><body><time>20:00</time></body></html>'
        )
        assert _extract_open_graph_event(html, page_url="https://example.invalid/e/3") is None
