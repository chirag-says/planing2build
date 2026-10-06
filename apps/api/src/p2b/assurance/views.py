"""Read models for assurance (Slice 3.7B). Batched per table; an inspection's content appears for
the homeowner and the contractor only once it is approved."""

import uuid
from collections import defaultdict
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.assurance import checklists, inspections
from p2b.assurance.common import LOCAL_TIMEZONE, NOT_CLOSED, today
from p2b.assurance.models import (
    AuditorAppointment,
    Checkpoint,
    Inspection,
    InspectionReport,
    InspectionResult,
    NonConformance,
)
from p2b.assurance.pdf import outcome
from p2b.assurance.schemas import (
    AssuranceOut,
    AuditorCheckpointOut,
    AuditorInspectionOut,
    AuditorInspectionSummary,
    CheckpointOut,
    DrawingOut,
    FindingOut,
    InspectionOut,
    OpsInspectionOut,
    ReportOut,
    ResultOut,
)
from p2b.buildplan.interface import accepted_manifest
from p2b.catalog.interface import active_spec_masters
from p2b.construction.interface import StageFacts, gate_stages
from p2b.core.vocabulary import (
    CheckpointResult,
    InspectionKind,
    InspectionState,
    NcState,
    Severity,
)
from p2b.projects.interface import connection_facts


async def stage_map(session: AsyncSession, project_id: uuid.UUID) -> dict[uuid.UUID, StageFacts]:
    return {s.id: s for s in await gate_stages(session, project_id)}


def ref(stage: StageFacts) -> dict[str, object]:
    return {"stage_instance_id": stage.id, "stage_number": stage.stage_number,
            "stage_name": stage.name, "floor": stage.floor, "gate": stage.gate or 0}  # fmt: skip


def checkpoint_out(c: Checkpoint) -> CheckpointOut:
    return CheckpointOut(
        id=c.id, gate=c.gate, sequence=c.sequence, code=c.code, text=c.text,
        expected_evidence=c.expected_evidence, is_critical=c.is_critical,
        spec_line_code=c.spec_line_code,
    )  # fmt: skip


def result_out(r: InspectionResult) -> ResultOut:
    return ResultOut(
        id=r.id, checkpoint_id=r.checkpoint_id, result=CheckpointResult(r.result), note=r.note,
        na_reason=r.na_reason, measurement=r.measurement, room_tag=r.room_tag,
        file_ids=list(r.file_ids), severity=Severity(r.severity) if r.severity else None,
        description=r.description, corrective_action=r.corrective_action, due_date=r.due_date,
    )  # fmt: skip


async def _reports(
    session: AsyncSession, inspection_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[ReportOut]]:
    out: dict[uuid.UUID, list[ReportOut]] = defaultdict(list)
    if not inspection_ids:
        return out
    for r in await session.scalars(
        select(InspectionReport)
        .where(InspectionReport.inspection_id.in_(inspection_ids))
        .order_by(InspectionReport.version)
    ):
        out[r.inspection_id].append(
            ReportOut(
                version=r.version, correction_reason=r.correction_reason, rendered_at=r.rendered_at
            )
        )
    return out


async def _codes(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, AuditorAppointment]:
    if not ids:
        return {}
    rows = await session.scalars(select(AuditorAppointment).where(AuditorAppointment.id.in_(ids)))
    return {r.id: r for r in rows}


def finding_out(nc: NonConformance, stage: StageFacts, on: date) -> FindingOut:
    return FindingOut(
        **ref(stage), id=nc.id, severity=Severity(nc.severity), description=nc.description,
        corrective_action=nc.corrective_action, due_date=nc.due_date, state=NcState(nc.state),
        overdue=nc.state in NOT_CLOSED and nc.due_date < on, closed_at=nc.closed_at,
    )  # fmt: skip


async def project_inspections(session: AsyncSession, project_id: uuid.UUID) -> list[Inspection]:
    return list(
        await session.scalars(
            select(Inspection)
            .where(Inspection.project_id == project_id)
            .order_by(Inspection.scheduled_at, Inspection.id)
        )
    )


async def assurance_out(session: AsyncSession, project_id: uuid.UUID) -> AssuranceOut:
    """The homeowner's and the contractor's view."""
    stages = await stage_map(session, project_id)
    rows = await project_inspections(session, project_id)
    approved = [r for r in rows if r.state == InspectionState.APPROVED.value]
    reports = await _reports(session, [r.id for r in approved])
    codes = await _codes(session, {r.appointment_id for r in approved})
    items = []
    for row in rows:
        done = row.state == InspectionState.APPROVED.value
        items.append(
            InspectionOut(
                **ref(stages[row.stage_instance_id]),
                id=row.id,
                kind=InspectionKind(row.kind),
                state=InspectionState(row.state),
                scheduled_at=row.scheduled_at,
                approved_at=row.approved_at if done else None,
                auditor_code=codes[row.appointment_id].auditor_code if done else None,
                outcome=outcome(await inspections.content(session, row)) if done else None,
                reports=reports.get(row.id, []),
            )
        )
    on = await today(session)
    findings = [
        finding_out(nc, stages[nc.stage_instance_id], on)
        for nc in await session.scalars(
            select(NonConformance)
            .where(NonConformance.project_id == project_id)
            .order_by(NonConformance.created_at, NonConformance.id)
        )
    ]
    return AssuranceOut(inspections=items, findings=findings)


