"""Execution routes for the homeowner (homeowner host) and the engaged contractor (professionals
host), Slice 3.7A. Transition POSTs take an `Idempotency-Key`. The owner and household read; only
the owner confirms or returns (EX-21). The contractor reaches only its ACTIVE CONTRACTOR
engagement and sees only its own updates; every other id is 404 (SECURITY 4.2). Execution is
free: no route here needs a package (EX-18). Evidence links are signed-in and logged."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from p2b.buildplan.interface import accepted_manifest
from p2b.construction import execution
from p2b.construction.schemas import (
    DecisionIn,
    DownloadOut,
    DrawingOut,
    EvidenceUploadIn,
    FamilyExecutionOut,
    FileOut,
    ProExecutionOut,
    ReasonDecisionIn,
    UpdateIn,
    UpdatesOut,
    UploadTicketOut,
)
from p2b.construction.service import Who
from p2b.construction.views import contractor_out, one_stage_out, stages_out, updates_out
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import DbSession
from p2b.core.errors import NotFound
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.ratelimit import Limit, enforce
from p2b.core.vocabulary import Audience, FilePurpose, MembershipRole
from p2b.documents.interface import (
    complete_project_file_upload,
    create_project_file_upload,
    project_file_url,
)
from p2b.engagements.interface import EngagementFacts
from p2b.identity.interface import Actor, require_actor
from p2b.projects.interface import member_role

router = APIRouter(tags=["execution"])

HOMEOWNER = require_actor(Audience.IHB)
PROFESSIONAL = require_actor(Audience.PRO)
UPDATE_LIMIT = Limit("stage_updates_session", 60, 600)  # T2
UPLOAD_LIMIT = Limit("stage_evidence_session", 60, 60)  # T3


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


def _family(actor: Actor) -> Who:
    return Who(actor.user_id, "FAMILY", actor.session_id)


def _professional(actor: Actor) -> Who:
    return Who(actor.user_id, "PROFESSIONAL", actor.session_id)


# --- the homeowner -------------------------------------------------------------------------


async def _family_view(db: DbSession, actor: Actor, project_id: uuid.UUID) -> FamilyExecutionOut:
    await execution.family_access(db, actor, project_id, write=False)
    membership = await member_role(db, user_id=actor.user_id, project_id=project_id)
    return FamilyExecutionOut(
        project_id=project_id,
        is_owner=membership is not None and membership.role == MembershipRole.OWNER,
        contractor=await contractor_out(db, project_id),
        stages=await stages_out(db, project_id),
    )


@router.get("/projects/{project_id}/execution", response_model=FamilyExecutionOut)
async def get_execution(
    project_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> FamilyExecutionOut:
    """Stages with what happened on them: state, actual dates, update counts, gate status and
    payment milestones. No planned dates, percentages or delays (EX-04)."""
    return await _family_view(db, actor, project_id)


@router.get("/projects/{project_id}/stages/{stage_id}/updates", response_model=UpdatesOut)
async def get_stage_updates(
    project_id: uuid.UUID, stage_id: uuid.UUID, db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> UpdatesOut:  # fmt: skip
    """Every update on the stage, newest first, with the contractor who posted it."""
    await execution.family_access(db, actor, project_id, write=False)
    stage = await execution.stage_row(db, stage_id)
    if stage.project_id != project_id:
        raise NotFound
    return UpdatesOut(
        stage=await one_stage_out(db, stage),
        updates=await updates_out(db, await execution.updates_of(db, stage.id)),
    )


@router.get(
    "/projects/{project_id}/stages/{stage_id}/files/{file_id}/url", response_model=DownloadOut
)
async def get_stage_file(
    project_id: uuid.UUID, stage_id: uuid.UUID, file_id: uuid.UUID, request: Request,
    db: DbSession, actor: Annotated[Actor, HOMEOWNER],
) -> DownloadOut:  # fmt: skip
    """A photo of an update on this stage (logged)."""
    await execution.family_access(db, actor, project_id, write=False)
    stage = await execution.stage_row(db, stage_id)
    if stage.project_id != project_id or not any(
        file_id in u.file_ids for u in await execution.updates_of(db, stage.id)
    ):
        raise NotFound
    url = await project_file_url(
        db, request.app.state.storage, project_id=project_id, file_id=file_id,
        purposes=frozenset({FilePurpose.STAGE_EVIDENCE}), viewer_user_id=actor.user_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)


@router.post("/projects/{project_id}/stages/{stage_id}/confirm", response_model=FamilyExecutionOut)
async def post_confirm(
    project_id: uuid.UUID, stage_id: uuid.UUID, body: DecisionIn, key: IdempotencyKeyHeader,
    db: DbSession, actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:  # fmt: skip
    """Confirm the contractor's completion request (EX-03). 409 `details.reason`:
    GATE_NOT_CLEARED (the stage's inspection gate is not cleared), STALE, PROJECT_CLOSED; or
    STATE_CONFLICT when no completion is requested."""

    async def act() -> FamilyExecutionOut:
        await execution.family_access(db, actor, project_id, write=True)
        await execution.confirm(
            db, _family(actor), stage_id, project_id, version=body.version, reason=None
        )
        return await _family_view(db, actor, project_id)

    return await _once(db, actor, key, {"stage": str(stage_id), **body.model_dump()}, act)


@router.post("/projects/{project_id}/stages/{stage_id}/return", response_model=FamilyExecutionOut)
async def post_return(
    project_id: uuid.UUID, stage_id: uuid.UUID, body: ReasonDecisionIn,
    key: IdempotencyKeyHeader, db: DbSession, actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:  # fmt: skip
    """Return the completion request with a reason; the stage goes back to in progress."""

    async def act() -> FamilyExecutionOut:
        await execution.family_access(db, actor, project_id, write=True)
        await execution.return_stage(
            db, _family(actor), stage_id, project_id, version=body.version, reason=body.reason
        )
        return await _family_view(db, actor, project_id)

    return await _once(db, actor, key, {"stage": str(stage_id), **body.model_dump()}, act)


# --- the contractor ------------------------------------------------------------------------


async def _pro_view(db: DbSession, engagement: EngagementFacts) -> ProExecutionOut:
    facts = await execution.project_facts(db, engagement.project_id)
    baseline = await accepted_manifest(db, engagement.project_id)
    drawings = [
        DrawingOut(
            file_id=uuid.UUID(str(d["file_id"])),
            title=d.get("title"),
            drawing_class=d.get("drawing_class"),
            floor=d.get("floor"),
            sheet_no=d.get("sheet_no"),
        )
        for d in (baseline.manifest.get("drawings", []) if baseline else [])
    ]
    return ProExecutionOut(
        engagement_id=engagement.id, project_id=engagement.project_id, project_code=facts.code,
        build_plan_version_no=baseline.version_no if baseline else None, drawings=drawings,
        stages=await stages_out(db, engagement.project_id, engagement_id=engagement.id),
    )  # fmt: skip


@router.get("/pro/engagements/{engagement_id}/execution", response_model=ProExecutionOut)
async def get_pro_execution(
    engagement_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> ProExecutionOut:
    """The project's stages with your own update counts, and the accepted Build Plan's drawings.
    Only while your contractor engagement is active."""
    engagement = await execution.own_contractor_engagement(db, actor, engagement_id)
    return await _pro_view(db, engagement)


@router.get("/pro/engagements/{engagement_id}/stages/{stage_id}/updates", response_model=UpdatesOut)
async def get_pro_stage_updates(
    engagement_id: uuid.UUID, stage_id: uuid.UUID, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> UpdatesOut:  # fmt: skip
    """Your own updates on the stage, newest first."""
    engagement = await execution.own_contractor_engagement(db, actor, engagement_id)
    stage = await execution.stage_row(db, stage_id)
    if stage.project_id != engagement.project_id:
        raise NotFound
    own = await execution.updates_of(db, stage.id, engagement_id=engagement.id)
    return UpdatesOut(
        stage=await one_stage_out(db, stage, engagement_id=engagement.id),
        updates=await updates_out(db, own),
    )


@router.post(
    "/pro/engagements/{engagement_id}/evidence",
    response_model=UploadTicketOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_evidence_upload(
    engagement_id: uuid.UUID, body: EvidenceUploadIn, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> UploadTicketOut:  # fmt: skip
    """A presigned upload of a photo for an update (JPEG or PNG), scanned and re-encoded before
    use; location metadata is removed from the stored image (EX-22)."""
    await enforce(request.app.state.database, UPLOAD_LIMIT, str(actor.session_id))
    engagement = await execution.own_contractor_engagement(db, actor, engagement_id)
    await execution.open_project(db, engagement.project_id)
    summary, ticket = await create_project_file_upload(
        db, _settings(request), request.app.state.storage, uploader_user_id=actor.user_id,
        project_id=engagement.project_id, purpose=FilePurpose.STAGE_EVIDENCE,
        original_name=body.file_name, content_type=body.content_type,
        size_bytes=body.size_bytes, capture_claim=body.claim(),
    )  # fmt: skip
    return UploadTicketOut(
        file=FileOut(
            file_id=summary.file_id, file_name=summary.file_name,
            content_type=summary.content_type, size_bytes=summary.size_bytes,
            state=summary.state,
        ),
        upload_url=ticket.url, headers=ticket.headers,
    )  # fmt: skip


@router.post("/pro/engagements/{engagement_id}/evidence/{file_id}/complete", response_model=FileOut)
async def post_evidence_complete(
    engagement_id: uuid.UUID, file_id: uuid.UUID, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> FileOut:  # fmt: skip
    await execution.own_contractor_engagement(db, actor, engagement_id)
    summary = await complete_project_file_upload(
        db, request.app.state.storage, uploader_user_id=actor.user_id, file_id=file_id
    )
    return FileOut(
        file_id=summary.file_id, file_name=summary.file_name, content_type=summary.content_type,
        size_bytes=summary.size_bytes, state=summary.state,
    )  # fmt: skip


@router.post(
    "/pro/engagements/{engagement_id}/stages/{stage_id}/updates",
    response_model=UpdatesOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": UpdatesOut}},
)
async def post_update(
    engagement_id: uuid.UUID, stage_id: uuid.UUID, body: UpdateIn, key: IdempotencyKeyHeader,
    request: Request, db: DbSession, actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    """Post a progress update or a completion request in the standard format (EX-02). The first
    update starts the stage. 409 `details.reason`: STAGE_COMPLETED, ALREADY_REQUESTED,
    NOT_CONTRACTOR, PROJECT_CLOSED; or STATE_CONFLICT."""
    await enforce(request.app.state.database, UPDATE_LIMIT, str(actor.session_id))

    async def act() -> UpdatesOut:
        engagement = await execution.own_contractor_engagement(db, actor, engagement_id)
        await execution.post_update(
            db, _settings(request), _professional(actor), stage_id=stage_id,
            engagement=engagement, kind=body.kind, note=body.note, materials=body.materials,
            open_problems=body.open_problems, file_ids=body.file_ids,
            corrects_update_id=body.corrects_update_id,
        )  # fmt: skip
        stage = await execution.stage_row(db, stage_id)
        own = await execution.updates_of(db, stage.id, engagement_id=engagement.id)
        return UpdatesOut(
            stage=await one_stage_out(db, stage, engagement_id=engagement.id),
            updates=await updates_out(db, own),
        )

    return await _once(
        db, actor, key, {"stage": str(stage_id), **body.model_dump(mode="json")}, act, 201
    )


@router.get(
    "/pro/engagements/{engagement_id}/execution/files/{file_id}/url", response_model=DownloadOut
)
async def get_pro_execution_file(
    engagement_id: uuid.UUID, file_id: uuid.UUID, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> DownloadOut:  # fmt: skip
    """A drawing of the accepted Build Plan, or a photo of one of your own updates (logged)."""
    engagement = await execution.own_contractor_engagement(db, actor, engagement_id)
    baseline = await accepted_manifest(db, engagement.project_id)
    drawings = {
        str(d["file_id"]) for d in (baseline.manifest.get("drawings", []) if baseline else [])
    }
    if str(file_id) in drawings:
        purpose = FilePurpose.DRAWING
    elif await execution.evidence_owned_by_stage(db, engagement.project_id, file_id, engagement.id):
        purpose = FilePurpose.STAGE_EVIDENCE
    else:
        raise NotFound
    url = await project_file_url(
        db, request.app.state.storage, project_id=engagement.project_id, file_id=file_id,
        purposes=frozenset({purpose}), viewer_user_id=actor.user_id, ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)
