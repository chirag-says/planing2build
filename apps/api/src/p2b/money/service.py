"""Payment marks (Slice 3.7A, EX-05; SLICE3_7_READINESS M, P.A).

On a payment-milestone stage, the owner may mark "paid" and the contractor of record may mark
"received", each YES or NO, at any time. Operations record "received" for an OUTSIDE contractor,
which has no account. A mark is a new append-only row; the latest per side is current. Nothing
reads a mark to allow or refuse anything: no block, no mismatch, no settled state."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.construction.interface import (
    StageFacts,
    Who,
    contractor_of_record,
    open_project,
    stage_facts,
    stage_notice,
)
from p2b.core.errors import NotFound, StateConflict
from p2b.core.ids import new_id
from p2b.core.vocabulary import EngagementParty, PaymentMarkSide, PaymentMarkValue, StageState
from p2b.engagements.interface import EngagementFacts
from p2b.money.models import PaymentMark


def conflict(reason: str, message: str) -> StateConflict:
    return StateConflict(message=message, details={"reason": reason})


@dataclass(frozen=True)
class CurrentMark:
    value: PaymentMarkValue
    marked_at: datetime
    by_operations: bool


@dataclass(frozen=True)
class Milestone:
    stage_instance_id: uuid.UUID
    due: bool  # informational: the stage is COMPLETED
    paid: CurrentMark | None
    received: CurrentMark | None


async def _milestone_stage(session: AsyncSession, stage_id: uuid.UUID) -> StageFacts:
    stage = await stage_facts(session, stage_id)
    if not stage.is_payment_milestone:
        raise conflict("NOT_A_MILESTONE", "This stage is not a payment milestone.")
    return stage


async def _latest(
    session: AsyncSession, stage_id: uuid.UUID, side: PaymentMarkSide
) -> PaymentMark | None:
    return (
        await session.scalars(
            select(PaymentMark)
            .where(PaymentMark.stage_instance_id == stage_id, PaymentMark.side == side.value)
            .order_by(PaymentMark.marked_at.desc(), PaymentMark.id.desc())
            .limit(1)
        )
    ).one_or_none()


async def mark(
    session: AsyncSession,
    who: Who,
    *,
    stage_id: uuid.UUID,
    project_id: uuid.UUID,
    side: PaymentMarkSide,
    value: PaymentMarkValue,
    engagement: EngagementFacts | None,
    note: str | None = None,
) -> PaymentMark:
    """The caller has checked who may mark `side` (and, for RECEIVED, that `engagement` is the
    contractor of record)."""
    assert who.user_id is not None  # noqa: S101 (a person marks)
    stage = await _milestone_stage(session, stage_id)
    if stage.project_id != project_id:
        raise NotFound
    await open_project(session, project_id)
    # One mark at a time per stage and side, so a repeated mark is seen as UNCHANGED.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
        {"k": f"payment_mark:{stage_id}:{side.value}"},
    )
    current = await _latest(session, stage_id, side)
    if current is not None and current.value == value.value:
        raise conflict("UNCHANGED", "This is already the current mark.")
    row = PaymentMark(
        id=new_id(), project_id=project_id, stage_instance_id=stage_id, side=side.value,
        value=value.value, engagement_id=engagement.id if engagement else None, note=note,
        marked_by=who.user_id, marked_role=who.role,
    )  # fmt: skip
    session.add(row)
    await session.flush()
    await record(
        session, action="payment_mark.recorded", entity_type="payment_mark", entity_id=row.id,
        project_id=project_id, actor_type=who.actor_type, actor_user_id=who.user_id,
        actor_role=who.role, session_id=who.session_id, reason=note,
        old_value={"value": current.value} if current else None,
        new_value={"side": side.value, "value": value.value, "stage": stage.stage_number,
                   "floor": stage.floor},
    )  # fmt: skip
    if side == PaymentMarkSide.PAID and value == PaymentMarkValue.YES:
        current_contractor = await contractor_of_record(session, project_id)
        if current_contractor and current_contractor.party == EngagementParty.LISTED.value:
            await stage_notice(
                session, "contractor", "MARKED_PAID", stage_id,
                engagement_id=current_contractor.id, ref=str(row.id),
            )  # fmt: skip
    return row


async def milestones(
    session: AsyncSession, project_id: uuid.UUID, stages: list[tuple[uuid.UUID, StageState]]
) -> list[Milestone]:
    """`stages` are the project's payment-milestone stages with their states."""
    rows = list(
        await session.scalars(
            select(PaymentMark)
            .where(PaymentMark.project_id == project_id)
            .order_by(PaymentMark.marked_at, PaymentMark.id)
        )
    )
    latest: dict[tuple[uuid.UUID, str], PaymentMark] = {}
    for row in rows:
        latest[(row.stage_instance_id, row.side)] = row

    def current(stage_id: uuid.UUID, side: PaymentMarkSide) -> CurrentMark | None:
        row = latest.get((stage_id, side.value))
        if row is None:
            return None
        return CurrentMark(
            PaymentMarkValue(row.value), row.marked_at, row.marked_role in ("OPS", "ADMIN")
        )

    return [
        Milestone(
            stage_id,
            state == StageState.COMPLETED,
            current(stage_id, PaymentMarkSide.PAID),
            current(stage_id, PaymentMarkSide.RECEIVED),
        )
        for stage_id, state in stages
    ]
