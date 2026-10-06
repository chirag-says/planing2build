"""Corrective actions (SLICE3_7_READINESS G; EX-11, EX-23). The contractor of record, or
operations for an OUTSIDE contractor, submit rectification evidence for an OPEN finding;
operations may send it back with a reason, extend the due date with a reason, and schedule a
re-inspection (inspections.schedule_reinspection). Nobody closes a finding here: only an approved
re-inspection does. A finding past its due date is an operations exception only (EX-23)."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.assurance.common import NOT_CLOSED, conflict, history, notify, today
from p2b.assurance.inspections import move_nc
from p2b.assurance.models import NonConformance
from p2b.construction.interface import Who, open_project
from p2b.core.errors import NotFound, ValidationFailed
from p2b.core.vocabulary import FilePurpose, FileState, NcState
from p2b.documents.interface import file_facts

MAX_PHOTOS = 10


async def nc_row(session: AsyncSession, nc_id: uuid.UUID, *, lock: bool = False) -> NonConformance:
    row = await session.get(NonConformance, nc_id, with_for_update=lock)
    if row is None:
        raise NotFound
    if lock:
        await session.refresh(row)
    return row


async def rectify(
    session: AsyncSession, who: Who, nc_id: uuid.UUID, project_id: uuid.UUID, *, note: str,
    file_ids: list[uuid.UUID], reason: str | None = None,
) -> NonConformance:  # fmt: skip
    """Evidence that the corrective action is done: a note and the actor's own scanned photos."""
    assert who.user_id is not None  # noqa: S101
    nc = await nc_row(session, nc_id, lock=True)
    if nc.project_id != project_id:
        raise NotFound
    await open_project(session, project_id)
    if nc.state != NcState.OPEN.value:
        raise conflict("NOT_OPEN", "Rectification is submitted for an open finding.",
                       current_state=nc.state)  # fmt: skip
    wanted = list(dict.fromkeys(file_ids))
    facts = await file_facts(session, wanted)
    if not 1 <= len(wanted) <= MAX_PHOTOS or any(
        (f := facts.get(fid)) is None
        or f.project_id != project_id
        or f.purpose != FilePurpose.STAGE_EVIDENCE
        or f.owner_user_id != who.user_id
        or f.state != FileState.AVAILABLE
        for fid in wanted
    ):
        raise ValidationFailed(
            details={"fields": {"file_ids": ["Attach 1 to 10 checked photos you uploaded."]}}
        )
    await move_nc(session, nc, "rectify", who, reason=reason, file_ids=wanted,
                  detail={"note": note})  # fmt: skip
    await notify(session, "ops", "RECTIFICATION_SUBMITTED", aggregate_id=project_id,
                 project_id=project_id, nc_id=nc.id, ref=f"{nc.id}:{nc.version}")  # fmt: skip
    return nc


async def reopen(session: AsyncSession, who: Who, nc_id: uuid.UUID, reason: str) -> NonConformance:
    """Operations send a rectification back (not enough evidence) with a reason."""
    nc = await nc_row(session, nc_id, lock=True)
    if nc.state != NcState.RECTIFICATION_SUBMITTED.value:
        raise conflict("NOT_RECTIFIED", "Only a submitted rectification is sent back.",
                       current_state=nc.state)  # fmt: skip
    await move_nc(session, nc, "reopen", who, reason=reason)
    return nc


async def set_due_date(
    session: AsyncSession, who: Who, nc_id: uuid.UUID, due_date: date, reason: str
) -> NonConformance:
    nc = await nc_row(session, nc_id, lock=True)
    if nc.state not in NOT_CLOSED:
        raise conflict("CLOSED", "This finding is closed.")
    if due_date < await today(session):
        raise ValidationFailed(details={"fields": {"due_date": ["The date cannot be past."]}})
    old = nc.due_date
    nc.due_date = due_date
    nc.version += 1
    await session.flush()
    await history(
        session, subject="NON_CONFORMANCE", subject_id=nc.id, project_id=nc.project_id,
        old=nc.state, new=nc.state, who=who, reason=reason,
        detail={"due_date_from": old.isoformat(), "due_date_to": due_date.isoformat()},
    )  # fmt: skip
    return nc


async def of_project(session: AsyncSession, project_id: uuid.UUID) -> list[NonConformance]:
    return list(
        await session.scalars(
            select(NonConformance)
            .where(NonConformance.project_id == project_id)
            .order_by(NonConformance.created_at, NonConformance.id)
        )
    )
