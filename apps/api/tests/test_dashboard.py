"""Slice 3.0: the free dashboard (PD-03, PD-21; PRODUCT_FLOW_RECONCILIATION v2.0).

The indicative estimate is stored with each submission and is immutable; the package can be
offered only once the project passed the initial review, and nothing can be bought yet; A, B and
C are specification groups with no purchase flag; whether criteria show before the package is a
setting (open point F-09)."""

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from p2b.catalog.demo_rate_card import load
from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.vocabulary import Audience
from p2b.projects.estimates import record_estimate
from p2b.projects.models import Project, ProjectEstimate
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.test_operations import submitted_project
from tests.test_projects import H, homeowner, new_project, save, submit
from tests.test_questions import COMPLETE
from tests.test_review_workspace import accept, ask, cancel, review_ready


async def estimate_of(client: AsyncClient, project_id: str) -> dict[str, Any]:
    response = await client.get(f"/api/v1/projects/{project_id}/estimate")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def estimate_rows(database: Database, project_id: str) -> list[ProjectEstimate]:
    async with database.transaction() as session:
        return list(
            await session.scalars(
                select(ProjectEstimate)
                .where(ProjectEstimate.project_id == project_id)
                .order_by(ProjectEstimate.requirement_version)
            )
        )


async def test_submission_stores_the_indicative_estimate_with_its_rate_card(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    await load(database, get_settings())
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    body = await estimate_of(family, project_id)
    assert body["status"] == "AVAILABLE"
    assert body["unavailable_reason"] is None
    assert body["inputs"] == {
        "city": "Raipur", "built_up_area_sqft": 2650, "floors": 2, "finish_level": "PREMIUM",
    }  # fmt: skip
    public = (
        await family.post(
            "/api/v1/public/estimate",
            json={"city": "Raipur", "built_up_area_sqft": 2650, "floors": 2,
                  "finish_level": "PREMIUM"},
            headers=H,
        )
    ).json()  # fmt: skip
    figures = body["figures"]
    for field in ("total_low", "total_high", "total_mid", "duration_months"):
        assert figures[field] == public[field]
    assert [(s["stage_number"], s["amount"]) for s in figures["stages"]] == [
        (s["stage_number"], s["amount"]) for s in public["stages"]
    ]
    assert figures["stages"][0]["stage_name"] == public["stages"][0]["stage_name"]
    assert figures["rate_card"]["is_demo"] is True
    rows = await estimate_rows(database, project_id)
    assert len(rows) == 1
    assert rows[0].rate_card_id is not None


async def test_without_a_rate_card_the_estimate_says_so_and_invents_nothing(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    body = await estimate_of(family, project_id)
    assert (body["status"], body["unavailable_reason"], body["figures"]) == (
        "UNAVAILABLE", "NO_RATE_CARD", None,
    )  # fmt: skip


async def test_an_unknown_built_up_area_gives_no_estimate(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    await load(database, get_settings())
    family, project_id = await submitted_project(
        client_for, make_user, sign_in, built_up_area_sqft="NOT_SURE"
    )
    body = await estimate_of(family, project_id)
    assert (body["status"], body["unavailable_reason"]) == (
        "UNAVAILABLE", "BUILT_UP_AREA_NOT_GIVEN",
    )  # fmt: skip
    assert body["inputs"]["built_up_area_sqft"] is None


async def test_demo_rates_never_reach_a_production_estimate(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    await load(database, get_settings())
    _, project_id = await submitted_project(client_for, make_user, sign_in)
    async with database.transaction() as session:
        project = await session.get(Project, project_id)
        assert project is not None
        await record_estimate(session, project, requirement_version=99, allow_demo=False)
    newest = (await estimate_rows(database, project_id))[-1]
    assert (newest.requirement_version, newest.status, newest.unavailable_reason) == (
        99, "UNAVAILABLE", "NO_RATE_CARD",
    )  # fmt: skip


async def test_the_estimate_is_for_members_only_and_only_after_submission(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    family = await homeowner(client_for, make_user, sign_in)
    draft = (await new_project(family))["project"]["project_id"]
    response = await family.get(f"/api/v1/projects/{draft}/estimate")
    assert response.status_code == 409
    _, project_id = await submitted_project(client_for, make_user, sign_in)
    assert (await family.get(f"/api/v1/projects/{project_id}/estimate")).status_code == 404
    anonymous = client_for(Audience.IHB)
    assert (await anonymous.get(f"/api/v1/projects/{project_id}/estimate")).status_code == 401


async def test_estimates_are_immutable(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    _, project_id = await submitted_project(client_for, make_user, sign_in)
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(
                text("UPDATE project_estimates SET status = 'AVAILABLE' WHERE project_id = :p"),
                {"p": project_id},
            )
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(
                text("DELETE FROM project_estimates WHERE project_id = :p"), {"p": project_id}
            )


async def test_a_resubmission_stores_a_new_estimate_and_shows_the_latest(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    await load(database, get_settings())
    family, project_id, staff = await review_ready(database, client_for, make_user, sign_in)
    assert (await ask(staff, project_id, "Please confirm the area.")).status_code == 200
    detail = (await family.get(f"/api/v1/projects/{project_id}")).json()
    version = detail["requirement"]["version"]
    saved = await save(family, project_id, {**COMPLETE, "built_up_area_sqft": 3000}, version)
    assert saved.status_code == 200, saved.text
    assert (await submit(family, project_id, version + 1)).status_code == 200
    rows = await estimate_rows(database, project_id)
    assert [row.inputs["built_up_area_sqft"] for row in rows] == [2650, 3000]
    assert (await estimate_of(family, project_id))["inputs"]["built_up_area_sqft"] == 3000


async def test_a_project_submitted_before_estimates_existed_gets_one_on_first_read(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    await load(database, get_settings())
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    async with database.transaction() as session:
        await session.execute(text("TRUNCATE project_estimates"))
    assert (await estimate_of(family, project_id))["status"] == "AVAILABLE"
    assert len(await estimate_rows(database, project_id)) == 1


async def test_the_package_is_offered_only_after_the_initial_review(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    async def package(client: AsyncClient, project_id: str) -> dict[str, Any]:
        offer: dict[str, Any] = (await client.get(f"/api/v1/projects/{project_id}")).json()[
            "package"
        ]
        # No offer is published in this test, so nothing is purchasable (test_billing covers
        # buying once one is).
        assert offer["purchasable"] is False
        assert offer["state"] == "NOT_ACTIVE"
        return offer

    family = await homeowner(client_for, make_user, sign_in)
    draft = (await new_project(family))["project"]["project_id"]
    assert (await package(family, draft))["availability"] == "NOT_SUBMITTED"

    family, project_id, staff = await review_ready(database, client_for, make_user, sign_in)
    assert (await package(family, project_id))["availability"] == "UNDER_REVIEW"
    await ask(staff, project_id, "More please.")
    assert (await package(family, project_id))["availability"] == "UNDER_REVIEW"

    family, accepted, staff = await review_ready(database, client_for, make_user, sign_in)
    await accept(staff, accepted)
    assert (await package(family, accepted))["availability"] == "ELIGIBLE"

    family, closed, staff = await review_ready(database, client_for, make_user, sign_in)
    await cancel(staff, closed, "Outside Raipur.")
    assert (await package(family, closed))["availability"] == "NOT_ELIGIBLE"


async def test_specification_groups_carry_no_purchase_and_criteria_follow_the_setting(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id, staff = await review_ready(database, client_for, make_user, sign_in)
    await accept(staff, project_id)
    workspace = (await family.get(f"/api/v1/projects/{project_id}/workspace")).json()
    assert [g["code"] for g in workspace["groups"]] == ["A", "B", "C"]
    assert "packages" not in workspace
    assert "purchased" not in str(workspace)
    assert workspace["criteria_visible"] is False
    lines = [line for g in workspace["groups"] for line in g["lines"]]
    assert len(lines) == 67
    assert all(line["performance_specification"] is None for line in lines)

    settings = app.state.settings.model_copy(update={"spec_criteria_before_package": True})
    monkeypatch.setattr(app.state, "settings", settings)
    shown = (await family.get(f"/api/v1/projects/{project_id}/workspace")).json()
    assert shown["criteria_visible"] is True
    first = shown["groups"][0]["lines"][0]
    assert first["code"] == "A01"
    assert first["performance_specification"].startswith("Bearing capacity")


async def test_the_dashboard_does_not_wait_for_the_review(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    """Straight after submission, before operations act, the family has its estimate and the
    review status; nothing returns 409 for want of acceptance except the stages and lines,
    which the initial review creates."""
    await load(database, get_settings())
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    detail = (await family.get(f"/api/v1/projects/{project_id}")).json()
    assert detail["project"]["status"] == "SUBMITTED"
    assert detail["package"]["availability"] == "UNDER_REVIEW"
    assert (await family.get(f"/api/v1/projects/{project_id}/estimate")).status_code == 200
    assert (await family.get(f"/api/v1/projects/{project_id}/files")).status_code == 200
    assert (await family.get(f"/api/v1/projects/{project_id}/workspace")).status_code == 409
    async with database.transaction() as session:
        count = await session.scalar(
            select(func.count()).select_from(ProjectEstimate).where(
                ProjectEstimate.project_id == project_id
            )
        )  # fmt: skip
    assert count == 1
