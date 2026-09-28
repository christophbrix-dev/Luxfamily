# A page's <title> is not an event's name.
#
# Four sources that had never been tried turned out to carry events, and two of
# them signed every title with the commune: "Journée de la commémoration
# nationale - Commune de Leudelange". Among them were pages that are not events
# at all — "Actualités - Commune de Leudelange" is a news archive, and it
# carried a date, so it would have been stored as something happening that day.
#
# The rule is deliberately narrow. Measuring this the first time with a crude
# regex produced the wrong answer and the wrong advice: 20 of Käerjeng's 24
# titles looked like site names and were in fact organisers — Handball
# Käerjeng, Kulturkommissioun, Käerjenger Musekschoul. Trimming those would
# have cost the reader who is holding the evening.

import pytest

from importers import is_not_an_event, site_identity, strip_site_tail


# ---------------------------------------------------------------------------
# Which name a site signs with
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("source_name, expected", [
    ("Käerjeng (Bascharage) — Sitemap", "Käerjeng"),
    ("Leudelange — Sitemap", "Leudelange"),
    ("Casino Luxembourg (Contemporary Art) — Sitemap", "Casino Luxembourg"),
    ("Ville de Luxembourg — Sitemap", "Ville de Luxembourg"),
    ("Rockhal", "Rockhal"),
])
def test_the_signature_comes_from_the_source_not_the_town(source_name, expected):
    """Käerjeng signs with "Käerjeng"; its events happen in Bascharage.

    Taking it from the event's town instead left every one of those tails in
    place, because the two words are simply different.
    """
    assert site_identity({"name": source_name}) == expected


def test_a_source_without_a_name_signs_with_nothing():
    assert site_identity({}) is None
    assert site_identity({"name": ""}) is None


# ---------------------------------------------------------------------------
# What is trimmed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title, expected", [
    ("Journée de la commémoration nationale - Commune de Leudelange",
     "Journée de la commémoration nationale"),
    ("L'apero des cultures - Commune de Leudelange", "L'apero des cultures"),
    ("Illusiounen - Commune de Leudelange", "Illusiounen"),
    ("Sproochecafé – Ville de Differdange", "Sproochecafé"),
    ("Concert – Gemeng Sandweiler", "Concert"),
])
def test_a_commune_signature_at_the_end_is_removed(title, expected):
    assert strip_site_tail(title) == expected


def test_a_title_with_its_own_dashes_keeps_them():
    """Only the tail is examined, and only when it is an identity.

    "Programm - Dag vun de Senioren - Commune de Leudelange" loses one segment,
    not two.
    """
    assert strip_site_tail("Programm - Dag vun de Senioren - Commune de Leudelange") \
        == "Programm - Dag vun de Senioren"


@pytest.mark.parametrize("title", [
    "Plogging – Pick up and run",
    "Trikot Party – Handball Käerjeng",
    "Liesowend mam Jemp Schuster – Kulturkommissioun",
    "Concert – Käerjenger Musekschoul",
    "Les couleurs de la nature – édition d’automne",
    "Rollenger Millefest",
])
def test_a_tail_that_is_not_a_signature_stays(title):
    """The half of this that matters.

    An organiser, a club, a music school or the second half of the event's own
    name all sit where a site signature would. Removing them would cost the
    reader more than leaving a suffix on ever could.
    """
    assert strip_site_tail(title, "Käerjeng") == title


def test_only_the_exact_commune_is_removed_when_it_stands_alone():
    assert strip_site_tail("Enseignement fondamental - Käerjeng", "Käerjeng") \
        == "Enseignement fondamental"
    # …and the same word inside a longer tail is left alone.
    assert strip_site_tail("Trikot Party – Handball Käerjeng", "Käerjeng") \
        == "Trikot Party – Handball Käerjeng"


def test_a_title_that_is_only_the_signature_is_left_for_the_caller():
    """Handing back an empty string would store an event with no name."""
    assert strip_site_tail("Käerjeng", "Käerjeng") == "Käerjeng"


# ---------------------------------------------------------------------------
# What is refused outright
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title, site", [
    ("Actualités - Commune de Leudelange", None),
    ("Archives des Actualités - Käerjeng", "Käerjeng"),
    ("Actualités", None),
    ("News", None),
    ("Agenda", None),
    ("Veranstaltungen", None),
])
def test_a_section_of_a_website_is_not_an_event(title, site):
    """These carry a date — the page's own — and would have been stored as
    something happening on it."""
    assert is_not_an_event(title, site)


@pytest.mark.parametrize("title", [
    "Agenda culturel de la Ville",
    "Actualités du quartier — fête de rue",
    "Rollenger Millefest",
    "Trikot Party – Handball Käerjeng",
    "",
])
def test_a_real_event_is_not_refused(title):
    """The refusal matches the whole title, not a word in it.

    An empty title is not refused here either: it is missing, and the importer
    above already declines to store an event without one.
    """
    assert not is_not_an_event(title, "Käerjeng")
