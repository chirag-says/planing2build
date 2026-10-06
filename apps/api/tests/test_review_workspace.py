"""Review decisions and workspace creation (STATE_MODEL 5 to 7; rulings 2.1 to 2.7).

Accept creates the workspace once: stage instances (5, 6 and 9 per floor, plus a basement) and
exactly one line per specification code. Ask-for-information reopens the requirement and a
resubmission returns to the queue. Cancel needs a reason, is idempotent, and a cancelled project
cannot be accepted. The family sees the message and the workspace, never flags, and criteria
only when open point F-09 allows (Slice 3.0)."""

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select

from p2b.audit.models import AuditEvent
from p2b.construction.models import StageInstance
from p2b.construction.service import floors_for
from p2b.core.db import Database
from p2b.core.outbox import OutboxEvent
from p2b.core.vocabulary import StaffRole
from p2b.operations.models import OpsQueueItem
from p2b.projects.models import Project, ProjectStatusHistory
from p2b.specification.models import ProjectSpecLine, SpecLineEvent
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.staff_support import OPS_HEADERS, Staff, verified_staff
from tests.test_operations import relay, submitted_project
from tests.test_projects import H, save, submit

NON_REPEATING_STAGES = 13  # 16 stages, of which 5, 6 and 9 repeat per floor


def key() -> dict[str, str]:
    return {**OPS_HEADERS, "Idempotency-Key": str(uuid.uuid4())}


async def review_ready(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
    **changes: Any,
) -> tuple[AsyncClient, str, Staff]:  # fmt: skip
    """A submitted project in the queue, claimed by a verified OPS reviewer."""
    family, project_id = await submitted_project(client_for, make_user, sign_in, **changes)
    await relay(database)
    staff = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    await claim(staff, project_id)
    return family, project_id, staff


async def claim(staff: Staff, project_id: str) -> None:
    item = (await staff.client.get(f"/api/v1/ops/projects/{project_id}")).json()["queue_item"]
    response = await staff.client.post(
        f"/api/v1/ops/queue-items/{item['item_id']}/claim", headers=OPS_HEADERS
    )
    assert response.status_code == 200, response.text


# Checklist version 1 (migration 0011; F-05), every item passed.
ELIGIBLE = {
    "checks": [
        {"item_id": item, "outcome": "PASSED"}
        for item in (
            "new_individual_house",
            "service_geography",
            "requirement_complete",
            "review_flags_resolved",
            "information_plausible",
        )
    ]
}


async def accept(staff: Staff, project_id: str, headers: dict[str, str] | None = None) -> Response:
    return await staff.client.post(
        f"/api/v1/ops/projects/{project_id}/accept", json=ELIGIBLE, headers=headers or key()
    )


async def ask(staff: Staff, project_id: str, message: str) -> Response:
    return await staff.client.post(
        f"/api/v1/ops/projects/{project_id}/request-information",
        json={"message": message},
        headers=key(),
    )


async def cancel(staff: Staff, project_id: str, reason: str) -> Response:
    return await staff.client.post(
        f"/api/v1/ops/projects/{project_id}/cancel", json={"reason": reason}, headers=key()
    )


async def counts(database: Database, project_id: str) -> tuple[int, int]:
    async with database.transaction() as session:
        stages = await session.scalar(
            select(func.count())
            .select_from(StageInstance)
            .where(StageInstance.project_id == uuid.UUID(project_id))
        )
        lines = await session.scalar(
            select(func.count())
            .select_from(ProjectSpecLine)
            .where(ProjectSpecLine.project_id == uuid.UUID(project_id))
        )
    return int(stages or 0), int(lines or 0)


# Acceptance and the workspace


