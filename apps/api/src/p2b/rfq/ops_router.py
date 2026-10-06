"""Operations and ADMIN routes for RFQs (admin host; staff role and MFA). Operations prepare and
issue RFQs, introduce contractors with a reason, extend deadlines, capture quotes, review them,
answer and ask questions, and publish comparisons. ADMIN activates selection statements. Nobody
edits a submitted quote, a frozen pack or a published comparison."""

import hashlib
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from p2b.audit.interface import record
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import DbSession
from p2b.core.errors import NotFound, ValidationFailed
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.vocabulary import (
    ActorType,
    Audience,
    FilePurpose,
    InvitationWithdrawReason,
    QuoteCheckState,
    RfqCancelReason,
    StaffRole,
)
from p2b.documents.interface import staff_download_url, store_staff_upload
from p2b.identity.interface import Actor, active_roles, require_actor
from p2b.rfq import comparison, quotes, review, rfqs, selection
from p2b.rfq.common import Who, project
from p2b.rfq.models import QuoteVersion, Rfq, RfqInvitation
from p2b.rfq.schemas import (
    AdjustmentsIn,
    CaptureIn,
    DeadlineIn,
    DownloadOut,
    ExtendIn,
    FileOut,
    IntroduceIn,
    OpsAnswerIn,
    OpsQuestionIn,
    OpsRfqOut,
    OpsRfqsOut,
    OpsRfqSummaryOut,
    QuoteIn,
    ReasonIn,
    RfqRequestIn,
    StatementIn,
    StatementOut,
)
from p2b.rfq.views import ops_rfq_out

router = APIRouter(tags=["rfq-operations"])

STAFF = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.OPS, StaffRole.ADMIN))
ADMIN = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.ADMIN,))
MAX_STAFF_UPLOAD = 10 * 1024 * 1024


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
    db: DbSession,
    actor: Actor,
    key: str,
    body: Any,
    act: Callable[[], Awaitable[BaseModel]],
    code: int = 200,
) -> JSONResponse:
    async def action() -> tuple[int, dict[str, object]]:
        return code, (await act()).model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key, request_body=body, action=action
    )


async def _view(db: DbSession, rfq_id: uuid.UUID) -> OpsRfqOut:
    rfq = await rfqs.rfq_row(db, rfq_id)
    return await ops_rfq_out(db, rfq, await project(db, rfq.project_id))


async def _rfq_of_version(db: DbSession, qv_id: uuid.UUID) -> uuid.UUID:
    qv = await db.get(QuoteVersion, qv_id)
    if qv is None:
        raise NotFound
    return qv.rfq_id


@router.get("/ops/rfqs", response_model=OpsRfqsOut)
async def get_rfqs(
    db: DbSession,
    actor: Annotated[Actor, STAFF],
    state: Annotated[str | None, Query(max_length=10)] = None,
) -> OpsRfqsOut:
    """RFQs, open ones first by deadline (at most 100)."""
    query = select(Rfq).order_by(Rfq.quotes_due_at.asc().nulls_first(), Rfq.created_at.desc())
    if state:
        query = query.where(Rfq.state == state)
    items = []
    for rfq in await db.scalars(query.limit(100)):
        facts = await project(db, rfq.project_id)
        invited = await db.scalar(
            select(func.count()).select_from(RfqInvitation).where(RfqInvitation.rfq_id == rfq.id)
        )
        quoted = await db.scalar(
            select(func.count()).select_from(QuoteVersion).where(QuoteVersion.rfq_id == rfq.id)
        )
        pending = await db.scalar(
            select(func.count())
            .select_from(QuoteVersion)
            .where(
                QuoteVersion.rfq_id == rfq.id,
                QuoteVersion.state == "SUBMITTED",
                QuoteVersion.review_state.in_(
                    (QuoteCheckState.PENDING.value, QuoteCheckState.NEEDS_CLARIFICATION.value)
                ),
            )
        )
        items.append(
            OpsRfqSummaryOut(
                id=rfq.id, project_id=rfq.project_id, project_code=facts.code, state=rfq.state,
                created_at=rfq.created_at, quotes_due_at=rfq.quotes_due_at,
                invitations=invited or 0, quotes=quoted or 0, pending_reviews=pending or 0,
            )
        )  # fmt: skip
    return OpsRfqsOut(items=items)


