"""Shared pieces of the assurance module: refusals with a reason, time, hashing, history and
audit, notices to the notifications module, package gating and the state machines
(SLICE3_7_READINESS P.B, P.C)."""

import hashlib
import json
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.assurance.models import AssuranceEvent
from p2b.audit.interface import record
from p2b.billing.interface import package_active
from p2b.construction.interface import Who
from p2b.core.errors import PackageRequired, StateConflict
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import InspectionState, NcState

LOCAL_TIMEZONE = "Asia/Kolkata"

I = InspectionState  # noqa: E741 (the readiness tables use these letters)
INSPECTION = TransitionTable[InspectionState](
    "inspection",
    [
        Transition(None, I.SCHEDULED, "schedule"),
        Transition(I.SCHEDULED, I.IN_PROGRESS, "start"),
        Transition(I.IN_PROGRESS, I.SUBMITTED, "submit"),
        Transition(I.SUBMITTED, I.APPROVED, "approve"),
        Transition(I.SUBMITTED, I.RETURNED, "return"),
        Transition(I.SCHEDULED, I.CANCELLED, "cancel"),
        Transition(I.IN_PROGRESS, I.CANCELLED, "cancel"),
    ],
)
N = NcState
NC = TransitionTable[NcState](
    "non_conformance",
    [
        Transition(None, N.OPEN, "open"),
        Transition(N.OPEN, N.RECTIFICATION_SUBMITTED, "rectify"),
        Transition(N.RECTIFICATION_SUBMITTED, N.OPEN, "reopen"),
        Transition(N.RECTIFICATION_SUBMITTED, N.REINSPECTION_SCHEDULED, "reinspect"),
        Transition(N.REINSPECTION_SCHEDULED, N.RECTIFICATION_SUBMITTED, "reinspection_cancelled"),
        Transition(N.REINSPECTION_SCHEDULED, N.CLOSED, "close"),
        Transition(N.REINSPECTION_SCHEDULED, N.OPEN, "not_closed"),
    ],
)
LIVE_INSPECTION = (I.SCHEDULED.value, I.IN_PROGRESS.value, I.SUBMITTED.value)
NOT_CLOSED = (N.OPEN.value, N.RECTIFICATION_SUBMITTED.value, N.REINSPECTION_SCHEDULED.value)

SYSTEM = Who(None, "SYSTEM")


def conflict(reason: str, message: str, **details: Any) -> StateConflict:
    return StateConflict(message=message, details={"reason": reason, **details})


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


async def db_now(session: AsyncSession) -> datetime:
    with session.sync_session.no_autoflush:
        now: datetime = (await session.execute(select(func.now()))).scalar_one()
    return now


async def today(session: AsyncSession) -> date:
    """The calendar date in Raipur (due dates and the EX-12 thresholds)."""
    with session.sync_session.no_autoflush:
        value: date = (
            await session.execute(
                text("SELECT (now() AT TIME ZONE :tz)::date").bindparams(tz=LOCAL_TIMEZONE)
            )
        ).scalar_one()
    return value


async def require_package(session: AsyncSession, project_id: uuid.UUID) -> None:
    """EX-18: scheduling and approving inspections need an active package."""
    if not await package_active(session, project_id):
        raise PackageRequired


async def history(
    session: AsyncSession,
    *,
    subject: str,
    subject_id: uuid.UUID,
    project_id: uuid.UUID | None,
    old: str | None,
    new: str,
    who: Who,
    reason: str | None = None,
    detail: dict[str, Any] | None = None,
    file_ids: list[uuid.UUID] | None = None,
) -> None:
    """One append-only history row and one audit row, in the caller's transaction."""
    session.add(
        AssuranceEvent(
            id=new_id(), project_id=project_id, subject=subject, subject_id=subject_id,
            from_state=old, to_state=new, actor_user_id=who.user_id, actor_role=who.role,
            reason=reason, detail=detail, file_ids=file_ids or [],
        )
    )  # fmt: skip
    await session.flush()
    await record(
        session,
        action=f"{subject.lower()}.{new.lower()}",
        entity_type=subject.lower(),
        entity_id=subject_id,
        project_id=project_id,
        actor_type=who.actor_type,
        actor_user_id=who.user_id,
        actor_role=who.role,
        session_id=who.session_id,
        reason=reason,
        old_value={"state": old} if old else None,
        new_value={"state": new, **(detail or {})},
    )


# --- notices: what the notifications module turns into email (section O) -------------------


class Notice(EventPayload):
    """Ids and a notice name only."""

    notice: str
    project_id: uuid.UUID
    inspection_id: uuid.UUID | None = None
    nc_id: uuid.UUID | None = None


async def notify(
    session: AsyncSession,
    audience: str,
    notice: str,
    *,
    aggregate_id: uuid.UUID,
    project_id: uuid.UUID,
    inspection_id: uuid.UUID | None = None,
    nc_id: uuid.UUID | None = None,
    ref: str,
) -> None:
    """`assurance.<audience>_notice`: family and ops carry the project, contractor the
    engagement, auditor the appointment, as the aggregate."""
    await publish(
        session,
        event_type=f"assurance.{audience}_notice",
        aggregate_type={"contractor": "project_engagement", "auditor": "auditor_appointment"}.get(
            audience, "project"
        ),
        aggregate_id=aggregate_id,
        payload=Notice(
            notice=notice, project_id=project_id, inspection_id=inspection_id, nc_id=nc_id
        ),
        dedupe_suffix=f"{notice}:{ref}",
    )
