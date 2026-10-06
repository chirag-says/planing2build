"""Professional registration, verification, listing and the public directory (Slice 3.2;
SLICE3_2_READINESS K0).

Only approval lists a category; listing is per professional and category; the checklist is data;
evidence stays private; operations decide with a claim and MFA; suspension, hiding and
re-verification keep history; the directory shows only listed, shown categories in a neutral
daily shuffle; a signed-in family can narrow it to professionals covering their plot."""

import asyncio
import hashlib
import io
import uuid
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from PIL import Image
from sqlalchemy import func, select, text, update

from p2b.audit.models import AuditEvent
from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.vocabulary import Audience, StaffRole
from p2b.documents.service import process_file
from p2b.identity.models import User
from p2b.integrations.clamav import AcceptAllScanner
from p2b.professionals.models import (
    ListingHistory,
    ProfessionalCategory,
    ProfessionalProfile,
)
from tests.conftest import ClientFactory, SignIn, UserFactory, csrf_headers
from tests.staff_support import OPS_HEADERS, Staff, verified_staff
from tests.test_operations import relay, submitted_project

PH = csrf_headers(Audience.PRO)
IH = csrf_headers(Audience.IHB)
RAIPUR = {"lat": 21.2514, "lng": 81.6296}  # the plot used by the requirement fixtures


def pkey() -> dict[str, str]:
    return {**PH, "Idempotency-Key": str(uuid.uuid4())}


def okey() -> dict[str, str]:
    return {**OPS_HEADERS, "Idempotency-Key": str(uuid.uuid4())}


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (12, 12), "green").save(out, format="PNG")
    return out.getvalue()


