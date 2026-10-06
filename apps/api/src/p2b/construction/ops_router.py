"""Operations routes for execution (admin host; OPS or ADMIN with MFA), Slice 3.7A. Operations
read every project's stages and updates, enter an OUTSIDE contractor's updates with how they were
received (EX-02), and confirm or return a completion request with a recorded reason (EX-03). The
queue lists completion requests waiting for a decision; one unanswered for the configured number
of days is an exception, with no reminder sent (EX-12)."""

import hashlib
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from p2b.catalog.interface import stage_master_names
from p2b.construction import execution
from p2b.construction.execution import conflict
from p2b.construction.models import StageInstance
from p2b.construction.schemas import (
    DownloadOut,
    FileOut,
    OpsExecutionOut,
    OpsExecutionQueueOut,
    OpsUpdateIn,
    OpsWaitingOut,
    ReasonDecisionIn,
    UpdatesOut,
)
from p2b.construction.service import Who
from p2b.construction.views import (
    contractor_out,
    one_stage_out,
    stage_out,
    stages_out,
    updates_out,
    waiting_exception,
)
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import DbSession
from p2b.core.errors import ValidationFailed
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.vocabulary import Audience, EngagementParty, FilePurpose, StaffRole, StageState
from p2b.documents.interface import staff_download_url, store_staff_upload
from p2b.identity.interface import Actor, active_roles, require_actor
from p2b.projects.interface import connection_facts

router = APIRouter(tags=["execution-operations"])

STAFF = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.OPS, StaffRole.ADMIN))
MAX_STAFF_UPLOAD = 10 * 1024 * 1024
QUEUE_SIZE = 200


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _ip_hash(request: Request) -> str:
    settings = _settings(request)
    peer = request.client.host if request.client else None
    return keyed_hash(
        settings.identifier_pepper.get_secret_value(), client_ip(request.headers, peer)
    )


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


async def _project_view(db: DbSession, project_id: uuid.UUID) -> OpsExecutionOut:
    facts = await execution.project_facts(db, project_id)
    return OpsExecutionOut(
        project_id=project_id, project_code=facts.code,
        contractor=await contractor_out(db, project_id), stages=await stages_out(db, project_id),
    )  # fmt: skip


async def _stage_updates(db: DbSession, stage: StageInstance) -> UpdatesOut:
    return UpdatesOut(
        stage=await one_stage_out(db, stage),
        updates=await updates_out(db, await execution.updates_of(db, stage.id)),
    )


@router.get("/ops/execution", response_model=OpsExecutionQueueOut)
async def get_queue(
    request: Request, db: DbSession, _: Annotated[Actor, STAFF]
) -> OpsExecutionQueueOut:
    """Completion requests waiting for a decision, oldest first."""
    days = _settings(request).completion_request_exception_days
    rows = list(
        await db.scalars(
            select(StageInstance)
            .where(StageInstance.state == StageState.COMPLETION_REQUESTED.value)
            .order_by(StageInstance.completion_requested_at, StageInstance.id)
            .limit(QUEUE_SIZE)
        )
    )
    names = await stage_master_names(db, list({r.stage_master_id for r in rows}))
    today = await execution.today(db)
    waiting = []
    codes: dict[uuid.UUID, str] = {}
    for row in rows:
        if row.project_id not in codes:
            facts = await connection_facts(db, row.project_id)
            codes[row.project_id] = facts.code if facts else ""
        waiting.append(
            OpsWaitingOut(
                project_id=row.project_id,
                project_code=codes[row.project_id],
                stage=stage_out(row, names.get(row.stage_master_id, ""), {}),
                exception=waiting_exception(row, today, days),
            )
        )
    return OpsExecutionQueueOut(exception_days=days, waiting=waiting)


@router.get("/ops/projects/{project_id}/execution", response_model=OpsExecutionOut)
async def get_project_execution(
    project_id: uuid.UUID, db: DbSession, _: Annotated[Actor, STAFF]
) -> OpsExecutionOut:
    return await _project_view(db, project_id)


@router.get("/ops/stages/{stage_id}/updates", response_model=UpdatesOut)
async def get_updates(stage_id: uuid.UUID, db: DbSession, _: Annotated[Actor, STAFF]) -> UpdatesOut:
    """Every update on the stage, from every contractor engaged over time."""
    return await _stage_updates(db, await execution.stage_row(db, stage_id))


