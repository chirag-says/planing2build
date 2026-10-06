"""Design intake: requests, drawing sets, checking and approval (BP-01 to BP-03).

Plan2Build generates no drawing. A professional (listed, outside, or arranged by Plan2Build) or
the family provides the files; the family reviews a professional's set; an appointed checker
approves it. An APPROVED set is authoritative and immutable; a later approved set of the same
request supersedes it. AI concepts may be named on a request as illustrative references only;
they are never files of a set (no path exists from an AI_CONCEPT file to a drawing)."""

import hashlib
import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.buildplan.common import Who, conflict, db_now, history, require_package
from p2b.buildplan.models import CheckerAppointment, DesignRequest, DrawingFile, DrawingSet
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import (
    ActorType,
    DesignRequestKind,
    DrawingClass,
    DrawingSetState,
    FilePurpose,
    FileState,
)
from p2b.designs.interface import concepts_of_project
from p2b.documents.interface import file_facts
from p2b.engagements.interface import engagement_facts

DS = DrawingSetState
SET = TransitionTable[DrawingSetState](
    "drawing_set",
    [
        Transition(None, DS.DRAFT, "create"),
        Transition(DS.DRAFT, DS.SUBMITTED, "submit"),
        Transition(DS.DRAFT, DS.IN_CHECK, "submit_by_family"),
        Transition(DS.SUBMITTED, DS.IN_CHECK, "family_approve"),
        Transition(DS.SUBMITTED, DS.CHANGES_REQUESTED, "family_changes"),
        Transition(DS.IN_CHECK, DS.APPROVED, "approve"),
        Transition(DS.IN_CHECK, DS.REJECTED, "reject"),
        Transition(DS.APPROVED, DS.SUPERSEDED, "supersede"),
    ],
)
K = DesignRequestKind


# --- checker appointments (BP-01) ------------------------------------------------------------


async def appoint_checker(
    session: AsyncSession,
    who: Who,
    *,
    name: str,
    qualification: str,
    registration_reference: str | None,
    user_id: uuid.UUID | None,
) -> CheckerAppointment:
    appointment = CheckerAppointment(
        id=new_id(), name=name, qualification=qualification,
        registration_reference=registration_reference, user_id=user_id, appointed_by=who.user_id,
    )  # fmt: skip
    session.add(appointment)
    await session.flush()
    await _audit_appointment(session, who, appointment, "APPOINTED")
    return appointment


async def end_checker(session: AsyncSession, who: Who, appointment_id: uuid.UUID) -> None:
    appointment = await session.get(CheckerAppointment, appointment_id, with_for_update=True)
    if appointment is None:
        raise NotFound
    if appointment.ended_at is not None:
        raise StateConflict(details={"current_state": "ENDED"})
    appointment.ended_at = await db_now(session)
    appointment.ended_by = who.user_id
    await session.flush()
    await _audit_appointment(session, who, appointment, "ENDED")


async def _audit_appointment(
    session: AsyncSession, who: Who, appointment: CheckerAppointment, state: str
) -> None:
    await record(
        session, action=f"drawing_checker.{state.lower()}", entity_type="drawing_checker",
        entity_id=appointment.id, actor_type=ActorType.USER, actor_user_id=who.user_id,
        actor_role=who.role, session_id=who.session_id,
        new_value={"name": appointment.name, "qualification": appointment.qualification},
    )  # fmt: skip


async def active_checkers(session: AsyncSession) -> list[CheckerAppointment]:
    return list(
        await session.scalars(
            select(CheckerAppointment)
            .where(CheckerAppointment.ended_at.is_(None))
            .order_by(CheckerAppointment.appointed_at)
        )
    )


# --- design requests -------------------------------------------------------------------------


async def open_request(
    session: AsyncSession,
    who: Who,
    project_id: uuid.UUID,
    *,
    kind: DesignRequestKind,
    engagement_id: uuid.UUID | None,
    provider_name: str | None,
    provider_qualification: str | None,
    scope_note: str,
    reference_design_ids: list[uuid.UUID],
) -> DesignRequest:
    await require_package(session, project_id)
    if kind == K.PLAN2BUILD_ARRANGED and who.role not in ("OPS", "ADMIN"):
        raise conflict("OPS_ONLY", "Only operations arrange a professional.")
    if kind in (K.LISTED_PROFESSIONAL, K.OUTSIDE_PROFESSIONAL):
        if engagement_id is None:
            raise ValidationFailed(
                details={"fields": {"engagement_id": ["Choose a professional."]}}
            )
        engagement = await engagement_facts(session, engagement_id)
        party = "LISTED" if kind == K.LISTED_PROFESSIONAL else "OUTSIDE"
        if (
            engagement is None
            or engagement.project_id != project_id
            or not engagement.active
            or engagement.party != party
        ):
            raise conflict("NO_ENGAGEMENT", "Choose an active professional on this project.")
        if kind == K.OUTSIDE_PROFESSIONAL:
            provider_name = provider_name or engagement.outside_name
    else:
        engagement_id = None
    if kind == K.PLAN2BUILD_ARRANGED and not (provider_name and provider_qualification):
        raise ValidationFailed(
            details={"fields": {"provider_name": ["Name the professional and qualification."]}}
        )
    references = list(dict.fromkeys(reference_design_ids))
    if set(references) - await concepts_of_project(session, project_id, references):
        raise ValidationFailed(details={"fields": {"reference_design_ids": ["Unknown concept."]}})
    request = DesignRequest(
        id=new_id(), project_id=project_id, kind=kind.value, engagement_id=engagement_id,
        provider_name=provider_name, provider_qualification=provider_qualification,
        scope_note=scope_note, reference_design_ids=references, opened_by=who.user_id,
    )  # fmt: skip
    session.add(request)
    await session.flush()
    await history(
        session, project_id=project_id, subject="DESIGN_REQUEST", subject_id=request.id,
        old=None, new="OPEN", who=who, detail={"kind": kind.value},
    )  # fmt: skip
    return request


