"""Execution tracking (Slice 3.7A; SLICE3_7_READINESS 0, D, E, P.A).

The project's stage instances are the execution record (EX-01: no project status moves). The
engaged CONTRACTOR posts progress updates in the standard format (EX-02): stage, kind, note and
photos, optional materials and open problems, never a percentage; for an OUTSIDE contractor
operations enter them. The first update starts a stage; a completion request with evidence
asks for completion; the owner confirms or returns it with a reason, or operations confirm with
a recorded reason; a gate stage completes only once its gate is cleared (EX-03). No ordering, no
planned dates, no behind-plan or delay calculation (EX-04, BP-07A). Every update records the
engagement it was made under, and a change of contractor on a stage is recorded (EX-19)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.construction.models import ConstructionEvent, StageInstance, StageUpdate
from p2b.construction.service import STAGE, Who
from p2b.core.config import Settings
from p2b.core.errors import Forbidden, NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.vocabulary import (
    EngagementParty,
    FilePurpose,
    FileState,
    GateStatus,
    MembershipRole,
    ProjectStatus,
    StageState,
    StageUpdateKind,
)
from p2b.documents.interface import file_facts
from p2b.engagements.interface import EngagementFacts, active_engagement, engagement_facts
from p2b.identity.interface import Actor
from p2b.professionals.interface import profile_by_user
from p2b.projects.interface import ConnectionFacts, connection_facts, member_role

S = StageState
CATEGORY = "CONTRACTOR"
LOCAL_TIMEZONE = "Asia/Kolkata"


def conflict(reason: str, message: str, **details: Any) -> StateConflict:
    return StateConflict(message=message, details={"reason": reason, **details})


async def today(session: AsyncSession) -> date:
    with session.sync_session.no_autoflush:
        value: date = (
            await session.execute(
                text("SELECT (now() AT TIME ZONE :tz)::date").bindparams(tz=LOCAL_TIMEZONE)
            )
        ).scalar_one()
    return value


async def db_now(session: AsyncSession) -> datetime:
    with session.sync_session.no_autoflush:
        now: datetime = (await session.execute(select(func.now()))).scalar_one()
    return now


# --- notices ---------------------------------------------------------------------------------


class Notice(EventPayload):
    """Ids and a notice name only."""

    notice: str
    stage_instance_id: uuid.UUID
    project_id: uuid.UUID


async def notify(
    session: AsyncSession, audience: str, notice: str, stage: StageInstance, *,
    engagement_id: uuid.UUID | None = None, ref: str,
) -> None:  # fmt: skip
    """`construction.family_notice` carries the stage; `construction.contractor_notice` the
    engagement (the contractor of record)."""
    await publish(
        session,
        event_type=f"construction.{audience}_notice",
        aggregate_type="project_engagement" if audience == "contractor" else "stage_instance",
        aggregate_id=engagement_id if audience == "contractor" and engagement_id else stage.id,
        payload=Notice(notice=notice, stage_instance_id=stage.id, project_id=stage.project_id),
        dedupe_suffix=f"{notice}:{ref}",
    )


# --- access ----------------------------------------------------------------------------------


async def stage_row(
    session: AsyncSession, stage_id: uuid.UUID, *, lock: bool = False
) -> StageInstance:
    stage = await session.get(StageInstance, stage_id, with_for_update=lock)
    if stage is None:
        raise NotFound
    if lock:
        await session.refresh(stage)
    return stage


async def project_facts(session: AsyncSession, project_id: uuid.UUID) -> ConnectionFacts:
    facts = await connection_facts(session, project_id)
    if facts is None:
        raise NotFound
    return facts


async def open_project(session: AsyncSession, project_id: uuid.UUID) -> ConnectionFacts:
    """Execution writes stop when the project is cancelled; reading continues."""
    facts = await project_facts(session, project_id)
    if facts.status == ProjectStatus.CANCELLED:
        raise conflict("PROJECT_CLOSED", "This project is no longer active.")
    return facts


async def family_access(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, *, write: bool
) -> ConnectionFacts:
    """Owner and household read; only the owner acts (EX-21). Not a member is 404."""
    membership = await member_role(session, user_id=actor.user_id, project_id=project_id)
    if membership is None or membership.role not in (
        MembershipRole.OWNER, MembershipRole.HOUSEHOLD,
    ):  # fmt: skip
        raise NotFound
    if write and membership.role != MembershipRole.OWNER:
        raise Forbidden
    return await project_facts(session, project_id)


async def own_contractor_engagement(
    session: AsyncSession, actor: Actor, engagement_id: uuid.UUID
) -> EngagementFacts:
    """The signed-in professional's ACTIVE CONTRACTOR engagement; anything else is 404. Access
    ends with the engagement (N-08 after acceptance)."""
    profile_id = await profile_by_user(session, actor.user_id)
    facts = await engagement_facts(session, engagement_id)
    if (
        profile_id is None
        or facts is None
        or facts.profile_id != profile_id
        or facts.category_code != CATEGORY
        or not facts.active
    ):
        raise NotFound
    return facts


async def contractor_of_record(
    session: AsyncSession, project_id: uuid.UUID
) -> EngagementFacts | None:
    return await active_engagement(session, project_id, CATEGORY)


# --- history ---------------------------------------------------------------------------------


async def history(
    session: AsyncSession, stage: StageInstance, *, subject: str, old: str | None, new: str,
    who: Who, reason: str | None = None,
) -> None:  # fmt: skip
    session.add(
        ConstructionEvent(
            id=new_id(), project_id=stage.project_id, stage_instance_id=stage.id, subject=subject,
            from_state=old, to_state=new, actor_user_id=who.user_id, actor_role=who.role,
            reason=reason,
        )
    )  # fmt: skip
    await session.flush()
    await record(
        session,
        action={"STAGE": f"stage.{new.lower()}", "GATE": f"stage.gate_{new.lower()}"}.get(
            subject, "stage.contractor_changed"
        ),
        entity_type="stage_instance",
        entity_id=stage.id,
        project_id=stage.project_id,
        actor_type=who.actor_type,
        actor_user_id=who.user_id,
        actor_role=who.role,
        session_id=who.session_id,
        reason=reason,
        old_value={"state": old} if old else None,
        new_value={"state": new, "stage": stage.stage_number, "floor": stage.floor},
    )


async def move(
    session: AsyncSession, stage: StageInstance, trigger: str, who: Who, reason: str | None = None
) -> None:
    old = stage.state
    stage.state = STAGE.target(S(old), trigger).value
    stage.version += 1
    await session.flush()
    await history(session, stage, subject="STAGE", old=old, new=stage.state, who=who, reason=reason)


# --- updates ---------------------------------------------------------------------------------


async def _check_files(
    session: AsyncSession, settings: Settings, stage: StageInstance, file_ids: list[uuid.UUID],
    uploader: uuid.UUID,
) -> None:  # fmt: skip
    if not 1 <= len(file_ids) <= settings.stage_update_photos_max:
        raise ValidationFailed(
            details={"fields": {"file_ids": [
                f"Attach 1 to {settings.stage_update_photos_max} photos."
            ]}}
        )  # fmt: skip
    facts = await file_facts(session, file_ids)
    for file_id in file_ids:
        fact = facts.get(file_id)
        if (
            fact is None
            or fact.project_id != stage.project_id
            or fact.purpose != FilePurpose.STAGE_EVIDENCE
            or fact.owner_user_id != uploader
            or fact.state != FileState.AVAILABLE
        ):
            raise ValidationFailed(
                details={"fields": {"file_ids": ["Upload the photos and wait for the check."]}}
            )


async def post_update(
    session: AsyncSession,
    settings: Settings,
    who: Who,
    *,
    stage_id: uuid.UUID,
    engagement: EngagementFacts,
    kind: StageUpdateKind,
    note: str,
    materials: str | None,
    open_problems: str | None,
    file_ids: list[uuid.UUID],
    corrects_update_id: uuid.UUID | None,
    reason: str | None = None,
) -> StageUpdate:
    """EX-02, EX-03, EX-19. The caller has checked who may post under `engagement`; `reason`
    records how operations received an OUTSIDE contractor's update."""
    assert who.user_id is not None  # noqa: S101 (a person posts)
    stage = await stage_row(session, stage_id, lock=True)
    if stage.project_id != engagement.project_id:
        raise NotFound
    await open_project(session, stage.project_id)
    current = await contractor_of_record(session, stage.project_id)
    if current is None or current.id != engagement.id:
        raise conflict("NOT_CONTRACTOR", "Only the engaged contractor's updates are recorded.")
    if stage.state == S.COMPLETED.value:
        raise conflict("STAGE_COMPLETED", "This stage is complete.")
    if kind == StageUpdateKind.COMPLETION_REQUEST and stage.state == S.COMPLETION_REQUESTED.value:
        raise conflict("ALREADY_REQUESTED", "Completion is already requested.")
    wanted = list(dict.fromkeys(file_ids))
    await _check_files(session, settings, stage, wanted, who.user_id)
    if corrects_update_id is not None:
        corrected = await session.get(StageUpdate, corrects_update_id)
        if corrected is None or corrected.stage_instance_id != stage.id:
            raise ValidationFailed(details={"fields": {"corrects_update_id": ["Not found."]}})
    previous = (
        await session.scalars(
            select(StageUpdate.engagement_id)
            .where(StageUpdate.stage_instance_id == stage.id)
            .order_by(StageUpdate.posted_at.desc(), StageUpdate.id.desc())
            .limit(1)
        )
    ).one_or_none()
    update = StageUpdate(
        id=new_id(), project_id=stage.project_id, stage_instance_id=stage.id,
        engagement_id=engagement.id, kind=kind.value, note=note, materials=materials,
        open_problems=open_problems, file_ids=wanted, corrects_update_id=corrects_update_id,
        posted_by=who.user_id, posted_role=who.role,
    )  # fmt: skip
    session.add(update)
    await session.flush()
    await record(
        session, action="stage_update.posted", entity_type="stage_update", entity_id=update.id,
        project_id=stage.project_id, actor_type=who.actor_type, actor_user_id=who.user_id,
        actor_role=who.role, session_id=who.session_id, reason=reason,
        new_value={"kind": kind.value, "stage": stage.stage_number, "floor": stage.floor,
                   "engagement": str(engagement.id), "photos": len(wanted)},
    )  # fmt: skip
    if previous is not None and previous != engagement.id:  # EX-19: the transition is recorded
        await history(
            session, stage, subject="CONTRACTOR", old=str(previous), new=str(engagement.id),
            who=who, reason="a different contractor engagement posted on this stage",
        )  # fmt: skip
    if stage.state == S.NOT_STARTED.value:
        stage.actual_start = await today(session)
        await move(session, stage, "start", who)
    if kind == StageUpdateKind.COMPLETION_REQUEST:
        stage.completion_requested_at = await db_now(session)
        await move(session, stage, "request", who)
        await notify(session, "family", "COMPLETION_REQUESTED", stage, ref=str(update.id))
        if stage.is_gate:  # operations schedule the gate inspection (section O)
            await notify(session, "ops", "GATE_COMPLETION_REQUESTED", stage, ref=str(update.id))
    return update


