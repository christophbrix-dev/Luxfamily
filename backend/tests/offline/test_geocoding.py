"""Geocoding: the right provider per country, and no invented coordinates."""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import geocoders  # noqa: E402
from geocoders import LuxembourgGeocoder, geocoder_for, supported_countries  # noqa: E402


def test_only_luxembourg_is_wired_up():
    """Doors built, deliberately closed. Adding a country is an entry, not a rewrite."""
    assert supported_countries() == ["LU"]
    assert geocoder_for("FR") is None
    assert geocoder_for("DE") is None


def test_an_uncovered_country_returns_nothing_rather_than_guessing():
    """A coordinate from an unverified source is worse than an empty field,
    because nothing downstream can tell the two apart."""
    assert geocoder_for("XX") is None
    assert geocoder_for("") is None


def test_country_code_is_case_insensitive():
    assert geocoder_for("lu") is not None


def test_nominatim_is_not_called_anywhere():
    """Its robots.txt disallows /search and its terms exclude bulk geocoding.

    Looks for the endpoint rather than the word — explaining in a comment why we
    do not use it is fine, calling it is not.
    """
    offenders = [
        p.name for p in BACKEND.glob("*.py")
        if "nominatim.openstreetmap.org" in p.read_text().lower()
    ]
    assert not offenders, f"still calling Nominatim: {offenders}"


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _stub(monkeypatch, address, accuracy):
    payload = {"results": [{
        "address": address,
        "accuracy": accuracy,
        "geomlonlat": {"coordinates": [6.1319, 49.6117]},
    }]}
    monkeypatch.setattr(geocoders.httpx, "get", lambda *a, **k: _Response(payload))


def test_a_house_number_is_reported_as_an_address(monkeypatch):
    _stub(monkeypatch, "1, Rue du Fort Thüngen 1499 Luxembourg", 8)
    result = LuxembourgGeocoder().geocode("1, rue du Fort Thüngen, Luxembourg")
    assert result.precision == "address"
    assert (round(result.lat, 4), round(result.lng, 4)) == (49.6117, 6.1319)


def test_a_street_is_reported_as_a_street(monkeypatch):
    _stub(monkeypatch, "Route de Trèves, Luxembourg", 6)
    assert LuxembourgGeocoder().geocode("Route de Trèves").precision == "street"


def test_a_real_locality_is_accepted(monkeypatch):
    _stub(monkeypatch, "bettembourg,Luxembourg", 5)
    assert LuxembourgGeocoder().geocode("Bettembourg").precision == "locality"


def test_accents_do_not_prevent_a_match(monkeypatch):
    _stub(monkeypatch, "esch-sur-alzette,Luxembourg", 5)
    assert LuxembourgGeocoder().geocode("Esch-sur-Alzette") is not None


def test_a_guessed_locality_is_rejected(monkeypatch):
    """The service answers with its nearest guess rather than nothing.

    'Escher Déierepark' comes back as 'hierheck' — a plausible-looking
    coordinate for a place that was never found. Its own confidence field reads
    0 for genuine localities too, so only the returned name can separate them.
    """
    _stub(monkeypatch, "hierheck,Luxembourg", 5)
    assert LuxembourgGeocoder().geocode("Escher Déierepark") is None


def test_nonsense_is_rejected(monkeypatch):
    _stub(monkeypatch, "eltz,Luxembourg", 5)
    assert LuxembourgGeocoder().geocode("völliger Unsinn xyz123") is None


def test_an_empty_query_never_hits_the_network(monkeypatch):
    def explode(*a, **k):
        raise AssertionError("should not have called out")

    monkeypatch.setattr(geocoders.httpx, "get", explode)
    assert LuxembourgGeocoder().geocode("   ") is None


def test_a_failing_service_yields_nothing(monkeypatch):
    def explode(*a, **k):
        raise OSError("timeout")

    monkeypatch.setattr(geocoders.httpx, "get", explode)
    assert LuxembourgGeocoder().geocode("Bettembourg") is None