async def request_row(session: AsyncSession, request_id: uuid.UUID) -> DesignRequest:
    request = await session.get(DesignRequest, request_id)
    if request is None:
        raise NotFound
    return request


async def may_provide(
    session: AsyncSession, request: DesignRequest, who: Who, *, profile_id: uuid.UUID | None
) -> bool:
    """Who adds files to a request's sets: the engaged listed professional; the owner for the
    family's own drawings and an outside professional's; operations for any."""
    if who.role in ("OPS", "ADMIN"):
        return True
    kind = DesignRequestKind(request.kind)
    if kind == K.LISTED_PROFESSIONAL and who.role == "PROFESSIONAL":
        assert request.engagement_id is not None  # noqa: S101 (CHECK)
        engagement = await engagement_facts(session, request.engagement_id)
        return bool(engagement and engagement.active and engagement.profile_id == profile_id)
    return who.role == "FAMILY" and kind in (K.OUTSIDE_PROFESSIONAL, K.HOMEOWNER_PROVIDED)


# --- drawing sets ----------------------------------------------------------------------------


async def set_row(session: AsyncSession, set_id: uuid.UUID, *, lock: bool = False) -> DrawingSet:
    drawing_set = await session.get(DrawingSet, set_id, with_for_update=lock)
    if drawing_set is None:
        raise NotFound
    return drawing_set


async def _move(
    session: AsyncSession,
    drawing_set: DrawingSet,
    trigger: str,
    who: Who,
    reason: str | None = None,
) -> None:
    old = drawing_set.state
    drawing_set.state = SET.target(DS(old), trigger).value
    drawing_set.version += 1
    await session.flush()
    await history(
        session, project_id=drawing_set.project_id, subject="DRAWING_SET",
        subject_id=drawing_set.id, old=old, new=drawing_set.state, who=who, reason=reason,
    )  # fmt: skip


async def new_set(session: AsyncSession, who: Who, request: DesignRequest) -> DrawingSet:
    await require_package(session, request.project_id)
    open_set = await session.scalar(
        select(DrawingSet.id).where(
            DrawingSet.request_id == request.id,
            DrawingSet.state.in_([DS.DRAFT.value, DS.SUBMITTED.value, DS.IN_CHECK.value]),
        )
    )
    if open_set is not None:
        raise conflict("OPEN_SET", "This request already has a set in progress.")
    latest = await session.scalar(
        select(func.max(DrawingSet.set_no)).where(DrawingSet.request_id == request.id)
    )
    drawing_set = DrawingSet(
        id=new_id(), project_id=request.project_id, request_id=request.id,
        set_no=(latest or 0) + 1, state=SET.target(None, "create").value, created_by=who.user_id,
    )  # fmt: skip
    session.add(drawing_set)
    await session.flush()
    await history(
        session, project_id=request.project_id, subject="DRAWING_SET", subject_id=drawing_set.id,
        old=None, new=drawing_set.state, who=who,
    )  # fmt: skip
    return drawing_set


async def add_file(
    session: AsyncSession,
    who: Who,
    drawing_set: DrawingSet,
    *,
    file_id: uuid.UUID,
    drawing_class: DrawingClass,
    floor: int | None,
    title: str,
    sheet_no: str | None,
) -> DrawingFile:
    await require_package(session, drawing_set.project_id)
    if drawing_set.state != DS.DRAFT.value:
        raise StateConflict(details={"current_state": drawing_set.state})
    facts = (await file_facts(session, [file_id])).get(file_id)
    if (
        facts is None
        or facts.project_id != drawing_set.project_id
        or facts.purpose != FilePurpose.DRAWING
        or facts.owner_user_id != who.user_id
    ):
        raise ValidationFailed(details={"fields": {"file_id": ["Upload the drawing first."]}})
    taken = await session.scalar(
        select(DrawingFile.id).where(
            DrawingFile.set_id == drawing_set.id, DrawingFile.file_id == file_id
        )
    )
    if taken is not None:
        raise conflict("DUPLICATE", "This file is already in the set.")
    row = DrawingFile(
        id=new_id(), set_id=drawing_set.id, project_id=drawing_set.project_id, file_id=file_id,
        drawing_class=drawing_class.value, floor=floor, title=title, sheet_no=sheet_no,
    )  # fmt: skip
    session.add(row)
    await session.flush()
    return row


