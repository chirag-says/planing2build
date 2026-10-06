"""Operations work queues (API 18; DATA `ops_queue_items`; EVENT map: `requirement.submitted`
creates a review item). The requirement review queue, claim and release, and the review
decisions (accept, ask for information, cancel; rulings 2.1, 2.6, 2.7). A decision needs the
reviewer's own claim and resolves the item in the same transaction as the project's transition.
"""

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import func, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import ActorType, ProjectStatus, QueueItemState, QueueKind, StaffRole
from p2b.identity.interface import Actor
from p2b.operations.models import OpsQueueItem
from p2b.projects.interface import (
    EligibilityCheck,
    accept_project,
    cancel_project,
    request_information,
    review_snapshots,
)

Q = QueueItemState
# The only writer of ops_queue_items.state (STATE_MODEL 1).
QUEUE_ITEM = TransitionTable[QueueItemState](
    "ops_queue_item",
    [
        Transition(None, Q.OPEN, "enqueue"),
        Transition(Q.OPEN, Q.CLAIMED, "claim"),
        Transition(Q.CLAIMED, Q.OPEN, "release"),
        Transition(Q.CLAIMED, Q.RESOLVED, "resolve"),
    ],
)

REF_PROJECT = "project"
REF_PROFESSIONAL_CATEGORY = "professional_category"
PAGE_SIZE = 50


async def enqueue_review(session: AsyncSession, project_id: uuid.UUID) -> None:
    """Open a review item for a submitted project. Idempotent: the relay delivers at least once."""
    await enqueue(session, QueueKind.REQUIREMENT_REVIEW, REF_PROJECT, project_id)


async def enqueue_professional_review(session: AsyncSession, category_id: uuid.UUID) -> None:
    """Open a review item for a submitted professional category (Slice 3.2). Idempotent."""
    await enqueue(session, QueueKind.PROFESSIONAL_REVIEW, REF_PROFESSIONAL_CATEGORY, category_id)


async def enqueue(session: AsyncSession, kind: QueueKind, ref_type: str, ref_id: uuid.UUID) -> None:
    """At most one open item per reference."""
    await session.execute(
        insert(OpsQueueItem)
        .values(
            id=new_id(),
            kind=kind.value,
            ref_type=ref_type,
            ref_id=ref_id,
            state=QUEUE_ITEM.target(None, "enqueue").value,
        )
        .on_conflict_do_nothing(
            index_elements=["kind", "ref_type", "ref_id"],
            # Literal SQL, not a bound parameter: Postgres matches a partial index only against
            # the predicate's text, and a parameter stops matching once the statement is planned
            # generically (from its sixth execution on a connection).
            index_where=text("state <> 'RESOLVED'"),
        )
    )


@dataclass(frozen=True)
class QueuePage:
    items: list[OpsQueueItem]
    next_cursor: str | None


def _cursor(item: OpsQueueItem) -> str:
    raw = f"{item.created_at.isoformat()}|{item.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _parse_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        created, item_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(created), uuid.UUID(item_id)
    except ValueError:
        raise ValidationFailed(details={"fields": {"cursor": ["Not a valid cursor."]}}) from None