@router.get("/ops/projects/{project_id}/rfqs", response_model=OpsRfqsOut)
async def get_project_rfqs(
    project_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, STAFF]
) -> OpsRfqsOut:
    facts = await project(db, project_id)
    items = [
        OpsRfqSummaryOut(
            id=r.id, project_id=r.project_id, project_code=facts.code, state=r.state,
            created_at=r.created_at, quotes_due_at=r.quotes_due_at, invitations=0, quotes=0,
            pending_reviews=0,
        )
        for r in await db.scalars(
            select(Rfq).where(Rfq.project_id == project_id).order_by(Rfq.created_at.desc())
        )
    ]  # fmt: skip
    return OpsRfqsOut(items=items)


@router.post(
    "/ops/projects/{project_id}/rfqs",
    response_model=OpsRfqOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": OpsRfqOut}},
)
async def post_rfq(
    project_id: uuid.UUID, body: RfqRequestIn, key: IdempotencyKeyHeader, request: Request,
    db: DbSession, actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Create a DRAFT at the owner's direction (QD-03)."""

    async def act() -> OpsRfqOut:
        facts = await project(db, project_id)
        rfq = await rfqs.request(
            db, _settings(request), await _who(db, actor), facts, body.profile_ids
        )
        return await _view(db, rfq.id)

    return await _once(
        db, actor, key, {"project": str(project_id), **body.model_dump(mode="json")}, act, 201
    )


@router.get("/ops/rfqs/{rfq_id}", response_model=OpsRfqOut)
async def get_rfq(rfq_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, STAFF]) -> OpsRfqOut:
    """Everything: invitations, every quote version with lines, review state and adjustments,
    clarifications, comparisons, the selection and the history."""
    return await _view(db, rfq_id)


@router.put("/ops/rfqs/{rfq_id}/deadline", response_model=OpsRfqOut)
async def put_deadline(
    rfq_id: uuid.UUID, body: DeadlineIn, db: DbSession, actor: Annotated[Actor, STAFF]
) -> OpsRfqOut:
    """The quote deadline of a DRAFT RFQ; no universal default (QD-05)."""
    await rfqs.set_deadline(db, await _who(db, actor), rfq_id, body.quotes_due_at)
    return await _view(db, rfq_id)


