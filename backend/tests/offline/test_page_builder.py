"""Page-builder markup must not reach a reader — and brackets people typed must.

51 of 354 events in the live database had descriptions like

    [et_pb_section fb_built="1" _builder_version="4.24.2" …][et_pb_row …]

with two sentences of real text buried inside, or with no text at all. Every
one came from a commune running Divi.

The eager version of this rule stripped every bracketed word, which also ate
"[Sold out]" and "[FR]" — things a person wrote on purpose. So the tests below
come in pairs: what must go, and what must stay.
"""
import pytest

from importers import _normalise_text as strip_ws
from importers import _strip_page_builder as strip


class TestBuilderMarkupGoes:
    def test_divi_wrapper_leaves_the_text(self):
        raw = (
            '[et_pb_section fb_built="1" _builder_version="4.24.2"]'
            '[et_pb_row][et_pb_column type="4_4"][et_pb_text]'
            "Chaque mercredi, le Labomobile sera devant la maison communale."
            "[/et_pb_text][/et_pb_column][/et_pb_row][/et_pb_section]"
        )
        assert strip(raw) == (
            "Chaque mercredi, le Labomobile sera devant la maison communale."
        )

    def test_markup_only_description_becomes_empty(self):
        """Nothing is more honest than a wall of shortcodes."""
        raw = '[et_pb_section fb_built="1"][et_pb_row][/et_pb_row][/et_pb_section]'
        assert strip(raw) == ""

    @pytest.mark.parametrize(
        "raw",
        [
            '[vc_row][vc_column]Hallo[/vc_column][/vc_row]',
            '[fusion_text]Hallo[/fusion_text]',
            '[av_textblock size="14"]Hallo[/av_textblock]',
            '[caption id="x" width="300"]Hallo[/caption]',
            '[gallery ids="1,2,3"]Hallo',
        ],
    )
    def test_other_builders_too(self, raw):
        assert strip(raw).strip() == "Hallo"


class TestHumanBracketsStay:
    """The half that the first draft got wrong."""

    @pytest.mark.parametrize(
        "raw",
        [
            "[Sold out] Konzert am Kader",
            "[FR] Visite guidée du château",
            "[Ausverkaft] Kannerfest",
            "Concert [annulé] – report en septembre",
            "Öffnungszeiten [siehe Website]",
        ],
    )
    def test_kept_verbatim(self, raw):
        assert strip(raw) == raw


class TestEdges:
    def test_plain_text_is_untouched(self):
        text = "Kannerfest am Park, 14:00 bis 18:00."
        assert strip(text) == text

    def test_empty_is_safe(self):
        assert strip("") == ""
        assert strip(None) is None

    def test_runs_of_whitespace_collapse(self):
        assert strip("[et_pb_text]A[/et_pb_text]   [et_pb_text]B[/et_pb_text]") == "A B"


class TestWhitespaceNormalisation:
    """Padding that reached the reader.

    One commune's JSON-LD delivers a description as
    "      \xa0    Orchestre des Jeunes de l'Est    Bech-Berbuerger Musek".
    Across the live database: 294 fields with runs of spaces, 219 with edge
    whitespace, 78 carrying a non-breaking space.
    """

    def test_padding_and_nbsp_collapse(self):
        assert strip_ws("      \xa0    Orchestre des Jeunes    Bech-Berbuerger Musek") == (
            "Orchestre des Jeunes Bech-Berbuerger Musek"
        )

    def test_line_breaks_become_spaces(self):
        """These render as one paragraph; a newline shows as a gap."""
        assert strip_ws("Kannerfest\n\nam Park") == "Kannerfest am Park"

    def test_the_ends_are_trimmed(self):
        assert strip_ws("  Konzert  ") == "Konzert"

    def test_zero_width_characters_go_too(self):
        assert strip_ws("Konzert​﻿ am Park") == "Konzert am Park"

    def test_ordinary_text_is_untouched(self):
        assert strip_ws("Kannerfest am Park, 14:00 bis 18:00.") == (
            "Kannerfest am Park, 14:00 bis 18:00."
        )

    def test_single_spaces_between_words_survive(self):
        assert strip_ws("a b c") == "a b c"

    def test_empty_input_is_safe(self):
        assert strip_ws("") == ""
        assert strip_ws(None) is None
