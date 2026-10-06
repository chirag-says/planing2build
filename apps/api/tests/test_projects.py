"""Projects, requirement capture and submission (STATE_MODEL 5; API sections 1 and 4; SECURITY 4.2;
REQUIREMENT_QUESTIONS_V1 section L)."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select

from p2b.audit.models import AuditEvent
from p2b.core.db import Database
from p2b.core.outbox import OutboxEvent
from p2b.core.vocabulary import Audience
from p2b.projects.models import Project, ProjectStatusHistory
from tests.conftest import ClientFactory, SignIn, UserFactory, csrf_headers
from tests.test_questions import COMPLETE

H = csrf_headers(Audience.IHB)


def _key() -> dict[str, str]:
    return {**H, "Idempotency-Key": str(uuid.uuid4())}


async def homeowner(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> AsyncClient:
    client = client_for(Audience.IHB)
    await sign_in(client, await make_user(), Audience.IHB)
    return client


async def new_project(client: AsyncClient) -> dict[str, Any]:
    response = await client.post("/api/v1/projects", json={"city": "Raipur"}, headers=_key())
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def save(
    client: AsyncClient, project_id: str, answers: dict[str, Any], version: int
) -> Response:
    return await client.put(
        f"/api/v1/projects/{project_id}/requirement",
        json={"answers": answers, "version": version}, headers=H,
    )  # fmt: skip


async def submit(client: AsyncClient, project_id: str, version: int) -> Response:
    return await client.post(
        f"/api/v1/projects/{project_id}/requirement/submit",
        json={"version": version},
        headers=_key(),
    )


async def test_creating_a_project_starts_a_draft_owned_by_the_homeowner(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    client = await homeowner(client_for, make_user, sign_in)
    body = await new_project(client)
    assert body["project"]["status"] == "DRAFT"
    assert body["project"]["code"].startswith("P2B-RPR-")
    assert body["requirement"] == {
        "question_set_version": 1,
        "answers": {},
        "version": 1,
        "submitted_at": None,
    }
    listed = (await client.get("/api/v1/projects")).json()
    assert [p["project_id"] for p in listed] == [body["project"]["project_id"]]
    async with database.transaction() as session:
        actions = list(await session.scalars(select(AuditEvent.action)))
        events = list(await session.scalars(select(OutboxEvent.event_type)))
    assert "project.status_changed" in actions
    assert events == ["project.created"]


async def test_project_creation_needs_an_idempotency_key_and_replays_safely(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    client = await homeowner(client_for, make_user, sign_in)
    missing = await client.post("/api/v1/projects", json={"city": "Raipur"}, headers=H)
    assert missing.status_code == 422
    headers = _key()
    first = await client.post("/api/v1/projects", json={"city": "Raipur"}, headers=headers)
    replay = await client.post("/api/v1/projects", json={"city": "Raipur"}, headers=headers)
    assert replay.status_code == 201
    assert replay.json() == first.json()
    async with database.transaction() as session:
        assert await session.scalar(select(func.count()).select_from(Project)) == 1
    mismatch = await client.post("/api/v1/projects", json={"city": "Bilaspur"}, headers=headers)
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "IDEMPOTENCY_MISMATCH"


async def test_only_active_cities_get_projects(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    client = await homeowner(client_for, make_user, sign_in)
    response = await client.post("/api/v1/projects", json={"city": "Pune"}, headers=_key())
    assert response.status_code == 422


async def test_another_family_cannot_see_or_touch_the_project(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    owner = await homeowner(client_for, make_user, sign_in)
    project_id = (await new_project(owner))["project"]["project_id"]
    stranger = await homeowner(client_for, make_user, sign_in)
    attempts = [
        await stranger.get(f"/api/v1/projects/{project_id}"),
        await save(stranger, project_id, {"budget_band": "40L_60L"}, 1),
        await submit(stranger, project_id, 1),
        await stranger.get(f"/api/v1/projects/{project_id}/files"),
    ]
    assert [r.status_code for r in attempts] == [404, 404, 404, 404]
    assert (await stranger.get("/api/v1/projects")).json() == []


async def test_professional_and_operations_hosts_have_no_project_routes(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    for audience in (Audience.PRO, Audience.OPS):
        client = client_for(audience)
        await sign_in(client, await make_user(audience), audience)
        assert (await client.get("/api/v1/projects")).status_code == 404


async def test_drafts_save_partially_with_optimistic_locking(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    client = await homeowner(client_for, make_user, sign_in)
    project_id = (await new_project(client))["project"]["project_id"]
    saved = await save(client, project_id, {"budget_band": "40L_60L"}, 1)
    assert saved.status_code == 200
    assert saved.json()["version"] == 2
    stale = await save(client, project_id, {"budget_band": "60L_80L"}, 1)
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"
    bad = await save(client, project_id, {"floors": "G_PLUS_9", "funding_source": "LOAN"}, 2)
    assert bad.status_code == 422
    assert set(bad.json()["error"]["details"]["fields"]) == {"floors", "funding_source"}


async def test_submission_requires_every_required_answer(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    client = await homeowner(client_for, make_user, sign_in)
    project_id = (await new_project(client))["project"]["project_id"]
    await save(client, project_id, {"budget_band": "40L_60L"}, 1)
    response = await submit(client, project_id, 2)
    assert response.status_code == 422
    assert "location" in response.json()["error"]["details"]["fields"]


async def test_a_complete_requirement_is_submitted_for_review(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    client = await homeowner(client_for, make_user, sign_in)
    project_id = (await new_project(client))["project"]["project_id"]
    await save(client, project_id, {**COMPLETE, "budget_band": "UNDER_40L"}, 1)
    response = await submit(client, project_id, 2)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project"]["status"] == "SUBMITTED"
    assert body["project"]["locality"] == "Shankar Nagar"
    assert body["requirement"]["submitted_at"] is not None
    assert "review_flags" not in body["requirement"]  # operations-facing only

    async with database.transaction() as session:
        project = await session.get_one(Project, uuid.UUID(project_id))
        point = await session.scalar(func.ST_AsText(project.plot_geom))
        history = list(await session.scalars(select(ProjectStatusHistory.to_status)))
        event = (
            await session.scalars(
                select(OutboxEvent).where(OutboxEvent.event_type == "requirement.submitted")
            )
        ).one()
    assert point == "POINT(81.6296 21.2514)"
    assert project.plot_area_sqft == 2400  # 40 x 60
    assert project.floors == 2
    assert project.budget_band == "UNDER_40L"  # budget never rejects (R-5)
    assert sorted(history) == ["DRAFT", "SUBMITTED"]
    assert event.payload["review_flags"] == []

    after = await save(client, project_id, {"budget_band": "40L_60L"}, 3)
    assert after.status_code == 409
    assert after.json()["error"]["code"] == "STATE_CONFLICT"
    again = await submit(client, project_id, 3)
    assert again.status_code == 409


@pytest.mark.parametrize(
    ("changes", "flags"),
    [
        ({"property_type": "OTHER", "property_type_other": "A hostel"}, ["PROPERTY_TYPE_OTHER"]),
        ({"construction_started": True}, ["CONSTRUCTION_STARTED"]),
    ],
)
async def test_review_signals_travel_with_the_submission(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database,
    changes: dict[str, Any], flags: list[str],
) -> None:  # fmt: skip
    client = await homeowner(client_for, make_user, sign_in)
    project_id = (await new_project(client))["project"]["project_id"]
    await save(client, project_id, {**COMPLETE, **changes}, 1)
    response = await submit(client, project_id, 2)
    assert response.json()["project"]["status"] == "SUBMITTED"  # reviewed, never auto-qualified
    async with database.transaction() as session:
        event = (
            await session.scalars(
                select(OutboxEvent).where(OutboxEvent.event_type == "requirement.submitted")
            )
        ).one()
    assert event.payload["review_flags"] == flags