def check_version(stage: StageInstance, version: int) -> None:
    if stage.version != version:
        raise conflict("STALE", "This stage changed. Reload and try again.", version=stage.version)


async def confirm(
    session: AsyncSession, who: Who, stage_id: uuid.UUID, project_id: uuid.UUID, *,
    version: int, reason: str | None,
) -> StageInstance:  # fmt: skip
    """EX-03: the owner, or operations with a recorded reason. A gate stage needs its gate
    cleared. No automatic completion."""
    stage = await stage_row(session, stage_id, lock=True)
    if stage.project_id != project_id:
        raise NotFound
    await open_project(session, project_id)
    if stage.state != S.COMPLETION_REQUESTED.value:
        raise StateConflict(details={"current_state": stage.state})
    check_version(stage, version)
    if who.role in ("OPS", "ADMIN") and not (reason or "").strip():
        raise ValidationFailed(details={"fields": {"reason": ["A reason is required."]}})
    if stage.is_gate and stage.gate_status != GateStatus.CLEARED.value:
        raise conflict("GATE_NOT_CLEARED", "This stage's inspection gate is not cleared yet.")
    stage.actual_end = await today(session)
    await move(session, stage, "confirm", who, reason)
    current = await contractor_of_record(session, stage.project_id)
    if current is not None and current.party == EngagementParty.LISTED.value:
        await notify(
            session, "contractor", "STAGE_CONFIRMED", stage, engagement_id=current.id,
            ref=str(stage.id),
        )  # fmt: skip
    if stage.is_payment_milestone:
        await notify(session, "family", "PAYMENT_DUE", stage, ref=str(stage.id))
    return stage