async def remove_file(
    session: AsyncSession, drawing_set: DrawingSet, drawing_file_id: uuid.UUID
) -> None:
    if drawing_set.state != DS.DRAFT.value:
        raise StateConflict(details={"current_state": drawing_set.state})
    row = await session.get(DrawingFile, drawing_file_id)
    if row is None or row.set_id != drawing_set.id:
        raise NotFound
    await session.delete(row)
    await session.flush()


async def set_files(session: AsyncSession, set_id: uuid.UUID) -> list[DrawingFile]:
    return list(
        await session.scalars(
            select(DrawingFile)
            .where(DrawingFile.set_id == set_id)
            .order_by(DrawingFile.drawing_class, DrawingFile.floor, DrawingFile.title)
        )
    )


def set_hash(files: list[DrawingFile]) -> str:
    rows = sorted(
        [str(f.file_id), f.sha256, f.drawing_class, f.floor, f.title, f.sheet_no] for f in files
    )
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


async def submit_set(session: AsyncSession, who: Who, drawing_set: DrawingSet) -> None:
    """Freezes the files. The family's own submission goes straight to the checker; a
    professional's waits for the family's review."""
    await require_package(session, drawing_set.project_id)
    files = await set_files(session, drawing_set.id)
    if not files:
        raise conflict("EMPTY", "Add at least one drawing.")
    facts = await file_facts(session, [f.file_id for f in files])
    pending = [f for f in files if facts[f.file_id].state != FileState.AVAILABLE]
    if pending:
        raise conflict("FILES_NOT_READY", "Wait until every file has been checked.")
    for f in files:
        f.sha256 = facts[f.file_id].sha256
    await session.flush()
    drawing_set.content_hash = set_hash(files)
    drawing_set.submitted_by = who.user_id
    drawing_set.submitted_at = await db_now(session)
    await _move(session, drawing_set, "submit_by_family" if who.role == "FAMILY" else "submit", who)


async def family_decide(
    session: AsyncSession, who: Who, drawing_set: DrawingSet, *, approve: bool, note: str | None
) -> None:
    await require_package(session, drawing_set.project_id)
    if not approve and not (note and note.strip()):
        raise ValidationFailed(details={"fields": {"note": ["Say what should change."]}})
    drawing_set.family_decided_at = await db_now(session)
    drawing_set.family_note = note
    await _move(session, drawing_set, "family_approve" if approve else "family_changes", who, note)


async def check_set(
    session: AsyncSession,
    who: Who,
    drawing_set: DrawingSet,
    *,
    appointment_id: uuid.UUID,
    approve: bool,
    note: str,
    evidence_file_id: uuid.UUID | None,
) -> None:
    """BP-01. A checker with a platform account records the check; otherwise operations record
    it with the checker's signed note as evidence."""
    await require_package(session, drawing_set.project_id)
    appointment = await session.get(CheckerAppointment, appointment_id)
    if appointment is None or appointment.ended_at is not None:
        raise conflict("NO_CHECKER", "Choose an appointed checker.")
    if appointment.user_id != who.user_id:
        facts = (await file_facts(session, [evidence_file_id] if evidence_file_id else [])).get(
            evidence_file_id  # type: ignore[arg-type]
        )
        if (
            facts is None
            or facts.project_id != drawing_set.project_id
            or facts.purpose != FilePurpose.BUILD_PLAN_EVIDENCE
            or facts.state != FileState.AVAILABLE
        ):
            raise ValidationFailed(
                details={"fields": {"evidence_file_id": ["Attach the checker's signed note."]}}
            )
    if drawing_set.state != DS.IN_CHECK.value:
        raise StateConflict(details={"current_state": drawing_set.state})
    drawing_set.checker_appointment_id = appointment.id
    drawing_set.checked_by = who.user_id
    drawing_set.checked_at = await db_now(session)
    drawing_set.check_note = note
    drawing_set.check_evidence_file_id = evidence_file_id
    if approve:
        for earlier in await session.scalars(
            select(DrawingSet)
            .where(
                DrawingSet.request_id == drawing_set.request_id,
                DrawingSet.state == DS.APPROVED.value,
            )
            .with_for_update()
        ):
            earlier.superseded_at = drawing_set.checked_at
            await _move(session, earlier, "supersede", who, "a later set was approved")
    await _move(session, drawing_set, "approve" if approve else "reject", who, note)


async def classes_of(session: AsyncSession, set_id: uuid.UUID) -> set[str]:
    return {f.drawing_class for f in await set_files(session, set_id)}
