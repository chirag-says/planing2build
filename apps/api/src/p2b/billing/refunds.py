"""Refunds (L-03; SLICE3_3_READINESS E). The buyer, or operations on their behalf, asks; OPS or
ADMIN decides with a reason and fresh MFA (route), approving an amount up to what remains
refundable, whether the package ends, and for AI credits how many unused credits are revoked.
Approval creates one provider refund per payment it draws on; a job asks the provider (checking
first for a refund already made with our id in its notes), and the provider's answer, by webhook
or reconciliation, completes it. A completed refund of an invoiced payment issues a credit note.

Refunds never happen automatically and never go anywhere but back to the original payment.
Whether staff roles differ before and after "substantial work" is open (O-04, O-10): both OPS and
ADMIN may decide; the entitlement's service-usage record is shown to them.
"""

import uuid
from decimal import Decimal

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.billing import credits, entitlements, invoices
from p2b.billing.clock import db_now
from p2b.billing.exceptions import raise_exception
from p2b.billing.models import (
    Invoice,
    Order,
    Payment,
    PaymentAttempt,
    PaymentDue,
    Refund,
    RefundDecision,
    RefundRequest,
)
from p2b.billing.money import rupees, to_paise
from p2b.billing.orders import ORDER, OS, lock_order, own_order
from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.payments import GatewayError, GatewayRefund, PaymentGateway
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import (
    ActorType,
    BillingExceptionKind,
    OfferingKind,
    RefundRequestState,
    RefundState,
)
from p2b.identity.interface import Actor

log = structlog.get_logger(__name__)

R = RefundRequestState
REQUEST = TransitionTable[RefundRequestState](
    "refund_request",
    [
        Transition(None, R.REQUESTED, "request"),
        Transition(R.REQUESTED, R.APPROVED, "approve"),
        Transition(R.REQUESTED, R.DECLINED, "decline"),
        Transition(R.APPROVED, R.REFUNDED, "complete"),
        Transition(R.APPROVED, R.FAILED, "fail"),
        Transition(R.FAILED, R.APPROVED, "retry"),
    ],
)
REFUNDABLE_ORDER_STATES = (
    OS.PART_PAID.value,
    OS.PAID.value,
    OS.PARTLY_REFUNDED.value,
    OS.CANCELLED.value,
)


class RefundRequested(EventPayload):
    request_id: uuid.UUID
    order_id: uuid.UUID


class RefundApproved(EventPayload):
    request_id: uuid.UUID
    refund_ids: list[uuid.UUID]


class RefundFinished(EventPayload):
    refund_id: uuid.UUID
    state: RefundState


async def _payments(session: AsyncSession, order_id: uuid.UUID) -> list[Payment]:
    """Every captured payment of the order, applied or not, newest first."""
    return list(
        await session.scalars(
            select(Payment)
            .join(PaymentAttempt, PaymentAttempt.id == Payment.attempt_id)
            .join(PaymentDue, PaymentDue.id == PaymentAttempt.due_id)
            .where(PaymentDue.order_id == order_id)
            .order_by(Payment.captured_at.desc())
        )
    )


async def _refunded(session: AsyncSession, payment_id: uuid.UUID) -> Decimal:
    """Refunded or in progress (failed refunds do not count)."""
    value = await session.scalar(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.payment_id == payment_id, Refund.state != RefundState.FAILED.value
        )
    )
    return rupees(value or 0)


async def refundable(session: AsyncSession, order_id: uuid.UUID) -> Decimal:
    total = Decimal("0.00")
    for payment in await _payments(session, order_id):
        total += payment.amount - await _refunded(session, payment.id)
    return total


async def _open_request(session: AsyncSession, order_id: uuid.UUID) -> RefundRequest | None:
    return (
        await session.scalars(
            select(RefundRequest).where(
                RefundRequest.order_id == order_id,
                RefundRequest.state.in_((R.REQUESTED.value, R.APPROVED.value)),
            )
        )
    ).one_or_none()


