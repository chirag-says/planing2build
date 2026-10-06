"""Operations: professional review (Slice 3.2; SLICE3_2_READINESS K0), admin host only.

The review queue, the verification detail with evidence, recording checks, the decisions
(approve, request changes, reject; the reviewer's own claim needed), suspension and
reinstatement (OPS or ADMIN, D-10), portfolio review, and creating a professional's account
(D-04). Every action needs a fresh second factor and is audited."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from p2b.core.db import DbSession
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.vocabulary import Audience, ListingState, QueueKind, StaffRole, VerificationDecision
from p2b.identity.interface import (
    Actor,
    active_roles,
    create_account_for,
    primary_emails,
    require_actor,
)
from p2b.operations.service import claimed_item, item_for, open_items, resolve
from p2b.professionals.interface import (
    CheckIn,
    CreatedProfessionalOut,
    CreateProfessionalIn,
    DecisionIn,
    ReasonIn,
    ReviewDetailOut,
    ReviewItemOut,
    ReviewQueueEntryOut,
    ReviewQueueOut,
    categories_in_states,
    category_names,
    create_profile_for,
    decide,
    queue_rows,
    record_check,
    review_detail,
    review_detail_out,
    review_portfolio_item,
    suspend_or_reinstate,
)

router = APIRouter(tags=["operations"])

OPERATIONS = require_actor(Audience.OPS, mfa=True, roles=[StaffRole.OPS])
STAFF = require_actor(Audience.OPS, mfa=True, roles=[StaffRole.OPS, StaffRole.ADMIN])
KIND = QueueKind.PROFESSIONAL_REVIEW


@router.get("/ops/queues/professional-review", response_model=ReviewQueueOut)
async def get_professional_queue(
    db: DbSession,
    actor: Annotated[Actor, OPERATIONS],
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> ReviewQueueOut:
    """Categories waiting for review, oldest first."""
    page = await open_items(db, KIND, cursor)
    rows = await queue_rows(db, [item.ref_id for item in page.items])
    return ReviewQueueOut(
        entries=[
            ReviewQueueEntryOut(
                item_id=item.id,
                category_id=item.ref_id,
                display_name=rows[item.ref_id].display_name,
                firm_name=rows[item.ref_id].firm_name,
                category_code=rows[item.ref_id].category_code,
                listing_state=ListingState(rows[item.ref_id].listing_state),
                submitted_at=rows[item.ref_id].submitted_at,
                claimed_by_me=item.claimed_by == actor.user_id,
                claimed=item.claimed_by is not None,
            )
            for item in page.items
            if item.ref_id in rows
        ],
        next_cursor=page.next_cursor,
    )


@router.get("/ops/professionals", response_model=list[ReviewQueueEntryOut])
async def get_professionals(
    db: DbSession,
    actor: Annotated[Actor, STAFF],
    state: Annotated[ListingState, Query()] = ListingState.LISTED,
) -> list[ReviewQueueEntryOut]:
    """Categories in one listing state (for suspension and reinstatement), newest first."""
    return [
        ReviewQueueEntryOut(
            item_id=None,
            category_id=row.category_id,
            display_name=row.display_name,
            firm_name=row.firm_name,
            category_code=row.category_code,
            listing_state=ListingState(row.listing_state),
            submitted_at=row.submitted_at,
            claimed_by_me=False,
            claimed=False,
        )
        for row in await categories_in_states(db, [state])
    ]


async def _detail(db: DbSession, actor: Actor, category_id: uuid.UUID) -> ReviewDetailOut:
    detail = await review_detail(db, category_id)
    item = await item_for(db, KIND, category_id)
    user_ids = {c.recorded_by for c in detail.checks}
    user_ids |= {h.actor_user_id for h in detail.history if h.actor_user_id}
    user_ids |= {detail.profile.user_id}
    if item and item.claimed_by:
        user_ids.add(item.claimed_by)
    emails = await primary_emails(db, list(user_ids))
    queue_item = (
        ReviewItemOut(
            item_id=item.id,
            state=item.state,
            claimed_by_me=item.claimed_by == actor.user_id,
            claimed_by_email=emails.get(item.claimed_by) if item.claimed_by else None,
        )
        if item
        else None
    )
    return review_detail_out(
        detail,
        names=await category_names(db),
        emails=emails,
        email=emails.get(detail.profile.user_id),
        queue_item=queue_item,
    )


@router.get("/ops/professional-categories/{category_id}", response_model=ReviewDetailOut)
async def get_professional_category(
    category_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, STAFF]
) -> ReviewDetailOut:
    """Everything operations need to decide: profile, contact email, requirements, evidence
    (documents open through logged signed links), references, recorded checks and history."""
    return await _detail(db, actor, category_id)


@router.post("/ops/professional-categories/{category_id}/checks", response_model=ReviewDetailOut)
async def post_check(
    category_id: uuid.UUID, body: CheckIn, db: DbSession, actor: Annotated[Actor, OPERATIONS]
) -> ReviewDetailOut:
    """Record one check result; needs your claim on the review."""
    await claimed_item(db, actor, KIND, category_id)
    await record_check(
        db,
        actor,
        category_id,
        kind=body.kind,
        subject=body.subject,
        outcome=body.outcome,
        detail=body.detail,
        note=body.note,
    )
    return await _detail(db, actor, category_id)


DECISIONS: dict[str, VerificationDecision] = {
    "approve": VerificationDecision.APPROVED,
    "request-changes": VerificationDecision.CHANGES_REQUESTED,
    "reject": VerificationDecision.REJECTED,
}


async def _decide(
    db: DbSession,
    actor: Actor,
    category_id: uuid.UUID,
    action: str,
    body: DecisionIn,
    key: str,
) -> JSONResponse:
    async def act() -> tuple[int, dict[str, object]]:
        item = await claimed_item(db, actor, KIND, category_id)
        await decide(
            db, actor, category_id, DECISIONS[action], message=body.message, note=body.note
        )
        await resolve(db, actor, item, action)
        return 200, (await _detail(db, actor, category_id)).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body={
            "category_id": str(category_id),
            "action": action,
            **body.model_dump(mode="json"),
        },
        action=act,
    )


@router.post(
    "/ops/professional-categories/{category_id}/approve",
    response_model=ReviewDetailOut,
    responses={200: {"model": ReviewDetailOut}},
)
async def post_approve(
    category_id: uuid.UUID,
    body: DecisionIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, OPERATIONS],
) -> JSONResponse:
    """List the category. 409 unless every requirement has a recorded check."""
    return await _decide(db, actor, category_id, "approve", body, key)


@router.post(
    "/ops/professional-categories/{category_id}/request-changes",
    response_model=ReviewDetailOut,
    responses={200: {"model": ReviewDetailOut}},
)
async def post_request_changes(
    category_id: uuid.UUID,
    body: DecisionIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, OPERATIONS],
) -> JSONResponse:
    """Send the category back with a message the professional sees."""
    return await _decide(db, actor, category_id, "request-changes", body, key)


@router.post(
    "/ops/professional-categories/{category_id}/reject",
    response_model=ReviewDetailOut,
    responses={200: {"model": ReviewDetailOut}},
)
async def post_reject(
    category_id: uuid.UUID,
    body: DecisionIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, OPERATIONS],
) -> JSONResponse:
    """Reject with a message the professional sees; they may reapply after the waiting time."""
    return await _decide(db, actor, category_id, "reject", body, key)


async def _suspension(
    db: DbSession,
    actor: Actor,
    category_id: uuid.UUID,
    action: Literal["suspend", "reinstate"],
    body: ReasonIn,
) -> ReviewDetailOut:
    role: Literal["OPS", "ADMIN"] = (
        "OPS" if StaffRole.OPS in await active_roles(db, actor.user_id) else "ADMIN"
    )
    await suspend_or_reinstate(db, actor, category_id, action=action, reason=body.reason, role=role)
    return await _detail(db, actor, category_id)


@router.post("/ops/professional-categories/{category_id}/suspend", response_model=ReviewDetailOut)
async def post_suspend(
    category_id: uuid.UUID, body: ReasonIn, db: DbSession, actor: Annotated[Actor, STAFF]
) -> ReviewDetailOut:
    """Take a listed category out of public view (D-10). Everything is kept."""
    return await _suspension(db, actor, category_id, "suspend", body)


@router.post("/ops/professional-categories/{category_id}/reinstate", response_model=ReviewDetailOut)
async def post_reinstate(
    category_id: uuid.UUID, body: ReasonIn, db: DbSession, actor: Annotated[Actor, STAFF]
) -> ReviewDetailOut:
    return await _suspension(db, actor, category_id, "reinstate", body)


@router.post("/ops/portfolio-items/{item_id}/{verdict}", response_model=dict[str, str])
async def post_portfolio_review(
    item_id: uuid.UUID,
    verdict: Literal["approve", "reject"],
    db: DbSession,
    actor: Annotated[Actor, OPERATIONS],
) -> dict[str, str]:
    """Only approved portfolio images are ever public."""
    item = await review_portfolio_item(db, actor, item_id, approve=verdict == "approve")
    return {"review_state": item.review_state}


@router.post(
    "/ops/professionals",
    response_model=CreatedProfessionalOut,
    responses={200: {"model": CreatedProfessionalOut}},
)
async def post_create_professional(
    body: CreateProfessionalIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, OPERATIONS],
) -> JSONResponse:
    """Create a professional's account and draft profile (D-04). They sign in with the emailed
    code on the professionals host and go through the same review as everyone else."""

    async def act() -> tuple[int, dict[str, object]]:
        user_id, created = await create_account_for(
            db, audience=Audience.PRO, email=body.email, created_by=actor.user_id
        )
        profile = await create_profile_for(
            db, user_id=user_id, created_by=actor.user_id, display_name=body.display_name
        )
        out = CreatedProfessionalOut(user_id=user_id, profile_id=profile.id, created=created)
        return 200, out.model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body=body.model_dump(mode="json"),
        action=act,
    )
