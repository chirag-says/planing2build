"""The package on a project (L-05, L-06): NOT_ACTIVE (no row) -> ACTIVE on the first verified
capture -> CANCELLED or REFUNDED by a staff decision. Activation opens the package services the
family chooses; it never changes the project's status or any professional relationship."""

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.billing.clock import db_now
from p2b.billing.models import (
    Order,
    PackageEntitlement,
    PackageEntitlementHistory,
    PackageServiceUsage,
    PaymentDue,
)
from p2b.core.errors import NotFound
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import ActorType, DueRule, DueState, PackageServiceKind, PackageState

E = PackageState
ENTITLEMENT = TransitionTable[PackageState](
    "package_entitlement",
    [
        Transition(None, E.ACTIVE, "activate"),
        Transition(E.ACTIVE, E.CANCELLED, "cancel"),
        Transition(E.ACTIVE, E.REFUNDED, "refund"),
    ],
)


class PackageChanged(EventPayload):
    project_id: uuid.UUID
    entitlement_id: uuid.UUID
    state: PackageState


async def _history(
    session: AsyncSession,
    entitlement: PackageEntitlement,
    old: PackageState | None,
    reason: str | None,
    actor_user_id: uuid.UUID | None,
    actor_role: str,
) -> None:
    session.add(
        PackageEntitlementHistory(
            id=new_id(),
            entitlement_id=entitlement.id,
            from_state=old.value if old else None,
            to_state=entitlement.state,
            reason=reason,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
    )
    await session.flush()
    await record(
        session,
        action=f"package.{entitlement.state.lower()}",
        entity_type="package_entitlement",
        entity_id=entitlement.id,
        project_id=entitlement.project_id,
        actor_type=ActorType.USER if actor_user_id else ActorType.JOB,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        reason=reason,
        old_value={"state": old.value if old else PackageState.NOT_ACTIVE.value},
        new_value={"state": entitlement.state},
    )
    await publish(
        session,
        event_type="billing.package_changed",
        aggregate_type="package_entitlement",
        aggregate_id=entitlement.id,
        payload=PackageChanged(
            project_id=entitlement.project_id,
            entitlement_id=entitlement.id,
            state=PackageState(entitlement.state),
        ),
        dedupe_suffix=entitlement.state,
    )


async def activate(session: AsyncSession, order: Order) -> PackageEntitlement:
    """In the capture transaction of the order's first due. Sets the later dues' dates."""
    assert order.project_id is not None  # noqa: S101 (CHECK: package orders have a project)
    entitlement = PackageEntitlement(
        id=new_id(),
        project_id=order.project_id,
        order_id=order.id,
        state=ENTITLEMENT.target(None, "activate").value,
    )
    session.add(entitlement)
    await session.flush()
    await session.refresh(entitlement)
    for due in await session.scalars(
        select(PaymentDue).where(
            PaymentDue.order_id == order.id,
            PaymentDue.due_rule == DueRule.DAYS_AFTER_ACTIVATION.value,
        )
    ):
        due.due_at = entitlement.activated_at + timedelta(days=due.due_days or 0)
        due.version += 1
    await _history(session, entitlement, None, "first payment captured", None, "SYSTEM")
    return entitlement


async def active_entitlement(
    session: AsyncSession, project_id: uuid.UUID, *, for_update: bool = False
) -> PackageEntitlement | None:
    query = select(PackageEntitlement).where(
        PackageEntitlement.project_id == project_id,
        PackageEntitlement.state == PackageState.ACTIVE.value,
    )
    return (await session.scalars(query.with_for_update() if for_update else query)).one_or_none()


async def package_state(session: AsyncSession, project_id: uuid.UUID) -> PackageState:
    """ACTIVE when an entitlement is in force; otherwise how the latest one ended, or
    NOT_ACTIVE."""
    latest = (
        await session.scalars(
            select(PackageEntitlement)
            .where(PackageEntitlement.project_id == project_id)
            .order_by(PackageEntitlement.activated_at.desc())
            .limit(1)
        )
    ).one_or_none()
    return PackageState(latest.state) if latest else PackageState.NOT_ACTIVE


async def package_active(session: AsyncSession, project_id: uuid.UUID) -> bool:
    return await active_entitlement(session, project_id) is not None


async def end(
    session: AsyncSession,
    entitlement: PackageEntitlement,
    trigger: str,
    *,
    reason: str,
    actor_user_id: uuid.UUID,
    actor_role: str,
) -> None:
    """CANCELLED or REFUNDED. Unpaid later dues are cancelled with it."""
    old = PackageState(entitlement.state)
    entitlement.state = ENTITLEMENT.target(old, trigger).value
    entitlement.ended_at = await db_now(session)
    entitlement.version += 1
    for due in await session.scalars(
        select(PaymentDue).where(
            PaymentDue.order_id == entitlement.order_id, PaymentDue.state == DueState.DUE.value
        )
    ):
        due.state = DueState.CANCELLED.value
        due.version += 1
    await session.flush()
    await _history(session, entitlement, old, reason, actor_user_id, actor_role)


async def cancel_package(
    session: AsyncSession,
    project_id: uuid.UUID,
    *,
    reason: str,
    actor_user_id: uuid.UUID,
    actor_role: str,
) -> PackageEntitlement:
    entitlement = await active_entitlement(session, project_id, for_update=True)
    if entitlement is None:
        raise NotFound
    await end(
        session,
        entitlement,
        "cancel",
        reason=reason,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    )
    return entitlement


async def history(
    session: AsyncSession, project_id: uuid.UUID
) -> list[tuple[PackageEntitlement, list[PackageEntitlementHistory]]]:
    rows = list(
        await session.scalars(
            select(PackageEntitlement)
            .where(PackageEntitlement.project_id == project_id)
            .order_by(PackageEntitlement.activated_at)
        )
    )
    result = []
    for row in rows:
        entries = list(
            await session.scalars(
                select(PackageEntitlementHistory)
                .where(PackageEntitlementHistory.entitlement_id == row.id)
                .order_by(PackageEntitlementHistory.at)
            )
        )
        result.append((row, entries))
    return result


async def record_service_usage(
    session: AsyncSession,
    project_id: uuid.UUID,
    service: PackageServiceKind,
    ref_id: uuid.UUID | None,
) -> bool:
    """A substantial-work event on the project's active package, once per kind: N-12 (a
    connection accepted) and QD-02 (an RFQ selection; a new product decision, 2026-10-06). False
    when no package is active or the kind was already recorded."""
    entitlement = await active_entitlement(session, project_id)
    if entitlement is None:
        return False
    inserted = await session.execute(
        pg_insert(PackageServiceUsage)
        .values(id=new_id(), entitlement_id=entitlement.id, service=service.value, ref_id=ref_id)
        .on_conflict_do_nothing(index_elements=["entitlement_id", "service"])
        .returning(PackageServiceUsage.id)
    )
    return inserted.scalar_one_or_none() is not None
