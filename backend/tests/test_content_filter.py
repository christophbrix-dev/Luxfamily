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


@pytest.mark.parametrize(
    "text",
    [
        # How these places name themselves, which is the register that matters.
        # A commune feed will never publish an insult; it could conceivably
        # syndicate a venue listing.
        "Club libertin – soirée privée",
        "Soirée libertine au château",
        "Saunaclub Wellness 24",
        "Begleitservice Luxembourg",
        "Terminwohnung – neue Adresse",
        "Gogo-Bar Eröffnung",
        "Adult Shop – Neueröffnung",
        "Salon de massage érotique",
        "Maison de passe",
        "Pornokino Nonstop",
        "Seksclub Venlo",
    ],
)
def test_refuses_the_operator_vocabulary(text):
    """Added after a public swear-word list turned out to cover none of this."""
    verdict = assess(text)
    assert verdict is not None, f"slipped through: {text!r}"
    assert verdict[0] == "explicit"


def test_a_plain_sauna_is_not_a_saunaclub():
    """Wellness is a normal family listing; only the compound is refused."""
    assert is_family_safe("Sauna und Hallenbad, Familientarif")
    assert is_family_safe("Wellness: Sauna, Dampfbad, Ruheraum")
    assert assess("Saunaclub") is not None


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


@pytest.mark.parametrize(
    "text",
    [
        # Luxembourgish "ass" is the verb "is" — the copula of the national
        # language. An English swear-word list contains "ass", and matching it
        # hit 39 events in the live database.
        "ADRAD Kayldall weist wat Funken ass",
        "Wat ass lass an der Gemeng?",
        # French "con" inside a dish, on a commune dinner listing.
        "Chili con carne am Kulturzentrum",
        # A wreath laid at a war memorial. "gerbe" is on the French list.
        "Cérémonie de dépôt de gerbe au monument aux morts",
        # A public swimming pool whose name is an acronym.
        "Piscine SPIC",
        # Dutch lists carry "nicht"; German "nicht" means "not".
        "Nicht-Mitglieder: Erwachsene 21 EUR",
        # Adult-site category names are ordinary English words.
        "Outdoor swimming pool",
        "Halloween Party am Duerf",
        "Jardin éphémère – Ephemeral Garden",
        "Musée 385th bomb group",
        "Un parking public se trouve des deux côtés du parc",
        "Séance tout public à 15h",
    ],
)
def test_public_wordlists_would_have_eaten_these(text):
    """Every line here is real text from the live database.

    Two off-the-shelf vocabularies were evaluated as a way to strengthen this
    filter: a public multi-language swear-word list, and the category taxonomy
    of adult sites. Measured against the 8,210 documents we actually hold,
    neither found a single piece of adult content — and between them they
    matched a war-memorial ceremony, a chili con carne dinner, a swimming
    pool, a WWII museum, the outdoor pool, the Halloween party, and 39
    Luxembourgish sentences containing the word "is".

    They are the wrong instrument: they are built to catch insults typed by
    anonymous users in chat, and our problem is classifying event listings
    from 103 curated municipal and cultural sources. These cases are kept as
    tests so the conclusion survives the next person who has the same idea.
    """
    assert assess(text) is None, f"wrongly refused real text: {text!r}"


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