async def _create_request(
    session: AsyncSession,
    order: Order,
    *,
    amount: Decimal | None,
    reason: str,
    requested_by: uuid.UUID,
    role: str,
    session_id: uuid.UUID,
) -> RefundRequest:
    text = reason.strip()
    if not text:
        raise ValidationFailed(details={"fields": {"reason": ["Give a reason."]}})
    order = await lock_order(session, order.id)
    if order.state not in REFUNDABLE_ORDER_STATES:
        raise StateConflict(details={"current_state": order.state})
    available = await refundable(session, order.id)
    if available <= 0:
        raise StateConflict(details={"refundable": "0.00"})
    if amount is not None and not (Decimal("0") < amount <= available):
        raise ValidationFailed(details={"fields": {"amount": [f"Up to {available}."]}})
    if await _open_request(session, order.id) is not None:
        raise StateConflict(details={"refund": "a request is already open"})
    request = RefundRequest(
        id=new_id(),
        order_id=order.id,
        amount_requested=amount,
        reason=text[:2000],
        requested_by=requested_by,
        requested_role=role,
        state=REQUEST.target(None, "request").value,
    )
    session.add(request)
    await session.flush()
    await record(
        session,
        action="billing.refund_requested",
        entity_type="refund_request",
        entity_id=request.id,
        project_id=order.project_id,
        actor_type=ActorType.USER,
        actor_user_id=requested_by,
        actor_role=role,
        session_id=session_id,
        reason=request.reason,
    )
    await publish(
        session,
        event_type="billing.refund_requested",
        aggregate_type="refund_request",
        aggregate_id=request.id,
        payload=RefundRequested(request_id=request.id, order_id=order.id),
        dedupe_suffix="requested",
    )
    return request


async def request_refund(
    session: AsyncSession, actor: Actor, order_id: uuid.UUID, *, reason: str
) -> RefundRequest:
    """The buyer asks for a refund of what remains refundable; staff decide the amount."""
    order = await own_order(session, actor, order_id)
    return await _create_request(
        session,
        order,
        amount=None,
        reason=reason,
        requested_by=actor.user_id,
        role="BUYER",
        session_id=actor.session_id,
    )


async def staff_request(
    session: AsyncSession,
    actor: Actor,
    role: str,
    order_id: uuid.UUID,
    *,
    amount: Decimal | None,
    reason: str,
) -> RefundRequest:
    order = await session.get(Order, order_id)
    if order is None:
        raise NotFound
    return await _create_request(
        session,
        order,
        amount=amount,
        reason=reason,
        requested_by=actor.user_id,
        role=role,
        session_id=actor.session_id,
    )


