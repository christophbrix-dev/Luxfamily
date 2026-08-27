"""Reading a price only when the page states one.

All 528 events carried `price_adult = 0.0`, which in a numeric field means
free, not unknown. A parent asking for free activities was told every event
qualified; some cost 30 €.

The half that matters here is what stays unknown. Filling the field in with a
guess reproduces the original defect in a new disguise.
"""
import pytest

from price_hints import read_price


class TestFreeAdmission:
    @pytest.mark.parametrize(
        "text",
        [
            "L'entrée est entièrement gratuite.",
            "Entrée libre",
            "Eintritt frei",
            "Freier Eintritt für alle",
            "Fräien Entrée, ouni Umeldung",
            "Free entry all day",
            "Admission is free",
        ],
    )
    def test_recognised(self, text):
        hint = read_price(text)
        assert hint.is_free and hint.adult == 0.0 and hint.source == "event"

    def test_a_free_item_inside_a_paid_event_is_not_free_entry(self):
        """Real listing: the breakfast is free, the event is not.

        "gratis" on its own would have marked this event free, and a parent
        filtering for free activities would have been sent to something that
        charges.
        """
        hint = read_price("Programm  08h30 – 11h00: Gratis Fairtrade-Frühstück  Ab 09h00: Second-Hand")
        assert not hint.is_free
        assert hint.source == "unknown"

    def test_free_wins_over_a_paid_extra(self):
        """Entry is the visitor's question; the workshop is a choice."""
        hint = read_price("Entrée libre. Atelier optionnel: 30 € par personne.")
        assert hint.is_free and hint.adult == 0.0


class TestAmounts:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("D'Plaze kaschten 30 € pro Persoun", 30.0),
            ("Kinder (6-12 Jahre) : 11 EUR", 11.0),
            ("Tarif: 12,50 €", 12.5),
            ("Preis: 8.00 EUR", 8.0),
            ("€ 15 pro Person", 15.0),
        ],
    )
    def test_read(self, text, expected):
        hint = read_price(text)
        assert hint.adult == expected
        assert hint.source == "event" and not hint.is_free


class TestWhatMustStayUnknown:
    @pytest.mark.parametrize(
        "text",
        [
            # A number is not a price without a currency. These are the ones
            # that would turn an anniversary into an entrance fee.
            "Konzert am Joer 2026",
            "50 Joer Guiden a Scouten",
            "Treffpunkt um 14:30, Dauer 90 Minuten",
            "Wir feiern 25 Jahre Partnerschaft",
            "Startnummer 100 bis 250",
            # Money that nobody pays to get in.
            "Preisgeld von 500 € für den Sieger",
            "Das Turnier ist mit 1000 € dotiert",
            "Spende ab 5 € erbeten",
            "Freiwëlleg Participatioun",
            # Nothing at all.
            "Kannerfest am Park",
            "",
        ],
    )
    def test_no_price_is_invented(self, text):
        hint = read_price(text)
        assert hint.adult is None
        assert hint.source == "unknown"
        assert not hint.is_free

    def test_an_implausible_amount_is_refused(self):
        """A four-figure number beside a euro sign is a misread."""
        assert read_price("Gesamtbudget 25000 €").adult is None


class TestInputHandling:
    def test_several_fields_are_searched(self):
        assert read_price("Konzert", None, "Eintritt frei").is_free

    def test_empty_input_is_unknown(self):
        assert read_price().source == "unknown"
        assert read_price("", None, "  ").adult is None