async def return_stage(
    session: AsyncSession, who: Who, stage_id: uuid.UUID, project_id: uuid.UUID, *,
    version: int, reason: str,
) -> StageInstance:  # fmt: skip
    stage = await stage_row(session, stage_id, lock=True)
    if stage.project_id != project_id:
        raise NotFound
    await open_project(session, project_id)
    if stage.state != S.COMPLETION_REQUESTED.value:
        raise StateConflict(details={"current_state": stage.state})
    check_version(stage, version)
    await move(session, stage, "return", who, reason)
    current = await contractor_of_record(session, stage.project_id)
    if current is not None and current.party == EngagementParty.LISTED.value:
        stamp = (await db_now(session)).isoformat()
        await notify(
            session, "contractor", "STAGE_RETURNED", stage, engagement_id=current.id, ref=stamp
        )
    return stage


async def updates_of(
    session: AsyncSession, stage_id: uuid.UUID, *, engagement_id: uuid.UUID | None = None
) -> list[StageUpdate]:
    query = (
        select(StageUpdate)
        .where(StageUpdate.stage_instance_id == stage_id)
        .order_by(StageUpdate.posted_at, StageUpdate.id)
    )
    if engagement_id is not None:
        query = query.where(StageUpdate.engagement_id == engagement_id)
    return list(await session.scalars(query))


