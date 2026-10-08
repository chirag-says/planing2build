"""Handover and Build Record routes for the homeowner (homeowner host) and the engaged contractor
(professionals host), Slice 3.7C. Owner and household read the handover and the Build Record
(EX-17); only the owner acknowledges, with a code (EX-21, EX-15). The contractor adds documents
and warranties while the handover is open and never reads the Build Record. No share link and no
transfer; downloads are signed-in and logged."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from p2b.construction.interface import Who, family_access, own_contractor_engagement
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import DbSession
from p2b.core.errors import NotFound
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.ratelimit import Limit, enforce
from p2b.core.vocabulary import (
    Audience,
    BuildRecordState,
    FilePurpose,
    HandoverState,
    MembershipRole,
    OtpPurpose,
)
from p2b.documents.interface import (
    complete_project_file_upload,
    create_project_file_upload,
    project_file_url,
)
from p2b.identity.interface import Actor, require_actor, start_confirmation
from p2b.projects.interface import member_role
from p2b.records import service
from p2b.records.models import BuildRecord
from p2b.records.schemas import (
    AcknowledgeIn,
    BuildRecordSnapshotOut,
    BuildRecordsOut,
    ChallengeOut,
    DocumentIn,
    DownloadOut,
    FileOut,
    HandoverOut,
    HandoverViewOut,
    UploadIn,
    UploadTicketOut,
    WarrantyIn,
)
from p2b.records.views import handover_out, records_out, snapshot_out

router = APIRouter(tags=["records"])

HOMEOWNER = require_actor(Audience.IHB)
PROFESSIONAL = require_actor(Audience.PRO)
UPLOAD_LIMIT = Limit("handover_uploads_session", 60, 60)  # T3


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _ip_hash(request: Request) -> str:
    settings = _settings(request)
    peer = request.client.host if request.client else None
    return keyed_hash(
        settings.identifier_pepper.get_secret_value(), client_ip(request.headers, peer)
    )


async def _once(
    db: DbSession, actor: Actor, key: str, body: Any, act: Callable[[], Awaitable[BaseModel]],
    code: int = 200,
) -> JSONResponse:  # fmt: skip
    async def action() -> tuple[int, dict[str, object]]:
        return code, (await act()).model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key, request_body=body, action=action
    )


# --- the homeowner -------------------------------------------------------------------------


async def _family_view(db: DbSession, actor: Actor, project_id: uuid.UUID) -> HandoverViewOut:
    await family_access(db, actor, project_id, write=False)
    membership = await member_role(db, user_id=actor.user_id, project_id=project_id)
    return HandoverViewOut(
        project_id=project_id,
        is_owner=membership is not None and membership.role == MembershipRole.OWNER,
        handover=await handover_out(db, await service.handover_of(db, project_id)),
    )


@router.get("/projects/{project_id}/handover", response_model=HandoverViewOut)
async def get_handover(
    project_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> HandoverViewOut:
    """The handover: documents, warranties, and whether the owner acknowledged it or Plan2Build
    issued it without acknowledgement."""
    return await _family_view(db, actor, project_id)


@router.get(
    "/projects/{project_id}/handover/documents/{document_id}/url", response_model=DownloadOut
)
async def get_handover_document(
    project_id: uuid.UUID, document_id: uuid.UUID, request: Request, db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> DownloadOut:  # fmt: skip
    await family_access(db, actor, project_id, write=False)
    row = await service.handover_of(db, project_id)
    document = next(
        (d for d in (await service.documents_of(db, row.id) if row else []) if d.id == document_id),
        None,
    )
    if document is None:
        raise NotFound
    url = await project_file_url(
        db, request.app.state.storage, project_id=project_id, file_id=document.file_id,
        purposes=frozenset({FilePurpose.HANDOVER_DOCUMENT}), viewer_user_id=actor.user_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)


@router.post("/projects/{project_id}/handover/acknowledgement-code", response_model=ChallengeOut)
async def post_acknowledgement_code(
    project_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> ChallengeOut:
    """Send a one-time code to the owner's email; the response carries the statement."""
    facts = await family_access(db, actor, project_id, write=True)
    row = await service.handover_of(db, project_id)
    if row is None or row.state != HandoverState.READY.value:
        raise service.conflict("NOT_READY", "The handover is not ready to acknowledge.")
    statement, text = await service.statement_text(db, facts)
    started = await start_confirmation(
        request.app.state.database, _settings(request), user_id=actor.user_id,
        audience=Audience.IHB, purpose=OtpPurpose.ACKNOWLEDGE_HANDOVER, subject_id=row.id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return ChallengeOut(
        challenge_id=started.challenge_id, sent_to=started.sent_to, expires_at=started.expires_at,
        statement_id=statement.id, statement_version=statement.version, statement_text=text,
    )  # fmt: skip


@router.post("/projects/{project_id}/handover/acknowledge", response_model=HandoverViewOut)
async def post_acknowledge(
    project_id: uuid.UUID, body: AcknowledgeIn, key: IdempotencyKeyHeader, request: Request,
    db: DbSession, actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:  # fmt: skip
    """Acknowledge with the code (EX-15). Free of the package (EX-18). 409 NOT_READY,
    STATEMENT_CHANGED."""

    async def act() -> HandoverViewOut:
        facts = await family_access(db, actor, project_id, write=True)
        await service.acknowledge(
            db, request.app.state.database, _settings(request), actor, facts,
            challenge_id=body.challenge_id, code=body.code, statement_id=body.statement_id,
            ip_hash=_ip_hash(request),
        )  # fmt: skip
        return await _family_view(db, actor, project_id)

    return await _once(db, actor, key, {"project": str(project_id),
                                        "challenge": str(body.challenge_id)}, act)  # fmt: skip


@router.get("/projects/{project_id}/build-record", response_model=BuildRecordsOut)
async def get_build_record(
    project_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> BuildRecordsOut:
    """Issued versions, newest last; superseded ones stay readable (EX-17)."""
    await family_access(db, actor, project_id, write=False)
    return await records_out(db, project_id, include_draft=False)


async def _issued(db: DbSession, project_id: uuid.UUID, version_no: int) -> BuildRecord:
    row = next(
        (r for r in await service.records_of(db, project_id) if r.version_no == version_no), None
    )
    if row is None or row.state == BuildRecordState.DRAFT.value:
        raise NotFound
    return row


@router.get(
    "/projects/{project_id}/build-record/versions/{version_no}",
    response_model=BuildRecordSnapshotOut,
)
async def get_build_record_version(
    project_id: uuid.UUID, version_no: int, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> BuildRecordSnapshotOut:
    await family_access(db, actor, project_id, write=False)
    return snapshot_out(await _issued(db, project_id, version_no))


@router.get(
    "/projects/{project_id}/build-record/versions/{version_no}/{form}/url",
    response_model=DownloadOut,
)
async def get_build_record_file(
    project_id: uuid.UUID, version_no: int, form: str, request: Request, db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> DownloadOut:  # fmt: skip
    """`form` is pdf or json (logged)."""
    await family_access(db, actor, project_id, write=False)
    row = await _issued(db, project_id, version_no)
    if form == "pdf" and row.pdf_file_id:
        file_id, purpose = row.pdf_file_id, FilePurpose.BUILD_RECORD_DOCUMENT
    elif form == "json" and row.json_file_id:
        file_id, purpose = row.json_file_id, FilePurpose.BUILD_RECORD_EXPORT
    else:
        raise NotFound
    url = await project_file_url(
        db, request.app.state.storage, project_id=project_id, file_id=file_id,
        purposes=frozenset({purpose}), viewer_user_id=actor.user_id, ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)


# --- the contractor ------------------------------------------------------------------------


def _professional(actor: Actor) -> Who:
    return Who(actor.user_id, "PROFESSIONAL", actor.session_id)


@router.get("/pro/engagements/{engagement_id}/handover", response_model=HandoverOut | None)
async def get_pro_handover(
    engagement_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> HandoverOut | None:
    engagement = await own_contractor_engagement(db, actor, engagement_id)
    return await handover_out(db, await service.handover_of(db, engagement.project_id))


@router.post(
    "/pro/engagements/{engagement_id}/handover/uploads",
    response_model=UploadTicketOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_handover_upload(
    engagement_id: uuid.UUID, body: UploadIn, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> UploadTicketOut:  # fmt: skip
    """A presigned upload of a handover document (PDF, JPG or PNG), scanned before use."""
    await enforce(request.app.state.database, UPLOAD_LIMIT, str(actor.session_id))
    engagement = await own_contractor_engagement(db, actor, engagement_id)
    summary, ticket = await create_project_file_upload(
        db, _settings(request), request.app.state.storage, uploader_user_id=actor.user_id,
        project_id=engagement.project_id, purpose=FilePurpose.HANDOVER_DOCUMENT,
        original_name=body.file_name, content_type=body.content_type, size_bytes=body.size_bytes,
    )  # fmt: skip
    return UploadTicketOut(
        file=FileOut(file_id=summary.file_id, file_name=summary.file_name,
                     content_type=summary.content_type, size_bytes=summary.size_bytes,
                     state=summary.state),
        upload_url=ticket.url, headers=ticket.headers,
    )  # fmt: skip


@router.post(
    "/pro/engagements/{engagement_id}/handover/uploads/{file_id}/complete", response_model=FileOut
)
async def post_handover_upload_complete(
    engagement_id: uuid.UUID, file_id: uuid.UUID, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> FileOut:  # fmt: skip
    await own_contractor_engagement(db, actor, engagement_id)
    summary = await complete_project_file_upload(
        db, request.app.state.storage, uploader_user_id=actor.user_id, file_id=file_id
    )
    return FileOut(file_id=summary.file_id, file_name=summary.file_name,
                   content_type=summary.content_type, size_bytes=summary.size_bytes,
                   state=summary.state)  # fmt: skip


@router.post(
    "/pro/engagements/{engagement_id}/handover/documents",
    response_model=HandoverOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": HandoverOut}},
)
async def post_pro_document(
    engagement_id: uuid.UUID, body: DocumentIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    """Add a handover document while the handover is open. 409 NOT_OPEN, DUPLICATE."""

    async def act() -> HandoverOut:
        engagement = await own_contractor_engagement(db, actor, engagement_id)
        await service.add_document(
            db, _professional(actor), engagement.project_id, kind=body.kind, title=body.title,
            file_id=body.file_id,
        )  # fmt: skip
        out = await handover_out(db, await service.handover_of(db, engagement.project_id))
        assert out is not None  # noqa: S101
        return out

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


@router.post(
    "/pro/engagements/{engagement_id}/handover/warranties",
    response_model=HandoverOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": HandoverOut}},
)
async def post_pro_warranty(
    engagement_id: uuid.UUID, body: WarrantyIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    async def act() -> HandoverOut:
        engagement = await own_contractor_engagement(db, actor, engagement_id)
        await service.add_warranty(db, _professional(actor), engagement.project_id,
                                   values=body.model_dump())  # fmt: skip
        out = await handover_out(db, await service.handover_of(db, engagement.project_id))
        assert out is not None  # noqa: S101
        return out

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)