async def auditor_summaries(
    session: AsyncSession, appointment_id: uuid.UUID
) -> list[AuditorInspectionSummary]:
    rows = list(
        await session.scalars(
            select(Inspection)
            .where(Inspection.appointment_id == appointment_id)
            .order_by(Inspection.scheduled_at.desc())
            .limit(200)
        )
    )
    out = []
    cache: dict[uuid.UUID, tuple[str, dict[uuid.UUID, StageFacts]]] = {}
    for row in rows:
        if row.project_id not in cache:
            facts = await connection_facts(session, row.project_id)
            cache[row.project_id] = (facts.code if facts else "",
                                     await stage_map(session, row.project_id))  # fmt: skip
        code, stages = cache[row.project_id]
        out.append(
            AuditorInspectionSummary(
                **ref(stages[row.stage_instance_id]),
                id=row.id,
                project_code=code,
                kind=InspectionKind(row.kind),
                state=InspectionState(row.state),
                scheduled_at=row.scheduled_at,
            )
        )
    return out


async def auditor_detail(session: AsyncSession, row: Inspection) -> AuditorInspectionOut:
    """No supplier, brand, product, price or homeowner contact (F.3): the accepted value is shown
    only for lines without a brand category."""
    facts = await connection_facts(session, row.project_id)
    stages = await stage_map(session, row.project_id)
    version = await checklists.version_row(session, row.checklist_version_id)
    masters = {m.code: m for m in await active_spec_masters(session)}
    baseline = await accepted_manifest(session, row.project_id)
    values = {
        str(v["code"]): v.get("value")
        for v in (baseline.manifest.get("specifications", []) if baseline else [])
    }
    points = []
    for c in await inspections.scope(session, row):
        master = masters.get(c.spec_line_code or "")
        plain = master is not None and master.brand_category is None
        points.append(
            AuditorCheckpointOut(
                **checkpoint_out(c).model_dump(),
                criteria=master.performance_specification if master else None,
                accepted_value=str(values[c.spec_line_code])
                if plain and c.spec_line_code in values and values[c.spec_line_code]
                else None,
            )
        )
    drawings = [
        DrawingOut(
            file_id=uuid.UUID(str(d["file_id"])),
            title=d.get("title"),
            drawing_class=d.get("drawing_class"),
            sheet_no=d.get("sheet_no"),
        )
        for d in (baseline.manifest.get("drawings", []) if baseline else [])
    ]
    return AuditorInspectionOut(
        **ref(stages[row.stage_instance_id]), id=row.id,
        project_code=facts.code if facts else "", kind=InspectionKind(row.kind),
        state=InspectionState(row.state), scheduled_at=row.scheduled_at,
        locality=facts.locality if facts else None, visit_note=row.visit_note,
        checklist_version=version.version, checkpoints=points,
        results=[result_out(r) for r in await inspections.results_of(session, row.id)],
        drawings=drawings, summary=row.summary, return_reason=row.return_reason,
        version=row.version,
    )  # fmt: skip


async def ops_inspection_out(
    session: AsyncSession, row: Inspection, stages: dict[uuid.UUID, StageFacts], code: str,
    reports: dict[uuid.UUID, list[ReportOut]], appointments: dict[uuid.UUID, AuditorAppointment],
) -> OpsInspectionOut:  # fmt: skip
    version = await checklists.version_row(session, row.checklist_version_id)
    appointment = appointments[row.appointment_id]
    done = row.state == InspectionState.APPROVED.value
    return OpsInspectionOut(
        **ref(stages[row.stage_instance_id]), id=row.id, kind=InspectionKind(row.kind),
        state=InspectionState(row.state), scheduled_at=row.scheduled_at,
        approved_at=row.approved_at, auditor_code=appointment.auditor_code,
        outcome=outcome(await inspections.content(session, row)) if done else None,
        reports=reports.get(row.id, []), project_id=row.project_id, project_code=code,
        appointment_id=row.appointment_id, auditor_name=appointment.name,
        checklist_version=version.version, visit_note=row.visit_note, summary=row.summary,
        staff_capture=row.staff_capture, content_sha256=row.content_sha256,
        return_reason=row.return_reason, cancel_reason=row.cancel_reason,
        amends_id=row.amends_id, reinspects_id=row.reinspects_id, nc_ids=list(row.nc_ids),
        checkpoints=[checkpoint_out(c) for c in await inspections.scope(session, row)],
        results=[result_out(r) for r in await inspections.results_of(session, row.id)],
        version=row.version,
    )  # fmt: skip


async def ops_project(
    session: AsyncSession, project_id: uuid.UUID
) -> tuple[str, list[OpsInspectionOut], list[FindingOut]]:
    facts = await connection_facts(session, project_id)
    code = facts.code if facts else ""
    stages = await stage_map(session, project_id)
    rows = await project_inspections(session, project_id)
    reports = await _reports(session, [r.id for r in rows])
    appointments = await _codes(session, {r.appointment_id for r in rows})
    out = [await ops_inspection_out(session, r, stages, code, reports, appointments) for r in rows]
    on = await today(session)
    findings = [
        finding_out(nc, stages[nc.stage_instance_id], on)
        for nc in await session.scalars(
            select(NonConformance)
            .where(NonConformance.project_id == project_id)
            .order_by(NonConformance.created_at, NonConformance.id)
        )
    ]
    return code, out, findings


def open_too_long(row: Inspection, on: date, days: int) -> bool:
    """EX-12: an inspection open (scheduled or in progress) for `days` calendar days."""
    started = row.scheduled_at.astimezone(ZoneInfo(LOCAL_TIMEZONE)).date()
    return (on - started) >= timedelta(days=days)
