"""Read models: the snapshot of one version (the single source for the PDF, the family's view
and the operations view) and the contractor RFQ manifest (BP-08: no Plan2Build rates)."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.buildplan import plans, signoffs
from p2b.buildplan.common import Who
from p2b.buildplan.design import may_provide, set_files
from p2b.buildplan.models import (
    AcceptanceStatement,
    BuildPlanAcceptance,
    BuildPlanVersion,
    CheckerAppointment,
    DesignRequest,
    DrawingSet,
    SignoffStatement,
)
from p2b.buildplan.schemas import (
    DesignRequestOut,
    DrawingFileOut,
    DrawingSetOut,
    FileOut,
    VersionSummaryOut,
)
from p2b.catalog.interface import active_spec_masters, item_rate_card
from p2b.construction.interface import stages_for
from p2b.core.vocabulary import BuildPlanState
from p2b.documents.interface import file_facts
from p2b.projects.interface import BuildPlanFacts

QUOTE_FORMAT_VERSION = 1


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


async def drawing_set_view(session: AsyncSession, set_id: uuid.UUID) -> dict[str, Any]:
    drawing_set = await session.get_one(DrawingSet, set_id)
    request = await session.get_one(DesignRequest, drawing_set.request_id)
    checker = (
        await session.get(CheckerAppointment, drawing_set.checker_appointment_id)
        if drawing_set.checker_appointment_id
        else None
    )
    return {
        "id": str(drawing_set.id),
        "set_no": drawing_set.set_no,
        "state": drawing_set.state,
        "content_hash": drawing_set.content_hash,
        "request_kind": request.kind,
        "provider_name": request.provider_name,
        "checker": {"name": checker.name, "qualification": checker.qualification}
        if checker
        else None,
        "checked_at": _iso(drawing_set.checked_at),
        "files": [
            {"id": str(f.id), "file_id": str(f.file_id), "drawing_class": f.drawing_class,
             "floor": f.floor, "title": f.title, "sheet_no": f.sheet_no, "sha256": f.sha256}
            for f in await set_files(session, drawing_set.id)
        ],
    }  # fmt: skip


async def snapshot(
    session: AsyncSession, facts: BuildPlanFacts, version: BuildPlanVersion
) -> dict[str, Any]:
    masters = {m.code: m for m in await active_spec_masters(session)}
    stage_names = {s.id: s.name for s in await stages_for(session, version.project_id)}
    boq = await plans.boq_of(session, version.id)
    stage_totals: dict[str, Decimal] = {}
    for line in boq:
        key = str(line.stage_number) if line.stage_number else "unassigned"
        stage_totals[key] = stage_totals.get(key, Decimal("0")) + line.amount
    card = await item_rate_card(session, version.rate_card_id) if version.rate_card_id else None
    statements = {s.id: s for s in await signoffs.statements(session, SignoffStatement)}
    others = [
        v
        for v in await plans.versions_of(session, version.project_id)
        if v.issued_at is not None and v.version_no <= version.version_no
    ]
    acceptance = (
        await session.scalars(
            select(BuildPlanAcceptance).where(BuildPlanAcceptance.version_id == version.id)
        )
    ).one_or_none()
    acceptance_versions = {
        s.id: s.version for s in await signoffs.statements(session, AcceptanceStatement)
    }
    return {
        "project": {"id": str(facts.project_id), "code": facts.code, "locality": facts.locality},
        "version": {
            "id": str(version.id), "version_no": version.version_no, "state": version.state,
            "content_hash": version.content_hash,
            "requirement_version": version.requirement_version,
            "submitted_at": _iso(version.submitted_at), "issued_at": _iso(version.issued_at),
            "accepted_at": _iso(version.accepted_at), "closed_at": _iso(version.closed_at),
            "close_reason": version.close_reason,
        },
        "drawing_set": await drawing_set_view(session, version.drawing_set_id)
        if version.drawing_set_id
        else None,
        "values": [
            {"code": v.line_code, "group": masters[v.line_code].group if v.line_code in masters
             else "", "item": masters[v.line_code].item if v.line_code in masters else "",
             "criteria": v.criteria_text, "applicability": v.applicability, "value": v.value_text,
             "basis": v.basis, "not_applicable_reason": v.not_applicable_reason,
             "source_note": v.source_note, "is_structural": v.is_structural}
            for v in await plans.values_of(session, version.id)
        ],
        "rate_card": {"id": str(card.id), "geography": card.geography, "version": card.version,
                      "is_demo": card.is_demo, "status": card.status.value} if card else None,
        "boq": [
            {"line_no": b.line_no, "item_code": b.item_code, "description": b.description,
             "unit": b.unit, "quantity": f"{b.quantity:.3f}", "rate": f"{b.rate:.2f}",
             "amount": f"{b.amount:.2f}", "quantity_basis": b.quantity_basis,
             "drawing_file_id": str(b.drawing_file_id) if b.drawing_file_id else None,
             "basis_note": b.basis_note, "stage_number": b.stage_number, "floor": b.floor,
             "spec_line_codes": list(b.spec_line_codes), "assumptions": b.assumptions}
            for b in boq
        ],
        "boq_total": f"{sum((b.amount for b in boq), Decimal('0')):.2f}",
        "stage_totals": {k: f"{v:.2f}" for k, v in sorted(stage_totals.items())},
        "schedule": [
            {"entry_key": e.entry_key, "stage_number": e.stage_number,
             "stage_name": stage_names.get(e.stage_instance_id, ""), "floor": e.floor,
             "duration_days": e.duration_days, "predecessors": list(e.predecessors),
             "note": e.note, "planned_start": None, "planned_end": None}
            for e in await plans.schedule_of(session, version.id)
        ],
        "dates_status": "NOT_CALCULATED_BP07A_DEFERRED",
        "scope": {"inclusions": list(version.inclusions), "exclusions": list(version.exclusions),
                  "assumptions": list(version.assumptions),
                  "explanation_note": version.explanation_note},
        "signoffs": [
            {"id": str(s.id), "line_code": s.line_code, "state": s.state, "mode": s.mode,
             "signer_kind": s.signer_kind, "engineer_name": s.engineer_name,
             "engineer_firm": s.engineer_firm, "registration_number": s.registration_number,
             "registration_issuer": s.registration_issuer, "category": s.category_code,
             "statement_version": statements[s.statement_id].version,
             "content_hash": s.content_hash, "drawing_hashes": list(s.drawing_hashes),
             "signed_at": _iso(s.signed_at), "void_reason": s.void_reason}
            for s in await signoffs.all_of(session, version.id)
        ],
        "statements": {
            str(statements[s].version): statements[s].text
            for s in {s.statement_id for s in await signoffs.signed(session, version.id)}
        },
        "unsigned_structural_lines": await signoffs.unsigned_lines(session, version)
        if version.state == BuildPlanState.IN_REVIEW.value
        else [],
        "history": [
            {"version_no": v.version_no, "state": v.state, "issued_at": _iso(v.issued_at),
             "closed_at": _iso(v.closed_at), "close_reason": v.close_reason}
            for v in others
        ],
        "acceptance": {"accepted_at": _iso(acceptance.accepted_at),
                       "content_hash": acceptance.content_hash,
                       "issued_document_sha256": acceptance.issued_document_sha256,
                       "statement": acceptance.statement_text,
                       "statement_version": acceptance_versions.get(acceptance.statement_id, 0)}
        if acceptance else None,
    }  # fmt: skip


def manifest(view: dict[str, Any]) -> dict[str, Any]:
    """The contractor RFQ manifest of an ACCEPTED version (BP-08). Scope, quantities and the
    issued specification values; never Plan2Build's rates, amounts or rate card."""
    drawing_set = view["drawing_set"] or {}
    return {
        "build_plan_version_id": view["version"]["id"],
        "version_no": view["version"]["version_no"],
        "content_hash": view["version"]["content_hash"],
        "accepted_at": view["version"]["accepted_at"],
        "project_code": view["project"]["code"],
        "drawings": [
            {"file_id": f["file_id"], "drawing_class": f["drawing_class"], "floor": f["floor"],
             "title": f["title"], "sheet_no": f["sheet_no"], "sha256": f["sha256"]}
            for f in drawing_set.get("files", [])
        ],
        "drawing_set_hash": drawing_set.get("content_hash"),
        "specifications": [
            {"code": v["code"], "item": v["item"], "criteria": v["criteria"],
             "applicability": v["applicability"], "value": v["value"],
             "not_applicable_reason": v["not_applicable_reason"]}
            for v in view["values"]
        ],
        "quantities": [
            {"line_no": b["line_no"], "item_code": b["item_code"],
             "description": b["description"], "unit": b["unit"], "quantity": b["quantity"],
             "stage_number": b["stage_number"], "floor": b["floor"],
             "spec_line_codes": b["spec_line_codes"], "assumptions": b["assumptions"]}
            for b in view["boq"]
        ],
        "schedule": [
            {"entry_key": e["entry_key"], "stage_number": e["stage_number"],
             "stage_name": e["stage_name"], "floor": e["floor"],
             "duration_days": e["duration_days"], "predecessors": e["predecessors"]}
            for e in view["schedule"]
        ],
        "dates_status": view["dates_status"],
        "scope": {k: view["scope"][k] for k in ("inclusions", "exclusions", "assumptions")},
        "quote_format": {
            "version": QUOTE_FORMAT_VERSION,
            "price_per_quantity_line": True,
            "explicit_exclusions_per_line": True,
            "contractor_schedule": True,
        },
    }  # fmt: skip


