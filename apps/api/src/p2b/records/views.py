"""Read models for the handover and the Build Record (Slice 3.7C)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.vocabulary import (
    BuildRecordBasis,
    BuildRecordState,
    HandoverDocumentKind,
    HandoverState,
)
from p2b.records import service
from p2b.records.models import BuildRecord, Handover
from p2b.records.schemas import (
    BuildRecordSnapshotOut,
    BuildRecordsOut,
    BuildRecordVersionOut,
    HandoverDocumentOut,
    HandoverOut,
    WarrantyOut,
)


async def handover_out(session: AsyncSession, row: Handover | None) -> HandoverOut | None:
    if row is None:
        return None
    forced = row.state == HandoverState.ISSUED_BY_OPERATIONS.value
    return HandoverOut(
        id=row.id, state=HandoverState(row.state), opened_at=row.opened_at, ready_at=row.ready_at,
        documents=[
            HandoverDocumentOut(id=d.id, kind=HandoverDocumentKind(d.kind), title=d.title,
                        file_id=d.file_id, added_role=d.added_role, added_at=d.added_at)
            for d in await service.documents_of(session, row.id)
        ],
        warranties=[
            WarrantyOut(id=w.id, item=w.item, term=w.term, expiry_date=w.expiry_date,
                        installer=w.installer, spec_line_code=w.spec_line_code,
                        document_id=w.document_id)
            for w in await service.warranties_of(session, row.id)
        ],
        acknowledged_at=row.acknowledged_at, statement_text=row.statement_text,
        issued_without_acknowledgement=forced, issued_at=row.forced_at if forced else None,
        issue_reason=row.forced_reason if forced else None,
    )  # fmt: skip


def version_out(row: BuildRecord) -> BuildRecordVersionOut:
    return BuildRecordVersionOut(
        id=row.id, version_no=row.version_no, state=BuildRecordState(row.state),
        basis=BuildRecordBasis(row.basis), correction_reason=row.correction_reason,
        snapshot_sha256=row.snapshot_sha256, pdf_sha256=row.pdf_sha256,
        json_sha256=row.json_sha256, issued_at=row.issued_at,
    )  # fmt: skip


async def records_out(
    session: AsyncSession, project_id: uuid.UUID, *, include_draft: bool
) -> BuildRecordsOut:
    rows = await service.records_of(session, project_id)
    return BuildRecordsOut(
        project_id=project_id,
        versions=[
            version_out(r) for r in rows if include_draft or r.state != BuildRecordState.DRAFT.value
        ],
    )


def snapshot_out(row: BuildRecord) -> BuildRecordSnapshotOut:
    return BuildRecordSnapshotOut(**version_out(row).model_dump(), snapshot=row.snapshot)