async def open_items(
    session: AsyncSession, kind: QueueKind, cursor: str | None = None, limit: int = PAGE_SIZE
) -> QueuePage:
    """Open and claimed items, oldest first (keyset pages; API 1)."""
    query = select(OpsQueueItem).where(
        OpsQueueItem.kind == kind.value, OpsQueueItem.state != Q.RESOLVED.value
    )
    if cursor:
        created, item_id = _parse_cursor(cursor)
        query = query.where(
            tuple_(OpsQueueItem.created_at, OpsQueueItem.id) > tuple_(created, item_id)
        )
    rows = list(
        await session.scalars(
            query.order_by(OpsQueueItem.created_at, OpsQueueItem.id).limit(limit + 1)
        )
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return QueuePage(rows, _cursor(rows[-1]) if more and rows else None)


async def item_for(
    session: AsyncSession, kind: QueueKind, ref_id: uuid.UUID, *, for_update: bool = False
) -> OpsQueueItem | None:
    query = select(OpsQueueItem).where(
        OpsQueueItem.kind == kind.value,
        OpsQueueItem.ref_id == ref_id,
        OpsQueueItem.state != Q.RESOLVED.value,
    )
    if for_update:
        query = query.with_for_update()
    return (await session.scalars(query)).one_or_none()


async def _locked(session: AsyncSession, item_id: uuid.UUID) -> OpsQueueItem:
    item = await session.get(OpsQueueItem, item_id, with_for_update=True)
    if item is None:
        raise NotFound
    return item


async def _audit(session: AsyncSession, item: OpsQueueItem, actor: Actor, action: str) -> None:
    await record(
        session,
        action=action,
        entity_type="ops_queue_item",
        entity_id=item.id,
        actor_type=ActorType.USER,
        actor_user_id=actor.user_id,
        actor_role=StaffRole.OPS.value,
        session_id=actor.session_id,
        project_id=item.ref_id if item.ref_type == REF_PROJECT else None,
        new_value={"state": item.state},
    )


async def claim(session: AsyncSession, actor: Actor, item_id: uuid.UUID) -> OpsQueueItem:
    """Take an item. Claiming your own item again is a no-op; another person's is 409."""
    item = await _locked(session, item_id)
    if item.state == Q.CLAIMED.value and item.claimed_by == actor.user_id:
        return item
    if item.state == Q.CLAIMED.value:
        raise StateConflict(details={"current_state": item.state, "claimed": True})
    item.state = QUEUE_ITEM.target(QueueItemState(item.state), "claim").value
    item.claimed_by = actor.user_id
    item.claimed_at = (await session.execute(select(func.now()))).scalar_one()
    item.version += 1
    await session.flush()
    await _audit(session, item, actor, "ops_queue_item.claimed")
    return item


async def release(session: AsyncSession, actor: Actor, item_id: uuid.UUID) -> OpsQueueItem:
    """Give an item back. Only the person who claimed it can release it."""
    item = await _locked(session, item_id)
    if item.state != Q.CLAIMED.value or item.claimed_by != actor.user_id:
        raise StateConflict(details={"current_state": item.state})
    item.state = QUEUE_ITEM.target(Q.CLAIMED, "release").value
    item.claimed_by = None
    item.claimed_at = None
    item.version += 1
    await session.flush()
    await _audit(session, item, actor, "ops_queue_item.released")
    return item


async def claimed_item(
    session: AsyncSession, actor: Actor, kind: QueueKind, ref_id: uuid.UUID
) -> OpsQueueItem:
    """The open item for the reference, which must be claimed by the actor (409 otherwise)."""
    item = await item_for(session, kind, ref_id, for_update=True)
    if item is None or item.state != Q.CLAIMED.value or item.claimed_by != actor.user_id:
        raise StateConflict(
            details={"current_state": item.state if item else None, "claim": "required"}
        )
    return item


async def resolve(
    session: AsyncSession, actor: Actor, item: OpsQueueItem, decision: str, *,
    project_id: uuid.UUID | None = None,
) -> None:  # fmt: skip
    item.state = QUEUE_ITEM.target(Q.CLAIMED, "resolve").value
    item.claimed_by = None
    item.claimed_at = None
    item.resolved_by = actor.user_id
    item.resolved_at = (await session.execute(select(func.now()))).scalar_one()
    item.version += 1
    await session.flush()
    await record(
        session,
        action="ops_queue_item.resolved",
        entity_type="ops_queue_item",
        entity_id=item.id,
        actor_type=ActorType.USER,
        actor_user_id=actor.user_id,
        actor_role=StaffRole.OPS.value,
        session_id=actor.session_id,
        project_id=project_id,
        new_value={"state": item.state, "decision": decision},
    )


Decision = Literal["accept", "ask", "cancel"]
# Where each decision leads; a repeat that finds the project already there is a no-op.
OUTCOME: dict[Decision, ProjectStatus] = {
    "accept": ProjectStatus.ACCEPTED,
    "ask": ProjectStatus.NEEDS_INFO,
    "cancel": ProjectStatus.CANCELLED,
}


async def decide(
    session: AsyncSession,
    actor: Actor,
    project_id: uuid.UUID,
    decision: Decision,
    text: str | None = None,
    checks: list[EligibilityCheck] | None = None,
) -> None:
    """Apply a review decision; accepting needs the eligibility checklist (F-05). The
    submission must be claimed by this reviewer. A repeated
    accept or cancel after success changes nothing; a NEEDS_INFO project (no open review item)
    can still be cancelled (STATE_MODEL 5)."""
    item = await item_for(session, QueueKind.REQUIREMENT_REVIEW, project_id, for_update=True)
    if item is None:
        snapshot = (await review_snapshots(session, [project_id])).get(project_id)
        if snapshot is None:
            raise NotFound
        repeat = decision in ("accept", "cancel") and snapshot.status == OUTCOME[decision]
        if repeat:
            return
        if not (decision == "cancel" and snapshot.status == ProjectStatus.NEEDS_INFO):
            raise StateConflict(details={"current_state": snapshot.status, "review": "none open"})
    elif item.state != Q.CLAIMED.value or item.claimed_by != actor.user_id:
        raise StateConflict(details={"current_state": item.state, "claim": "required"})

    if decision == "accept":
        await accept_project(session, actor, project_id, checks or [])
    elif decision == "ask":
        await request_information(session, actor, project_id, message=text or "")
    else:
        await cancel_project(session, actor, project_id, reason=text or "")

    if item is not None:
        await resolve(session, actor, item, decision, project_id=project_id)
