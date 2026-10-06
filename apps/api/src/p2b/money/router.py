"""Payment mark routes (Slice 3.7A, EX-05) on the three hosts. The owner marks "paid", the
contractor of record "received", operations "received" for an OUTSIDE contractor with a reason.
Household members read only (EX-21). Free of the package (EX-18). No route takes an amount."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from p2b.construction.interface import (
    Who,
    contractor_of_record,
    family_access,
    milestone_stages,
    own_contractor_engagement,
    stage_facts,
)
from p2b.core.db import DbSession
from p2b.core.errors import NotFound, StateConflict
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.vocabulary import Audience, EngagementParty, PaymentMarkSide, StaffRole
from p2b.identity.interface import Actor, active_roles, require_actor
from p2b.money import service
from p2b.money.schemas import MarkIn, MarkOut, MilestoneOut, MilestonesOut, OpsMarkIn
from p2b.projects.interface import connection_facts

router = APIRouter(tags=["payment-marks"])

HOMEOWNER = require_actor(Audience.IHB)
PROFESSIONAL = require_actor(Audience.PRO)
STAFF = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.OPS, StaffRole.ADMIN))


async def _once(
    db: DbSession, actor: Actor, key: str, body: Any, act: Callable[[], Awaitable[BaseModel]]
) -> JSONResponse:
    async def action() -> tuple[int, dict[str, object]]:
        return 200, (await act()).model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key, request_body=body, action=action
    )


def _mark(mark: service.CurrentMark | None) -> MarkOut | None:
    if mark is None:
        return None
    return MarkOut(value=mark.value, marked_at=mark.marked_at, by_operations=mark.by_operations)


async def _view(db: DbSession, project_id: uuid.UUID) -> MilestonesOut:
    stages = await milestone_stages(db, project_id)
    by_id = {s.id: s for s in stages}
    rows = await service.milestones(db, project_id, [(s.id, s.state) for s in stages])
    return MilestonesOut(
        milestones=[
            MilestoneOut(
                stage_instance_id=m.stage_instance_id,
                stage_number=by_id[m.stage_instance_id].stage_number,
                floor=by_id[m.stage_instance_id].floor,
                due=m.due,
                paid=_mark(m.paid),
                received=_mark(m.received),
            )
            for m in rows
        ]
    )


# --- the homeowner -------------------------------------------------------------------------


@router.get("/projects/{project_id}/payment-marks", response_model=MilestonesOut)
async def get_family_marks(
    project_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> MilestonesOut:
    """Payment milestones with the current marks. Information only: Plan2Build does not handle
    construction payments."""
    await family_access(db, actor, project_id, write=False)
    return await _view(db, project_id)


@router.post("/projects/{project_id}/stages/{stage_id}/payment-mark", response_model=MilestonesOut)
async def post_paid_mark(
    project_id: uuid.UUID, stage_id: uuid.UUID, body: MarkIn, key: IdempotencyKeyHeader,
    db: DbSession, actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:  # fmt: skip
    """Mark whether you paid the contractor for this milestone. 409 `details.reason`:
    NOT_A_MILESTONE, UNCHANGED, PROJECT_CLOSED."""

    async def act() -> MilestonesOut:
        await family_access(db, actor, project_id, write=True)
        await service.mark(
            db, Who(actor.user_id, "FAMILY", actor.session_id), stage_id=stage_id,
            project_id=project_id, side=PaymentMarkSide.PAID, value=body.value, engagement=None,
        )  # fmt: skip
        return await _view(db, project_id)

    return await _once(db, actor, key, {"stage": str(stage_id), **body.model_dump()}, act)


# --- the contractor ------------------------------------------------------------------------


@router.get("/pro/engagements/{engagement_id}/payment-marks", response_model=MilestonesOut)
async def get_pro_marks(
    engagement_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> MilestonesOut:
    engagement = await own_contractor_engagement(db, actor, engagement_id)
    return await _view(db, engagement.project_id)


@router.post(
    "/pro/engagements/{engagement_id}/stages/{stage_id}/payment-mark",
    response_model=MilestonesOut,
)
async def post_received_mark(
    engagement_id: uuid.UUID, stage_id: uuid.UUID, body: MarkIn, key: IdempotencyKeyHeader,
    db: DbSession, actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    """Mark whether you received the homeowner's payment for this milestone."""

    async def act() -> MilestonesOut:
        engagement = await own_contractor_engagement(db, actor, engagement_id)
        await service.mark(
            db, Who(actor.user_id, "PROFESSIONAL", actor.session_id), stage_id=stage_id,
            project_id=engagement.project_id, side=PaymentMarkSide.RECEIVED, value=body.value,
            engagement=engagement,
        )  # fmt: skip
        return await _view(db, engagement.project_id)

    return await _once(db, actor, key, {"stage": str(stage_id), **body.model_dump()}, act)


# --- operations ------------------------------------------------------------------------------


@router.get("/ops/projects/{project_id}/payment-marks", response_model=MilestonesOut)
async def get_ops_marks(
    project_id: uuid.UUID, db: DbSession, _: Annotated[Actor, STAFF]
) -> MilestonesOut:
    if await connection_facts(db, project_id) is None:
        raise NotFound
    return await _view(db, project_id)


@router.post("/ops/stages/{stage_id}/payment-mark", response_model=MilestonesOut)
async def post_ops_received_mark(
    stage_id: uuid.UUID, body: OpsMarkIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Record an OUTSIDE contractor's "received" mark with how it was learnt. 409
    `details.reason`: LISTED_CONTRACTOR (it marks its own), NOT_CONTRACTOR."""

    async def act() -> MilestonesOut:
        stage = await stage_facts(db, stage_id)
        current = await contractor_of_record(db, stage.project_id)
        if current is None:
            raise StateConflict(details={"reason": "NOT_CONTRACTOR"})
        if current.party != EngagementParty.OUTSIDE.value:
            raise StateConflict(details={"reason": "LISTED_CONTRACTOR"})
        roles = await active_roles(db, actor.user_id)
        role = StaffRole.ADMIN.value if StaffRole.ADMIN in roles else StaffRole.OPS.value
        await service.mark(
            db, Who(actor.user_id, role, actor.session_id), stage_id=stage_id,
            project_id=stage.project_id, side=PaymentMarkSide.RECEIVED, value=body.value,
            engagement=current, note=body.reason,
        )  # fmt: skip
        return await _view(db, stage.project_id)

    return await _once(db, actor, key, {"stage": str(stage_id), **body.model_dump()}, act)