async def events_of(session: AsyncSession, project_id: uuid.UUID) -> list[ConstructionEvent]:
    return list(
        await session.scalars(
            select(ConstructionEvent)
            .where(ConstructionEvent.project_id == project_id)
            .order_by(ConstructionEvent.at.desc(), ConstructionEvent.id)
            .limit(500)
        )
    )


async def update_counts(
    session: AsyncSession, project_id: uuid.UUID, *, engagement_id: uuid.UUID | None = None
) -> dict[uuid.UUID, tuple[int, datetime | None]]:
    query = (
        select(StageUpdate.stage_instance_id, func.count(), func.max(StageUpdate.posted_at))
        .where(StageUpdate.project_id == project_id)
        .group_by(StageUpdate.stage_instance_id)
    )
    if engagement_id is not None:
        query = query.where(StageUpdate.engagement_id == engagement_id)
    return {row[0]: (int(row[1]), row[2]) for row in (await session.execute(query)).all()}


async def evidence_owned_by_stage(
    session: AsyncSession, project_id: uuid.UUID, file_id: uuid.UUID,
    engagement_id: uuid.UUID | None = None,
) -> bool:  # fmt: skip
    """The file is a photo of an update on this project (of this engagement, when given)."""
    query = select(StageUpdate.id).where(
        StageUpdate.project_id == project_id, StageUpdate.file_ids.contains([file_id])
    )
    if engagement_id is not None:
        query = query.where(StageUpdate.engagement_id == engagement_id)
    return (await session.scalars(query.limit(1))).first() is not None