async def decide(
    session: AsyncSession,
    actor: Actor,
    role: str,
    request_id: uuid.UUID,
    *,
    approve: bool,
    amount: Decimal | None,
    ends_package: bool,
    credits_revoked: int,
    reason: str,
) -> RefundRequest:
    text = reason.strip()
    if not text:
        raise ValidationFailed(details={"fields": {"reason": ["Give a reason."]}})
    request = await session.get(RefundRequest, request_id)
    if request is None:
        raise NotFound
    order = await lock_order(session, request.order_id)
    request = await session.get_one(
        RefundRequest, request_id, with_for_update=True, populate_existing=True
    )
    target = REQUEST.target(R(request.state), "approve" if approve else "decline")
    approved: Decimal | None = None
    refund_ids: list[uuid.UUID] = []
    if approve:
        available = await refundable(session, order.id)
        approved = rupees(amount) if amount is not None else None
        if approved is None or not (Decimal("0") < approved <= available):
            raise ValidationFailed(
                details={"fields": {"amount": [f"Between 0.01 and {available}."]}}
            )
        if credits_revoked and order.kind != OfferingKind.AI_CREDIT.value:
            raise ValidationFailed(
                details={"fields": {"credits_revoked": ["Only for AI credits."]}}
            )
        if ends_package and order.kind != OfferingKind.PACKAGE.value:
            raise ValidationFailed(details={"fields": {"ends_package": ["Only for the package."]}})
        if credits_revoked > order.quantity:
            raise ValidationFailed(
                details={"fields": {"credits_revoked": ["More than were bought."]}}
            )
    decision = RefundDecision(
        id=new_id(),
        request_id=request.id,
        decision="APPROVED" if approve else "DECLINED",
        approved_amount=approved,
        ends_package=bool(approve and ends_package),
        credits_revoked=credits_revoked if approve else 0,
        reason=text[:2000],
        decided_by=actor.user_id,
        role=role,
    )
    session.add(decision)
    await session.flush()
    if approve and approved is not None:
        if credits_revoked:
            await credits.revoke_credits(
                session,
                account_user_id=order.buyer_user_id,
                order_id=order.id,
                refund_request_id=request.id,
                quantity=credits_revoked,
            )
        if ends_package and order.project_id is not None:
            entitlement = await entitlements.active_entitlement(
                session, order.project_id, for_update=True
            )
            if entitlement is not None and entitlement.order_id == order.id:
                await entitlements.end(
                    session,
                    entitlement,
                    "refund",
                    reason=text,
                    actor_user_id=actor.user_id,
                    actor_role=role,
                )
        left = approved
        for payment in await _payments(session, order.id):
            if left <= 0:
                break
            portion = min(left, payment.amount - await _refunded(session, payment.id))
            if portion <= 0:
                continue
            refund = Refund(
                id=new_id(),
                decision_id=decision.id,
                payment_id=payment.id,
                amount=portion,
                provider=payment.provider,
                state=RefundState.PROCESSING.value,
            )
            session.add(refund)
            refund_ids.append(refund.id)
            left -= portion
        await session.flush()
    request.state = target.value
    request.version += 1
    await session.flush()
    await record(
        session,
        action=f"billing.refund_{decision.decision.lower()}",
        entity_type="refund_request",
        entity_id=request.id,
        project_id=order.project_id,
        actor_type=ActorType.USER,
        actor_user_id=actor.user_id,
        actor_role=role,
        session_id=actor.session_id,
        reason=text,
        new_value={
            "amount": str(approved) if approved else None,
            "ends_package": decision.ends_package,
            "credits_revoked": decision.credits_revoked,
        },
    )
    if refund_ids:
        await publish(
            session,
            event_type="billing.refund_approved",
            aggregate_type="refund_request",
            aggregate_id=request.id,
            payload=RefundApproved(request_id=request.id, refund_ids=refund_ids),
            dedupe_suffix=f"approved:{request.version}",
        )
    return request


async def retry(
    session: AsyncSession, actor: Actor, role: str, request_id: uuid.UUID
) -> RefundRequest:
    """A FAILED request goes back to the provider: one new refund per failed one."""
    request = await session.get(RefundRequest, request_id)
    if request is None:
        raise NotFound
    await lock_order(session, request.order_id)
    request = await session.get_one(
        RefundRequest, request_id, with_for_update=True, populate_existing=True
    )
    target = REQUEST.target(R(request.state), "retry")
    decision = (
        await session.scalars(select(RefundDecision).where(RefundDecision.request_id == request.id))
    ).one()
    failed = list(
        await session.scalars(
            select(Refund).where(
                Refund.decision_id == decision.id, Refund.state == RefundState.FAILED.value
            )
        )
    )
    refund_ids = []
    for old in failed:
        fresh = Refund(
            id=new_id(),
            decision_id=decision.id,
            payment_id=old.payment_id,
            amount=old.amount,
            provider=old.provider,
            state=RefundState.PROCESSING.value,
        )
        session.add(fresh)
        refund_ids.append(fresh.id)
    request.state = target.value
    request.version += 1
    await session.flush()
    await record(
        session,
        action="billing.refund_retried",
        entity_type="refund_request",
        entity_id=request.id,
        actor_type=ActorType.USER,
        actor_user_id=actor.user_id,
        actor_role=role,
        session_id=actor.session_id,
    )
    await publish(
        session,
        event_type="billing.refund_approved",
        aggregate_type="refund_request",
        aggregate_id=request.id,
        payload=RefundApproved(request_id=request.id, refund_ids=refund_ids),
        dedupe_suffix=f"approved:{request.version}",
    )
    return request


