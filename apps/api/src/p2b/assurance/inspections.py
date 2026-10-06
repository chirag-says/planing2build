"""Inspections (Slice 3.7B; SLICE3_7_READINESS F.2, F.5, G, P.B, P.C).

Operations schedule one inspection per gate stage instance (EX-07) with an appointed auditor and
the published checklist version, with the package active (EX-18). The auditor confirms readiness,
records each checkpoint (a non-conformance with severity, description, corrective action and due
date, EX-11), and submits with a one-time code (EX-09); operations may capture an inspection from
the auditor's signed report instead. Submission freezes and hashes the content. Operations
approve (package active) or return it. Approval opens the findings, renders the report once
(EX-14) and sets the stage's gate. A re-inspection re-checks rectified findings; only its approved
PASS closes one. The gate status is always derived from the records, never set by hand."""

import hashlib
import uuid
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.assurance import appointments, checklists
from p2b.assurance.common import (
    INSPECTION,
    LIVE_INSPECTION,
    NC,
    NOT_CLOSED,
    conflict,
    db_now,
    history,
    notify,
    require_package,
    sha256,
    today,
)
from p2b.assurance.models import (
    AuditorAppointment,
    Checkpoint,
    Inspection,
    InspectionReport,
    InspectionResult,
    NonConformance,
    TestResult,
)
from p2b.assurance.pdf import render_report
from p2b.construction.interface import (
    StageFacts,
    Who,
    contractor_of_record,
    open_project,
    set_gate_status,
    stage_facts,
)
from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.errors import NotFound, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.storage import Storage
from p2b.core.vocabulary import (
    CheckpointResult,
    EngagementParty,
    FilePurpose,
    FileState,
    GateStatus,
    InspectionCancelReason,
    InspectionKind,
    InspectionState,
    NcState,
    OtpPurpose,
)
from p2b.documents.interface import file_facts, store_generated_file
from p2b.identity.interface import verify_confirmation
from p2b.projects.interface import connection_facts

S = InspectionState
R = CheckpointResult


async def inspection_row(
    session: AsyncSession, inspection_id: uuid.UUID, *, lock: bool = False
) -> Inspection:
    row = await session.get(Inspection, inspection_id, with_for_update=lock)
    if row is None:
        raise NotFound
    if lock:
        await session.refresh(row)
    return row


