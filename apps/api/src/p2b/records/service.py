"""Handover and Build Record (Slice 3.7C; SLICE3_7_READINESS H, I, K, L, P.D, P.E).

Operations open the handover once Gate 6 is cleared and no finding is open (EX-15). The
contractor or operations record documents and warranties while it is OPEN; operations confirm it
READY. The owner acknowledges it with a one-time code against the ACTIVE statement version; if the
owner does not respond, operations may issue it with a reason, recorded as such and never as an
acknowledgement. Either way a DRAFT Build Record is assembled from the records (no manual
compilation, MVP P8). Operations issue it with the package active (EX-18): the snapshot is hashed,
a deterministic PDF and a JSON export are stored, and an earlier ISSUED version becomes
SUPERSEDED, still readable. A correction is a new version with a reason (EX-17)."""

import hashlib
import json
import uuid
from datetime import datetime
from string import Template
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.assurance.interface import assurance_summary, open_findings
from p2b.audit.interface import record
from p2b.billing.interface import package_active
from p2b.buildplan.interface import accepted_manifest
from p2b.catalog.interface import active_spec_masters
from p2b.construction.interface import (
    Who,
    contractor_of_record,
    execution_summary,
    gate_stages,
    open_project,
)
from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.errors import NotFound, PackageRequired, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.storage import Storage
from p2b.core.vocabulary import (
    BuildRecordBasis,
    BuildRecordState,
    EngagementParty,
    FilePurpose,
    FileState,
    GateStatus,
    HandoverDocumentKind,
    HandoverState,
    OtpPurpose,
)
from p2b.documents.interface import file_facts, store_generated_file
from p2b.engagements.interface import contractor_history
from p2b.identity.interface import Actor, verify_confirmation
from p2b.money.interface import marks_summary
from p2b.projects.interface import ConnectionFacts, connection_facts
from p2b.records.models import (
    AcknowledgementStatement,
    BuildRecord,
    Handover,
    HandoverDocument,
    RecordsEvent,
    Warranty,
)
from p2b.records.pdf import render_record

H = HandoverState
HANDOVER = TransitionTable[HandoverState](
    "handover",
    [
        Transition(None, H.OPEN, "open"),
        Transition(H.OPEN, H.READY, "ready"),
        Transition(H.READY, H.OPEN, "reopen"),
        Transition(H.READY, H.ACKNOWLEDGED, "acknowledge"),
        Transition(H.READY, H.ISSUED_BY_OPERATIONS, "issue_without_acknowledgement"),
    ],
)
B = BuildRecordState
BUILD_RECORD = TransitionTable[BuildRecordState](
    "build_record",
    [
        Transition(None, B.DRAFT, "assemble"),
        Transition(B.DRAFT, B.ISSUED, "issue"),
        Transition(B.ISSUED, B.SUPERSEDED, "supersede"),
    ],
)
CLOSED = (H.ACKNOWLEDGED.value, H.ISSUED_BY_OPERATIONS.value)
SCHEMA_VERSION = 1
NOT_RECORDED = "NOT RECORDED"
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