# --- with the provider ---------------------------------------------------------------------


async def execute_refund(
    database: Database, settings: Settings, gateway: PaymentGateway, refund_id: uuid.UUID
) -> RefundState | None:
    """The job. Asks the provider once: a refund already carrying our id is adopted, never
    repeated. Retryable provider failures raise (the job retries); others fail the refund."""
    async with database.transaction() as session:
        refund = await session.get(Refund, refund_id)
        if (
            refund is None
            or refund.state != RefundState.PROCESSING.value
            or refund.provider_refund_id
        ):
            return None
        payment = await session.get_one(Payment, refund.payment_id)
        provider_payment_id, amount_paise = payment.provider_payment_id, to_paise(refund.amount)
    existing = [
        r
        for r in await gateway.payment_refunds(provider_payment_id)
        if r.notes.get("refund_id") == str(refund_id)
    ]
    try:
        result = (
            existing[0]
            if existing
            else await gateway.create_refund(
                payment_id=provider_payment_id,
                amount_paise=amount_paise,
                notes={"refund_id": str(refund_id)},
            )
        )
    except GatewayError as exc:
        if exc.retryable:
            raise
        async with database.transaction() as session:
            await _finish(session, settings, refund_id, RefundState.FAILED, failure=str(exc)[:500])
        return RefundState.FAILED
    async with database.transaction() as session:
        refund = await session.get_one(Refund, refund_id, with_for_update=True)
        if refund.provider_refund_id is None:
            refund.provider_refund_id = result.refund_id
            refund.version += 1
            await session.flush()
        if result.status == "processed":
            await _finish(session, settings, refund_id, RefundState.REFUNDED)
            return RefundState.REFUNDED
        if result.status == "failed":
            await _finish(
                session, settings, refund_id, RefundState.FAILED, failure="provider failed"
            )
            return RefundState.FAILED
    return RefundState.PROCESSING


async def _finish(
    session: AsyncSession,
    settings: Settings,
    refund_id: uuid.UUID,
    state: RefundState,
    *,
    failure: str | None = None,
) -> None:
    refund = await session.get_one(Refund, refund_id)
    decision = await session.get_one(RefundDecision, refund.decision_id)
    request = await session.get_one(RefundRequest, decision.request_id)
    order = await lock_order(session, request.order_id)
    refund = await session.get_one(Refund, refund_id, with_for_update=True, populate_existing=True)
    if refund.state != RefundState.PROCESSING.value:
        return
    refund.state = state.value
    refund.failure = failure
    refund.completed_at = await db_now(session)
    refund.version += 1
    await session.flush()
    if state == RefundState.REFUNDED:
        payment = await session.get_one(Payment, refund.payment_id)
        invoiced = await session.scalar(select(Invoice.id).where(Invoice.payment_id == payment.id))
        if invoiced is not None:
            await invoices.issue_credit_note(session, order, refund)
        if order.state != OS.CANCELLED.value:
            paid = [p for p in await _payments(session, order.id) if p.applied]
            refunded = rupees(
                await session.scalar(
                    select(func.coalesce(func.sum(Refund.amount), 0)).where(
                        Refund.state == RefundState.REFUNDED.value,
                        Refund.payment_id.in_([p.id for p in paid]),
                    )
                )
                or 0
            )
            if refunded > 0:
                applied = sum((p.amount for p in paid), Decimal("0.00"))
                trigger = "refund_all" if refunded >= applied else "refund_part"
                order.state = ORDER.target(OS(order.state), trigger).value
                order.version += 1
    # One batch of refunds per approval or retry, created in one transaction (same time).
    states = set(
        await session.scalars(
            select(Refund.state).where(
                Refund.decision_id == decision.id, Refund.created_at == refund.created_at
            )
        )
    )
    request = await session.get_one(
        RefundRequest, request.id, with_for_update=True, populate_existing=True
    )
    if request.state == R.APPROVED.value and RefundState.PROCESSING.value not in states:
        trigger = "fail" if RefundState.FAILED.value in states else "complete"
        request.state = REQUEST.target(R.APPROVED, trigger).value
        request.version += 1
    await session.flush()
    await record(
        session,
        action=f"billing.refund_{state.value.lower()}",
        entity_type="refund",
        entity_id=refund.id,
        project_id=order.project_id,
        actor_type=ActorType.JOB,
        new_value={"amount": str(refund.amount)},
        reason=failure,
    )
    await publish(
        session,
        event_type="billing.refund_finished",
        aggregate_type="refund",
        aggregate_id=refund.id,
        payload=RefundFinished(refund_id=refund.id, state=state),
        dedupe_suffix=state.value,
    )


