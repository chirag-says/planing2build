"""The two capture paths (REQUIREMENT_QUESTIONS_V1 L.3) and the locality from the map pin (R-3;
INTEGRATION section 5)."""

import asyncio
from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from p2b.core.db import Database
from p2b.core.geocoding import GeocoderUnavailable, Place
from p2b.core.outbox import OutboxEvent
from p2b.core.vocabulary import Audience
from p2b.integrations.nominatim import NominatimGeocoder
from p2b.projects.models import Enquiry
from tests.conftest import ClientFactory, SignIn, UserFactory, csrf_headers

H = csrf_headers(Audience.IHB)


async def test_coming_soon_help_records_the_work_type_and_email(
    client_for: ClientFactory, database: Database
) -> None:
    response = await client_for(Audience.IHB).post(
        "/api/v1/public/enquiries",
        json={"kind": "COMING_SOON_HELP", "work_type": "INTERIORS", "email": "Fam@Example.in"},
        headers=H,
    )
    assert response.status_code == 202
    async with database.transaction() as session:
        enquiry = (await session.scalars(select(Enquiry))).one()
        events = list(await session.scalars(select(OutboxEvent.event_type)))
    assert (enquiry.kind, enquiry.work_type, enquiry.email) == (
        "COMING_SOON_HELP",
        "INTERIORS",
        "fam@example.in",
    )
    assert events == ["enquiry.created"]


async def test_other_city_captures_email_only(
    client_for: ClientFactory, database: Database
) -> None:
    client = client_for(Audience.IHB)
    ok = await client.post(
        "/api/v1/public/enquiries", json={"kind": "OTHER_CITY", "email": "a@b.in"}, headers=H
    )
    assert ok.status_code == 202
    with_work = await client.post(
        "/api/v1/public/enquiries",
        json={"kind": "OTHER_CITY", "email": "a@b.in", "work_type": "REPAIRS"}, headers=H,
    )  # fmt: skip
    assert with_work.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "COMING_SOON_HELP", "email": "a@b.in"},  # type of work missing
        {"kind": "COMING_SOON_HELP", "email": "a@b.in", "work_type": "KITCHEN"},
        {"kind": "COMING_SOON_HELP", "email": "not-an-email", "work_type": "REPAIRS"},
        {"kind": "MATERIAL_SUPPLY", "email": "a@b.in"},
    ],
)
async def test_invalid_enquiries_are_rejected(
    client_for: ClientFactory, body: dict[str, str]
) -> None:
    response = await client_for(Audience.IHB).post("/api/v1/public/enquiries", json=body, headers=H)
    assert response.status_code == 422


async def test_enquiries_are_rate_limited_per_contact(client_for: ClientFactory) -> None:
    client = client_for(Audience.IHB)
    body = {"kind": "OTHER_CITY", "email": "same@b.in"}
    codes = [
        (await client.post("/api/v1/public/enquiries", json=body, headers=H)).status_code
        for _ in range(6)
    ]
    assert codes == [202] * 5 + [429]


async def test_enquiries_need_the_csrf_headers(client_for: ClientFactory) -> None:
    response = await client_for(Audience.IHB).post(
        "/api/v1/public/enquiries", json={"kind": "OTHER_CITY", "email": "a@b.in"}
    )
    assert response.status_code == 403


class FakeGeocoder:
    name = "fake"

    def __init__(self, place: Place | None) -> None:
        self.place = place
        self.calls = 0

    async def reverse(self, lat: float, lng: float) -> Place:
        self.calls += 1
        if self.place is None:
            raise GeocoderUnavailable("down")
        return self.place


@pytest.fixture
def geocoder(app: FastAPI) -> Iterator[FakeGeocoder]:
    fake = FakeGeocoder(Place(locality="Shankar Nagar", city="Raipur", raw={"x": 1}))
    original = app.state.geocoder
    app.state.geocoder = fake
    yield fake
    app.state.geocoder = original


async def test_the_locality_comes_from_the_pin_and_is_cached(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, geocoder: FakeGeocoder
) -> None:
    client = client_for(Audience.IHB)
    await sign_in(client, await make_user(), Audience.IHB)
    for _ in range(2):
        response = await client.get(
            "/api/v1/geo/locality", params={"lat": 21.25141, "lng": 81.62961}
        )
        assert response.json() == {"locality": "Shankar Nagar"}
        await asyncio.sleep(1.05)  # the global provider limit is one per second
    assert geocoder.calls == 1


async def test_a_geocoder_outage_leaves_the_locality_for_the_family_to_type(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, geocoder: FakeGeocoder
) -> None:
    geocoder.place = None
    client = client_for(Audience.IHB)
    await sign_in(client, await make_user(), Audience.IHB)
    response = await client.get("/api/v1/geo/locality", params={"lat": 21.3, "lng": 81.7})
    assert response.status_code == 200
    assert response.json() == {"locality": None}


async def test_the_locality_lookup_needs_a_signed_in_homeowner(client_for: ClientFactory) -> None:
    response = await client_for(Audience.IHB).get(
        "/api/v1/geo/locality", params={"lat": 1, "lng": 1}
    )
    assert response.status_code == 401


async def test_nominatim_adapter_reads_the_neighbourhood() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "address": {"suburb": "Shankar Nagar", "city": "Raipur", "state": "Chhattisgarh"}
            },
        )

    geocoder = NominatimGeocoder(
        "https://nominatim.test", "Plan2Build-test", httpx.MockTransport(handle)
    )
    place = await geocoder.reverse(21.25, 81.63)
    assert (place.locality, place.city) == ("Shankar Nagar", "Raipur")
    assert seen[0].headers["user-agent"] == "Plan2Build-test"
    assert seen[0].url.params["lat"] == "21.25"


async def test_nominatim_failure_is_reported_as_unavailable() -> None:
    geocoder = NominatimGeocoder(
        "https://nominatim.test", "ua", httpx.MockTransport(lambda _: httpx.Response(503))
    )
    with pytest.raises(GeocoderUnavailable):
        await geocoder.reverse(1, 1)
