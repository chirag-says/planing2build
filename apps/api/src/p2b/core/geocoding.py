"""Reverse geocoding interface (INTEGRATION_ARCHITECTURE section 5). The pin is the truth; the
locality name is a suggestion the family confirms or corrects (REQUIREMENT_QUESTIONS_V1 R-3)."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Place:
    locality: str | None
    city: str | None
    raw: dict[str, Any]


class GeocoderUnavailable(Exception):
    pass


class Geocoder(Protocol):
    name: str

    async def reverse(self, lat: float, lng: float) -> Place: ...
