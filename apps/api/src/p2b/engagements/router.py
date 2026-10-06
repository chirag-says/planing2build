"""Service needs, connections and engagements: the family (homeowner host) and the professional
(professionals host). Every creating or transition POST takes an `Idempotency-Key`."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from p2b.billing.interface import package_state
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import Database, DbSession
from p2b.core.errors import NotFound
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.ratelimit import Limit, enforce
from p2b.core.vocabulary import Audience, FilePurpose
from p2b.documents.interface import (
    complete_personal_upload,
    create_personal_upload,
    personal_file_url,
    personal_files,
    shared_file_url,
)
from p2b.engagements import service
from p2b.engagements.models import Connection
from p2b.engagements.schemas import (
    AcceptIn,
    ConnectionIn,
    ConnectionTargetOut,
    DeclineIn,
    DownloadOut,
    FileOut,
    NeedIn,
    OutsideIn,
    ProConnectionOut,
    ProConnectionsOut,
    ProEngagementOut,
    QuoteReviewIn,
    ReasonIn,
    ServicesOut,
    ShareIn,
    UploadIn,
    UploadTicketOut,
)
from p2b.engagements.views import (
    file_out,
    pro_connection_out,
    pro_engagement_out,
    services_out,
)
from p2b.identity.interface import Actor, require_actor
from p2b.professionals.interface import connection_candidate

router = APIRouter(tags=["engagements"])

HOMEOWNER = require_actor(Audience.IHB)
PROFESSIONAL = require_actor(Audience.PRO)
SEND_LIMIT = Limit("connections_session", 20, 600)  # T2
UPLOAD_LIMIT = Limit("quote_uploads_session", 30, 60)  # T3


def _ip_hash(request: Request) -> str:
    settings: Settings = request.app.state.settings
    peer = request.client.host if request.client else None
    return keyed_hash(
        settings.identifier_pepper.get_secret_value(), client_ip(request.headers, peer)
    )


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def _services(
    db: DbSession, request: Request, actor: Actor, project_id: uuid.UUID
) -> ServicesOut:
    facts = await service.family_access(db, actor, project_id, write=False)
    return await services_out(db, _settings(request), actor, facts)


async def _once(
    db: DbSession, actor: Actor, key: str, body: object, act: object, code: int = 200
) -> JSONResponse:
    async def action() -> tuple[int, dict[str, object]]:
        out = await act()  # type: ignore[operator]
        return code, out.model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key, request_body=body, action=action
    )


# --- the family ----------------------------------------------------------------------------


@router.get("/projects/{project_id}/services", response_model=ServicesOut)
async def get_services(
    project_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> ServicesOut:
    """Each professional category: the need, open and past requests, the active engagement,
    and the quotes sent for review."""
    return await _services(db, request, actor, project_id)


@router.put("/projects/{project_id}/services/{code}/need", response_model=ServicesOut)
async def put_need(
    project_id: uuid.UUID,
    code: str,
    body: NeedIn,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> ServicesOut:
    await service.set_need(db, actor, project_id, code, body.state, body.subtypes)
    return await _services(db, request, actor, project_id)


@router.get("/projects/{project_id}/connection-target", response_model=ConnectionTargetOut)
async def get_connection_target(
    project_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
    category: Annotated[str, Query(max_length=40)],
    profile_id: uuid.UUID,
) -> ConnectionTargetOut:
    """The request screen: whether a request can be sent now, and why not."""
    settings = _settings(request)
    facts = await service.family_access(db, actor, project_id, write=False)
    known = await service.categories(db)
    if category not in known.names:
        raise NotFound
    candidate = await connection_candidate(db, profile_id, category, facts.point or (0.0, 0.0))
    if candidate is None or not candidate.listed or candidate.hidden:
        raise NotFound
    need = (await service.needs(db, facts))[category]
    open_now = await service.open_count(db, project_id, category)
    blocked = await service.send_blocker(
        db, settings, actor, facts, category, need.state, candidate
    )
    return ConnectionTargetOut(
        project_id=project_id,
        project_code=facts.code,
        category=category,
        category_name=known.names[category],
        profile_id=profile_id,
        professional_name=candidate.display_name,
        firm_name=candidate.firm_name,
        package_state=await package_state(db, project_id),
        blocked=blocked,
        open_requests=open_now,
        open_limit=settings.connection_open_limit,
        response_hours=settings.connection_response_hours,
        contact_name=actor.display_name,
    )


@router.post(
    "/projects/{project_id}/connections",
    response_model=ServicesOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": ServicesOut}},
)
async def post_connection(
    project_id: uuid.UUID,
    body: ConnectionIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """Send a connection request (needs the active package). 409 `PACKAGE_REQUIRED`, or
    `STATE_CONFLICT` with `details.reason`: NOT_NEEDED, ENGAGED, DUPLICATE, OPEN_LIMIT,
    NOT_LISTED, OUTSIDE_AREA, NO_LOCATION, SELF, NOT_ELIGIBLE."""
    database: Database = request.app.state.database
    await enforce(database, SEND_LIMIT, str(actor.session_id))

    async def act() -> ServicesOut:
        await service.send_connection(
            db, _settings(request), actor, project_id, body.category, body.profile_id,
            service.FamilyContact(body.contact_name, body.contact_phone, body.site_address),
        )  # fmt: skip
        return await _services(db, request, actor, project_id)

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


@router.post(
    "/projects/{project_id}/connections/{connection_id}/withdraw", response_model=ServicesOut
)
async def post_withdraw(
    project_id: uuid.UUID,
    connection_id: uuid.UUID,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    async def act() -> ServicesOut:
        await service.withdraw_by_family(db, actor, project_id, connection_id)
        return await _services(db, request, actor, project_id)

    return await _once(db, actor, key, {"connection_id": str(connection_id)}, act)


@router.post(
    "/projects/{project_id}/engagements",
    response_model=ServicesOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": ServicesOut}},
)
async def post_outside(
    project_id: uuid.UUID,
    body: OutsideIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """Record the family's own professional for a category (no package needed)."""

    async def act() -> ServicesOut:
        await service.record_outside(
            db, actor, project_id, body.category,
            service.OutsideProfessional(body.name, body.firm, body.contact),
        )  # fmt: skip
        return await _services(db, request, actor, project_id)

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