async def professional(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> AsyncClient:
    client = client_for(Audience.PRO)
    await sign_in(client, await make_user(Audience.PRO), Audience.PRO)
    return client


async def upload(app: FastAPI, database: Database, client: AsyncClient, purpose: str) -> str:
    data = png()
    response = await client.post(
        "/api/v1/pro/uploads",
        json={
            "purpose": purpose,
            "file_name": "x.png",
            "content_type": "image/png",
            "size_bytes": len(data),
        },
        headers=pkey(),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    await app.state.storage.write(urlparse(body["upload_url"]).path.lstrip("/"), data, "image/png")
    file_id: str = body["file"]["file_id"]
    assert (
        await client.post(f"/api/v1/pro/uploads/{file_id}/complete", headers=PH)
    ).status_code == 200
    await process_file(database, app.state.storage, AcceptAllScanner(), uuid.UUID(file_id))
    return file_id


async def complete_profile(
    client: AsyncClient,
    name: str = "Asha Verma",
    point: dict[str, float] = RAIPUR,
    radius: int = 25,
) -> None:
    response = await client.patch(
        "/api/v1/pro/profile",
        json={
            "display_name": name,
            "firm_name": f"{name} Studio",
            "bio": "Homes in Raipur.",
            "years_experience": 9,
            "team_size": 6,
            "base_locality": "Shankar Nagar",
            "base_point": point,
            "service_radius_km": radius,
        },
        headers=PH,
    )
    assert response.status_code == 200, response.text


async def add_category(
    client: AsyncClient, code: str, subtypes: list[str] | None = None
) -> Response:
    return await client.post(
        "/api/v1/pro/categories",
        json={"category": code, "subtypes": subtypes or []},
        headers=pkey(),
    )


async def document(
    app: FastAPI, database: Database, client: AsyncClient, kind: str, **extra: str
) -> None:
    file_id = await upload(app, database, client, "VERIFICATION_EVIDENCE")
    response = await client.post(
        "/api/v1/pro/documents", json={"kind": kind, "file_id": file_id, **extra}, headers=PH
    )
    assert response.status_code == 200, response.text


async def reference(client: AsyncClient, code: str, name: str = "Client One") -> None:
    response = await client.post(
        "/api/v1/pro/references",
        json={"category_code": code, "name": name, "phone": "9800000000", "project_note": "G+1"},
        headers=PH,
    )
    assert response.status_code == 200, response.text


async def portfolio(
    app: FastAPI, database: Database, client: AsyncClient, caption: str = "House"
) -> str:
    file_id = await upload(app, database, client, "PORTFOLIO")
    response = await client.post(
        "/api/v1/pro/portfolio", json={"file_id": file_id, "caption": caption}, headers=PH
    )
    assert response.status_code == 200, response.text
    items = response.json()["portfolio"]
    item_id: str = next(p["item_id"] for p in items if p["file"]["file_id"] == file_id)
    return item_id


async def ready_architect(
    app: FastAPI, database: Database, client: AsyncClient, name: str = "Asha Verma"
) -> None:
    await complete_profile(client, name)
    assert (await add_category(client, "ARCHITECT")).status_code == 201
    await document(app, database, client, "IDENTITY")
    await document(
        app,
        database,
        client,
        "REGISTRATION",
        category_code="ARCHITECT",
        issuer="Council of Architecture",
        number="CA/2015/12345",
    )
    await portfolio(app, database, client)


async def submit(client: AsyncClient, code: str) -> Response:
    return await client.post(f"/api/v1/pro/categories/{code}/submit", headers=pkey())


async def category_id_of(database: Database, client: AsyncClient, code: str) -> str:
    profile_id = (await client.get("/api/v1/pro/profile")).json()["profile"]["profile_id"]
    async with database.transaction() as session:
        return str(
            await session.scalar(
                select(ProfessionalCategory.id).where(
                    ProfessionalCategory.profile_id == uuid.UUID(profile_id),
                    ProfessionalCategory.category_code == code,
                )
            )
        )


async def claim(staff: Staff, category_id: str) -> None:
    detail = (await staff.client.get(f"/api/v1/ops/professional-categories/{category_id}")).json()
    item_id = detail["queue_item"]["item_id"]
    response = await staff.client.post(
        f"/api/v1/ops/queue-items/{item_id}/claim", headers=OPS_HEADERS
    )
    assert response.status_code == 200, response.text


async def check(
    staff: Staff, category_id: str, kind: str, subject: str = "seen", outcome: str = "PASSED"
) -> Response:
    return await staff.client.post(
        f"/api/v1/ops/professional-categories/{category_id}/checks",
        json={
            "kind": kind,
            "subject": subject,
            "outcome": outcome,
            "note": "internal: looked fine",
        },
        headers=OPS_HEADERS,
    )


async def decision(
    staff: Staff, category_id: str, action: str, message: str | None = None
) -> Response:
    return await staff.client.post(
        f"/api/v1/ops/professional-categories/{category_id}/{action}",
        json={"message": message, "note": "internal reviewer note"},
        headers=okey(),
    )


async def listed_architect(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    name: str = "Asha Verma",
) -> tuple[AsyncClient, str, Staff]:
    client = await professional(client_for, make_user, sign_in)
    await ready_architect(app, database, client, name)
    assert (await submit(client, "ARCHITECT")).status_code == 200
    await relay(database)
    staff = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    category_id = await category_id_of(database, client, "ARCHITECT")
    await claim(staff, category_id)
    for kind in ("IDENTITY", "REGISTRATION", "PORTFOLIO"):
        assert (await check(staff, category_id, kind)).status_code == 200
    approved = await decision(staff, category_id, "approve")
    assert approved.status_code == 200, approved.text
    return client, category_id, staff


async def directory(client: AsyncClient, **params: str) -> dict[str, Any]:
    response = await client.get("/api/v1/public/professionals", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


# --- the workflow -------------------------------------------------------------------------------


async def test_only_approval_lists_a_category(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    public = client_for(Audience.IHB)
    client = await professional(client_for, make_user, sign_in)
    await ready_architect(app, database, client)
    mine = (await client.get("/api/v1/pro/profile")).json()
    assert [c["listing_state"] for c in mine["categories"]] == ["DRAFT"]
    assert (await directory(public))["items"] == []

    assert (await submit(client, "ARCHITECT")).status_code == 200
    assert (await directory(public))["items"] == []  # pending is not public
    await relay(database)
    staff = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    queue = (await staff.client.get("/api/v1/ops/queues/professional-review")).json()["entries"]
    assert [(e["category_code"], e["listing_state"]) for e in queue] == [
        ("ARCHITECT", "PENDING_REVIEW")
    ]
    category_id = queue[0]["category_id"]

    assert (await decision(staff, category_id, "approve")).status_code == 409  # no claim
    await claim(staff, category_id)
    blocked = await decision(staff, category_id, "approve")
    assert blocked.status_code == 409
    assert set(blocked.json()["error"]["details"]["unmet"]) == {
        "identity",
        "registration",
        "portfolio",
    }
    for kind in ("IDENTITY", "REGISTRATION", "PORTFOLIO"):
        assert (await check(staff, category_id, kind)).status_code == 200
    assert (await decision(staff, category_id, "approve")).status_code == 200

    mine = (await client.get("/api/v1/pro/profile")).json()["categories"][0]
    assert (mine["listing_state"], mine["public"]) == ("LISTED", True)
    assert mine["review_due_at"] is not None
    items = (await directory(public))["items"]
    assert [i["display_name"] for i in items] == ["Asha Verma"]
    profile = (await public.get(f"/api/v1/public/professionals/{items[0]['profile_id']}")).json()
    [category] = profile["categories"]
    assert category["code"] == "ARCHITECT"
    assert set(category["verified"]) == {"IDENTITY", "REGISTRATION", "PORTFOLIO"}
    assert category["registrations"] == [
        {"issuer": "Council of Architecture", "number": "CA/2015/12345"}
    ]
    assert profile["bio"] == "Homes in Raipur."
    assert profile["team_size"] == 6
    body = str(profile)
    for private in (
        "9800000000",
        "@",
        "phone",
        "email",
        "website",
        "internal",
        "base_point",
        "21.25",
    ):
        assert private not in body, private
    queue = (await staff.client.get("/api/v1/ops/queues/professional-review")).json()["entries"]
    assert queue == []  # resolved


async def test_submission_lists_what_is_still_needed(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    client = await professional(client_for, make_user, sign_in)
    assert (await add_category(client, "CONTRACTOR")).status_code == 201
    response = await submit(client, "CONTRACTOR")
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert set(details["profile"]) == {
        "display_name",
        "base_locality",
        "base_geom",
        "service_radius_km",
        "years_experience",
        "bio",
    }
    assert set(details["requirements"]) == {"identity", "business", "portfolio", "references"}
    await complete_profile(client)
    await document(app, database, client, "IDENTITY")
    await document(app, database, client, "BUSINESS", gstin="22AAAAA0000A1Z5")
    await portfolio(app, database, client)
    await reference(client, "CONTRACTOR")
    still = await submit(client, "CONTRACTOR")
    assert still.json()["error"]["details"]["requirements"] == ["references"]  # two needed
    await reference(client, "CONTRACTOR", "Client Two")
    assert (await submit(client, "CONTRACTOR")).status_code == 200


async def test_contractor_approval_needs_references_and_a_site_visit(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    client = await professional(client_for, make_user, sign_in)
    await complete_profile(client)
    await add_category(client, "CONTRACTOR")
    await document(app, database, client, "IDENTITY")
    await document(app, database, client, "BUSINESS")
    await portfolio(app, database, client)
    await reference(client, "CONTRACTOR")
    await reference(client, "CONTRACTOR", "Client Two")
    assert (await submit(client, "CONTRACTOR")).status_code == 200
    await relay(database)
    staff = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    category_id = await category_id_of(database, client, "CONTRACTOR")
    await claim(staff, category_id)
    for kind in ("IDENTITY", "BUSINESS", "PORTFOLIO"):
        await check(staff, category_id, kind)
    await check(staff, category_id, "REFERENCE", "Client One")
    assert set(
        (await decision(staff, category_id, "approve")).json()["error"]["details"]["unmet"]
    ) == {
        "references",
        "site_visit",
    }
    await check(staff, category_id, "REFERENCE", "Client Two")
    await check(staff, category_id, "SITE_VISIT", "Visit 1")
    assert (await decision(staff, category_id, "approve")).status_code == 200
    detail = (await staff.client.get(f"/api/v1/ops/professional-categories/{category_id}")).json()
    assert detail["listing_state"] == "LISTED"
    assert detail["checks"][0]["internal_note"] == "internal: looked fine"  # operations only
    assert [r["phone"] for r in detail["references"]] == ["9800000000", "9800000000"]


async def test_where_applicable_needs_an_explicit_not_applicable(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    client = await professional(client_for, make_user, sign_in)
    await complete_profile(client)
    await add_category(client, "MEP")
    await document(app, database, client, "IDENTITY")
    await reference(client, "MEP")
    assert (await submit(client, "MEP")).status_code == 200  # qualification is where applicable
    await relay(database)
    staff = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    category_id = await category_id_of(database, client, "MEP")
    await claim(staff, category_id)
    await check(staff, category_id, "IDENTITY")
    await check(staff, category_id, "REFERENCE", "Client One")
    assert (await decision(staff, category_id, "approve")).json()["error"]["details"]["unmet"] == [
        "qualification"
    ]
    await check(staff, category_id, "REGISTRATION", "licence", outcome="NOT_APPLICABLE")
    assert (await decision(staff, category_id, "approve")).status_code == 200
    # A kind this category does not use is refused.
    other = await professional(client_for, make_user, sign_in)
    await ready_architect(app, database, other, "Other")
    await submit(other, "ARCHITECT")
    await relay(database)
    other_id = await category_id_of(database, other, "ARCHITECT")
    await claim(staff, other_id)
    assert (await check(staff, other_id, "SITE_VISIT")).status_code == 422


async def test_changes_rejection_and_reapply(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    client = await professional(client_for, make_user, sign_in)
    await ready_architect(app, database, client)
    await submit(client, "ARCHITECT")
    await relay(database)
    staff = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    category_id = await category_id_of(database, client, "ARCHITECT")
    await claim(staff, category_id)
    assert (await decision(staff, category_id, "request-changes")).status_code == 422  # message
    assert (
        await decision(staff, category_id, "request-changes", "Upload a clearer ID.")
    ).status_code == 200
    mine = (await client.get("/api/v1/pro/profile")).json()["categories"][0]
    assert (mine["listing_state"], mine["message"]) == ("CHANGES_REQUESTED", "Upload a clearer ID.")
    assert "internal" not in str(await client.get("/api/v1/pro/profile"))

    assert (await submit(client, "ARCHITECT")).status_code == 200
    await relay(database)
    await claim(staff, category_id)
    assert (
        await decision(staff, category_id, "reject", "Registration could not be verified.")
    ).status_code == 200
    mine = (await client.get("/api/v1/pro/profile")).json()["categories"][0]
    assert mine["listing_state"] == "REJECTED"
    assert mine["reapply_after"] is not None
    early = await submit(client, "ARCHITECT")
    assert early.status_code == 409
    async with database.transaction() as session:
        await session.execute(
            update(ProfessionalCategory).values(reapply_after=func.now() - timedelta(days=1))
        )
    assert (await submit(client, "ARCHITECT")).status_code == 200
    public = client_for(Audience.IHB)
    assert (await directory(public))["items"] == []


async def test_suspension_hiding_and_reverification(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    client, category_id, staff = await listed_architect(
        app, database, client_for, make_user, sign_in
    )
    public = client_for(Audience.IHB)
    assert len((await directory(public))["items"]) == 1

    url = f"/api/v1/ops/professional-categories/{category_id}"
    assert (
        await staff.client.post(f"{url}/suspend", json={"reason": ""}, headers=OPS_HEADERS)
    ).status_code == 422
    assert (
        await staff.client.post(
            f"{url}/suspend", json={"reason": "Complaint under review"}, headers=OPS_HEADERS
        )
    ).status_code == 200
    assert (await directory(public))["items"] == []
    mine = (await client.get("/api/v1/pro/profile")).json()["categories"][0]
    assert mine["listing_state"] == "SUSPENDED"
    assert (
        await client.post("/api/v1/pro/categories/ARCHITECT/hide", headers=PH)
    ).status_code == 409
    admin = await verified_staff(database, client_for, sign_in, StaffRole.ADMIN)
    assert (
        await admin.client.post(
            f"{url}/reinstate", json={"reason": "Resolved"}, headers=OPS_HEADERS
        )
    ).status_code == 200
    assert len((await directory(public))["items"]) == 1
    # Admins may suspend and reinstate, but the review decisions are operations' own.
    assert (await admin.client.get("/api/v1/ops/queues/professional-review")).status_code == 403

    assert (
        await client.post("/api/v1/pro/categories/ARCHITECT/hide", headers=PH)
    ).status_code == 200
    mine = (await client.get("/api/v1/pro/profile")).json()["categories"][0]
    assert (mine["listing_state"], mine["hidden"], mine["public"]) == ("LISTED", True, False)
    assert (await directory(public))["items"] == []
    assert (
        await client.post("/api/v1/pro/categories/ARCHITECT/show", headers=PH)
    ).status_code == 200
    assert len((await directory(public))["items"]) == 1

    async with database.transaction() as session:
        history = [
            (h.event, h.actor_role)
            for h in await session.scalars(select(ListingHistory).order_by(ListingHistory.at))
        ]
    assert history == [
        ("create", "PROFESSIONAL"),
        ("submit", "PROFESSIONAL"),
        ("approve", "OPS"),
        ("suspend", "OPS"),
        ("reinstate", "ADMIN"),
        ("hide", "PROFESSIONAL"),
        ("show", "PROFESSIONAL"),
    ]

    # Hidden past the re-verification date: showing again needs re-verification.
    assert (
        await client.post("/api/v1/pro/categories/ARCHITECT/hide", headers=PH)
    ).status_code == 200
    async with database.transaction() as session:
        await session.execute(
            update(ProfessionalCategory).values(review_due_at=func.now() - timedelta(days=1))
        )
    shown = await client.post("/api/v1/pro/categories/ARCHITECT/show", headers=PH)
    assert (shown.status_code, shown.json()["error"]["details"]["reverification"]) == (409, "due")
    assert (await submit(client, "ARCHITECT")).status_code == 200
    mine = (await client.get("/api/v1/pro/profile")).json()["categories"][0]
    assert mine["listing_state"] == "PENDING_REVIEW"
    await relay(database)
    assert (
        len((await staff.client.get("/api/v1/ops/queues/professional-review")).json()["entries"])
        == 1
    )


async def test_listing_is_per_category_and_names_are_fixed_once_submitted(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    client, _, _ = await listed_architect(app, database, client_for, make_user, sign_in)
    assert (await add_category(client, "INTERIOR_DESIGNER")).status_code == 201
    await reference(client, "INTERIOR_DESIGNER")
    assert (await submit(client, "INTERIOR_DESIGNER")).status_code == 200
    states = {
        c["code"]: c["listing_state"]
        for c in (await client.get("/api/v1/pro/profile")).json()["categories"]
    }
    assert states == {"ARCHITECT": "LISTED", "INTERIOR_DESIGNER": "PENDING_REVIEW"}
    public = client_for(Audience.IHB)
    [item] = (await directory(public))["items"]
    assert [c["code"] for c in item["categories"]] == ["ARCHITECT"]
    assert (await directory(public, category="INTERIOR_DESIGNER"))["items"] == []
    assert len((await directory(public, category="ARCHITECT"))["items"]) == 1
    renamed = await client.patch(
        "/api/v1/pro/profile", json={"display_name": "Someone Else"}, headers=PH
    )
    assert renamed.status_code == 409
    assert (
        await client.patch("/api/v1/pro/profile", json={"bio": "Updated."}, headers=PH)
    ).status_code == 200
    bad = await add_category(client, "SPECIALIST", ["WATERPROOFING", "ARCHITECT"])
    assert bad.status_code == 422  # only the category's own subtypes
    assert (await add_category(client, "SPECIALIST", ["WATERPROOFING", "SOLAR"])).status_code == 201


async def test_evidence_and_portfolio_privacy(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    client, category_id, staff = await listed_architect(
        app, database, client_for, make_user, sign_in
    )
    dashboard = (await client.get("/api/v1/pro/profile")).json()
    evidence_file = dashboard["documents"][0]["file"]["file_id"]
    [item] = dashboard["portfolio"]
    public = client_for(Audience.IHB)
    [card] = (await directory(public))["items"]
    profile = (await public.get(f"/api/v1/public/professionals/{card['profile_id']}")).json()
    assert profile["portfolio"] == []  # not yet approved by operations
    assert card["cover_image_url"] is None

    assert (
        await staff.client.post(
            f"/api/v1/ops/portfolio-items/{item['item_id']}/approve", headers=OPS_HEADERS
        )
    ).json() == {"review_state": "APPROVED"}
    profile = (await public.get(f"/api/v1/public/professionals/{card['profile_id']}")).json()
    assert profile["portfolio"][0]["image_url"].startswith("https://storage.test/")
    assert "inline=" in profile["portfolio"][0]["image_url"]
    assert "documents" not in profile
    assert "references" not in profile

    # Evidence: the owner and operations only.
    assert (await client.get(f"/api/v1/pro/files/{evidence_file}/url")).status_code == 200
    stranger = await professional(client_for, make_user, sign_in)
    assert (await stranger.get(f"/api/v1/pro/files/{evidence_file}/url")).status_code == 404
    family, _ = await submitted_project(client_for, make_user, sign_in)
    assert (await family.get(f"/api/v1/files/{evidence_file}/url")).status_code == 404
    assert (await staff.client.get(f"/api/v1/ops/files/{evidence_file}/url")).status_code == 200
    # Operations routes are not reachable from other hosts.
    assert (
        await client.get(f"/api/v1/ops/professional-categories/{category_id}")
    ).status_code == 404
    assert (
        await family.get(f"/api/v1/ops/professional-categories/{category_id}")
    ).status_code == 404


async def test_the_directory_is_a_neutral_daily_shuffle(
    database: Database, client_for: ClientFactory, make_user: UserFactory
) -> None:
    ids = []
    async with database.transaction() as session:
        for name in ("Aarav", "Bhavna", "Chetan", "Divya", "Esha", "Farhan", "Gita"):
            user_id = await make_user(Audience.PRO)
            profile_id = new_id()
            session.add(
                ProfessionalProfile(
                    id=profile_id,
                    user_id=user_id,
                    display_name=name,
                    base_locality="Raipur",
                    service_radius_km=20,
                )
            )
            await session.flush()
            session.add(
                ProfessionalCategory(
                    id=new_id(),
                    profile_id=profile_id,
                    category_code="CONTRACTOR",
                    listing_state="LISTED",
                )
            )
            ids.append(profile_id)
        today = (await session.execute(select(func.current_date()))).scalar_one()
    expected = sorted(
        ids,
        key=lambda i: (
            hashlib.md5(f"{i}{today.isoformat()}".encode(), usedforsecurity=False).hexdigest(),
            i,
        ),
    )
    public = client_for(Audience.IHB)
    first = await public.get("/api/v1/public/professionals")
    assert first.json()["order"] == "daily_shuffle"
    seen = [uuid.UUID(i["profile_id"]) for i in first.json()["items"]]
    assert seen == expected
    again = [uuid.UUID(i["profile_id"]) for i in (await directory(public))["items"]]
    assert again == seen  # stable within the day
    other_day = sorted(
        ids,
        key=lambda i: (
            hashlib.md5(
                f"{i}{(today + timedelta(days=1)).isoformat()}".encode(), usedforsecurity=False
            ).hexdigest(),
            i,
        ),
    )
    assert other_day != seen or len(ids) < 3  # a different day gives a different order


async def test_directory_pages_cover_everyone_once(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import p2b.professionals.service as service

    monkeypatch.setattr(service, "PAGE_SIZE", 2)
    async with database.transaction() as session:
        for index in range(5):
            profile_id = new_id()
            session.add(
                ProfessionalProfile(
                    id=profile_id, user_id=await make_user(Audience.PRO), display_name=f"P{index}"
                )
            )
            await session.flush()
            session.add(
                ProfessionalCategory(
                    id=new_id(),
                    profile_id=profile_id,
                    category_code="ARCHITECT",
                    listing_state="LISTED",
                )
            )
    public = client_for(Audience.IHB)
    seen: list[str] = []
    cursor = None
    while True:
        page = await directory(public, **({"cursor": cursor} if cursor else {}))
        seen += [i["profile_id"] for i in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 5


async def test_project_aware_filter_narrows_to_professionals_covering_the_plot(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    _, _, staff = await listed_architect(
        app, database, client_for, make_user, sign_in, "Near Studio"
    )
    far = await professional(client_for, make_user, sign_in)
    await complete_profile(far, "Far Studio", {"lat": 19.0760, "lng": 72.8777}, 50)  # Mumbai
    await add_category(far, "ARCHITECT")
    await document(app, database, far, "IDENTITY")
    await document(app, database, far, "REGISTRATION", category_code="ARCHITECT")
    await portfolio(app, database, far)
    await submit(far, "ARCHITECT")
    await relay(database)
    far_id = await category_id_of(database, far, "ARCHITECT")
    await claim(staff, far_id)
    for kind in ("IDENTITY", "REGISTRATION", "PORTFOLIO"):
        await check(staff, far_id, kind)
    assert (await decision(staff, far_id, "approve")).status_code == 200

    public = client_for(Audience.IHB)
    assert {i["display_name"] for i in (await directory(public))["items"]} == {
        "Near Studio",
        "Far Studio",
    }
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    response = await family.get(f"/api/v1/projects/{project_id}/professionals")
    assert response.status_code == 200, response.text
    assert [i["display_name"] for i in response.json()["items"]] == ["Near Studio"]
    other_family, _ = await submitted_project(client_for, make_user, sign_in)
    assert (
        await other_family.get(f"/api/v1/projects/{project_id}/professionals")
    ).status_code == 404
    assert (await public.get(f"/api/v1/projects/{project_id}/professionals")).status_code == 401


async def test_racing_first_requests_create_one_profile(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    """A page and its layout ask for the new profile at once; neither fails (regression)."""
    client = await professional(client_for, make_user, sign_in)
    responses = await asyncio.gather(*(client.get("/api/v1/pro/profile") for _ in range(4)))
    assert [r.status_code for r in responses] == [200] * 4
    profile_ids = {r.json()["profile"]["profile_id"] for r in responses}
    assert len(profile_ids) == 1
    async with database.transaction() as session:
        created = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.entity_id == uuid.UUID(profile_ids.pop()),
                AuditEvent.action == "professional_profile.created",
            )
        )
    assert created == 1


async def test_operations_can_create_an_account_that_enters_the_same_review(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    staff = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    body = {"email": "Builder@Example.in", "display_name": "Raipur Builders"}
    created = await staff.client.post("/api/v1/ops/professionals", json=body, headers=okey())
    assert created.status_code == 200, created.text
    assert created.json()["created"] is True
    again = await staff.client.post("/api/v1/ops/professionals", json=body, headers=okey())
    assert again.json()["created"] is False
    assert again.json()["profile_id"] == created.json()["profile_id"]
    user_id = uuid.UUID(created.json()["user_id"])
    async with database.transaction() as session:
        user = await session.get_one(User, user_id)
        audit = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.entity_id == user_id, AuditEvent.action == "user.registered")
        )
    assert (user.audience, user.status, audit) == ("pro", "PENDING_VERIFICATION", 1)
    # The first sign-in with the emailed code activates the account (identity, tested there).
    async with database.transaction() as session:
        await session.execute(update(User).where(User.id == user_id).values(status="ACTIVE"))
    client = client_for(Audience.PRO)
    await sign_in(client, user_id, Audience.PRO)
    mine = (await client.get("/api/v1/pro/profile")).json()
    assert mine["profile"]["display_name"] == "Raipur Builders"
    assert mine["categories"] == []  # not listed: the same review applies


async def test_no_membership_or_single_route_structures_exist(database: Database) -> None:
    async with database.transaction() as session:
        tables = set(
            await session.scalars(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                )
            )
        )
        project_columns = set(
            await session.scalars(
                text(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_name = 'projects'"
                )
            )
        )
        category_columns = set(
            await session.scalars(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'professional_categories'"
                )
            )
        )
    assert not {t for t in tables if t.startswith("club")}
    assert not project_columns & {"contractor_route", "path", "contractor_status"}
    assert "class" not in category_columns  # D-05
    assert "enlistment_class" not in category_columns
