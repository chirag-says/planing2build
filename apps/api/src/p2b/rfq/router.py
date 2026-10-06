"""RFQ routes for the homeowner (homeowner host) and the invited contractor (professionals
host). Creating and transition POSTs take an `Idempotency-Key`. A contractor reaches only its own
invitation; every other id is 404 (SECURITY 4.2). The homeowner sees prices only in a published
comparison (QD-07). Downloads are signed-in and logged; there is no share link (QD-23)."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from p2b.buildplan.interface import accepted_manifest
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import DbSession
from p2b.core.errors import NotFound
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.ratelimit import Limit, enforce
from p2b.core.vocabulary import (
    Audience,
    ComparisonState,
    FilePurpose,
    InvitationState,
    OtpPurpose,
    RfqCancelReason,
    RfqState,
)
from p2b.documents.interface import (
    complete_project_file_upload,
    create_project_file_upload,
    file_facts,
    project_file_url,
)
from p2b.identity.interface import Actor, require_actor, start_confirmation
from p2b.professionals.interface import profile_by_user
from p2b.rfq import quotes, review, rfqs, selection
from p2b.rfq.common import family, family_access, professional
from p2b.rfq.models import Comparison, QuoteVersion, Rfq, RfqInvitation
from p2b.rfq.schemas import (
    AnswerIn,
    CancelIn,
    ChallengeOut,
    DeclineIn,
    DownloadOut,
    FamilyRfqOut,
    FamilyRfqsOut,
    FileOut,
    InvitationAcceptIn,
    ProInvitationOut,
    ProInvitationsOut,
    QuestionIn,
    QuoteDraftIn,
    QuoteIn,
    ReasonIn,
    RenewIn,
    RfqRequestIn,
    SelectIn,
    SelectionCodeIn,
    UploadIn,
    UploadTicketOut,
)
from p2b.rfq.views import (
    family_rfqs_out,
    pro_invitation_out,
    pro_summaries,
)

router = APIRouter(tags=["rfq"])

HOMEOWNER = require_actor(Audience.IHB)
PROFESSIONAL = require_actor(Audience.PRO)
QUOTE_LIMIT = Limit("rfq_quotes_session", 30, 600)  # T2
QUESTION_LIMIT = Limit("rfq_questions_session", 20, 600)  # T2
UPLOAD_LIMIT = Limit("rfq_uploads_session", 30, 60)  # T3


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


# --- the homeowner -------------------------------------------------------------------------


async def _family_view(
    db: DbSession, request: Request, actor: Actor, project_id: uuid.UUID
) -> FamilyRfqsOut:
    facts = await family_access(db, actor, project_id, write=False)
    baseline = await accepted_manifest(db, project_id)
    return await family_rfqs_out(
        db, _settings(request), actor, facts, baseline.version_no if baseline else None
    )


async def _family_rfq(db: DbSession, project_id: uuid.UUID, rfq_id: uuid.UUID) -> Rfq:
    rfq = await db.get(Rfq, rfq_id)
    if rfq is None or rfq.project_id != project_id:
        raise NotFound
    return rfq


@router.get("/projects/{project_id}/rfqs", response_model=FamilyRfqsOut)
async def get_rfqs(
    project_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> FamilyRfqsOut:
    """Requests for contractor quotes: status, contractors and quote versions; prices only in a
    published comparison."""
    return await _family_view(db, request, actor, project_id)


@router.post(
    "/projects/{project_id}/rfqs",
    response_model=FamilyRfqsOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": FamilyRfqsOut}},
)
async def post_rfq(
    project_id: uuid.UUID,
    body: RfqRequestIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """Ask Plan2Build for contractor quotes on the accepted Build Plan, nominating listed
    contractors. 409 `details.reason`: NO_ACCEPTED_VERSION, OPEN_RFQ, NOT_NEEDED, ENGAGED,
    NOT_LISTED, OUTSIDE_AREA, NO_LOCATION, SELF, DUPLICATE, LIMIT; or PACKAGE_REQUIRED."""

    async def act() -> FamilyRfqsOut:
        facts = await family_access(db, actor, project_id, write=True)
        await rfqs.request(db, _settings(request), family(actor), facts, body.profile_ids)
        return await _family_view(db, request, actor, project_id)

    return await _once(
        db, actor, key, {"project": str(project_id), **body.model_dump(mode="json")}, act, 201
    )


@router.post("/projects/{project_id}/rfqs/{rfq_id}/cancel", response_model=FamilyRfqsOut)
async def post_cancel_rfq(
    project_id: uuid.UUID,
    rfq_id: uuid.UUID,
    body: CancelIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """Withdraw the request. Allowed without a package: it stops coordination."""

    async def act() -> FamilyRfqsOut:
        await family_access(db, actor, project_id, write=True)
        rfq = await _family_rfq(db, project_id, rfq_id)
        rfq = await rfqs.rfq_row(db, rfq.id, lock=True)
        await rfqs.cancel(db, family(actor), rfq, RfqCancelReason.OWNER, body.note)
        return await _family_view(db, request, actor, project_id)

    return await _once(db, actor, key, {"rfq": str(rfq_id), **body.model_dump(mode="json")}, act)


@router.get("/projects/{project_id}/rfqs/{rfq_id}", response_model=FamilyRfqOut)
async def get_rfq(
    project_id: uuid.UUID, rfq_id: uuid.UUID, request: Request, db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> FamilyRfqOut:  # fmt: skip
    view = await _family_view(db, request, actor, project_id)
    rfq = await _family_rfq(db, project_id, rfq_id)
    return next(r for r in view.rfqs if r.id == rfq.id)


@router.get(
    "/projects/{project_id}/rfqs/{rfq_id}/comparisons/{comparison_id}/document",
    response_model=DownloadOut,
)
async def get_comparison_document(
    project_id: uuid.UUID,
    rfq_id: uuid.UUID,
    comparison_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> DownloadOut:
    """The comparison PDF (logged; owner and household)."""
    await family_access(db, actor, project_id, write=False)
    row = await db.get(Comparison, comparison_id)
    if row is None or row.rfq_id != rfq_id or row.project_id != project_id:
        raise NotFound
    url = await project_file_url(
        db, request.app.state.storage, project_id=project_id, file_id=row.document_file_id,
        purposes=frozenset({FilePurpose.COMPARISON_DOCUMENT}), viewer_user_id=actor.user_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)


@router.get("/projects/{project_id}/rfqs/{rfq_id}/files/{file_id}/url", response_model=DownloadOut)
async def get_family_quote_file(
    project_id: uuid.UUID,
    rfq_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> DownloadOut:
    """An attachment of a quote that is in a published comparison (logged). Never before."""
    await family_access(db, actor, project_id, write=False)
    rfq = await _family_rfq(db, project_id, rfq_id)
    published = await db.scalars(
        select(Comparison.quote_version_ids).where(
            Comparison.rfq_id == rfq.id,
            Comparison.state.in_(
                (ComparisonState.PUBLISHED.value, ComparisonState.SUPERSEDED.value,
                 ComparisonState.DECIDED.value)
            ),
        )
    )  # fmt: skip
    version_ids = {v for ids in published for v in ids}
    attached = {
        f
        for files in await db.scalars(
            select(QuoteVersion.attachment_file_ids).where(QuoteVersion.id.in_(version_ids))
        )
        for f in files
    } if version_ids else set()  # fmt: skip
    if file_id not in attached:
        raise NotFound
    url = await project_file_url(
        db, request.app.state.storage, project_id=project_id, file_id=file_id,
        purposes=frozenset({FilePurpose.QUOTE_ATTACHMENT}), viewer_user_id=actor.user_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)


@router.post("/projects/{project_id}/rfqs/{rfq_id}/selection-code", response_model=ChallengeOut)
async def post_selection_code(
    project_id: uuid.UUID,
    rfq_id: uuid.UUID,
    body: SelectionCodeIn,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> ChallengeOut:
    """Send a one-time code to the owner's email to confirm selecting this exact quote version;
    the response carries the statement to confirm."""
    facts = await family_access(db, actor, project_id, write=True)
    _, _, qv, inv = await selection.selectable(db, rfq_id, project_id, body.quote_version_id)
    statement, text = await selection.statement_text(db, facts, qv, inv)
    started = await start_confirmation(
        request.app.state.database, _settings(request), user_id=actor.user_id,
        audience=Audience.IHB, purpose=OtpPurpose.SELECT_QUOTE, subject_id=qv.id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return ChallengeOut(
        challenge_id=started.challenge_id, sent_to=started.sent_to, expires_at=started.expires_at,
        statement_id=statement.id, statement_version=statement.version, statement_text=text,
    )  # fmt: skip


@router.post("/projects/{project_id}/rfqs/{rfq_id}/select", response_model=FamilyRfqsOut)
async def post_select(
    project_id: uuid.UUID,
    rfq_id: uuid.UUID,
    body: SelectIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """Select one quote version with the one-time code (QD-12). The contractor is engaged for
    contractor work; Plan2Build is not a party to the contract and receives no money. 409
    `details.reason`: NO_COMPARISON, STALE, EXPIRED, NOT_LISTED, ENGAGED, STATEMENT_CHANGED."""

    async def act() -> FamilyRfqsOut:
        facts = await family_access(db, actor, project_id, write=True)
        await selection.select_quote(
            db, request.app.state.database, _settings(request), actor, facts, rfq_id,
            quote_version_id=body.quote_version_id, challenge_id=body.challenge_id,
            code=body.code, statement_id=body.statement_id, contact_name=body.contact_name,
            contact_phone=body.contact_phone, ip_hash=_ip_hash(request),
        )  # fmt: skip
        return await _family_view(db, request, actor, project_id)

    return await _once(
        db, actor, key, {"rfq": str(rfq_id), "challenge": str(body.challenge_id)}, act
    )


# --- the contractor ------------------------------------------------------------------------


@router.get("/pro/rfq-invitations", response_model=ProInvitationsOut)
async def get_invitations(
    db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> ProInvitationsOut:
    """Requests to quote sent to you, newest first."""
    profile_id = await profile_by_user(db, actor.user_id)
    if profile_id is None:
        raise NotFound
    rows = list(
        await db.scalars(
            select(RfqInvitation)
            .where(
                RfqInvitation.profile_id == profile_id,
                RfqInvitation.state != InvitationState.PROPOSED.value,
            )
            .order_by(RfqInvitation.sent_at.desc())
            .limit(200)
        )
    )
    return ProInvitationsOut(items=await pro_summaries(db, rows))


@router.get("/pro/rfq-invitations/{invitation_id}", response_model=ProInvitationOut)
async def get_invitation(
    invitation_id: uuid.UUID, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> ProInvitationOut:  # fmt: skip
    """The brief before you accept; the pack, your quote versions and the clarifications you may
    see after. Never another contractor's information or Plan2Build's rates."""
    inv = await rfqs.own_invitation(db, actor, invitation_id)
    return await pro_invitation_out(db, _settings(request), inv)


async def _pro_once(
    db: DbSession, request: Request, actor: Actor, key: str, invitation_id: uuid.UUID,
    body: dict[str, Any], change: Callable[[], Awaitable[object]], code: int = 200,
) -> JSONResponse:  # fmt: skip
    async def act() -> ProInvitationOut:
        await change()
        inv = await rfqs.own_invitation(db, actor, invitation_id)
        return await pro_invitation_out(db, _settings(request), inv)

    return await _once(db, actor, key, {"invitation": str(invitation_id), **body}, act, code)


@router.post("/pro/rfq-invitations/{invitation_id}/accept", response_model=ProInvitationOut)
async def post_accept_invitation(
    invitation_id: uuid.UUID, body: InvitationAcceptIn, key: IdempotencyKeyHeader,
    request: Request, db: DbSession, actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    """Agree to prepare a quote. This is not an engagement. 409 `details.reason`: EXPIRED,
    RFQ_CLOSED, DEADLINE_PASSED, NOT_LISTED; or PACKAGE_REQUIRED."""
    return await _pro_once(
        db, request, actor, key, invitation_id, body.model_dump(mode="json"),
        lambda: rfqs.accept(db, actor, professional(actor), invitation_id, body.phone),
    )  # fmt: skip


@router.post("/pro/rfq-invitations/{invitation_id}/decline", response_model=ProInvitationOut)
async def post_decline_invitation(
    invitation_id: uuid.UUID, body: DeclineIn, key: IdempotencyKeyHeader, request: Request,
    db: DbSession, actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    return await _pro_once(
        db, request, actor, key, invitation_id, body.model_dump(mode="json"),
        lambda: rfqs.decline(db, actor, professional(actor), invitation_id, body.reason,
                             body.note),
    )  # fmt: skip


@router.get(
    "/pro/rfq-invitations/{invitation_id}/drawings/{file_id}/url", response_model=DownloadOut
)
async def get_pack_drawing(
    invitation_id: uuid.UUID, file_id: uuid.UUID, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> DownloadOut:  # fmt: skip
    """A drawing of the frozen pack (logged), while your invitation is accepted and the RFQ is
    open, or once your quote was selected."""
    inv = await rfqs.own_invitation(db, actor, invitation_id)
    view = await pro_invitation_out(db, _settings(request), inv)
    if view.pack is None or file_id not in {d.file_id for d in view.pack.drawings}:
        raise NotFound
    url = await project_file_url(
        db, request.app.state.storage, project_id=inv.project_id, file_id=file_id,
        purposes=frozenset({FilePurpose.DRAWING}), viewer_user_id=actor.user_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)


@router.put("/pro/rfq-invitations/{invitation_id}/quote-draft", response_model=ProInvitationOut)
async def put_quote_draft(
    invitation_id: uuid.UUID, body: QuoteDraftIn, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> ProInvitationOut:  # fmt: skip
    """Save your working copy (private; not a submission)."""
    await quotes.save_draft(db, actor, invitation_id, body)
    inv = await rfqs.own_invitation(db, actor, invitation_id)
    return await pro_invitation_out(db, _settings(request), inv)


@router.delete("/pro/rfq-invitations/{invitation_id}/quote-draft", response_model=ProInvitationOut)
async def delete_quote_draft(
    invitation_id: uuid.UUID, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> ProInvitationOut:  # fmt: skip
    await quotes.discard_draft(db, actor, invitation_id)
    inv = await rfqs.own_invitation(db, actor, invitation_id)
    return await pro_invitation_out(db, _settings(request), inv)


@router.post(
    "/pro/rfq-invitations/{invitation_id}/quotes",
    response_model=ProInvitationOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": ProInvitationOut}},
)
async def post_quote(
    invitation_id: uuid.UUID, body: QuoteIn, key: IdempotencyKeyHeader, request: Request,
    db: DbSession, actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    """Submit a quote version: every line priced or excluded with a reason; amounts are computed
    from the RFQ quantities. A new version supersedes the previous. 422 lists the lines to fix;
    409 `details.reason`: DEADLINE_PASSED, RFQ_CLOSED, NOT_LISTED."""
    await enforce(request.app.state.database, QUOTE_LIMIT, str(actor.session_id))
    return await _pro_once(
        db, request, actor, key, invitation_id, body.model_dump(mode="json"),
        lambda: quotes.submit(db, _settings(request), actor, professional(actor), invitation_id,
                              body),
        201,
    )  # fmt: skip


@router.post("/pro/rfq-invitations/{invitation_id}/quote/renew", response_model=ProInvitationOut)
async def post_renew(
    invitation_id: uuid.UUID, body: RenewIn, key: IdempotencyKeyHeader, request: Request,
    db: DbSession, actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    """After expiry: the same quote with new validity dates (QD-06)."""
    return await _pro_once(
        db, request, actor, key, invitation_id, body.model_dump(mode="json"),
        lambda: quotes.renew(db, _settings(request), actor, professional(actor), invitation_id,
                             body.valid_from, body.valid_to),
    )  # fmt: skip


@router.post("/pro/rfq-invitations/{invitation_id}/quote/withdraw", response_model=ProInvitationOut)
async def post_withdraw_quote(
    invitation_id: uuid.UUID, body: ReasonIn, key: IdempotencyKeyHeader, request: Request,
    db: DbSession, actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    return await _pro_once(
        db, request, actor, key, invitation_id, body.model_dump(mode="json"),
        lambda: quotes.withdraw(db, actor, professional(actor), invitation_id, body.reason),
    )  # fmt: skip


@router.post("/pro/rfq-invitations/{invitation_id}/clarifications", response_model=ProInvitationOut)
async def post_question(
    invitation_id: uuid.UUID, body: QuestionIn, key: IdempotencyKeyHeader, request: Request,
    db: DbSession, actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    """Ask Plan2Build about the pack. Never a channel to the homeowner (QD-17)."""
    await enforce(request.app.state.database, QUESTION_LIMIT, str(actor.session_id))
    return await _pro_once(
        db, request, actor, key, invitation_id, body.model_dump(mode="json"),
        lambda: review.contractor_asks(db, actor, professional(actor), invitation_id,
                                       body.question),
    )  # fmt: skip


@router.post(
    "/pro/rfq-invitations/{invitation_id}/clarifications/{clarification_id}/answer",
    response_model=ProInvitationOut,
)
async def post_answer(
    invitation_id: uuid.UUID, clarification_id: uuid.UUID, body: AnswerIn,
    key: IdempotencyKeyHeader, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    """Answer Plan2Build's question. An answer never changes your quote: submit a new version."""
    return await _pro_once(
        db, request, actor, key, invitation_id,
        {"clarification": str(clarification_id), **body.model_dump(mode="json")},
        lambda: review.answer_by_contractor(db, actor, professional(actor), invitation_id,
                                            clarification_id, body.answer),
    )  # fmt: skip


