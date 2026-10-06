import uuid
from typing import Annotated

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import Database, DbSession
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.images import ImageProvider
from p2b.core.ratelimit import Limit, enforce
from p2b.core.vocabulary import (
    Audience,
    DesignBlock,
    DesignFailureReason,
    DesignFunding,
    DesignGenerationState,
    DesignView,
)
from p2b.designs.schemas import (
    DesignListOut,
    DesignOut,
    DesignQuotaOut,
    DesignReferenceOut,
    DesignRequest,
)
from p2b.designs.service import (
    DesignItem,
    get_design,
    list_designs,
    mark_reference,
    remove_reference,
    request_generation,
)
from p2b.identity.interface import Actor, require_actor

router = APIRouter(tags=["designs"])

HOMEOWNER = require_actor(Audience.IHB)
# Tier T2 writes: generation requests per session, on top of the daily quotas.
REQUEST_LIMIT = Limit("design_request_session", 20, 600)


def _ip_hash(request: Request) -> str:
    settings: Settings = request.app.state.settings
    peer = request.client.host if request.client else None
    return keyed_hash(
        settings.identifier_pepper.get_secret_value(), client_ip(request.headers, peer)
    )


def _out(item: DesignItem) -> DesignOut:
    g = item.generation
    return DesignOut(
        design_id=str(g.id),
        sequence=g.sequence,
        view=DesignView(g.view),
        state=DesignGenerationState(g.state),
        funding=DesignFunding(g.funding),
        created_at=g.created_at,
        completed_at=g.completed_at,
        failure_reason=DesignFailureReason(g.failure_reason) if g.failure_reason else None,
        image_url=item.image_url,
        reference=DesignReferenceOut(marked_at=item.reference_marked_at)
        if item.reference_marked_at
        else None,
    )


@router.get("/projects/{project_id}/designs", response_model=DesignListOut)
async def get_designs(
    project_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> DesignListOut:
    """The project's concepts, newest first, with the quota as the server counts it."""
    provider: ImageProvider = request.app.state.image_provider
    quota, items = await list_designs(
        db, request.app.state.settings, request.app.state.storage, provider, actor, project_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DesignListOut(
        quota=DesignQuotaOut(
            free_total=quota.free_total,
            free_used=quota.free_used,
            in_progress=quota.in_progress,
            free_remaining=quota.free_remaining,
            can_generate=quota.block is None,
            block=quota.block,
            credit_balance=quota.credit_balance,
            can_use_credit=quota.block == DesignBlock.FREE_QUOTA_USED
            and quota.paid_block is None
            and quota.credit_balance > 0,
            paid_block=quota.paid_block,
        ),
        items=[_out(item) for item in items],
    )


@router.post(
    "/projects/{project_id}/designs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DesignOut,
    responses={202: {"model": DesignOut}},
)
async def post_design(
    project_id: uuid.UUID,
    body: DesignRequest,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """Ask for an illustrative concept. 202 with the QUEUED generation; the image follows when
    the job finishes. 409 QUOTA_EXHAUSTED or STATE_CONFLICT, 503 when no provider is set up."""
    database: Database = request.app.state.database
    await enforce(database, REQUEST_LIMIT, str(actor.session_id))
    settings: Settings = request.app.state.settings
    provider: ImageProvider = request.app.state.image_provider

    async def act() -> tuple[int, dict[str, object]]:
        generation = await request_generation(
            db, settings, provider, actor, project_id, view=body.view, use_credit=body.use_credit
        )
        item = DesignItem(generation, None, None)
        return 202, _out(item).model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key,
        request_body={"project_id": str(project_id), **body.model_dump(mode="json")}, action=act,
    )  # fmt: skip


@router.get("/projects/{project_id}/designs/{design_id}", response_model=DesignOut)
async def get_one_design(
    project_id: uuid.UUID,
    design_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> DesignOut:
    item = await get_design(
        db, request.app.state.storage, actor, project_id, design_id, ip_hash=_ip_hash(request)
    )
    return _out(item)


@router.post(
    "/projects/{project_id}/designs/{design_id}/reference",
    response_model=DesignOut,
    responses={200: {"model": DesignOut}},
)
async def post_reference(
    project_id: uuid.UUID,
    design_id: uuid.UUID,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """Mark the concept as a design reference. A reference only: it stays illustrative and
    starts no Build Plan, BOQ, RFQ or approval."""
    ip_hash = _ip_hash(request)

    async def act() -> tuple[int, dict[str, object]]:
        await mark_reference(db, actor, project_id, design_id)
        item = await get_design(
            db, request.app.state.storage, actor, project_id, design_id, ip_hash=ip_hash
        )
        return 200, _out(item).model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key,
        request_body={"project_id": str(project_id), "design_id": str(design_id)}, action=act,
    )  # fmt: skip


@router.delete(
    "/projects/{project_id}/designs/{design_id}/reference",
    response_model=DesignOut,
)
async def delete_reference(
    project_id: uuid.UUID,
    design_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> DesignOut:
    """Remove the design reference. Only the reference changes; the concept, its quota count and
    its illustrative status stay as they were. Idempotent (DELETE needs no key)."""
    await remove_reference(db, actor, project_id, design_id)
    item = await get_design(
        db, request.app.state.storage, actor, project_id, design_id, ip_hash=_ip_hash(request)
    )
    return _out(item)