async def test_accepting_creates_the_workspace_and_resolves_the_review(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    family, project_id, staff = await review_ready(database, client_for, make_user, sign_in)
    response = await accept(staff, project_id)
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["project"]["status"] == "ACCEPTED"
    assert detail["queue_item"] is None  # resolved
    assert detail["history"][-1]["to_status"] == "ACCEPTED"
    assert detail["history"][-1]["actor_email"] == staff.email
    assert await counts(database, project_id) == (NON_REPEATING_STAGES + 3 * 2, 67)  # G+1

    async with database.transaction() as session:
        item = (await session.scalars(select(OpsQueueItem))).one()
        actions = list(
            await session.scalars(
                select(AuditEvent.action).where(AuditEvent.project_id == uuid.UUID(project_id))
            )
        )
        events = list(await session.scalars(select(OutboxEvent.event_type)))
    assert (item.state, item.resolved_by) == ("RESOLVED", staff.user_id)
    assert actions.count("stage_instance.created") == 19
    assert actions.count("spec_line.created") == 67
    assert "ops_queue_item.resolved" in actions
    assert events.count("project.accepted") == 1

    workspace = (await family.get(f"/api/v1/projects/{project_id}/workspace")).json()
    assert workspace["project"]["status"] == "ACCEPTED"
    assert len(workspace["stages"]) == 19


async def test_repeated_and_concurrent_acceptance_never_duplicates_the_workspace(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    _, project_id, staff = await review_ready(database, client_for, make_user, sign_in)
    first, second = await asyncio.gather(accept(staff, project_id), accept(staff, project_id))
    assert {first.status_code, second.status_code} == {200}
    retry_headers = key()
    assert (await accept(staff, project_id, retry_headers)).status_code == 200
    assert (await accept(staff, project_id, retry_headers)).status_code == 200  # replay
    assert await counts(database, project_id) == (19, 67)
    async with database.transaction() as session:
        accepted = await session.scalar(
            select(func.count())
            .select_from(ProjectStatusHistory)
            .where(ProjectStatusHistory.to_status == "ACCEPTED")
        )
        events = await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_type == "project.accepted")
        )
    assert (accepted, events) == (1, 1)


