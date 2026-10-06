"""Operations console API (API_ARCHITECTURE 18), admin host only, OPS role with MFA.

The requirement review queue, claim and release, the submission detail with its decision
history, file downloads, and the review decisions (accept, ask for information, cancel)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.catalog.interface import active_eligibility_checklist, eligibility_checklist
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import DbSession
from p2b.core.errors import NotFound
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.storage import DOWNLOAD_URL_TTL_SECONDS
from p2b.core.vocabulary import Audience, EligibilityOutcome, QueueKind, ReviewFlag, StaffRole
from p2b.documents.interface import files_for_staff, staff_download_url
from p2b.identity.interface import Actor, primary_emails, require_actor
from p2b.operations.models import OpsQueueItem
from p2b.operations.schemas import (
    AcceptRequest,
    CancellationRequest,
    EligibilityItemOut,
    EligibilityOut,
    EligibilityResultOut,
    HistoryOut,
    InformationRequest,
    OpsProjectDetail,
    QueueItemOut,
    ReviewProjectOut,
    ReviewQueueEntry,
    ReviewQueuePage,
    ReviewRequirementOut,
    StaffDownloadLink,
    StaffFileOut,
)
from p2b.operations.service import Decision, claim, decide, item_for, open_items, release
from p2b.projects.interface import (
    EligibilityCheck,
    ReviewSnapshot,
    eligibility_assessment,
    review_snapshots,
    status_history,
)

router = APIRouter(tags=["operations"])

OPERATIONS = require_actor(Audience.OPS, mfa=True, roles=[StaffRole.OPS])


def _item(item: OpsQueueItem, actor: Actor, emails: dict[uuid.UUID, str]) -> QueueItemOut:
    return QueueItemOut(
        item_id=item.id,
        state=item.state,
        claimed_by_me=item.claimed_by == actor.user_id,
        claimed_by_email=emails.get(item.claimed_by) if item.claimed_by else None,
        claimed_at=item.claimed_at,
        created_at=item.created_at,
    )


def _project(snapshot: ReviewSnapshot) -> ReviewProjectOut:
    return ReviewProjectOut(
        project_id=snapshot.project_id,
        code=snapshot.code,
        status=snapshot.status,
        locality=snapshot.locality,
        submitted_at=snapshot.submitted_at,
        review_flags=[ReviewFlag(flag) for flag in snapshot.review_flags],
    )


@router.get("/ops/queues/requirement-review", response_model=ReviewQueuePage)
async def get_review_queue(
    db: DbSession,
    actor: Annotated[Actor, OPERATIONS],
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> ReviewQueuePage:
    page = await open_items(db, QueueKind.REQUIREMENT_REVIEW, cursor)
    snapshots = await review_snapshots(db, [item.ref_id for item in page.items])
    claimers = [item.claimed_by for item in page.items if item.claimed_by]
    emails = await primary_emails(db, claimers)
    return ReviewQueuePage(
        entries=[
            ReviewQueueEntry(
                item=_item(item, actor, emails), project=_project(snapshots[item.ref_id])
            )
            for item in page.items
            if item.ref_id in snapshots
        ],
        next_cursor=page.next_cursor,
    )


@router.post("/ops/queue-items/{item_id}/claim", response_model=QueueItemOut)
async def post_claim(
    item_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, OPERATIONS]
) -> QueueItemOut:
    item = await claim(db, actor, item_id)
    return _item(item, actor, await primary_emails(db, [actor.user_id]))


@router.post("/ops/queue-items/{item_id}/release", response_model=QueueItemOut)
async def post_release(
    item_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, OPERATIONS]
) -> QueueItemOut:
    item = await release(db, actor, item_id)
    return _item(item, actor, {})


async def _detail(db: AsyncSession, actor: Actor, project_id: uuid.UUID) -> OpsProjectDetail:
    snapshot = (await review_snapshots(db, [project_id])).get(project_id)
    if snapshot is None:
        raise NotFound
    item = await item_for(db, QueueKind.REQUIREMENT_REVIEW, project_id)
    history = await status_history(db, project_id)
    assessment = await eligibility_assessment(db, project_id)
    checklist = (
        await eligibility_checklist(db, assessment.checklist_version_id)
        if assessment else await active_eligibility_checklist(db)
    )  # fmt: skip
    people = [snapshot.owner_user_id] + ([item.claimed_by] if item and item.claimed_by else [])
    people += [assessment.assessed_by] if assessment else []
    people += [entry.actor_user_id for entry in history if entry.actor_user_id]
    emails = await primary_emails(db, people)
    files = await files_for_staff(db, project_id)
    return OpsProjectDetail(
        project=_project(snapshot),
        city_code=snapshot.city_code,
        created_at=snapshot.created_at,
        owner_email=emails.get(snapshot.owner_user_id),
        requirement=ReviewRequirementOut(
            question_set_version=snapshot.question_set_version, answers=snapshot.answers
        ),
        files=[
            StaffFileOut(
                file_id=f.file_id,
                file_name=f.file_name,
                content_type=f.content_type,
                size_bytes=f.size_bytes,
                state=f.state,
                created_at=f.created_at,
            )
            for f in files
        ],
        queue_item=_item(item, actor, emails) if item else None,
        history=[
            HistoryOut(
                from_status=entry.from_status,
                to_status=entry.to_status,
                actor_email=emails.get(entry.actor_user_id) if entry.actor_user_id else None,
                reason=entry.reason,
                at=entry.at,
            )
            for entry in history
        ],
        eligibility=EligibilityOut(
            checklist_version=checklist.version if checklist else None,
            items=[EligibilityItemOut(id=i.id, label=i.label, help=i.help)
                   for i in (checklist.items if checklist else [])],
            assessment=[
                EligibilityResultOut(item_id=r["item_id"], outcome=EligibilityOutcome(r["outcome"]),
                                     note=r.get("note", ""))
                for r in assessment.results
            ] if assessment else None,
            assessed_by_email=emails.get(assessment.assessed_by) if assessment else None,
            assessed_at=assessment.assessed_at if assessment else None,
        ),
    )  # fmt: skip


@router.get("/ops/projects/{project_id}", response_model=OpsProjectDetail)
async def get_ops_project(
    project_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, OPERATIONS]
) -> OpsProjectDetail:
    return await _detail(db, actor, project_id)


async def _decide(
    db: AsyncSession,
    actor: Actor,
    key: str,
    project_id: uuid.UUID,
    decision: Decision,
    text: str | None = None,
    checks: list[EligibilityCheck] | None = None,
) -> JSONResponse:
    async def act() -> tuple[int, dict[str, object]]:
        await decide(db, actor, project_id, decision, text, checks)
        return 200, (await _detail(db, actor, project_id)).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body={
            "project_id": str(project_id),
            "decision": decision,
            "text": text,
            "checks": [c.__dict__ for c in checks or []],
        },
        action=act,
    )


@router.post("/ops/projects/{project_id}/accept", response_model=OpsProjectDetail)
async def post_accept(
    project_id: uuid.UUID,
    body: AcceptRequest,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, OPERATIONS],
) -> JSONResponse:
    """Accept: Plan2Build has completed its initial service-eligibility review and may offer the
    package (F-05). Needs every checklist item PASSED; creates the workspace, once (rulings 2.2
    to 2.6). Approves no design, budget, professional or whole project."""
    checks = [EligibilityCheck(c.item_id, c.outcome, c.note) for c in body.checks]
    return await _decide(db, actor, key, project_id, "accept", checks=checks)


@router.post("/ops/projects/{project_id}/request-information", response_model=OpsProjectDetail)
async def post_request_information(
    project_id: uuid.UUID,
    body: InformationRequest,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, OPERATIONS],
) -> JSONResponse:
    """Ask the family for more; the requirement reopens for them (ruling 2.7)."""
    return await _decide(db, actor, key, project_id, "ask", body.message)


@router.post("/ops/projects/{project_id}/cancel", response_model=OpsProjectDetail)
async def post_cancel(
    project_id: uuid.UUID,
    body: CancellationRequest,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, OPERATIONS],
) -> JSONResponse:
    """Decline with a reason the family sees (ruling 2.1)."""
    return await _decide(db, actor, key, project_id, "cancel", body.reason)


@router.get("/ops/files/{file_id}/url", response_model=StaffDownloadLink)
async def get_ops_file_url(
    file_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, OPERATIONS]
) -> StaffDownloadLink:
    settings: Settings = request.app.state.settings
    peer = request.client.host if request.client else None
    ip_hash = keyed_hash(
        settings.identifier_pepper.get_secret_value(), client_ip(request.headers, peer)
    )
    url = await staff_download_url(
        db,
        request.app.state.storage,
        viewer_user_id=actor.user_id,
        file_id=file_id,
        ip_hash=ip_hash,
    )
    return StaffDownloadLink(url=url, expires_in_seconds=DOWNLOAD_URL_TTL_SECONDS)