async def design_requests_out(
    session: AsyncSession,
    project_id: uuid.UUID,
    who: Who,
    *,
    profile_id: uuid.UUID | None,
    only: uuid.UUID | None = None,
) -> list[DesignRequestOut]:
    query = select(DesignRequest).where(DesignRequest.project_id == project_id)
    if only is not None:
        query = query.where(DesignRequest.id == only)
    requests = list(await session.scalars(query.order_by(DesignRequest.opened_at)))
    out = []
    for request in requests:
        sets = list(
            await session.scalars(
                select(DrawingSet)
                .where(DrawingSet.request_id == request.id)
                .order_by(DrawingSet.set_no)
            )
        )
        set_out = []
        for drawing_set in sets:
            files = await set_files(session, drawing_set.id)
            facts = await file_facts(session, [f.file_id for f in files])
            checker = (
                await session.get(CheckerAppointment, drawing_set.checker_appointment_id)
                if drawing_set.checker_appointment_id
                else None
            )
            set_out.append(
                DrawingSetOut(
                    id=drawing_set.id, set_no=drawing_set.set_no, state=drawing_set.state,
                    content_hash=drawing_set.content_hash, submitted_at=drawing_set.submitted_at,
                    family_note=drawing_set.family_note,
                    checker_name=checker.name if checker else None,
                    checked_at=drawing_set.checked_at, check_note=drawing_set.check_note,
                    files=[
                        DrawingFileOut(
                            id=f.id, file_id=f.file_id, drawing_class=f.drawing_class,
                            floor=f.floor, title=f.title, sheet_no=f.sheet_no, sha256=f.sha256,
                            file_name=facts[f.file_id].file_name,
                            file_state=facts[f.file_id].state,
                        )
                        for f in files
                    ],
                )
            )  # fmt: skip
        out.append(
            DesignRequestOut(
                id=request.id, kind=request.kind, engagement_id=request.engagement_id,
                provider_name=request.provider_name,
                provider_qualification=request.provider_qualification,
                scope_note=request.scope_note,
                reference_design_ids=list(request.reference_design_ids),
                opened_at=request.opened_at,
                can_provide=await may_provide(session, request, who, profile_id=profile_id),
                sets=set_out,
            )
        )  # fmt: skip
    return out


def version_summary(version: BuildPlanVersion) -> VersionSummaryOut:
    return VersionSummaryOut(
        id=version.id, version_no=version.version_no, state=version.state,
        content_hash=version.content_hash, issued_at=version.issued_at,
        accepted_at=version.accepted_at, closed_at=version.closed_at,
        close_reason=version.close_reason, issued_document_id=version.issued_document_id,
        accepted_document_id=version.accepted_document_id,
    )  # fmt: skip


def file_out(summary: Any) -> FileOut:
    return FileOut(
        file_id=summary.file_id, file_name=summary.file_name,
        content_type=summary.content_type, size_bytes=summary.size_bytes, state=summary.state,
    )  # fmt: skip