async def move(
    session: AsyncSession, row: Inspection, trigger: str, who: Who, *, reason: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:  # fmt: skip
    old = row.state
    row.state = INSPECTION.target(S(old), trigger).value
    row.version += 1
    await session.flush()
    await history(
        session, subject="INSPECTION", subject_id=row.id, project_id=row.project_id, old=old,
        new=row.state, who=who, reason=reason,
        detail={"stage_instance_id": str(row.stage_instance_id), "gate": row.gate,
                "kind": row.kind, **(detail or {})},
    )  # fmt: skip


async def move_nc(
    session: AsyncSession, nc: NonConformance, trigger: str, who: Who, *,
    reason: str | None = None, file_ids: list[uuid.UUID] | None = None,
    detail: dict[str, Any] | None = None,
) -> None:  # fmt: skip
    old = nc.state
    nc.state = NC.target(NcState(old), trigger).value
    nc.version += 1
    await session.flush()
    await history(
        session, subject="NON_CONFORMANCE", subject_id=nc.id, project_id=nc.project_id, old=old,
        new=nc.state, who=who, reason=reason, file_ids=file_ids, detail=detail,
    )  # fmt: skip


async def refresh_gate(session: AsyncSession, stage_id: uuid.UUID, who: Who) -> GateStatus:
    """The gate follows the records (F.5): findings not closed → OPEN_NC; an approved initial
    inspection → CLEARED; a live one → SCHEDULED; otherwise NOT_INSPECTED. Observations never
    block."""
    open_nc = await session.scalar(
        select(
            exists().where(
                NonConformance.stage_instance_id == stage_id,
                NonConformance.state.in_(NOT_CLOSED),
            )
        )
    )
    approved = await session.scalar(
        select(
            exists().where(
                Inspection.stage_instance_id == stage_id,
                Inspection.kind == InspectionKind.INITIAL.value,
                Inspection.state == S.APPROVED.value,
            )
        )
    )
    live = await session.scalar(
        select(
            exists().where(
                Inspection.stage_instance_id == stage_id,
                Inspection.kind == InspectionKind.INITIAL.value,
                Inspection.state.in_(LIVE_INSPECTION),
            )
        )
    )
    status = (
        GateStatus.OPEN_NC if open_nc
        else GateStatus.CLEARED if approved
        else GateStatus.SCHEDULED if live
        else GateStatus.NOT_INSPECTED
    )  # fmt: skip
    await set_gate_status(session, stage_id, status, who)
    return status


async def _tell_contractor(
    session: AsyncSession, project_id: uuid.UUID, notice: str, *, ref: str,
    inspection_id: uuid.UUID | None = None, nc_id: uuid.UUID | None = None,
) -> None:  # fmt: skip
    current = await contractor_of_record(session, project_id)
    if current is not None and current.party == EngagementParty.LISTED.value:
        await notify(
            session, "contractor", notice, aggregate_id=current.id, project_id=project_id,
            inspection_id=inspection_id, nc_id=nc_id, ref=ref,
        )  # fmt: skip


async def _tell_auditor(
    session: AsyncSession, appointment: AuditorAppointment, row: Inspection, notice: str, ref: str
) -> None:
    if appointment.user_id is not None:
        await notify(
            session, "auditor", notice, aggregate_id=appointment.id, project_id=row.project_id,
            inspection_id=row.id, ref=ref,
        )  # fmt: skip


# --- scheduling --------------------------------------------------------------------------------


async def schedule(
    session: AsyncSession, who: Who, *, stage_id: uuid.UUID, appointment_id: uuid.UUID,
    visit_note: str | None, amends_id: uuid.UUID | None = None,
) -> Inspection:  # fmt: skip
    """An INITIAL inspection of a gate stage instance (EX-07); `amends_id` names a RETURNED one
    it replaces. 409 reasons: NOT_A_GATE, ALREADY_SCHEDULED, NO_CHECKLIST, APPOINTMENT_ENDED,
    NOT_RETURNED, PROJECT_CLOSED; or PACKAGE_REQUIRED."""
    assert who.user_id is not None  # noqa: S101 (operations act)
    stage = await stage_facts(session, stage_id, lock=True)
    await require_package(session, stage.project_id)
    await open_project(session, stage.project_id)
    if not stage.is_gate or stage.gate is None:
        raise conflict("NOT_A_GATE", "Only a gate stage is inspected.")
    live = await session.scalar(
        select(Inspection.id).where(
            Inspection.stage_instance_id == stage.id,
            Inspection.kind == InspectionKind.INITIAL.value,
            Inspection.state.notin_((S.RETURNED.value, S.CANCELLED.value)),
        )
    )
    if live is not None:
        raise conflict("ALREADY_SCHEDULED", "This stage already has its inspection.")
    if amends_id is not None:
        amended = await inspection_row(session, amends_id)
        if amended.stage_instance_id != stage.id or amended.state != S.RETURNED.value:
            raise conflict("NOT_RETURNED", "Only a returned inspection of this stage is amended.")
    appointment = await appointments.active(session, appointment_id)
    version = await checklists.published(session)
    if version is None or not await checklists.checkpoints(session, version.id, stage.gate):
        raise conflict("NO_CHECKLIST", f"No published checklist has Gate {stage.gate} checkpoints.")
    row = Inspection(
        id=new_id(), project_id=stage.project_id, stage_instance_id=stage.id, gate=stage.gate,
        kind=InspectionKind.INITIAL.value, appointment_id=appointment.id,
        checklist_version_id=version.id, amends_id=amends_id, nc_ids=[],
        state=INSPECTION.target(None, "schedule").value, visit_note=visit_note,
        scheduled_by=who.user_id,
    )  # fmt: skip
    session.add(row)
    await session.flush()
    await history(
        session, subject="INSPECTION", subject_id=row.id, project_id=row.project_id, old=None,
        new=row.state, who=who,
        detail={"stage_instance_id": str(stage.id), "gate": stage.gate, "kind": row.kind,
                "auditor_code": appointment.auditor_code, "checklist_version": version.version,
                "amends": str(amends_id) if amends_id else None},
    )  # fmt: skip
    await refresh_gate(session, stage.id, who)
    ref = str(row.id)
    await _tell_auditor(session, appointment, row, "INSPECTION_ASSIGNED", ref)
    await notify(session, "family", "INSPECTION_SCHEDULED", aggregate_id=row.project_id,
                 project_id=row.project_id, inspection_id=row.id, ref=ref)  # fmt: skip
    await _tell_contractor(session, row.project_id, "INSPECTION_SCHEDULED", ref=ref,
                           inspection_id=row.id)  # fmt: skip
    return row


async def schedule_reinspection(
    session: AsyncSession, who: Who, *, nc_ids: list[uuid.UUID], appointment_id: uuid.UUID,
    visit_note: str | None,
) -> Inspection:  # fmt: skip
    """A re-inspection of rectified findings of one stage (G). 409 reasons: NOT_RECTIFIED,
    MIXED_STAGES; or PACKAGE_REQUIRED."""
    assert who.user_id is not None  # noqa: S101
    wanted = list(dict.fromkeys(nc_ids))
    ncs = list(
        await session.scalars(
            select(NonConformance).where(NonConformance.id.in_(wanted)).with_for_update()
        )
    )
    if len(ncs) != len(wanted):
        raise NotFound
    if len({nc.stage_instance_id for nc in ncs}) != 1 or len({nc.inspection_id for nc in ncs}) != 1:
        raise conflict("MIXED_STAGES", "Re-inspect findings of one inspection at a time.")
    if any(nc.state != NcState.RECTIFICATION_SUBMITTED.value for nc in ncs):
        raise conflict("NOT_RECTIFIED", "Every finding needs its rectification first.")
    original = await inspection_row(session, ncs[0].inspection_id)
    await require_package(session, original.project_id)
    await open_project(session, original.project_id)
    appointment = await appointments.active(session, appointment_id)
    row = Inspection(
        id=new_id(), project_id=original.project_id, stage_instance_id=original.stage_instance_id,
        gate=original.gate, kind=InspectionKind.REINSPECTION.value, appointment_id=appointment.id,
        checklist_version_id=original.checklist_version_id, reinspects_id=original.id,
        nc_ids=[nc.id for nc in ncs], state=INSPECTION.target(None, "schedule").value,
        visit_note=visit_note, scheduled_by=who.user_id,
    )  # fmt: skip
    session.add(row)
    await session.flush()
    await history(
        session, subject="INSPECTION", subject_id=row.id, project_id=row.project_id, old=None,
        new=row.state, who=who,
        detail={"stage_instance_id": str(row.stage_instance_id), "gate": row.gate,
                "kind": row.kind, "reinspects": str(original.id),
                "auditor_code": appointment.auditor_code},
    )  # fmt: skip
    for nc in ncs:
        await move_nc(session, nc, "reinspect", who, detail={"inspection_id": str(row.id)})
    ref = str(row.id)
    await _tell_auditor(session, appointment, row, "INSPECTION_ASSIGNED", ref)
    await _tell_contractor(session, row.project_id, "REINSPECTION_SCHEDULED", ref=ref,
                           inspection_id=row.id)  # fmt: skip
    return row


# --- performing ----------------------------------------------------------------------------------


async def scope(session: AsyncSession, row: Inspection) -> list[Checkpoint]:
    """The checkpoints this inspection answers: its gate's in its checklist version, or the
    findings' checkpoints for a re-inspection."""
    if row.kind == InspectionKind.INITIAL.value:
        return await checklists.checkpoints(session, row.checklist_version_id, row.gate)
    ids = set(
        await session.scalars(
            select(NonConformance.checkpoint_id).where(NonConformance.id.in_(row.nc_ids))
        )
    )
    points = await checklists.checkpoints(session, row.checklist_version_id, row.gate)
    return [c for c in points if c.id in ids]


async def results_of(session: AsyncSession, inspection_id: uuid.UUID) -> list[InspectionResult]:
    return list(
        await session.scalars(
            select(InspectionResult).where(InspectionResult.inspection_id == inspection_id)
        )
    )


async def start(session: AsyncSession, who: Who, inspection_id: uuid.UUID) -> Inspection:
    """The auditor confirms the stage is ready (F.5)."""
    row = await inspection_row(session, inspection_id, lock=True)
    if row.state != S.SCHEDULED.value:
        raise conflict("NOT_SCHEDULED", "This inspection is not waiting to start.",
                       current_state=row.state)  # fmt: skip
    await open_project(session, row.project_id)
    row.readiness_at = await db_now(session)
    await move(session, row, "start", who)
    return row


async def save_results(
    session: AsyncSession, who: Who, row: Inspection, items: list[dict[str, Any]]
) -> None:
    """Record or replace checkpoint results while IN_PROGRESS. Each item: checkpoint_id, result,
    note, na_reason, measurement, room_tag, file_ids, and for a finding severity, description,
    corrective_action, due_date."""
    if row.state != S.IN_PROGRESS.value:
        raise conflict("NOT_IN_PROGRESS", "Results are recorded while the inspection is open.",
                       current_state=row.state)  # fmt: skip
    allowed = {c.id for c in await scope(session, row)}
    errors: dict[str, list[str]] = {}
    on = await today(session)
    files = await file_facts(session, list({f for i in items for f in i["file_ids"]}))
    seen: set[uuid.UUID] = set()
    for n, item in enumerate(items):
        where = f"results.{n}"
        result = R(item["result"])
        finding = item.get("severity") is not None
        if item["checkpoint_id"] not in allowed or item["checkpoint_id"] in seen:
            errors[where] = ["Not a checkpoint of this inspection, or given twice."]
        elif result == R.NOT_APPLICABLE and not item.get("na_reason"):
            errors[where] = ["Say why the checkpoint does not apply."]
        elif row.kind == InspectionKind.REINSPECTION.value and (
            result not in (R.PASS, R.NON_CONFORMANCE) or finding
        ):
            errors[where] = ["A re-inspection records PASS or NON_CONFORMANCE only."]
        elif row.kind == InspectionKind.INITIAL.value and (result == R.NON_CONFORMANCE) != finding:
            errors[where] = ["A non-conformance needs its finding, and only a non-conformance."]
        elif finding and not (
            item.get("description") and item.get("corrective_action") and item.get("due_date")
        ):
            errors[where] = ["Give the description, corrective action and due date."]
        elif finding and item["due_date"] < on:
            errors[where] = ["The due date cannot be in the past."]
        elif any(
            (f := files.get(fid)) is None
            or f.project_id != row.project_id
            or f.purpose != FilePurpose.INSPECTION_EVIDENCE
            or f.state != FileState.AVAILABLE
            for fid in item["file_ids"]
        ):
            errors[where] = ["Upload the photos and wait for the check."]
        seen.add(item["checkpoint_id"])
    if errors:
        raise ValidationFailed(details={"fields": errors})
    existing = {r.checkpoint_id: r for r in await results_of(session, row.id)}
    for item in items:
        old = existing.get(item["checkpoint_id"])
        if old is not None:
            await session.delete(old)
    await session.flush()
    for item in items:
        session.add(
            InspectionResult(
                id=new_id(), inspection_id=row.id, checkpoint_id=item["checkpoint_id"],
                result=item["result"], note=item.get("note"), na_reason=item.get("na_reason"),
                measurement=item.get("measurement"), room_tag=item.get("room_tag"),
                file_ids=list(dict.fromkeys(item["file_ids"])), severity=item.get("severity"),
                description=item.get("description"),
                corrective_action=item.get("corrective_action"), due_date=item.get("due_date"),
            )
        )  # fmt: skip
    await session.flush()


async def content(session: AsyncSession, row: Inspection) -> dict[str, Any]:
    """What submission freezes: the checkpoints with their results and the hashes of their
    evidence (BR-123). The hash of this is `content_sha256`."""
    points = await scope(session, row)
    results = {r.checkpoint_id: r for r in await results_of(session, row.id)}
    files = await file_facts(session, list({f for r in results.values() for f in r.file_ids}))
    return {
        "inspection_id": str(row.id), "project_id": str(row.project_id),
        "stage_instance_id": str(row.stage_instance_id), "gate": row.gate, "kind": row.kind,
        "checklist_version_id": str(row.checklist_version_id),
        "nc_ids": sorted(str(i) for i in row.nc_ids), "summary": row.summary,
        "staff_capture": row.staff_capture,
        "capture_evidence_file_id": str(row.capture_evidence_file_id)
        if row.capture_evidence_file_id else None,
        "checkpoints": [
            {
                "code": c.code, "text": c.text,
                **(
                    {
                        "result": r.result, "note": r.note, "na_reason": r.na_reason,
                        "measurement": r.measurement, "room_tag": r.room_tag,
                        "severity": r.severity, "description": r.description,
                        "corrective_action": r.corrective_action,
                        "due_date": r.due_date.isoformat() if r.due_date else None,
                        "evidence": [
                            {"file_id": str(f), "sha256": files[f].sha256 if f in files else None}
                            for f in r.file_ids
                        ],
                    }
                    if (r := results.get(c.id)) is not None
                    else {"result": None}
                ),
            }
            for c in points
        ],
    }  # fmt: skip


async def _freeze(session: AsyncSession, who: Who, row: Inspection, summary: str | None) -> None:
    points = await scope(session, row)
    answered = {r.checkpoint_id for r in await results_of(session, row.id)}
    missing = [c.code for c in points if c.id not in answered]
    if missing:
        raise conflict("INCOMPLETE", "Record every checkpoint before submitting.", missing=missing)
    row.summary = summary
    row.submitted_at = await db_now(session)
    row.submitted_by = who.user_id
    row.submitted_role = who.role
    await session.flush()
    row.content_sha256 = sha256(await content(session, row))
    await move(session, row, "submit", who, detail={"content_sha256": row.content_sha256})
    await notify(session, "ops", "INSPECTION_SUBMITTED", aggregate_id=row.project_id,
                 project_id=row.project_id, inspection_id=row.id, ref=str(row.id))  # fmt: skip


async def submit(
    session: AsyncSession, database: Database, settings: Settings, who: Who, *,
    inspection_id: uuid.UUID, summary: str | None, challenge_id: uuid.UUID, code: str,
    ip_hash: str,
) -> Inspection:  # fmt: skip
    """The auditor submits with a fresh one-time code (EX-09)."""
    assert who.user_id is not None  # noqa: S101
    row = await inspection_row(session, inspection_id, lock=True)
    if row.state != S.IN_PROGRESS.value:
        raise conflict("NOT_IN_PROGRESS", "Only an open inspection is submitted.",
                       current_state=row.state)  # fmt: skip
    await verify_confirmation(
        database, settings, challenge_id=challenge_id, code=code, user_id=who.user_id,
        purpose=OtpPurpose.SUBMIT_INSPECTION, subject_id=row.id, ip_hash=ip_hash,
    )  # fmt: skip
    row.submit_challenge_id = challenge_id
    await _freeze(session, who, row, summary)
    return row


async def capture(
    session: AsyncSession, who: Who, *, inspection_id: uuid.UUID, items: list[dict[str, Any]],
    summary: str | None, evidence_file_id: uuid.UUID,
) -> Inspection:  # fmt: skip
    """Operations enter an inspection from the auditor's signed report (F.3, without an account),
    recorded as staff capture with that evidence."""
    row = await inspection_row(session, inspection_id, lock=True)
    facts = (await file_facts(session, [evidence_file_id])).get(evidence_file_id)
    if (
        facts is None
        or facts.project_id != row.project_id
        or facts.purpose != FilePurpose.INSPECTION_EVIDENCE
        or facts.state != FileState.AVAILABLE
    ):
        raise ValidationFailed(
            details={"fields": {"evidence_file_id": ["Upload the signed report first."]}}
        )
    if row.state == S.SCHEDULED.value:
        await start(session, who, row.id)
    elif row.state != S.IN_PROGRESS.value:
        raise conflict("NOT_IN_PROGRESS", "Only an open inspection is captured.",
                       current_state=row.state)  # fmt: skip
    await save_results(session, who, row, items)
    row.staff_capture = True
    row.capture_evidence_file_id = evidence_file_id
    await _freeze(session, who, row, summary)
    return row


# --- deciding ----------------------------------------------------------------------------------


async def report_snapshot(session: AsyncSession, row: Inspection) -> dict[str, Any]:
    """Everything the report shows, from the frozen content and the approval: deterministic."""
    stage = await stage_facts(session, row.stage_instance_id)
    facts = await connection_facts(session, row.project_id)
    appointment = await session.get_one(AuditorAppointment, row.appointment_id)
    version = await checklists.version_row(session, row.checklist_version_id)
    frozen = await content(session, row)
    return {
        "project_code": facts.code if facts else "", "stage": stage.name,
        "stage_number": stage.stage_number, "floor": stage.floor, "gate": row.gate,
        "kind": row.kind, "auditor_code": appointment.auditor_code,
        "auditor_name": appointment.name, "qualification": appointment.qualification,
        "checklist_version": version.version, "staff_capture": row.staff_capture,
        "scheduled_at": row.scheduled_at.isoformat(),
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "content_sha256": row.content_sha256, "summary": row.summary,
        "checkpoints": frozen["checkpoints"],
    }  # fmt: skip


async def _render(
    session: AsyncSession, settings: Settings, storage: Storage, who: Who, row: Inspection, *,
    version: int, reason: str | None,
) -> InspectionReport:  # fmt: skip
    assert who.user_id is not None  # noqa: S101
    assert row.approved_at is not None  # noqa: S101
    snapshot = await report_snapshot(session, row)
    data = render_report(settings, snapshot, version=version, correction_reason=reason)
    file_id = await store_generated_file(
        session, settings, storage, project_id=row.project_id, owner_user_id=who.user_id,
        purpose=FilePurpose.INSPECTION_REPORT, data=data, mime="application/pdf",
        file_name=f"inspection-{snapshot['project_code']}-gate{row.gate}-v{version}.pdf",
    )  # fmt: skip
    report = InspectionReport(
        id=new_id(), project_id=row.project_id, inspection_id=row.id, version=version,
        file_id=file_id, sha256=hashlib.sha256(data).hexdigest(), correction_reason=reason,
        rendered_by=who.user_id,
    )  # fmt: skip
    session.add(report)
    await session.flush()
    return report


async def approve(
    session: AsyncSession, settings: Settings, storage: Storage, who: Who, inspection_id: uuid.UUID
) -> Inspection:
    row = await inspection_row(session, inspection_id, lock=True)
    if row.state != S.SUBMITTED.value:
        raise conflict("NOT_SUBMITTED", "Only a submitted inspection is approved.",
                       current_state=row.state)  # fmt: skip
    await require_package(session, row.project_id)
    if sha256(await content(session, row)) != row.content_sha256:
        raise conflict("CONTENT_CHANGED", "The inspection content does not match its hash.")
    results = {r.checkpoint_id: r for r in await results_of(session, row.id)}
    row.approved_by = who.user_id
    row.approved_at = await db_now(session)
    await move(session, row, "approve", who)
    opened: list[NonConformance] = []
    closed: list[NonConformance] = []
    if row.kind == InspectionKind.INITIAL.value:
        current = await contractor_of_record(session, row.project_id)
        for r in results.values():
            if r.severity is None:
                continue
            assert r.description is not None  # noqa: S101 (CHECK finding_complete)
            assert r.corrective_action is not None  # noqa: S101
            assert r.due_date is not None  # noqa: S101
            nc = NonConformance(
                id=new_id(), project_id=row.project_id, stage_instance_id=row.stage_instance_id,
                inspection_id=row.id, result_id=r.id, checkpoint_id=r.checkpoint_id,
                severity=r.severity, description=r.description,
                corrective_action=r.corrective_action, due_date=r.due_date,
                engagement_id=current.id if current else None,
                state=NC.target(None, "open").value,
            )  # fmt: skip
            session.add(nc)
            await session.flush()
            await history(
                session, subject="NON_CONFORMANCE", subject_id=nc.id, project_id=nc.project_id,
                old=None, new=nc.state, who=who,
                detail={"severity": nc.severity, "inspection_id": str(row.id)},
            )  # fmt: skip
            opened.append(nc)
    else:
        for nc in await session.scalars(
            select(NonConformance).where(NonConformance.id.in_(row.nc_ids)).with_for_update()
        ):
            result = results.get(nc.checkpoint_id)
            if result is not None and result.result == R.PASS.value:
                nc.closed_by_inspection_id = row.id
                nc.closed_at = row.approved_at
                await move_nc(session, nc, "close", who, detail={"inspection_id": str(row.id)})
                closed.append(nc)
            else:
                await move_nc(session, nc, "not_closed", who,
                              detail={"inspection_id": str(row.id)})  # fmt: skip
    gate = await refresh_gate(session, row.stage_instance_id, who)
    await _render(session, settings, storage, who, row, version=1, reason=None)
    ref = str(row.id)
    await notify(session, "family", "REPORT_APPROVED", aggregate_id=row.project_id,
                 project_id=row.project_id, inspection_id=row.id, ref=ref)  # fmt: skip
    if opened:
        await _tell_contractor(session, row.project_id, "FINDINGS", ref=ref, inspection_id=row.id)
    if closed:
        await _tell_contractor(session, row.project_id, "FINDINGS_CLOSED", ref=ref,
                               inspection_id=row.id)  # fmt: skip
    if gate == GateStatus.CLEARED:
        await _tell_contractor(session, row.project_id, "GATE_CLEARED", ref=ref,
                               inspection_id=row.id)  # fmt: skip
    return row


async def return_(
    session: AsyncSession, who: Who, inspection_id: uuid.UUID, reason: str
) -> Inspection:
    """Back to the auditor for amendment: the returned record stays as it is; operations
    schedule a replacement that names it (initial), or the findings wait for a new re-inspection."""
    row = await inspection_row(session, inspection_id, lock=True)
    if row.state != S.SUBMITTED.value:
        raise conflict("NOT_SUBMITTED", "Only a submitted inspection is returned.",
                       current_state=row.state)  # fmt: skip
    row.return_reason = reason
    await move(session, row, "return", who, reason=reason)
    await _release(session, who, row)
    appointment = await session.get_one(AuditorAppointment, row.appointment_id)
    await _tell_auditor(session, appointment, row, "INSPECTION_RETURNED", str(row.id))
    return row


async def _release(session: AsyncSession, who: Who, row: Inspection) -> None:
    """After a return or a cancellation: re-inspected findings go back to waiting; the gate is
    derived again."""
    if row.kind == InspectionKind.REINSPECTION.value:
        for nc in await session.scalars(
            select(NonConformance).where(NonConformance.id.in_(row.nc_ids)).with_for_update()
        ):
            if nc.state == NcState.REINSPECTION_SCHEDULED.value:
                await move_nc(session, nc, "reinspection_cancelled", who,
                              detail={"inspection_id": str(row.id)})  # fmt: skip
    await refresh_gate(session, row.stage_instance_id, who)


async def cancel(
    session: AsyncSession,
    who: Who,
    inspection_id: uuid.UUID,
    reason: InspectionCancelReason,
    note: str | None,
) -> Inspection:
    row = await inspection_row(session, inspection_id, lock=True)
    if row.state not in (S.SCHEDULED.value, S.IN_PROGRESS.value):
        raise conflict("NOT_OPEN", "Only an inspection not yet submitted is cancelled.",
                       current_state=row.state)  # fmt: skip
    row.cancel_reason = reason.value
    row.cancel_note = note
    await move(session, row, "cancel", who, reason=note or reason.value,
               detail={"cancel_reason": reason.value})  # fmt: skip
    await _release(session, who, row)
    appointment = await session.get_one(AuditorAppointment, row.appointment_id)
    await _tell_auditor(session, appointment, row, "INSPECTION_CANCELLED", str(row.id))
    await notify(session, "family", "INSPECTION_CANCELLED", aggregate_id=row.project_id,
                 project_id=row.project_id, inspection_id=row.id, ref=str(row.id))  # fmt: skip
    return row


async def cancel_open(
    session: AsyncSession, project_id: uuid.UUID, reason: InspectionCancelReason, who: Who
) -> int:
    """The package ended (EX-18: inspections not yet started) or the project closed (also those
    in progress). Submitted ones stay and wait. Idempotent: only open records move."""
    states = (S.SCHEDULED.value,) if reason == InspectionCancelReason.PACKAGE_ENDED else (
        S.SCHEDULED.value, S.IN_PROGRESS.value,
    )  # fmt: skip
    ids = list(
        await session.scalars(
            select(Inspection.id).where(
                Inspection.project_id == project_id, Inspection.state.in_(states)
            )
        )
    )
    for inspection_id in ids:
        await cancel(session, who, inspection_id, reason, None)
    return len(ids)


async def correct_report(
    session: AsyncSession, settings: Settings, storage: Storage, who: Who,
    inspection_id: uuid.UUID, reason: str,
) -> InspectionReport:  # fmt: skip
    """EX-14: a new report version; the earlier one stays readable and unchanged."""
    row = await inspection_row(session, inspection_id, lock=True)
    if row.state != S.APPROVED.value:
        raise conflict("NOT_APPROVED", "Only an approved inspection has a report.")
    latest = await session.scalar(
        select(InspectionReport.version)
        .where(InspectionReport.inspection_id == row.id)
        .order_by(InspectionReport.version.desc())
        .limit(1)
    )
    report = await _render(
        session, settings, storage, who, row, version=(latest or 0) + 1, reason=reason
    )
    await history(
        session, subject="INSPECTION", subject_id=row.id, project_id=row.project_id,
        old=row.state, new=row.state, who=who, reason=reason,
        detail={"report_version": report.version},
    )  # fmt: skip
    return report


async def add_test_result(
    session: AsyncSession, who: Who, result_id: uuid.UUID, *, test_kind: str, value: str,
    file_id: uuid.UUID | None,
) -> TestResult:  # fmt: skip
    """A later result (cube tests at 7 and 28 days) on an approved inspection's checkpoint."""
    assert who.user_id is not None  # noqa: S101
    result = await session.get(InspectionResult, result_id)
    if result is None:
        raise NotFound
    row = await inspection_row(session, result.inspection_id)
    if row.state != S.APPROVED.value:
        raise conflict("NOT_APPROVED", "Test results attach to an approved inspection.")
    if file_id is not None:
        facts = (await file_facts(session, [file_id])).get(file_id)
        if facts is None or facts.project_id != row.project_id or facts.purpose != (
            FilePurpose.INSPECTION_EVIDENCE
        ) or facts.state != FileState.AVAILABLE:  # fmt: skip
            raise ValidationFailed(details={"fields": {"file_id": ["Upload the result first."]}})
    test = TestResult(
        id=new_id(), project_id=row.project_id, result_id=result.id, test_kind=test_kind,
        value=value, file_id=file_id, recorded_by=who.user_id, recorded_role=who.role,
    )  # fmt: skip
    session.add(test)
    await session.flush()
    await history(
        session, subject="INSPECTION", subject_id=row.id, project_id=row.project_id,
        old=row.state, new=row.state, who=who,
        detail={"test_result": str(test.id), "test_kind": test_kind},
    )  # fmt: skip
    return test


async def stage_of(session: AsyncSession, row: Inspection) -> StageFacts:
    return await stage_facts(session, row.stage_instance_id)