async def history(
    session: AsyncSession, *, subject: str, subject_id: uuid.UUID, project_id: uuid.UUID,
    old: str | None, new: str, who: Who, reason: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:  # fmt: skip
    session.add(
        RecordsEvent(
            id=new_id(), project_id=project_id, subject=subject, subject_id=subject_id,
            from_state=old, to_state=new, actor_user_id=who.user_id, actor_role=who.role,
            reason=reason, detail=detail,
        )
    )  # fmt: skip
    await session.flush()
    await record(
        session, action=f"{subject.lower()}.{new.lower()}", entity_type=subject.lower(),
        entity_id=subject_id, project_id=project_id, actor_type=who.actor_type,
        actor_user_id=who.user_id, actor_role=who.role, session_id=who.session_id,
        reason=reason, old_value={"state": old} if old else None,
        new_value={"state": new, **(detail or {})},
    )  # fmt: skip


class Notice(EventPayload):
    """Ids and a notice name only."""

    notice: str
    project_id: uuid.UUID


async def notify(
    session: AsyncSession, audience: str, notice: str, project_id: uuid.UUID, *, ref: str,
    aggregate_id: uuid.UUID | None = None,
) -> None:  # fmt: skip
    """`records.<audience>_notice`: family and ops carry the project, contractor the engagement."""
    await publish(
        session, event_type=f"records.{audience}_notice",
        aggregate_type="project_engagement" if audience == "contractor" else "project",
        aggregate_id=aggregate_id or project_id,
        payload=Notice(notice=notice, project_id=project_id), dedupe_suffix=f"{notice}:{ref}",
    )  # fmt: skip


async def _tell_contractor(session: AsyncSession, project_id: uuid.UUID, notice: str, ref: str) -> None:
    current = await contractor_of_record(session, project_id)
    if current is not None and current.party == EngagementParty.LISTED.value:
        await notify(session, "contractor", notice, project_id, ref=ref, aggregate_id=current.id)


# --- statements --------------------------------------------------------------------------------


async def active_statement(session: AsyncSession) -> AcknowledgementStatement:
    row = (
        await session.scalars(
            select(AcknowledgementStatement).where(AcknowledgementStatement.status == "ACTIVE")
        )
    ).one_or_none()
    if row is None:
        raise conflict("NO_STATEMENT", "No acknowledgement statement is active.")
    return row


async def statement_text(
    session: AsyncSession, facts: ConnectionFacts
) -> tuple[AcknowledgementStatement, str]:
    row = await active_statement(session)
    return row, Template(row.text).substitute(project_code=facts.code)


async def draft_statement(
    session: AsyncSession, user_id: uuid.UUID, text: str, note: str
) -> AcknowledgementStatement:
    try:
        Template(text).substitute(project_code="P2B-TEST")
    except (KeyError, ValueError):
        raise ValidationFailed(
            details={"fields": {"text": ["Use $project_code as the only placeholder."]}}
        ) from None
    number = (await session.scalar(select(func.max(AcknowledgementStatement.version)))) or 0
    row = AcknowledgementStatement(
        id=new_id(), version=number + 1, text=text, status="DRAFT", note=note, created_by=user_id
    )
    session.add(row)
    await session.flush()
    return row


async def activate_statement(
    session: AsyncSession, user_id: uuid.UUID, statement_id: uuid.UUID
) -> AcknowledgementStatement:
    row = await session.get(AcknowledgementStatement, statement_id, with_for_update=True)
    if row is None:
        raise NotFound
    if row.status != "DRAFT":
        raise conflict("NOT_DRAFT", "Only a draft statement is activated.")
    for current in await session.scalars(
        select(AcknowledgementStatement).where(AcknowledgementStatement.status == "ACTIVE")
    ):
        current.status = "RETIRED"
    await session.flush()
    row.status = "ACTIVE"
    row.activated_by = user_id
    row.activated_at = await db_now(session)
    await session.flush()
    return row


# --- handover ----------------------------------------------------------------------------------


async def handover_of(
    session: AsyncSession, project_id: uuid.UUID, *, lock: bool = False
) -> Handover | None:
    query = select(Handover).where(Handover.project_id == project_id)
    if lock:
        query = query.with_for_update()
    row = (await session.scalars(query)).one_or_none()
    if row is not None and lock:
        await session.refresh(row)
    return row


async def _move(
    session: AsyncSession, row: Handover, trigger: str, who: Who, *, reason: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:  # fmt: skip
    old = row.state
    row.state = HANDOVER.target(H(old), trigger).value
    row.version += 1
    await session.flush()
    await history(session, subject="HANDOVER", subject_id=row.id, project_id=row.project_id,
                  old=old, new=row.state, who=who, reason=reason, detail=detail)  # fmt: skip


async def open_handover(session: AsyncSession, who: Who, project_id: uuid.UUID) -> Handover:
    """409 reasons: GATE6_NOT_CLEARED, OPEN_FINDINGS, ALREADY_OPEN, PROJECT_CLOSED."""
    assert who.user_id is not None  # noqa: S101 (operations act)
    await open_project(session, project_id)
    if await handover_of(session, project_id) is not None:
        raise conflict("ALREADY_OPEN", "This project's handover is already open.")
    snag = [s for s in await gate_stages(session, project_id) if s.gate == 6]
    if not snag or any(s.gate_status != GateStatus.CLEARED for s in snag):
        raise conflict("GATE6_NOT_CLEARED", "The final snag gate (Gate 6) is not cleared.")
    if await open_findings(session, project_id):
        raise conflict("OPEN_FINDINGS", "Every finding must be closed by re-inspection first.")
    row = Handover(
        id=new_id(), project_id=project_id, state=HANDOVER.target(None, "open").value,
        opened_by=who.user_id,
    )  # fmt: skip
    session.add(row)
    await session.flush()
    await history(session, subject="HANDOVER", subject_id=row.id, project_id=project_id,
                  old=None, new=row.state, who=who)  # fmt: skip
    await notify(session, "family", "HANDOVER_OPENED", project_id, ref=str(row.id))
    await _tell_contractor(session, project_id, "HANDOVER_OPENED", str(row.id))
    return row


async def _open_row(session: AsyncSession, project_id: uuid.UUID) -> Handover:
    row = await handover_of(session, project_id, lock=True)
    if row is None:
        raise NotFound
    if row.state != H.OPEN.value:
        raise conflict("NOT_OPEN", "Documents change only while the handover is open.",
                       current_state=row.state)  # fmt: skip
    return row


async def add_document(
    session: AsyncSession, who: Who, project_id: uuid.UUID, *, kind: HandoverDocumentKind,
    title: str, file_id: uuid.UUID,
) -> HandoverDocument:  # fmt: skip
    assert who.user_id is not None  # noqa: S101
    row = await _open_row(session, project_id)
    fact = (await file_facts(session, [file_id])).get(file_id)
    if (
        fact is None
        or fact.project_id != project_id
        or fact.purpose != FilePurpose.HANDOVER_DOCUMENT
        or fact.state != FileState.AVAILABLE
    ):
        raise ValidationFailed(details={"fields": {"file_id": ["Upload the document first."]}})
    exists = await session.scalar(
        select(HandoverDocument.id).where(
            HandoverDocument.handover_id == row.id, HandoverDocument.file_id == file_id
        )
    )
    if exists is not None:
        raise conflict("DUPLICATE", "This file is already in the handover.")
    document = HandoverDocument(
        id=new_id(), handover_id=row.id, kind=kind.value, title=title, file_id=file_id,
        added_by=who.user_id, added_role=who.role,
    )  # fmt: skip
    session.add(document)
    await session.flush()
    await history(session, subject="HANDOVER", subject_id=row.id, project_id=project_id,
                  old=row.state, new=row.state, who=who,
                  detail={"document_added": str(document.id), "kind": kind.value})  # fmt: skip
    return document


async def remove_document(
    session: AsyncSession, who: Who, project_id: uuid.UUID, document_id: uuid.UUID
) -> None:
    row = await _open_row(session, project_id)
    document = await session.get(HandoverDocument, document_id)
    if document is None or document.handover_id != row.id:
        raise NotFound
    linked = await session.scalar(select(Warranty.id).where(Warranty.document_id == document.id))
    if linked is not None:
        raise conflict("HAS_WARRANTY", "Remove the warranty that names this document first.")
    await session.delete(document)
    await session.flush()
    await history(session, subject="HANDOVER", subject_id=row.id, project_id=project_id,
                  old=row.state, new=row.state, who=who,
                  detail={"document_removed": str(document_id)})  # fmt: skip


async def add_warranty(
    session: AsyncSession, who: Who, project_id: uuid.UUID, *, values: dict[str, Any]
) -> Warranty:
    """A warranty with its term, expiry and installer (MVP P8)."""
    assert who.user_id is not None  # noqa: S101
    row = await _open_row(session, project_id)
    document_id = values.get("document_id")
    if document_id is not None:
        document = await session.get(HandoverDocument, document_id)
        if document is None or document.handover_id != row.id:
            raise ValidationFailed(details={"fields": {"document_id": ["Not in this handover."]}})
    warranty = Warranty(id=new_id(), handover_id=row.id, added_by=who.user_id, **values)
    session.add(warranty)
    await session.flush()
    await history(session, subject="HANDOVER", subject_id=row.id, project_id=project_id,
                  old=row.state, new=row.state, who=who,
                  detail={"warranty_added": str(warranty.id)})  # fmt: skip
    return warranty


async def documents_of(session: AsyncSession, handover_id: uuid.UUID) -> list[HandoverDocument]:
    return list(
        await session.scalars(
            select(HandoverDocument)
            .where(HandoverDocument.handover_id == handover_id)
            .order_by(HandoverDocument.added_at, HandoverDocument.id)
        )
    )


async def warranties_of(session: AsyncSession, handover_id: uuid.UUID) -> list[Warranty]:
    return list(
        await session.scalars(
            select(Warranty)
            .where(Warranty.handover_id == handover_id)
            .order_by(Warranty.added_at, Warranty.id)
        )
    )


async def ready(session: AsyncSession, who: Who, project_id: uuid.UUID) -> Handover:
    """Operations confirm the required documents are recorded (EX-15). 409 NO_DOCUMENTS,
    WARRANTY_MISSING (a warranty document without its warranty entry)."""
    row = await _open_row(session, project_id)
    documents = await documents_of(session, row.id)
    if not documents:
        raise conflict("NO_DOCUMENTS", "Record the handover documents first.")
    linked = {w.document_id for w in await warranties_of(session, row.id)}
    missing = [d.title for d in documents
               if d.kind == HandoverDocumentKind.WARRANTY.value and d.id not in linked]  # fmt: skip
    if missing:
        raise conflict("WARRANTY_MISSING", "Record the term, expiry and installer of each "
                       "warranty document.", documents=missing)  # fmt: skip
    row.ready_by = who.user_id
    row.ready_at = await db_now(session)
    await _move(session, row, "ready", who)
    await notify(session, "family", "HANDOVER_READY", project_id, ref=f"{row.id}:{row.version}")
    return row


async def reopen(session: AsyncSession, who: Who, project_id: uuid.UUID, reason: str) -> Handover:
    row = await handover_of(session, project_id, lock=True)
    if row is None:
        raise NotFound
    if row.state != H.READY.value:
        raise conflict("NOT_READY", "Only a ready handover is reopened.", current_state=row.state)
    row.ready_by = None
    row.ready_at = None
    await _move(session, row, "reopen", who, reason=reason)
    return row


async def acknowledge(
    session: AsyncSession, database: Database, settings: Settings, actor: Actor,
    facts: ConnectionFacts, *, challenge_id: uuid.UUID, code: str, statement_id: uuid.UUID,
    ip_hash: str,
) -> Handover:  # fmt: skip
    """The owner, with the code and the ACTIVE statement version (EX-15). A DRAFT Build Record
    follows. 409 NOT_READY, STATEMENT_CHANGED."""
    row = await handover_of(session, facts.project_id, lock=True)
    if row is None:
        raise NotFound
    if row.state != H.READY.value:
        raise conflict("NOT_READY", "The handover is not ready to acknowledge.",
                       current_state=row.state)  # fmt: skip
    statement, text = await statement_text(session, facts)
    if statement.id != statement_id:
        raise conflict("STATEMENT_CHANGED", "The statement changed; read it again.")
    await verify_confirmation(
        database, settings, challenge_id=challenge_id, code=code, user_id=actor.user_id,
        purpose=OtpPurpose.ACKNOWLEDGE_HANDOVER, subject_id=row.id, ip_hash=ip_hash,
    )  # fmt: skip
    who = Who(actor.user_id, "FAMILY", actor.session_id)
    row.acknowledged_by = actor.user_id
    row.acknowledged_at = await db_now(session)
    row.challenge_id = challenge_id
    row.statement_id = statement.id
    row.statement_text = text
    await _move(session, row, "acknowledge", who, detail={"statement_version": statement.version})
    await notify(session, "ops", "HANDOVER_ACKNOWLEDGED", facts.project_id, ref=str(row.id))
    await _tell_contractor(session, facts.project_id, "HANDOVER_ACKNOWLEDGED", str(row.id))
    await assemble(session, SYSTEM, facts.project_id)
    return row


async def issue_without_acknowledgement(
    session: AsyncSession, who: Who, project_id: uuid.UUID, reason: str
) -> Handover:
    """EX-15: the owner did not respond; operations issue the handover record with a reason. It
    is recorded as an operations issue, never as the owner's acknowledgement."""
    row = await handover_of(session, project_id, lock=True)
    if row is None:
        raise NotFound
    if row.state != H.READY.value:
        raise conflict("NOT_READY", "Only a ready handover is issued.", current_state=row.state)
    row.forced_by = who.user_id
    row.forced_at = await db_now(session)
    row.forced_reason = reason
    await _move(session, row, "issue_without_acknowledgement", who, reason=reason)
    await assemble(session, who, project_id)
    return row


# --- the Build Record ----------------------------------------------------------------------------


async def snapshot(session: AsyncSession, project_id: uuid.UUID, row: Handover) -> dict[str, Any]:
    """The authoritative content (I.1), assembled from the records. No quote price, no amount;
    product, purchase and installation are NOT RECORDED (EX-16)."""
    facts = await connection_facts(session, project_id)
    if facts is None:
        raise NotFound
    baseline = await accepted_manifest(session, project_id)
    manifest = baseline.manifest if baseline else {}
    values = {str(v["code"]): v for v in manifest.get("specifications", [])}
    assurance = await assurance_summary(session, project_id)
    line_results = assurance["line_results"]
    assert isinstance(line_results, dict)  # noqa: S101
    documents = await documents_of(session, row.id)
    files = await file_facts(session, [d.file_id for d in documents])
    return {
        "schema_version": SCHEMA_VERSION,
        "identity": {"project_code": facts.code, "locality": facts.locality},
        "plan": {
            "build_plan_version_no": baseline.version_no if baseline else None,
            "content_hash": baseline.content_hash if baseline else None,
            "accepted_at": manifest.get("accepted_at"),
        },
        "drawings": [
            {k: d.get(k) for k in ("file_id", "drawing_class", "floor", "title", "sheet_no",
                                   "sha256")}
            for d in manifest.get("drawings", [])
        ],  # fmt: skip
        "specification": [
            {
                "code": m.code, "item": m.item,
                "accepted_value": values.get(m.code, {}).get("value"),
                "applicability": values.get(m.code, {}).get("applicability"),
                "verification": line_results.get(m.code, []),
                "product": NOT_RECORDED, "purchase": NOT_RECORDED, "installation": NOT_RECORDED,
            }
            for m in await active_spec_masters(session)
        ],  # fmt: skip
        "contractors": await contractor_history(session, project_id),
        "execution": await execution_summary(session, project_id),
        "assurance": {"inspections": assurance["inspections"], "findings": assurance["findings"]},
        "payment_marks": await marks_summary(session, project_id),
        "handover": {
            "state": row.state,
            "opened_at": row.opened_at.isoformat(),
            "documents": [
                {"kind": d.kind, "title": d.title, "file_id": str(d.file_id),
                 "sha256": files[d.file_id].sha256 if d.file_id in files else None}
                for d in documents
            ],
            "warranties": [
                {"item": w.item, "term": w.term, "expiry_date": w.expiry_date.isoformat(),
                 "installer": w.installer, "spec_line_code": w.spec_line_code}
                for w in await warranties_of(session, row.id)
            ],
            "acknowledgement": {
                "acknowledged_at": row.acknowledged_at.isoformat(),
                "statement_text": row.statement_text,
            } if row.state == H.ACKNOWLEDGED.value and row.acknowledged_at else None,
            "issued_without_acknowledgement": {
                "issued_at": row.forced_at.isoformat(), "reason": row.forced_reason,
            } if row.state == H.ISSUED_BY_OPERATIONS.value and row.forced_at else None,
        },  # fmt: skip
    }


async def records_of(session: AsyncSession, project_id: uuid.UUID) -> list[BuildRecord]:
    return list(
        await session.scalars(
            select(BuildRecord)
            .where(BuildRecord.project_id == project_id)
            .order_by(BuildRecord.version_no)
        )
    )


async def assemble(
    session: AsyncSession, who: Who, project_id: uuid.UUID, *, reason: str | None = None
) -> BuildRecord:
    """The DRAFT version from the records: re-assembled when one exists; a new version after an
    issued one needs a correction reason. 409 NO_HANDOVER, REASON_REQUIRED."""
    row = await handover_of(session, project_id)
    if row is None or row.state not in CLOSED:
        raise conflict("NO_HANDOVER", "The handover is not acknowledged or issued yet.")
    existing = await records_of(session, project_id)
    content = await snapshot(session, project_id, row)
    draft = next((r for r in existing if r.state == B.DRAFT.value), None)
    if draft is not None:
        draft.snapshot = content
        draft.version += 1
        await session.flush()
        await history(session, subject="BUILD_RECORD", subject_id=draft.id,
                      project_id=project_id, old=draft.state, new=draft.state, who=who,
                      detail={"reassembled": True})  # fmt: skip
        return draft
    version_no = (max((r.version_no for r in existing), default=0)) + 1
    if version_no > 1 and not reason:
        raise conflict("REASON_REQUIRED", "A new version corrects an issued one: give the reason.")
    basis = (
        BuildRecordBasis.ACKNOWLEDGED if row.state == H.ACKNOWLEDGED.value
        else BuildRecordBasis.ISSUED_BY_OPERATIONS
    )  # fmt: skip
    record_row = BuildRecord(
        id=new_id(), project_id=project_id, handover_id=row.id, version_no=version_no,
        state=BUILD_RECORD.target(None, "assemble").value, basis=basis.value, snapshot=content,
        correction_reason=reason if version_no > 1 else None, assembled_by_role=who.role,
    )  # fmt: skip
    session.add(record_row)
    await session.flush()
    await history(session, subject="BUILD_RECORD", subject_id=record_row.id,
                  project_id=project_id, old=None, new=record_row.state, who=who, reason=reason,
                  detail={"version_no": version_no, "basis": basis.value})  # fmt: skip
    await notify(session, "ops", "BUILD_RECORD_DRAFT", project_id, ref=str(record_row.id))
    return record_row


def export_document(row: BuildRecord, issued_at: datetime, digest: str) -> dict[str, Any]:
    """The JSON export: the snapshot with its version, issue time and hash."""
    return {"build_record_version": row.version_no, "issued_at": issued_at.isoformat(),
            "basis": row.basis, "correction_reason": row.correction_reason,
            "snapshot_sha256": digest, "snapshot": row.snapshot}  # fmt: skip


async def issue(
    session: AsyncSession, settings: Settings, storage: Storage, who: Who, record_id: uuid.UUID
) -> BuildRecord:
    """Freeze the DRAFT (EX-17): hash, PDF, JSON; the previous ISSUED version is SUPERSEDED.
    Needs the package (EX-18). 409 NOT_DRAFT; or PACKAGE_REQUIRED."""
    assert who.user_id is not None  # noqa: S101
    row = await session.get(BuildRecord, record_id, with_for_update=True)
    if row is None:
        raise NotFound
    await session.refresh(row)
    if row.state != B.DRAFT.value:
        raise conflict("NOT_DRAFT", "Only a draft is issued.", current_state=row.state)
    if not await package_active(session, row.project_id):
        raise PackageRequired
    issued_at = await db_now(session)
    digest = sha256(row.snapshot)
    pdf = render_record(settings, row.snapshot, version_no=row.version_no, issued_at=issued_at,
                        digest=digest, basis=row.basis,
                        correction_reason=row.correction_reason)  # fmt: skip
    export = canonical(export_document(row, issued_at, digest)).encode()
    code = row.snapshot["identity"]["project_code"]
    pdf_id = await store_generated_file(
        session, settings, storage, project_id=row.project_id, owner_user_id=who.user_id,
        purpose=FilePurpose.BUILD_RECORD_DOCUMENT, data=pdf, mime="application/pdf",
        file_name=f"build-record-{code}-v{row.version_no}.pdf",
    )  # fmt: skip
    json_id = await store_generated_file(
        session, settings, storage, project_id=row.project_id, owner_user_id=who.user_id,
        purpose=FilePurpose.BUILD_RECORD_EXPORT, data=export, mime="application/json",
        file_name=f"build-record-{code}-v{row.version_no}.json",
    )  # fmt: skip
    for earlier in await records_of(session, row.project_id):
        if earlier.state == B.ISSUED.value:
            earlier.state = BUILD_RECORD.target(B.ISSUED, "supersede").value
            earlier.version += 1
            await session.flush()
            await history(session, subject="BUILD_RECORD", subject_id=earlier.id,
                          project_id=row.project_id, old=B.ISSUED.value, new=earlier.state,
                          who=who, detail={"superseded_by": row.version_no})  # fmt: skip
    row.snapshot_sha256 = digest
    row.pdf_file_id = pdf_id
    row.pdf_sha256 = hashlib.sha256(pdf).hexdigest()
    row.json_file_id = json_id
    row.json_sha256 = hashlib.sha256(export).hexdigest()
    row.issued_by = who.user_id
    row.issued_at = issued_at
    old = row.state
    row.state = BUILD_RECORD.target(B(old), "issue").value
    row.version += 1
    await session.flush()
    await history(session, subject="BUILD_RECORD", subject_id=row.id, project_id=row.project_id,
                  old=old, new=row.state, who=who,
                  detail={"version_no": row.version_no, "snapshot_sha256": digest})  # fmt: skip
    await notify(session, "family", "BUILD_RECORD_ISSUED", row.project_id, ref=str(row.id))
    return row