@router.post("/ops/rfqs/{rfq_id}/deadline/extend", response_model=OpsRfqOut)
async def post_extend(
    rfq_id: uuid.UUID, body: ExtendIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Extend with a reason; every contractor still in the RFQ gets the same notice (QD-05)."""

    async def act() -> OpsRfqOut:
        await rfqs.extend_deadline(
            db, await _who(db, actor), rfq_id, body.quotes_due_at, body.reason
        )
        return await _view(db, rfq_id)

    return await _once(db, actor, key, {"rfq": str(rfq_id), **body.model_dump(mode="json")}, act)


@router.post("/ops/rfqs/{rfq_id}/invitations", response_model=OpsRfqOut)
async def post_introduce(
    rfq_id: uuid.UUID, body: IntroduceIn, key: IdempotencyKeyHeader, request: Request,
    db: DbSession, actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Introduce a listed contractor with a written reason (QD-03), within the limit (QD-04)."""

    async def act() -> OpsRfqOut:
        await rfqs.introduce(
            db, _settings(request), await _who(db, actor), rfq_id, body.profile_id, body.reason
        )
        return await _view(db, rfq_id)

    return await _once(db, actor, key, {"rfq": str(rfq_id), **body.model_dump(mode="json")}, act)


@router.post("/ops/rfq-invitations/{invitation_id}/withdraw", response_model=OpsRfqOut)
async def post_withdraw_invitation(
    invitation_id: uuid.UUID, body: ReasonIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    async def act() -> OpsRfqOut:
        inv = await db.get(RfqInvitation, invitation_id, with_for_update=True)
        if inv is None:
            raise NotFound
        await rfqs.withdraw_invitation(
            db, await _who(db, actor), inv, InvitationWithdrawReason.OPERATIONS, body.reason
        )
        return await _view(db, inv.rfq_id)

    return await _once(
        db, actor, key, {"invitation": str(invitation_id), **body.model_dump(mode="json")}, act
    )


@router.post("/ops/rfqs/{rfq_id}/issue", response_model=OpsRfqOut)
async def post_issue(
    rfq_id: uuid.UUID, key: IdempotencyKeyHeader, request: Request, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Freeze the accepted Build Plan's contractor pack and send the invitations. 409
    `details.reason`: NO_DEADLINE, BASELINE_CHANGED, NO_RECIPIENTS, NOT_ELIGIBLE; or
    PACKAGE_REQUIRED."""

    async def act() -> OpsRfqOut:
        await rfqs.issue(db, _settings(request), await _who(db, actor), rfq_id)
        return await _view(db, rfq_id)

    return await _once(db, actor, key, {"rfq": str(rfq_id)}, act)


@router.post("/ops/rfqs/{rfq_id}/cancel", response_model=OpsRfqOut)
async def post_cancel(
    rfq_id: uuid.UUID, body: ReasonIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    async def act() -> OpsRfqOut:
        rfq = await rfqs.rfq_row(db, rfq_id, lock=True)
        await rfqs.cancel(db, await _who(db, actor), rfq, RfqCancelReason.OPERATIONS, body.reason)
        return await _view(db, rfq_id)

    return await _once(db, actor, key, {"rfq": str(rfq_id), **body.model_dump(mode="json")}, act)


@router.post(
    "/ops/projects/{project_id}/rfq-files",
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": FileOut}},
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
async def post_rfq_file(
    project_id: uuid.UUID,
    file_name: Annotated[str, Query(min_length=1, max_length=200)],
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    """A contractor's quote document received outside the portal, uploaded through the API (raw
    body; the admin host does not upload to storage directly). Scanned before use."""
    await project(db, project_id)
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip()
    if int(request.headers.get("content-length") or 0) > MAX_STAFF_UPLOAD:
        raise ValidationFailed(details={"fields": {"file": ["The file is too large."]}})
    data = await request.body()

    async def act() -> FileOut:
        summary = await store_staff_upload(
            db, _settings(request), request.app.state.storage, uploader_user_id=actor.user_id,
            project_id=project_id, purpose=FilePurpose.QUOTE_ATTACHMENT, original_name=file_name,
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


@router.get("/ops/rfq-files/{file_id}/url", response_model=DownloadOut)
async def get_rfq_file(
    file_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, STAFF]
) -> DownloadOut:
    """A quote attachment, capture evidence or comparison document (logged)."""
    url = await staff_download_url(
        db, request.app.state.storage, viewer_user_id=actor.user_id, file_id=file_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)


@router.post("/ops/rfq-invitations/{invitation_id}/capture", response_model=OpsRfqOut)
async def post_capture(
    invitation_id: uuid.UUID, body: CaptureIn, key: IdempotencyKeyHeader, request: Request,
    db: DbSession, actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Enter a quote in the standard structure for an outside contractor, or for a listed one who
    sent it outside the portal; the contractor's document is the evidence (QD-22)."""

    async def act() -> OpsRfqOut:
        fields = body.model_dump(exclude={"evidence_file_id"})
        qv = await quotes.capture(
            db, _settings(request), await _who(db, actor), invitation_id,
            QuoteIn.model_validate(fields), body.evidence_file_id,
        )  # fmt: skip
        return await _view(db, qv.rfq_id)

    return await _once(
        db, actor, key, {"invitation": str(invitation_id), **body.model_dump(mode="json")}, act
    )


@router.put("/ops/quote-versions/{quote_version_id}/adjustments", response_model=OpsRfqOut)
async def put_adjustments(
    quote_version_id: uuid.UUID, body: AdjustmentsIn, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> OpsRfqOut:  # fmt: skip
    """Replace the adjustment list while the review is open. Never shown to contractors."""
    qv = await review.set_adjustments(db, await _who(db, actor), quote_version_id, body.adjustments)
    return await _view(db, qv.rfq_id)


@router.post("/ops/quote-versions/{quote_version_id}/reviewed", response_model=OpsRfqOut)
async def post_reviewed(
    quote_version_id: uuid.UUID, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """The adjustment list is complete: the version may be compared."""

    async def act() -> OpsRfqOut:
        qv = await review.mark_reviewed(db, await _who(db, actor), quote_version_id)
        return await _view(db, qv.rfq_id)

    return await _once(db, actor, key, {"quote_version": str(quote_version_id)}, act)


@router.post("/ops/rfqs/{rfq_id}/clarifications", response_model=OpsRfqOut)
async def post_ops_question(
    rfq_id: uuid.UUID, body: OpsQuestionIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    async def act() -> OpsRfqOut:
        await review.plan2build_asks(
            db, await _who(db, actor), rfq_id, body.invitation_id, body.quote_version_id,
            body.question,
        )  # fmt: skip
        return await _view(db, rfq_id)

    return await _once(db, actor, key, {"rfq": str(rfq_id), **body.model_dump(mode="json")}, act)


@router.post("/ops/rfq-clarifications/{clarification_id}/answer", response_model=OpsRfqOut)
async def post_ops_answer(
    clarification_id: uuid.UUID, body: OpsAnswerIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Answer a contractor's question; optionally share it with every contractor who accepted,
    without the asker's identity (QD-17)."""

    async def act() -> OpsRfqOut:
        row = await review.answer_by_ops(
            db, await _who(db, actor), clarification_id, body.answer, body.shared_with_all
        )
        return await _view(db, row.rfq_id)

    return await _once(
        db, actor, key, {"clarification": str(clarification_id), **body.model_dump(mode="json")},
        act,
    )  # fmt: skip


@router.post("/ops/rfq-clarifications/{clarification_id}/close", response_model=OpsRfqOut)
async def post_ops_close(
    clarification_id: uuid.UUID, body: ReasonIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    async def act() -> OpsRfqOut:
        row = await review.close_by_ops(db, await _who(db, actor), clarification_id, body.reason)
        return await _view(db, row.rfq_id)

    return await _once(
        db, actor, key, {"clarification": str(clarification_id), **body.model_dump(mode="json")},
        act,
    )  # fmt: skip


@router.post("/ops/rfqs/{rfq_id}/comparisons", response_model=OpsRfqOut)
async def post_publish(
    rfq_id: uuid.UUID, key: IdempotencyKeyHeader, request: Request, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Publish a comparison version of every current REVIEWED quote, with its PDF. 409
    `details.reason`: NO_REVIEWED_QUOTES; or PACKAGE_REQUIRED."""

    async def act() -> OpsRfqOut:
        await comparison.publish(
            db, _settings(request), request.app.state.storage, await _who(db, actor), rfq_id
        )
        return await _view(db, rfq_id)

    return await _once(db, actor, key, {"rfq": str(rfq_id)}, act)


# --- selection statements (ADMIN) ---------------------------------------------------------


def _statement_out(row: Any) -> StatementOut:
    return StatementOut(
        id=row.id, version=row.version, text=row.text, status=row.status, note=row.note
    )


@router.get("/ops/selection-statements", response_model=list[StatementOut])
async def get_statements(db: DbSession, actor: Annotated[Actor, STAFF]) -> list[StatementOut]:
    """The selection statement versions (QD-12)."""
    return [_statement_out(s) for s in await selection.statements(db)]


@router.post(
    "/admin/selection-statements",
    response_model=StatementOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": StatementOut}},
)
async def post_statement(
    body: StatementIn, key: IdempotencyKeyHeader, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> JSONResponse:
    async def act() -> StatementOut:
        row = await selection.draft_statement(db, await _who(db, actor), body.text, body.note)
        return _statement_out(row)

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


@router.post(
    "/admin/selection-statements/{statement_id}/activate", response_model=list[StatementOut]
)
async def post_activate_statement(
    statement_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> list[StatementOut]:
    who = await _who(db, actor)
    await selection.activate_statement(db, who, statement_id)
    await record(
        db, action="selection_statement.activated", entity_type="selection_statement",
        entity_id=statement_id, actor_type=ActorType.USER, actor_user_id=who.user_id,
        actor_role=who.role, session_id=who.session_id,
    )  # fmt: skip
    return [_statement_out(s) for s in await selection.statements(db)]
