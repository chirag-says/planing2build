"""Operations and ADMIN routes for the handover and the Build Record (admin host; staff role and
MFA), Slice 3.7C. Operations open the handover, record documents and warranties, confirm it
ready, reopen it with a reason, issue it without the owner's acknowledgement with a reason
(EX-15), assemble and issue Build Record versions (EX-17; issue needs the package, EX-18). ADMIN
activates acknowledgement statements."""

import hashlib
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from p2b.construction.interface import Who, open_project
from p2b.core.config import Settings
from p2b.core.db import DbSession
from p2b.core.errors import NotFound, ValidationFailed
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.vocabulary import Audience, FilePurpose, StaffRole
from p2b.documents.interface import store_staff_upload
from p2b.identity.interface import Actor, active_roles, require_actor
from p2b.projects.interface import connection_facts
from p2b.records import service
from p2b.records.models import AcknowledgementStatement, BuildRecord
from p2b.records.schemas import (
    AssembleIn,
    BuildRecordsOut,
    BuildRecordSnapshotOut,
    DocumentIn,
    FileOut,
    HandoverOut,
    ReasonIn,
    WarrantyIn,
)
from p2b.records.views import handover_out, records_out, snapshot_out

router = APIRouter(tags=["records-operations"])

STAFF = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.OPS, StaffRole.ADMIN))
ADMIN = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.ADMIN,))
MAX_STAFF_UPLOAD = 20 * 1024 * 1024


class OpsHandoverOut(BaseModel):
    project_id: uuid.UUID
    project_code: str
    handover: HandoverOut | None
    build_records: BuildRecordsOut


class StatementOut(BaseModel):
    id: uuid.UUID
    version: int
    status: str
    text: str
    note: str


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def _who(db: DbSession, actor: Actor) -> Who:
    roles = await active_roles(db, actor.user_id)
    role = StaffRole.ADMIN.value if StaffRole.ADMIN in roles else StaffRole.OPS.value
    return Who(actor.user_id, role, actor.session_id)


async def _once(
    db: DbSession, actor: Actor, key: str, body: Any, act: Callable[[], Awaitable[BaseModel]],
    code: int = 200,
) -> JSONResponse:  # fmt: skip
    async def action() -> tuple[int, dict[str, object]]:
        return code, (await act()).model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key, request_body=body, action=action
    )


async def _view(db: DbSession, project_id: uuid.UUID) -> OpsHandoverOut:
    facts = await connection_facts(db, project_id)
    if facts is None:
        raise NotFound
    return OpsHandoverOut(
        project_id=project_id, project_code=facts.code,
        handover=await handover_out(db, await service.handover_of(db, project_id)),
        build_records=await records_out(db, project_id, include_draft=True),
    )  # fmt: skip


@router.get("/ops/projects/{project_id}/handover", response_model=OpsHandoverOut)
async def get_handover(
    project_id: uuid.UUID, db: DbSession, _: Annotated[Actor, STAFF]
) -> OpsHandoverOut:
    return await _view(db, project_id)