async def apply_refund_event(
    session: AsyncSession, settings: Settings, provider: str, gateway_refund: GatewayRefund
) -> str:
    """A verified `refund.processed` or `refund.failed`. A refund we did not ask for, or with a
    different amount, is an exception for operations."""
    refund = (
        await session.scalars(
            select(Refund).where(
                Refund.provider == provider, Refund.provider_refund_id == gateway_refund.refund_id
            )
        )
    ).one_or_none()
    if refund is None and gateway_refund.notes.get("refund_id"):
        try:
            refund = await session.get(Refund, uuid.UUID(gateway_refund.notes["refund_id"]))
        except ValueError:
            refund = None
    observed = {
        "refund_id": gateway_refund.refund_id,
        "payment_id": gateway_refund.payment_id,
        "amount_paise": gateway_refund.amount_paise,
        "status": gateway_refund.status,
    }
    if refund is None or to_paise(refund.amount) != gateway_refund.amount_paise:
        await raise_exception(
            session,
            BillingExceptionKind.REFUND_MISMATCH,
            provider=provider,
            provider_ref=gateway_refund.refund_id,
            expected={"amount_paise": to_paise(refund.amount)} if refund else {},
            observed=observed,
        )
        return "REFUND_MISMATCH"
    if refund.provider_refund_id is None:
        refund.provider_refund_id = gateway_refund.refund_id
        refund.version += 1
        await session.flush()
    if gateway_refund.status == "processed":
        await _finish(session, settings, refund.id, RefundState.REFUNDED)
        return "REFUNDED"
    if gateway_refund.status == "failed":
        await _finish(session, settings, refund.id, RefundState.FAILED, failure="provider failed")
        return "REFUND_FAILED"
    return "IGNORED"


async def reconcile_processing(
    database: Database, settings: Settings, gateway: PaymentGateway
) -> int:
    """Refunds still PROCESSING after the check window: ask the provider."""
    async with database.transaction() as session:
        rows = list(
            await session.execute(
                select(Refund.id, Refund.provider_refund_id, Payment.provider_payment_id)
                .join(Payment, Payment.id == Refund.payment_id)
                .where(
                    Refund.state == RefundState.PROCESSING.value,
                    Refund.provider == gateway.name,
                    Refund.created_at
                    < func.now()
                    - func.make_interval(0, 0, 0, 0, 0, settings.billing_attempt_check_minutes),
                )
                .limit(200)
            )
        )
    settled = 0
    for refund_id, provider_refund_id, provider_payment_id in rows:
        if provider_refund_id is None:
            await execute_refund(database, settings, gateway, refund_id)
            continue
        for found in await gateway.payment_refunds(provider_payment_id):
            if found.refund_id == provider_refund_id and found.status != "pending":
                async with database.transaction() as session:
                    await apply_refund_event(session, settings, gateway.name, found)
                settled += 1
    return settled


async def requests_for(session: AsyncSession, order_id: uuid.UUID) -> list[RefundRequest]:
    return list(
        await session.scalars(
            select(RefundRequest)
            .where(RefundRequest.order_id == order_id)
            .order_by(RefundRequest.created_at)
        )
    )
