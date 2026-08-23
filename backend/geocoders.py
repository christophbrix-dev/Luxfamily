"""Address geocoding, one provider per country.

Only Luxembourg is wired up. The registry exists so the border regions can be
added later as an entry rather than a rewrite — every country runs its own
cadastral service with its own endpoint and its own response shape, so there is
no single provider to grow into.

What is deliberately *not* here:

* Nominatim. Its robots.txt disallows /search, and its usage policy states that
  bulk geocoding is unsupported. The Luxembourg cadastre publishes the same data
  for this country with better precision and no such restriction.
* Any provider needing an API key. None is required for the countries we cover.

Adding a country later means writing one `_Geocoder` subclass and adding it to
GEOCODERS. Known starting points, verified as reachable without a key:

    FR  https://api-adresse.data.gouv.fr/search/   (Base Adresse Nationale)
    DE  https://sg.geodatenzentrum.de/...          (BKG — needs registration)
    BE  regional services, one per region

Precision is recorded alongside every result. A coordinate guessed from a
canton centroid must stay distinguishable from a rooftop match, otherwise the
map shows both with the same confidence.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Dict, NamedTuple, Optional

import httpx

from crawler_utils import USER_AGENT

logger = logging.getLogger("lux-backend.geocode")

# The only country the app covers today. Records carry their country so a later
# expansion can route to the right provider and filter by region.
DEFAULT_COUNTRY = "LU"


class GeoResult(NamedTuple):
    lat: float
    lng: float
    precision: str  # "address" | "street" | "locality"
    source: str
    label: str = ""


class _Geocoder:
    """One country's address service."""

    country: str = ""
    name: str = ""

    def geocode(self, query: str, *, timeout: float = 10.0) -> Optional[GeoResult]:
        raise NotImplementedError


class LuxembourgGeocoder(_Geocoder):
    """Administration du cadastre et de la topographie, via api.geoportail.lu.

    Official Luxembourg address data: no key, no quota, and precise to the
    building for a well-formed address. It resolves *addresses*, not venue
    names — "Mudam Luxembourg" returns the city centroid, while
    "1 rue du Fort Thuengen Luxembourg" returns the building. Callers should try
    a local POI lookup first for anything that is a name rather than an address.
    """

    country = "LU"
    name = "geoportail.lu"
    URL = "https://api.geoportail.lu/geocode/search"

    # The service reports how specific a match is. 8 and above is a house
    # number, 6-7 a street, below that a locality centroid.
    _ADDRESS_ACCURACY = 8
    _STREET_ACCURACY = 6

    @staticmethod
    def _tokens(text: str) -> set:
        """Comparable words: lowercased, accent-free, four letters or more."""
        stripped = "".join(
            c for c in unicodedata.normalize("NFD", text.lower())
            if unicodedata.category(c) != "Mn"
        )
        return {w for w in re.split(r"[^a-z0-9]+", stripped) if len(w) >= 4}

    @classmethod
    def _answers_the_question(cls, query: str, address: str) -> bool:
        """Whether a locality-level hit actually relates to what was asked.

        The service always returns its closest guess rather than nothing:
        "Escher Déierepark" comes back as "hierheck", and pure nonsense comes
        back as "eltz". Both look like ordinary locality matches, and its own
        `ratio` field is 0 for genuine localities too, so it cannot separate
        them. Requiring a shared word can: a real locality echoes the name back,
        a guess does not.
        """
        q, a = cls._tokens(query), cls._tokens(address)
        return bool(q & a)

    def geocode(self, query: str, *, timeout: float = 10.0) -> Optional[GeoResult]:
        if not query.strip():
            return None
        try:
            resp = httpx.get(
                self.URL,
                params={"queryString": query},
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
            )
            resp.raise_for_status()
            results = (resp.json() or {}).get("results") or []
        except Exception as exc:
            logger.warning("%s failed for %r: %s", self.name, query, exc)
            return None
        if not results:
            return None

        hit = results[0]
        coords = (hit.get("geomlonlat") or {}).get("coordinates") or []
        if len(coords) != 2:
            return None
        lng, lat = float(coords[0]), float(coords[1])

        accuracy = hit.get("accuracy") or 0
        address = str(hit.get("address") or "")
        if accuracy >= self._ADDRESS_ACCURACY:
            precision = "address"
        elif accuracy >= self._STREET_ACCURACY:
            precision = "street"
        else:
            precision = "locality"
            if not self._answers_the_question(query, address):
                logger.info("%s guessed %r for %r — rejected", self.name, address, query)
                return None

        return GeoResult(lat, lng, precision, self.name, address)


# Country code -> provider. One entry today, by choice.
GEOCODERS: Dict[str, _Geocoder] = {
    LuxembourgGeocoder.country: LuxembourgGeocoder(),
}


def geocoder_for(country: str = DEFAULT_COUNTRY) -> Optional[_Geocoder]:
    """The provider for a country, or None if we do not cover it yet.

    Returning None rather than falling back to some global service is
    deliberate: a coordinate from an unverified source is worse than an empty
    field, because nothing downstream can tell the difference.
    """
    return GEOCODERS.get((country or "").upper())


def supported_countries() -> list[str]:
    return sorted(GEOCODERS)