@router.post("/projects/{project_id}/engagements/{engagement_id}/end", response_model=ServicesOut)
async def post_end_by_family(
    project_id: uuid.UUID,
    engagement_id: uuid.UUID,
    body: ReasonIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    async def act() -> ServicesOut:
        await service.end_by_family(db, actor, project_id, engagement_id, body.reason)
        return await _services(db, request, actor, project_id)

    return await _once(db, actor, key, body.model_dump(mode="json"), act)


@router.post("/projects/{project_id}/engagements/{engagement_id}/files", response_model=ServicesOut)
async def post_share(
    project_id: uuid.UUID,
    engagement_id: uuid.UUID,
    body: ShareIn,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> ServicesOut:
    """Share requirement files with an active engagement with a listed professional. Repeating
    it changes nothing."""
    await service.share_files(db, actor, project_id, engagement_id, body.file_ids)
    return await _services(db, request, actor, project_id)


@router.delete(
    "/projects/{project_id}/engagements/{engagement_id}/files/{file_id}",
    response_model=ServicesOut,
)
async def delete_share(
    project_id: uuid.UUID,
    engagement_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> ServicesOut:
    await service.unshare_file(db, actor, project_id, engagement_id, file_id)
    return await _services(db, request, actor, project_id)


@router.post(
    "/projects/{project_id}/quote-reviews/uploads",
    response_model=UploadTicketOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": UploadTicketOut}},
)
async def post_quote_upload(
    project_id: uuid.UUID,
    body: UploadIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """A presigned upload for a quote document (JPG, PNG or PDF; scanned before use)."""
    database: Database = request.app.state.database
    await enforce(database, UPLOAD_LIMIT, str(actor.session_id))
    await service.family_access(db, actor, project_id, write=True)

    async def act() -> UploadTicketOut:
        summary, ticket = await create_personal_upload(
            db, _settings(request), request.app.state.storage, actor,
            purpose=FilePurpose.QUOTE_DOCUMENT, original_name=body.file_name,
            content_type=body.content_type, size_bytes=body.size_bytes,
        )  # fmt: skip
        return UploadTicketOut(
            file=file_out(summary), upload_url=ticket.url, headers=ticket.headers
        )

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


@router.post(
    "/projects/{project_id}/quote-reviews/uploads/{file_id}/complete", response_model=FileOut
)
async def post_quote_upload_complete(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> FileOut:
    await service.family_access(db, actor, project_id, write=True)
    return file_out(await complete_personal_upload(db, request.app.state.storage, actor, file_id))


@router.get("/projects/{project_id}/quote-reviews/uploads/{file_id}", response_model=FileOut)
async def get_quote_upload(
    project_id: uuid.UUID, file_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> FileOut:
    """A quote upload's state while it is checked (the screen polls it)."""
    await service.family_access(db, actor, project_id, write=False)
    summary = (await personal_files(db, actor.user_id, [file_id])).get(file_id)
    if summary is None:
        raise NotFound
    return file_out(summary)


@router.get("/projects/{project_id}/quote-reviews/files/{file_id}/url", response_model=DownloadOut)
async def get_quote_file_url(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> DownloadOut:
    await service.family_access(db, actor, project_id, write=False)
    url = await personal_file_url(db, request.app.state.storage, actor, file_id, _ip_hash(request))
    return DownloadOut(url=url)


@router.post(
    "/projects/{project_id}/quote-reviews",
    response_model=ServicesOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": ServicesOut}},
)
async def post_quote_review(
    project_id: uuid.UUID,
    body: QuoteReviewIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """Send a quote you already hold to Plan2Build for review (needs the active package).
    This records the request; the review itself comes later."""

    async def act() -> ServicesOut:
        await service.submit_quote_review(
            db, actor, project_id, body.category, body.quoted_by, body.note, body.file_ids
        )
        return await _services(db, request, actor, project_id)

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


# --- the professional ----------------------------------------------------------------------


@router.get("/pro/connections", response_model=ProConnectionsOut)
async def get_pro_connections(
    db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> ProConnectionsOut:
    """Requests sent to you, newest first. Before you accept, a request shows the project's
    brief only."""
    profile_id = await service.own_profile_id(db, actor)
    rows = await db.scalars(
        select(Connection)
        .where(Connection.profile_id == profile_id)
        .order_by(Connection.sent_at.desc())
        .limit(200)
    )
    return ProConnectionsOut(items=[await pro_connection_out(db, c, detail=False) for c in rows])


@router.get("/pro/connections/{connection_id}", response_model=ProConnectionOut)
async def get_pro_connection(
    connection_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> ProConnectionOut:
    connection = await service.own_connection(db, actor, connection_id)
    return await pro_connection_out(db, connection, detail=True)


async def _pro_once(
    db: DbSession, actor: Actor, key: str, connection_id: uuid.UUID, body: dict[str, object],
    change: object,
) -> JSONResponse:  # fmt: skip
    async def act() -> ProConnectionOut:
        await change()  # type: ignore[operator]
        connection = await service.own_connection(db, actor, connection_id)
        return await pro_connection_out(db, connection, detail=True)

    return await _once(db, actor, key, {"connection_id": str(connection_id), **body}, act)


@router.post("/pro/connections/{connection_id}/accept", response_model=ProConnectionOut)
async def post_accept(
    connection_id: uuid.UUID,
    body: AcceptIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:
    """Accept: the family sees your name, phone and email; you see theirs, the plot pin and the
    files they share. 409 `details.reason`: EXPIRED, ENGAGED, PACKAGE_ENDED, PROJECT_CLOSED,
    NOT_LISTED."""

    async def change() -> None:
        await service.accept(db, actor, connection_id, body.phone)

    return await _pro_once(db, actor, key, connection_id, body.model_dump(mode="json"), change)


@router.post("/pro/connections/{connection_id}/decline", response_model=ProConnectionOut)
async def post_decline(
    connection_id: uuid.UUID,
    body: DeclineIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:
    """Decline with a reason (an explanation for OTHER). The family sees a neutral message."""

    async def change() -> None:
        await service.decline(db, actor, connection_id, body.reason, body.note)

    return await _pro_once(db, actor, key, connection_id, body.model_dump(mode="json"), change)


@router.post("/pro/connections/{connection_id}/end", response_model=ProConnectionOut)
async def post_end_by_professional(
    connection_id: uuid.UUID,
    body: ReasonIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:
    async def change() -> None:
        await service.end_by_professional(db, actor, connection_id, body.reason)

    return await _pro_once(db, actor, key, connection_id, body.model_dump(mode="json"), change)


@router.get("/pro/connections/{connection_id}/files/{file_id}/url", response_model=DownloadOut)
async def get_shared_file_url(
    connection_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> DownloadOut:
    """A file the family shared with your active engagement (logged)."""
    connection = await service.professional_may_read(db, actor, connection_id, file_id)
    url = await shared_file_url(
        db, request.app.state.storage, project_id=connection.project_id, file_id=file_id,
        viewer_user_id=actor.user_id, ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)


# --- the professional's engagements, whatever their origin (ADR-024) ------------------------


@router.get("/pro/engagements/{engagement_id}", response_model=ProEngagementOut)
async def get_pro_engagement(
    engagement_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> ProEngagementOut:
    """An engagement you hold, for example from a homeowner's selection of your RFQ quote."""
    return await pro_engagement_out(db, await service.own_engagement(db, actor, engagement_id))


@router.post("/pro/engagements/{engagement_id}/end", response_model=ProEngagementOut)
async def post_end_own_engagement(
    engagement_id: uuid.UUID,
    body: ReasonIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:
    async def act() -> ProEngagementOut:
        await service.end_own_engagement(db, actor, engagement_id, body.reason)
        return await pro_engagement_out(db, await service.own_engagement(db, actor, engagement_id))

    return await _once(
        db, actor, key, {"engagement_id": str(engagement_id), **body.model_dump(mode="json")}, act
    )


@router.get("/pro/engagements/{engagement_id}/files/{file_id}/url", response_model=DownloadOut)
async def get_engagement_file_url(
    engagement_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> DownloadOut:
    """A file the family shared with your active engagement (logged)."""
    engagement = await service.professional_may_read_shared(db, actor, engagement_id, file_id)
    url = await shared_file_url(
        db, request.app.state.storage, project_id=engagement.project_id, file_id=file_id,
        viewer_user_id=actor.user_id, ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)
