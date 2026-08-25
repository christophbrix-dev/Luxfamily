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