@router.post(
    "/pro/rfq-invitations/{invitation_id}/attachments",
    response_model=UploadTicketOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_attachment(
    invitation_id: uuid.UUID, body: UploadIn, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> UploadTicketOut:  # fmt: skip
    """A presigned upload of a quote attachment, scanned before use."""
    await enforce(request.app.state.database, UPLOAD_LIMIT, str(actor.session_id))
    inv = await rfqs.own_invitation(db, actor, invitation_id)
    if inv.state != InvitationState.ACCEPTED.value:
        raise NotFound
    rfq = await rfqs.rfq_row(db, inv.rfq_id)
    if rfq.state != RfqState.ISSUED.value:
        raise NotFound
    summary, ticket = await create_project_file_upload(
        db, _settings(request), request.app.state.storage, uploader_user_id=actor.user_id,
        project_id=inv.project_id, purpose=FilePurpose.QUOTE_ATTACHMENT,
        original_name=body.file_name, content_type=body.content_type, size_bytes=body.size_bytes,
    )  # fmt: skip
    return UploadTicketOut(
        file=FileOut(
            file_id=summary.file_id, file_name=summary.file_name,
            content_type=summary.content_type, size_bytes=summary.size_bytes,
            state=summary.state,
        ),
        upload_url=ticket.url, headers=ticket.headers,
    )  # fmt: skip


@router.post(
    "/pro/rfq-invitations/{invitation_id}/attachments/{file_id}/complete", response_model=FileOut
)
async def post_attachment_complete(
    invitation_id: uuid.UUID, file_id: uuid.UUID, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> FileOut:  # fmt: skip
    await rfqs.own_invitation(db, actor, invitation_id)
    summary = await complete_project_file_upload(
        db, request.app.state.storage, uploader_user_id=actor.user_id, file_id=file_id
    )
    return FileOut(
        file_id=summary.file_id, file_name=summary.file_name, content_type=summary.content_type,
        size_bytes=summary.size_bytes, state=summary.state,
    )  # fmt: skip


@router.get("/pro/rfq-invitations/{invitation_id}/files/{file_id}/url", response_model=DownloadOut)
async def get_own_attachment(
    invitation_id: uuid.UUID, file_id: uuid.UUID, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> DownloadOut:  # fmt: skip
    """Your own quote attachment, uploaded by you or attached to one of your versions."""
    inv = await rfqs.own_invitation(db, actor, invitation_id)
    mine = {
        f
        for files in await db.scalars(
            select(QuoteVersion.attachment_file_ids).where(QuoteVersion.invitation_id == inv.id)
        )
        for f in files
    }
    fact = (await file_facts(db, [file_id])).get(file_id)
    if file_id not in mine and (fact is None or fact.owner_user_id != actor.user_id):
        raise NotFound
    url = await project_file_url(
        db, request.app.state.storage, project_id=inv.project_id, file_id=file_id,
        purposes=frozenset({FilePurpose.QUOTE_ATTACHMENT}), viewer_user_id=actor.user_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)