@router.post(
    "/ops/projects/{project_id}/stage-evidence",
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                t: {"schema": {"type": "string", "format": "binary"}}
                for t in ("image/jpeg", "image/png")
            },
        }
    },
)
async def post_stage_evidence(
    project_id: uuid.UUID,
    file_name: Annotated[str, Query(min_length=1, max_length=200)],
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    """A photo an OUTSIDE contractor sent, uploaded through the API (raw body). Scanned and
    re-encoded before use."""
    await execution.open_project(db, project_id)
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip()
    if int(request.headers.get("content-length") or 0) > MAX_STAFF_UPLOAD:
        raise ValidationFailed(details={"fields": {"file": ["The file is too large."]}})
    data = await request.body()

    async def act() -> FileOut:
        summary = await store_staff_upload(
            db, _settings(request), request.app.state.storage, uploader_user_id=actor.user_id,
            project_id=project_id, purpose=FilePurpose.STAGE_EVIDENCE, original_name=file_name,
            content_type=content_type, data=data,
        )  # fmt: skip
        return FileOut(
            file_id=summary.file_id, file_name=summary.file_name,
            content_type=summary.content_type, size_bytes=summary.size_bytes,
            state=summary.state,
        )  # fmt: skip

    body = {"project": str(project_id), "name": file_name,
            "sha256": hashlib.sha256(data).hexdigest()}  # fmt: skip
    return await _once(db, actor, key, body, act, 201)


@router.post(
    "/ops/stages/{stage_id}/updates",
    response_model=UpdatesOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": UpdatesOut}},
)
async def post_update(
    stage_id: uuid.UUID, body: OpsUpdateIn, key: IdempotencyKeyHeader, request: Request,
    db: DbSession, actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Enter an update for an OUTSIDE contractor, with how it was received (EX-02). A listed
    contractor posts its own: 409 `details.reason` LISTED_CONTRACTOR; NOT_CONTRACTOR when no
    contractor is engaged."""

    async def act() -> UpdatesOut:
        stage = await execution.stage_row(db, stage_id)
        current = await execution.contractor_of_record(db, stage.project_id)
        if current is None:
            raise conflict("NOT_CONTRACTOR", "No contractor is engaged on this project.")
        if current.party != EngagementParty.OUTSIDE.value:
            raise conflict("LISTED_CONTRACTOR", "A listed contractor posts its own updates.")
        await execution.post_update(
            db, _settings(request), await _who(db, actor), stage_id=stage_id,
            engagement=current, kind=body.kind, note=body.note, materials=body.materials,
            open_problems=body.open_problems, file_ids=body.file_ids,
            corrects_update_id=body.corrects_update_id, reason=body.reason,
        )  # fmt: skip
        return await _stage_updates(db, await execution.stage_row(db, stage_id))

    return await _once(
        db, actor, key, {"stage": str(stage_id), **body.model_dump(mode="json")}, act, 201
    )


@router.post("/ops/stages/{stage_id}/confirm", response_model=OpsExecutionOut)
async def post_confirm(
    stage_id: uuid.UUID, body: ReasonDecisionIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Confirm a completion request with a recorded reason (EX-03). 409 GATE_NOT_CLEARED,
    STALE, PROJECT_CLOSED; or STATE_CONFLICT."""

    async def act() -> OpsExecutionOut:
        stage = await execution.stage_row(db, stage_id)
        await execution.confirm(
            db, await _who(db, actor), stage_id, stage.project_id, version=body.version,
            reason=body.reason,
        )  # fmt: skip
        return await _project_view(db, stage.project_id)

    return await _once(db, actor, key, {"stage": str(stage_id), **body.model_dump()}, act)


@router.post("/ops/stages/{stage_id}/return", response_model=OpsExecutionOut)
async def post_return(
    stage_id: uuid.UUID, body: ReasonDecisionIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    async def act() -> OpsExecutionOut:
        stage = await execution.stage_row(db, stage_id)
        await execution.return_stage(
            db, await _who(db, actor), stage_id, stage.project_id, version=body.version,
            reason=body.reason,
        )  # fmt: skip
        return await _project_view(db, stage.project_id)

    return await _once(db, actor, key, {"stage": str(stage_id), **body.model_dump()}, act)


@router.get("/ops/stage-files/{file_id}/url", response_model=DownloadOut)
async def get_stage_file(
    file_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, STAFF]
) -> DownloadOut:
    """A photo of an update (logged)."""
    url = await staff_download_url(
        db, request.app.state.storage, viewer_user_id=actor.user_id, file_id=file_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)
