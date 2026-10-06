"""Nominatim reverse geocoding behind `p2b.core.geocoding.Geocoder` (INTEGRATION sections 5, 10).
The public instance allows about one request per second with an identifying user agent; callers
cache results (`geocode_cache`) and rate-limit. Timeouts: connect 3 s, read 5 s. Only the pin's
coordinates are sent, never a name or contact."""

from typing import Any

import httpx

from p2b.core.config import Settings
from p2b.core.geocoding import Geocoder, GeocoderUnavailable, Place

TIMEOUT = httpx.Timeout(5.0, connect=3.0)
# Nominatim address parts that name a neighbourhood, most specific first.
LOCALITY_KEYS = ("neighbourhood", "suburb", "quarter", "residential", "city_district", "village")
CITY_KEYS = ("city", "town", "county", "state_district")


def place_from(payload: dict[str, Any]) -> Place:
    address = payload.get("address") or {}
    locality = next((address[k] for k in LOCALITY_KEYS if address.get(k)), None)
    city = next((address[k] for k in CITY_KEYS if address.get(k)), None)
    return Place(locality=locality, city=city, raw=payload)


class NominatimGeocoder:
    name = "nominatim"

    def __init__(
        self, base_url: str, user_agent: str, transport: httpx.AsyncBaseTransport | None = None
    ):
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        self._transport = transport

    async def reverse(self, lat: float, lng: float) -> Place:
        async with httpx.AsyncClient(
            timeout=TIMEOUT, transport=self._transport, headers={"User-Agent": self._user_agent}
        ) as client:
            try:
                response = await client.get(
                    f"{self._base_url}/reverse",
                    params={"format": "jsonv2", "lat": lat, "lon": lng, "zoom": 16,
                            "addressdetails": 1, "accept-language": "en"},
                )  # fmt: skip
            except httpx.TransportError as exc:
                raise GeocoderUnavailable(type(exc).__name__) from exc
        if response.status_code != 200:
            raise GeocoderUnavailable(f"status {response.status_code}")
        return place_from(response.json())


class NoGeocoder:
    """No lookup: the family types the locality (offline development and tests)."""

    name = "none"

    async def reverse(self, lat: float, lng: float) -> Place:
        return Place(locality=None, city=None, raw={})


def build_geocoder(settings: Settings) -> Geocoder:
    if settings.geocoder_provider == "nominatim":
        return NominatimGeocoder(settings.nominatim_url, settings.nominatim_user_agent)
    return NoGeocoder()
