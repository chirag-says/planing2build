"""Billing exceptions (SLICE3_3_READINESS D, G): payments and refunds billing will not apply
automatically. Each is recorded once per provider reference, alerts operations through the log
(OBSERVABILITY: AMOUNT_MISMATCH pages), and is resolved by staff with a reason. Funds are never
applied by raising or resolving one; a captured payment that was not applied can be refunded
through a refund request."""

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.billing.clock import db_now
from p2b.billing.models import BillingException
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.vocabulary import ActorType, BillingExceptionKind, BillingExceptionState

log = structlog.get_logger(__name__)


async def raise_exception(
    session: AsyncSession,
    kind: BillingExceptionKind,
    *,
    provider: str,
    provider_ref: str,
    expected: dict[str, Any],
    observed: dict[str, Any],
    order_id: uuid.UUID | None = None,
    attempt_id: uuid.UUID | None = None,
    payment_id: uuid.UUID | None = None,
) -> None:
    inserted = await session.execute(
        insert(BillingException)
        .values(
            id=new_id(),
            kind=kind.value,
            provider=provider,
            provider_ref=provider_ref,
            order_id=order_id,
            attempt_id=attempt_id,
            payment_id=payment_id,
            expected=expected,
            observed=observed,
            state=BillingExceptionState.OPEN.value,
        )
        .on_conflict_do_nothing(index_elements=["kind", "provider", "provider_ref"])
        .returning(BillingException.id)
    )
    exception_id = inserted.scalar_one_or_none()
    if exception_id is not None:
        log.error(
            "billing.exception",
            kind=kind.value,
            provider_ref=provider_ref,
            order_id=str(order_id) if order_id else None,
        )
        await record(
            session,
            action="billing.exception_raised",
            entity_type="billing_exception",
            entity_id=exception_id,
            actor_type=ActorType.JOB,
            new_value={"kind": kind.value, "expected": expected, "observed": observed},
        )


async def open_exceptions(session: AsyncSession, *, limit: int = 100) -> list[BillingException]:
    return list(
        await session.scalars(
            select(BillingException)
            .order_by(BillingException.state, BillingException.created_at.desc())
            .limit(limit)
        )
    )


async def resolve_exception(
    session: AsyncSession,
    exception_id: uuid.UUID,
    *,
    resolution: str,
    actor_user_id: uuid.UUID,
    actor_role: str,
    session_id: uuid.UUID,
) -> BillingException:
    text = resolution.strip()
    if not text:
        raise ValidationFailed(details={"fields": {"resolution": ["Say how it was resolved."]}})
    row = await session.get(BillingException, exception_id, with_for_update=True)
    if row is None:
        raise NotFound
    if row.state != BillingExceptionState.OPEN.value:
        raise StateConflict(details={"current_state": row.state})
    row.state = BillingExceptionState.RESOLVED.value
    row.resolution = text[:2000]
    row.resolved_by = actor_user_id
    row.resolved_at = await db_now(session)
    row.version += 1
    await session.flush()
    await record(
        session,
        action="billing.exception_resolved",
        entity_type="billing_exception",
        entity_id=row.id,
        actor_type=ActorType.USER,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        session_id=session_id,
        reason=row.resolution,
    )
    return row
