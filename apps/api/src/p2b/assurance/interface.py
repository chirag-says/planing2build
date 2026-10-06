"""Public interface of the assurance module. Notifications read what an assurance email may say
(SLICE3_7_READINESS O): the project code, the stage and its gate; never a finding's text, a
homeowner's identity for the auditor or the contractor, or an amount. The records module (3.7C)
reads gate facts and inspection results for the handover and the Build Record."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.assurance.common import NOT_CLOSED
from p2b.assurance.models import (
    AuditorAppointment,
    Inspection,
    InspectionReport,
    NonConformance,
)
from p2b.construction.interface import stage_facts
from p2b.engagements.interface import engagement_facts
from p2b.professionals.interface import profile_names
from p2b.projects.interface import connection_facts

FLOOR_NAMES = {-1: "basement", 0: "ground floor", 1: "first floor", 2: "second floor",
               3: "third floor"}  # fmt: skip


@dataclass(frozen=True)
class AssuranceNotice:
    """`user_id` is None for an operations notice (the operations mailbox)."""

    user_id: uuid.UUID | None
    values: dict[str, str]


async def assurance_notice(
    session: AsyncSession, audience: str, aggregate_id: uuid.UUID, payload: dict[str, object]
) -> AssuranceNotice | None:
    stage_id = None
    if payload.get("inspection_id"):
        inspection = await session.get(Inspection, uuid.UUID(str(payload["inspection_id"])))
        stage_id = inspection.stage_instance_id if inspection else None
    elif payload.get("nc_id"):
        nc = await session.get(NonConformance, uuid.UUID(str(payload["nc_id"])))
        stage_id = nc.stage_instance_id if nc else None
    facts = await connection_facts(session, uuid.UUID(str(payload["project_id"])))
    if stage_id is None or facts is None:
        return None
    stage = await stage_facts(session, stage_id)
    floor = "" if stage.floor is None else f" ({FLOOR_NAMES.get(stage.floor, stage.floor)})"
    values = {"code": facts.code, "stage": f"{stage.name}{floor}", "gate": str(stage.gate or "")}
    if audience == "ops":
        return AssuranceNotice(None, values)
    if audience == "family":
        return AssuranceNotice(facts.owner_user_id, values)
    if audience == "auditor":
        appointment = await session.get(AuditorAppointment, aggregate_id)
        if appointment is None or appointment.user_id is None:
            return None
        return AssuranceNotice(appointment.user_id, values)
    engagement = await engagement_facts(session, aggregate_id)
    if engagement is None or engagement.profile_id is None:
        return None
    names = await profile_names(session, [engagement.profile_id])
    if engagement.profile_id not in names:
        return None
    return AssuranceNotice(names[engagement.profile_id][0], values)


async def open_findings(session: AsyncSession, project_id: uuid.UUID) -> int:
    """Findings not closed on the project (EX-15: handover needs none)."""
    rows = await session.scalars(
        select(NonConformance.id).where(
            NonConformance.project_id == project_id, NonConformance.state.in_(NOT_CLOSED)
        )
    )
    return len(list(rows))


async def assurance_summary(session: AsyncSession, project_id: uuid.UUID) -> dict[str, object]:
    """Approved inspections (gate, stage, date, auditor ID, outcome, report hashes), every
    finding with its closure, and per specification line the results recorded at the gates
    (EX-16: results only; completion is never inferred from them)."""
    rows = list(
        await session.scalars(
            select(Inspection)
            .where(Inspection.project_id == project_id, Inspection.state == "APPROVED")
            .order_by(Inspection.approved_at, Inspection.id)
        )
    )
    codes = {
        a.id: a.auditor_code
        for a in await session.scalars(
            select(AuditorAppointment).where(
                AuditorAppointment.id.in_({r.appointment_id for r in rows})
            )
        )
    } if rows else {}  # fmt: skip
    reports: dict[uuid.UUID, list[dict[str, object]]] = {}
    for report in await session.scalars(
        select(InspectionReport)
        .where(InspectionReport.project_id == project_id)
        .order_by(InspectionReport.version)
    ):
        reports.setdefault(report.inspection_id, []).append(
            {"version": report.version, "sha256": report.sha256}
        )
    approved = []
    lines: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        content = await inspections.content(session, row)
        stage = await stage_facts(session, row.stage_instance_id)
        approved.append({
            "inspection_id": str(row.id), "gate": row.gate, "kind": row.kind,
            "stage_number": stage.stage_number, "stage": stage.name, "floor": stage.floor,
            "approved_at": row.approved_at.isoformat() if row.approved_at else None,
            "auditor_code": codes.get(row.appointment_id), "outcome": outcome(content),
            "content_sha256": row.content_sha256, "reports": reports.get(row.id, []),
        })  # fmt: skip
        points = {c.code: c for c in await inspections.scope(session, row)}
        for point in content["checkpoints"]:
            code = points[point["code"]].spec_line_code
            if code and point.get("result"):
                lines.setdefault(code, []).append({
                    "gate": row.gate, "floor": stage.floor, "result": point["result"],
                    "approved_at": row.approved_at.isoformat() if row.approved_at else None,
                })  # fmt: skip
    findings = [
        {
            "severity": nc.severity, "description": nc.description,
            "corrective_action": nc.corrective_action, "due_date": nc.due_date.isoformat(),
            "state": nc.state, "closed_at": nc.closed_at.isoformat() if nc.closed_at else None,
            "closed_by_inspection_id": str(nc.closed_by_inspection_id)
            if nc.closed_by_inspection_id else None,
        }
        for nc in await session.scalars(
            select(NonConformance)
            .where(NonConformance.project_id == project_id)
            .order_by(NonConformance.created_at, NonConformance.id)
        )
    ]  # fmt: skip
    return {"inspections": approved, "findings": findings, "line_results": lines}


__all__ = ["AssuranceNotice", "assurance_notice", "assurance_summary", "open_findings"]
