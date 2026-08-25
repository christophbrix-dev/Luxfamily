"""What the family filter must catch, and — more importantly — must not.

The second half of this file matters more than the first. A filter that misses
one strip club shows one bad row that a user can report. A filter that is too
eager deletes the Schueberfouer, and nobody ever finds out why the biggest
event in the country stopped appearing.

Every case in `test_keeps_*` is a real Luxembourg event type that an earlier
draft of the vocabulary would have thrown away.
"""
import pytest

from content_filter import assess, is_family_safe


# --------------------------------------------------------------------------
# must be refused
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Nightclub XY – Striptease Show ab 22 Uhr",
        "Sexparty im Keller",
        "Besuch im Bordell",
        "Eros-Center Neueröffnung",
        "Erotikmesse Luxemburg 2026",
        "Salon érotique de Luxembourg",
        "Swingerclub Abend",
        "Escort Service – diskret",
        "Table-Dance Bar",
        "Peep-Show",
        "Maison close",
        "Fetisch-Party",
        "Nacktbar",
        "XXX-Kino",
        "Pornofilm-Abend",
    ],
)
def test_refuses_explicit(text):
    verdict = assess(text)
    assert verdict is not None, f"slipped through: {text!r}"
    assert verdict[0] == "explicit"


def test_explicit_description_beats_harmless_title():
    """A clean title does not launder the body text."""
    verdict = assess("Abend im Zentrum", "Striptease und Table-Dance ab 22 Uhr")
    assert verdict is not None
    assert verdict[0] == "explicit"


def test_reports_the_word_it_matched():
    """The log has to say why, or the filter cannot be checked."""
    reason, word = assess("Grosse Sexmesse")
    assert reason == "explicit"
    assert "sexmesse" in word.lower()


# --------------------------------------------------------------------------
# must be kept — the half that matters
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        # Christoph's own examples. Alcohol and an over-18 evening are not
        # reasons to hide anything.
        "Schueberfouer 2026 – Fouer-Owend mat Bierzelt",
        "Kartoffelpuffer und Glühwein am Stand",
        "Cocktailbar – Happy Hour ab 18 Joer",
        "Weinprobe im Musel-Keller, ab 18 Jahren",
        "Bierfest Diekirch",
        "Restaurant-Abend mit Weinbegleitung, 18+",
        "Nightlife: DJ-Set bis 4 Uhr, Eintritt ab 18",
        # The event this filter first flagged in the live database. "Ab 18" is
        # half past six.
        "Kuebecafé – Freides, 🕡 Ab 18:30 📍 Um Centre Kueb",
        # Innocent compounds.
        "Sextett spielt Schubert",
        "Blechbläser-Sextett",
        "Nacktschnecken-Wanderung für Kinder",
        "Comic-Strip Workshop für Kinder",
        "Ford Escort Oldtimertreffen",
        "XXX. Editioun vum Festival",
        "Hardcore-Punk Konzert in der Rockhal",
        "Streifen am Zebrastreifen – Verkehrserziehung",
        "Filmstrip-Ausstellung",
        # Ordinary listings.
        "Kannerfest am Park",
        "Concert pour adultes et enfants",
        "Cours de poterie pour adultes",
    ],
)
def test_keeps_ordinary_events(text):
    verdict = assess(text)
    assert verdict is None, f"wrongly refused {text!r} because of {verdict}"


def test_keeps_the_schueberfouer_in_full():
    """Named explicitly, because losing it is the failure that would matter."""
    assert is_family_safe(
        "Schueberfouer",
        "Dee gréisste Vollek sfest vu Lëtzebuerg. Bierzelter, Fahrgeschäfter, "
        "Kartoffelpuffer a Gromperekichelcher. Owes ab 18 Joer am Festzelt.",
        "Festival, Familie",
    )


# --------------------------------------------------------------------------
# edges
# --------------------------------------------------------------------------
def test_empty_input_is_safe():
    assert assess() is None
    assert assess("", None, "   ") is None


def test_matching_ignores_case():
    assert assess("STRIPCLUB") is not None
    assert assess("bOrDeLl") is not None


def test_word_boundaries_hold():
    """The fragment must be a word, not a substring of one."""
    assert assess("Sextett") is None
    assert assess("Sex-Shop") is not None