@router.post("/ops/projects/{project_id}/handover", response_model=OpsHandoverOut)
async def post_open(
    project_id: uuid.UUID, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Open the handover (EX-15). 409 GATE6_NOT_CLEARED, OPEN_FINDINGS, ALREADY_OPEN."""

    async def act() -> OpsHandoverOut:
        await service.open_handover(db, await _who(db, actor), project_id)
        return await _view(db, project_id)

    return await _once(db, actor, key, {"project": str(project_id), "step": "open"}, act)


@router.post("/ops/projects/{project_id}/handover/documents", response_model=OpsHandoverOut)
async def post_document(
    project_id: uuid.UUID, body: DocumentIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    async def act() -> OpsHandoverOut:
        await service.add_document(db, await _who(db, actor), project_id, kind=body.kind,
                                   title=body.title, file_id=body.file_id)  # fmt: skip
        return await _view(db, project_id)

    return await _once(db, actor, key, {"project": str(project_id),
                                        **body.model_dump(mode="json")}, act)  # fmt: skip


@router.post("/ops/projects/{project_id}/handover/warranties", response_model=OpsHandoverOut)
async def post_warranty(
    project_id: uuid.UUID, body: WarrantyIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    async def act() -> OpsHandoverOut:
        await service.add_warranty(db, await _who(db, actor), project_id,
                                   values=body.model_dump())  # fmt: skip
        return await _view(db, project_id)

    return await _once(db, actor, key, {"project": str(project_id),
                                        **body.model_dump(mode="json")}, act)  # fmt: skip


@router.post("/ops/projects/{project_id}/handover/ready", response_model=OpsHandoverOut)
async def post_ready(
    project_id: uuid.UUID, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Confirm the required documents are recorded. 409 NO_DOCUMENTS, WARRANTY_MISSING."""

    async def act() -> OpsHandoverOut:
        await service.ready(db, await _who(db, actor), project_id)
        return await _view(db, project_id)

    return await _once(db, actor, key, {"project": str(project_id), "step": "ready"}, act)


@router.post("/ops/projects/{project_id}/handover/reopen", response_model=OpsHandoverOut)
async def post_reopen(
    project_id: uuid.UUID, body: ReasonIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    async def act() -> OpsHandoverOut:
        await service.reopen(db, await _who(db, actor), project_id, body.reason)
        return await _view(db, project_id)

    return await _once(db, actor, key, {"project": str(project_id), "step": "reopen",
                                        **body.model_dump()}, act)  # fmt: skip


@router.post(
    "/ops/projects/{project_id}/handover/issue-without-acknowledgement",
    response_model=OpsHandoverOut,
)
async def post_issue_without_acknowledgement(
    project_id: uuid.UUID, body: ReasonIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """The owner did not respond: issue with a reason, recorded as an operations issue and never
    as the owner's acknowledgement (EX-15). 409 NOT_READY."""

    async def act() -> OpsHandoverOut:
        await service.issue_without_acknowledgement(db, await _who(db, actor), project_id,
                                                    body.reason)  # fmt: skip
        return await _view(db, project_id)

    return await _once(db, actor, key, {"project": str(project_id), "step": "issue",
                                        **body.model_dump()}, act)  # fmt: skip


@router.post(
    "/ops/projects/{project_id}/handover/documents/{document_id}/remove",
    response_model=OpsHandoverOut,
)
async def post_remove_document(
    project_id: uuid.UUID, document_id: uuid.UUID, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    async def act() -> OpsHandoverOut:
        await service.remove_document(db, await _who(db, actor), project_id, document_id)
        return await _view(db, project_id)

    return await _once(db, actor, key, {"document": str(document_id)}, act)


@router.post(
    "/ops/projects/{project_id}/handover-files",
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                t: {"schema": {"type": "string", "format": "binary"}}
                for t in ("application/pdf", "image/jpeg", "image/png")
            },
        }
    },
)
async def post_handover_file(
    project_id: uuid.UUID,
    file_name: Annotated[str, Query(min_length=1, max_length=200)],
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    """A handover document received outside the portal (raw body), scanned before use."""
    await open_project(db, project_id)
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip()
    if int(request.headers.get("content-length") or 0) > MAX_STAFF_UPLOAD:
        raise ValidationFailed(details={"fields": {"file": ["The file is too large."]}})
    data = await request.body()

    async def act() -> FileOut:
        summary = await store_staff_upload(
            db, _settings(request), request.app.state.storage, uploader_user_id=actor.user_id,
            project_id=project_id, purpose=FilePurpose.HANDOVER_DOCUMENT,
            original_name=file_name, content_type=content_type, data=data,
        )  # fmt: skip
        return FileOut(file_id=summary.file_id, file_name=summary.file_name,
                       content_type=summary.content_type, size_bytes=summary.size_bytes,
                       state=summary.state)  # fmt: skip

    body = {"project": str(project_id), "name": file_name,
            "sha256": hashlib.sha256(data).hexdigest()}  # fmt: skip
    return await _once(db, actor, key, body, act, 201)


@router.post("/ops/projects/{project_id}/build-record/assemble", response_model=OpsHandoverOut)
async def post_assemble(
    project_id: uuid.UUID, body: AssembleIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Re-assemble the DRAFT from the records, or start a corrected version after an issued one
    (a reason is required). 409 NO_HANDOVER, REASON_REQUIRED."""

    async def act() -> OpsHandoverOut:
        await service.assemble(db, await _who(db, actor), project_id, reason=body.reason)
        return await _view(db, project_id)

    return await _once(db, actor, key, {"project": str(project_id), **body.model_dump()}, act)


@router.post("/ops/build-records/{record_id}/issue", response_model=OpsHandoverOut)
async def post_issue(
    record_id: uuid.UUID, key: IdempotencyKeyHeader, request: Request, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Issue the DRAFT: snapshot hash, PDF and JSON; the previous version is SUPERSEDED. 409
    NOT_DRAFT; or PACKAGE_REQUIRED."""

    async def act() -> OpsHandoverOut:
        row = await service.issue(db, _settings(request), request.app.state.storage,
                                  await _who(db, actor), record_id)  # fmt: skip
        return await _view(db, row.project_id)

    return await _once(db, actor, key, {"record": str(record_id)}, act)


@router.get("/ops/build-records/{record_id}", response_model=BuildRecordSnapshotOut)
async def get_record(
    record_id: uuid.UUID, db: DbSession, _: Annotated[Actor, STAFF]
) -> BuildRecordSnapshotOut:
    row = await db.get(BuildRecord, record_id)
    if row is None:
        raise NotFound
    return snapshot_out(row)


class StatementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, Field(min_length=20, max_length=4000)]
    note: Annotated[str, Field(min_length=1, max_length=1000)]


@router.post(
    "/admin/acknowledgement-statements",
    response_model=StatementOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": StatementOut}},
)
async def post_statement(
    body: StatementIn, key: IdempotencyKeyHeader, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> JSONResponse:
    """A DRAFT statement version; `$project_code` is the only placeholder."""

    async def act() -> StatementOut:
        row = await service.draft_statement(db, actor.user_id, body.text, body.note)
        return StatementOut(id=row.id, version=row.version, status=row.status, text=row.text,
                            note=row.note)  # fmt: skip

    return await _once(db, actor, key, body.model_dump(), act, 201)


@router.post(
    "/admin/acknowledgement-statements/{statement_id}/activate", response_model=StatementOut
)
async def post_activate_statement(
    statement_id: uuid.UUID, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, ADMIN],
) -> JSONResponse:  # fmt: skip
    """The DRAFT becomes ACTIVE; the previous ACTIVE one is RETIRED."""

    async def act() -> StatementOut:
        row = await service.activate_statement(db, actor.user_id, statement_id)
        return StatementOut(id=row.id, version=row.version, status=row.status, text=row.text,
                            note=row.note)  # fmt: skip

    return await _once(db, actor, key, {"statement": str(statement_id)}, act)


@router.get("/ops/acknowledgement-statements", response_model=list[StatementOut])
async def get_statements(db: DbSession, _: Annotated[Actor, STAFF]) -> list[StatementOut]:
    rows = await db.scalars(
        select(AcknowledgementStatement).order_by(AcknowledgementStatement.version)
    )
    return [StatementOut(id=r.id, version=r.version, status=r.status, text=r.text, note=r.note)
            for r in rows]  # fmt: skip