async def test_a_decision_needs_your_own_claim(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    _, project_id = await submitted_project(client_for, make_user, sign_in)
    await relay(database)
    alice = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    bob = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    unclaimed = await accept(alice, project_id)
    assert unclaimed.status_code == 409
    await claim(alice, project_id)
    assert (await accept(bob, project_id)).status_code == 409
    assert (await cancel(bob, project_id, "not ours")).status_code == 409
    assert await counts(database, project_id) == (0, 0)


@pytest.mark.parametrize(
    ("floors", "basement", "expected_floors"),
    [
        ("G", False, [0]),
        ("G_PLUS_1", False, [0, 1]),
        ("G_PLUS_2", True, [-1, 0, 1, 2]),
        ("G_PLUS_3", True, [-1, 0, 1, 2, 3]),
    ],
)
async def test_stages_5_6_and_9_repeat_per_floor_and_for_a_basement(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
    floors: str, basement: bool, expected_floors: list[int],
) -> None:  # fmt: skip
    family, project_id, staff = await review_ready(
        database, client_for, make_user, sign_in, floors=floors, basement=basement
    )
    assert (await accept(staff, project_id)).status_code == 200
    async with database.transaction() as session:
        rows = list(
            await session.execute(
                select(
                    StageInstance.stage_number,
                    StageInstance.floor,
                    StageInstance.state,
                    StageInstance.gate_status,
                )
                .where(StageInstance.project_id == uuid.UUID(project_id))
                .order_by(StageInstance.sequence)
            )
        )
    by_stage: dict[int, list[int | None]] = {}
    for number, floor, _, _ in rows:
        by_stage.setdefault(number, []).append(floor)
    assert sorted(by_stage) == list(range(1, 17))
    for number in (5, 6, 9):
        assert by_stage[number] == expected_floors
    for number in set(range(1, 17)) - {5, 6, 9}:
        assert by_stage[number] == [None]
    assert len(rows) == NON_REPEATING_STAGES + 3 * len(expected_floors)
    assert {state for _, _, state, _ in rows} == {"NOT_STARTED"}
    gates = {number: gate for number, _, _, gate in rows}
    assert gates[3] == "NOT_INSPECTED"  # a gate stage
    assert gates[2] is None  # not a gate

    workspace = (await family.get(f"/api/v1/projects/{project_id}/workspace")).json()
    stages = workspace["stages"]
    assert all(s["planned_start"] is None and s["planned_end"] is None for s in stages)  # 2.9
    if basement:
        assert stages[[s["stage_number"] for s in stages].index(5)]["floor"] == -1  # basement first


def test_floor_rules() -> None:
    assert floors_for(1, False) == [0]
    assert floors_for(4, True) == [-1, 0, 1, 2, 3]
    with pytest.raises(ValueError, match="floors"):
        floors_for(5, False)


async def test_exactly_one_line_per_code_with_structural_lines_unbranded_and_pending(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    _, project_id, staff = await review_ready(
        database, client_for, make_user, sign_in, floors="G_PLUS_3", basement=True
    )
    assert (await accept(staff, project_id)).status_code == 200
    async with database.transaction() as session:
        lines = list(
            await session.scalars(
                select(ProjectSpecLine).where(ProjectSpecLine.project_id == uuid.UUID(project_id))
            )
        )
        events = await session.scalar(select(func.count()).select_from(SpecLineEvent))
        stage_of = dict(
            (
                await session.execute(
                    select(StageInstance.id, StageInstance.floor).where(
                        StageInstance.stage_number == 5
                    )
                )
            ).all()
        )
    codes = [line.code for line in lines]
    assert len(codes) == len(set(codes)) == 67  # no copies per floor (2.3)
    assert events == 67
    by_code = {line.code: line for line in lines}
    structural = {"A01", "A02", "A04", "A05", "A09", "A12", "A13", "A19"}
    for code, line in by_code.items():
        assert line.state == "SPECIFIED"
        assert line.engineer_signoff == ("PENDING" if code in structural else "NOT_REQUIRED")
        assert line.decide_by is None  # no schedule yet
    assert by_code["A01"].issued_criteria.startswith("Bearing capacity")
    assert stage_of[by_code["A16"].consuming_stage_instance_id] == -1  # first instance: basement
    assert {c for c, line in by_code.items() if line.is_long_lead} == {
        "B07", "B14", "C16", "C17", "C18", "C19", "C20", "C21", "C22",
    }  # fmt: skip


async def test_the_family_sees_lines_by_group_without_criteria_by_default(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    family, project_id, staff = await review_ready(database, client_for, make_user, sign_in)
    assert (
        await family.get(f"/api/v1/projects/{project_id}/workspace")
    ).status_code == 409  # not yet
    await accept(staff, project_id)
    workspace = (await family.get(f"/api/v1/projects/{project_id}/workspace")).json()
    groups = workspace["groups"]
    assert [(p["code"], p["name"], len(p["lines"])) for p in groups] == [
        ("A", "Structure", 21), ("B", "Concealed systems", 22), ("C", "Finishes", 24),
    ]  # fmt: skip
    assert workspace["criteria_visible"] is False
    lines = [line for p in groups for line in p["lines"]]
    assert all(line["performance_specification"] is None for line in lines)  # 2.6
    assert lines[0] == {
        "code": "A01", "item": "Soil investigation", "state": "SPECIFIED", "is_long_lead": False,
        "is_structural": True, "engineer_signoff": "PENDING", "performance_specification": None,
    }  # fmt: skip
    assert {line["code"] for line in lines if line["engineer_signoff"] == "PENDING"} == {
        line["code"] for line in lines if line["is_structural"]
    }
    body = str(workspace)
    assert "Bearing capacity" not in body
    assert "review_flags" not in body
    assert "Testing lab" not in body


async def test_only_members_see_a_workspace(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    _, project_id, staff = await review_ready(database, client_for, make_user, sign_in)
    await accept(staff, project_id)
    _, other = await submitted_project(client_for, make_user, sign_in)
    stranger, _ = await submitted_project(client_for, make_user, sign_in)
    assert (await stranger.get(f"/api/v1/projects/{project_id}/workspace")).status_code == 404
    assert (await staff.client.get(f"/api/v1/projects/{project_id}/workspace")).status_code == 404
    assert other != project_id


# Needs information


async def test_asking_for_information_reopens_the_requirement_and_resubmission_requeues(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    family, project_id, staff = await review_ready(
        database,
        client_for,
        make_user,
        sign_in,
        property_type="OTHER",
        property_type_other="A hostel",
    )
    blank = await ask(staff, project_id, "   ")
    assert blank.status_code == 422
    asked = await ask(staff, project_id, "Please share the plot's survey number.")
    assert asked.json()["project"]["status"] == "NEEDS_INFO"

    detail = (await family.get(f"/api/v1/projects/{project_id}")).json()
    assert detail["project"]["status"] == "NEEDS_INFO"
    assert detail["review_message"]["message"] == "Please share the plot's survey number."
    assert detail["requirement"]["answers"]["property_type_other"] == "A hostel"  # kept
    assert "review_flags" not in str(detail)
    assert "PROPERTY_TYPE_OTHER" not in str(detail)

    version = detail["requirement"]["version"]
    saved = await save(
        family,
        project_id,
        {**detail["requirement"]["answers"], "notes": "Survey no. 12/4"},
        version,
    )
    assert saved.status_code == 200
    resubmitted = await submit(family, project_id, version + 1)
    assert resubmitted.json()["project"]["status"] == "SUBMITTED"
    assert resubmitted.json()["review_message"] is None

    await relay(database)
    async with database.transaction() as session:
        submitted_events = await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_type == "requirement.submitted")
        )
        items = list(
            await session.execute(select(OpsQueueItem.state).order_by(OpsQueueItem.created_at))
        )
        history = list(
            await session.scalars(
                select(ProjectStatusHistory.to_status).order_by(ProjectStatusHistory.at)
            )
        )
    assert submitted_events == 2
    assert [state for (state,) in items] == ["RESOLVED", "OPEN"]
    assert history == ["DRAFT", "SUBMITTED", "NEEDS_INFO", "SUBMITTED"]


async def test_a_project_waiting_for_information_can_be_cancelled(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    _, project_id, staff = await review_ready(database, client_for, make_user, sign_in)
    await ask(staff, project_id, "More please")
    response = await cancel(staff, project_id, "No reply after two weeks")
    assert response.json()["project"]["status"] == "CANCELLED"


# Cancellation


async def test_cancelling_needs_a_reason_that_the_family_sees(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    family, project_id, staff = await review_ready(database, client_for, make_user, sign_in)
    missing = await staff.client.post(
        f"/api/v1/ops/projects/{project_id}/cancel", json={"reason": ""}, headers=key()
    )
    assert missing.status_code == 422
    blank = await cancel(staff, project_id, "  ")
    assert blank.status_code == 422
    done = await cancel(staff, project_id, "Outside the area Plan2Build serves")
    assert done.json()["project"]["status"] == "CANCELLED"
    seen = (await family.get(f"/api/v1/projects/{project_id}")).json()
    assert seen["review_message"] == {
        "status": "CANCELLED",
        "message": "Outside the area Plan2Build serves",
        "at": seen["review_message"]["at"],
    }
    async with database.transaction() as session:
        row = (
            await session.scalars(
                select(ProjectStatusHistory).where(ProjectStatusHistory.to_status == "CANCELLED")
            )
        ).one()
        audit = (
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.action == "project.status_changed", AuditEvent.reason.is_not(None)
                )
            )
        ).one()
    assert (row.actor_user_id, row.reason) == (staff.user_id, "Outside the area Plan2Build serves")
    assert row.at is not None
    assert (audit.actor_user_id, audit.actor_role) == (staff.user_id, "OPS")


async def test_cancellation_is_idempotent_and_final(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    family, project_id, staff = await review_ready(database, client_for, make_user, sign_in)
    assert (await cancel(staff, project_id, "Duplicate request")).status_code == 200
    again = await cancel(staff, project_id, "Duplicate request")
    assert again.status_code == 200
    accepted = await accept(staff, project_id)
    assert accepted.status_code == 409
    assert accepted.json()["error"]["code"] == "STATE_CONFLICT"
    assert await counts(database, project_id) == (0, 0)
    detail = (await family.get(f"/api/v1/projects/{project_id}")).json()
    edit = await save(family, project_id, {"notes": "x"}, detail["requirement"]["version"])
    assert edit.status_code == 409
    async with database.transaction() as session:
        cancelled = await session.scalar(
            select(func.count())
            .select_from(ProjectStatusHistory)
            .where(ProjectStatusHistory.to_status == "CANCELLED")
        )
        events = await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_type == "project.cancelled")
        )
        project = await session.get_one(Project, uuid.UUID(project_id))
    assert (cancelled, events, project.status) == (1, 1, "CANCELLED")


# Access


async def test_review_decisions_are_for_operations_only(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    family, project_id, _ = await review_ready(database, client_for, make_user, sign_in)
    admin = await verified_staff(database, client_for, sign_in, StaffRole.ADMIN)
    for path in ("accept", "cancel", "request-information"):
        url = f"/api/v1/ops/projects/{project_id}/{path}"
        assert (
            await family.post(
                url,
                json={"reason": "x", "message": "x", **ELIGIBLE},
                headers={**H, "Idempotency-Key": str(uuid.uuid4())},
            )
        ).status_code == 404
        assert (
            await admin.client.post(
                url, json={"reason": "x", "message": "x", **ELIGIBLE}, headers=key()
            )
        ).status_code == 403
    assert await counts(database, project_id) == (0, 0)
