"""Payments (SLICE3_3_READINESS D, G, K).

Checkout: the server creates one provider order per attempt for a due's exact amount; the
browser receives the public key id and the provider order id.

Authority: only a verified webhook, or an authenticated server-to-provider fetch, can change a
payment's state. The browser's checkout callback is a hint: its signature is checked, and a
valid hint only queues an immediate verified fetch. Nothing the browser sends is applied.

Processing: every capture, whatever its source, goes through `apply_capture` under the order's
lock. It applies a capture once (UNIQUE provider payment id), only for the attempt's exact
amount and currency, and only to a due still DUE on a live order. Anything else is recorded as a
billing exception for operations and never applied: a wrong amount, an unknown provider order,
a second capture for a paid due, a capture after the order was cancelled.

Reconciliation: every 15 minutes, open attempts older than the check window are fetched from the
provider (captures applied, authorised-only payments flagged, attempts with nothing expired), and
processing refunds are checked; daily, every capture of the last 3 days is matched.
"""

import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.billing import credits, entitlements, invoices, refunds
from p2b.billing.clock import db_now
from p2b.billing.exceptions import raise_exception
from p2b.billing.models import Order, Payment, PaymentAttempt, PaymentDue, PaymentEvent
from p2b.billing.money import from_paise, to_paise
from p2b.billing.orders import ORDER, OS, cancel_order, lock_order, own_order
from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.errors import NotFound, ProviderUnavailable, SignatureInvalid, StateConflict
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.payments import GatewayError, GatewayPayment, GatewayRefund, PaymentGateway
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import (
    ActorType,
    AttemptState,
    BillingExceptionKind,
    DueState,
    OfferingKind,
)
from p2b.identity.interface import Actor

log = structlog.get_logger(__name__)

A = AttemptState
ATTEMPT = TransitionTable[AttemptState](
    "payment_attempt",
    [
        Transition(None, A.CREATED, "create"),
        Transition(A.CREATED, A.CAPTURED, "capture"),
        Transition(A.CREATED, A.FAILED, "fail"),
        Transition(A.CREATED, A.EXPIRED, "expire"),
        # The provider captured after we gave up on the attempt: still the due's money.
        Transition(A.FAILED, A.CAPTURED, "late_capture"),
        Transition(A.EXPIRED, A.CAPTURED, "late_capture"),
    ],
)
CAPTURE_EVENTS = frozenset({"payment.captured", "order.paid"})
REFUND_EVENTS = frozenset({"refund.processed", "refund.failed"})


class CheckoutReturned(EventPayload):
    attempt_id: uuid.UUID


class PaymentEventReceived(EventPayload):
    payment_event_id: uuid.UUID


class PaymentCaptured(EventPayload):
    order_id: uuid.UUID
    due_id: uuid.UUID
    payment_id: uuid.UUID


class PaymentFailed(EventPayload):
    order_id: uuid.UUID
    attempt_id: uuid.UUID


# --- checkout ------------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckoutTicket:
    attempt: PaymentAttempt
    order: Order
    due: PaymentDue
    provider: str
    key_id: str
    amount_paise: int


async def _payable_due(session: AsyncSession, order: Order, due_id: uuid.UUID) -> PaymentDue:
    """The next unpaid due of a live order. Later instalments only once the package is
    active."""
    if order.state not in (OS.AWAITING_PAYMENT.value, OS.PART_PAID.value):
        raise StateConflict(details={"current_state": order.state})
    due = await session.get(PaymentDue, due_id, with_for_update=True)
    if due is None or due.order_id != order.id:
        raise NotFound
    first_unpaid = await session.scalar(
        select(func.min(PaymentDue.sequence)).where(
            PaymentDue.order_id == order.id, PaymentDue.state == DueState.DUE.value
        )
    )
    if due.state != DueState.DUE.value or due.sequence != first_unpaid:
        raise StateConflict(details={"current_state": due.state, "due": "not the next to pay"})
    if due.sequence > 1 and order.kind == OfferingKind.PACKAGE.value:
        assert order.project_id is not None  # noqa: S101
        if await entitlements.active_entitlement(session, order.project_id) is None:
            raise StateConflict(details={"package": "not active"})
    return due


async def start_checkout(
    session: AsyncSession,
    settings: Settings,
    gateway: PaymentGateway,
    actor: Actor,
    due_id: uuid.UUID,
    *,
    on_new_attempt: Any,
) -> CheckoutTicket:
    """An attempt for the due, reusing an open one younger than the check window so the family
    never holds two provider orders at once. `on_new_attempt` enforces the per-due rate limit."""
    if not gateway.configured:
        raise ProviderUnavailable(details={"provider": gateway.name})
    due_row = await session.get(PaymentDue, due_id)
    if due_row is None:
        raise NotFound
    order = await own_order(session, actor, due_row.order_id)
    order = await lock_order(session, order.id)
    due = await _payable_due(session, order, due_id)
    window = timedelta(minutes=settings.billing_attempt_check_minutes)
    open_attempt = (
        await session.scalars(
            select(PaymentAttempt)
            .where(
                PaymentAttempt.due_id == due.id,
                PaymentAttempt.state == A.CREATED.value,
                PaymentAttempt.provider == gateway.name,
                PaymentAttempt.created_at > func.now() - window,
            )
            .order_by(PaymentAttempt.created_at.desc())
            .limit(1)
        )
    ).one_or_none()
    if open_attempt is None:
        await on_new_attempt()
        amount_paise = to_paise(due.amount)
        try:
            provider_order = await gateway.create_order(
                amount_paise=amount_paise,
                currency=order.currency,
                receipt=f"{order.code}-{due.sequence}",
                notes={"order_code": order.code, "due_sequence": str(due.sequence)},
            )
        except GatewayError as exc:
            raise ProviderUnavailable(details={"provider": gateway.name}) from exc
        if provider_order.amount_paise != amount_paise or provider_order.currency != order.currency:
            raise ProviderUnavailable(details={"provider": gateway.name, "order": "mismatch"})
        open_attempt = PaymentAttempt(
            id=new_id(),
            due_id=due.id,
            provider=gateway.name,
            provider_order_id=provider_order.provider_order_id,
            amount=due.amount,
            currency=order.currency,
            state=ATTEMPT.target(None, "create").value,
            created_by=actor.user_id,
        )
        session.add(open_attempt)
        await session.flush()
        await session.refresh(open_attempt)
        await record(
            session,
            action="billing.attempt_created",
            entity_type="payment_attempt",
            entity_id=open_attempt.id,
            project_id=order.project_id,
            actor_type=ActorType.USER,
            actor_user_id=actor.user_id,
            session_id=actor.session_id,
            new_value={"due": due.sequence, "amount": str(due.amount)},
        )
    return CheckoutTicket(
        open_attempt, order, due, gateway.name, gateway.public_key_id, to_paise(open_attempt.amount)
    )


async def checkout_returned(
    session: AsyncSession,
    gateway: PaymentGateway,
    actor: Actor,
    attempt_id: uuid.UUID,
    *,
    provider_order_id: str,
    provider_payment_id: str,
    signature: str,
) -> PaymentAttempt:
    """The browser's callback. Never authoritative: a valid signature only queues a verified
    fetch from the provider; an invalid one is refused and logged. Returns the attempt as it is."""
    attempt = await session.get(PaymentAttempt, attempt_id)
    if attempt is None:
        raise NotFound
    due = await session.get_one(PaymentDue, attempt.due_id)
    await own_order(session, actor, due.order_id)
    if attempt.provider_order_id != provider_order_id or not gateway.verify_checkout_signature(
        order_id=provider_order_id, payment_id=provider_payment_id, signature=signature
    ):
        raise SignatureInvalid
    await publish(
        session,
        event_type="billing.checkout_returned",
        aggregate_type="payment_attempt",
        aggregate_id=attempt.id,
        payload=CheckoutReturned(attempt_id=attempt.id),
        dedupe_suffix=f"returned:{provider_payment_id}",
    )
    return attempt


# --- webhooks ------------------------------------------------------------------------------


def _payment_dict(payment: GatewayPayment | None) -> dict[str, Any] | None:
    if payment is None:
        return None
    data = asdict(payment)
    data["created_at"] = payment.created_at.isoformat() if payment.created_at else None
    return data


def _payment_of(data: dict[str, Any]) -> GatewayPayment:
    created = data.get("created_at")
    return GatewayPayment(
        **{**data, "created_at": datetime.fromisoformat(created) if created else None}
    )


async def receive_webhook(
    session: AsyncSession,
    gateway: PaymentGateway,
    *,
    body: bytes,
    signature: str,
    event_id: str,
) -> bool:
    """Verify, store once, queue processing. Returns whether the event is new. The caller
    answers 200 either way once this returns; an invalid signature raises."""
    if not signature or not gateway.verify_webhook_signature(body=body, signature=signature):
        raise SignatureInvalid
    event = gateway.parse_event(body)
    payload = {
        "event_type": event.event_type,
        "payment": _payment_dict(event.payment),
        "refund": asdict(event.refund) if event.refund else None,
    }
    stored = await session.execute(
        insert(PaymentEvent)
        .values(
            id=new_id(),
            provider=gateway.name,
            provider_event_id=event_id[:80],
            event_type=event.event_type[:60],
            payload=payload,
        )
        .on_conflict_do_nothing(index_elements=["provider", "provider_event_id"])
        .returning(PaymentEvent.id)
    )
    event_row = stored.scalar_one_or_none()
    if event_row is None:
        return False  # a replay: 200, no effect
    await publish(
        session,
        event_type="billing.payment_event_received",
        aggregate_type="payment_event",
        aggregate_id=event_row,
        payload=PaymentEventReceived(payment_event_id=event_row),
        dedupe_suffix="received",
    )
    return True


async def process_event(
    database: Database, settings: Settings, event_row_id: uuid.UUID
) -> str | None:
    """The job behind a stored webhook. Idempotent: a processed event is left alone."""
    async with database.transaction() as session:
        event = await session.get(PaymentEvent, event_row_id, with_for_update=True)
        if event is None or event.processed_at is not None:
            return None
        payload = event.payload
        payment = _payment_of(payload["payment"]) if payload.get("payment") else None
        refund = GatewayRefund(**payload["refund"]) if payload.get("refund") else None
        if event.event_type in CAPTURE_EVENTS and payment is not None and payment.captured:
            result = await apply_capture(
                session, settings, event.provider, payment, source="WEBHOOK"
            )
        elif event.event_type == "payment.failed" and payment is not None:
            result = await apply_failure(session, event.provider, payment)
        elif event.event_type in REFUND_EVENTS and refund is not None:
            result = await refunds.apply_refund_event(session, settings, event.provider, refund)
        else:
            result = "IGNORED"
        event.processed_at = await db_now(session)
        event.result = result[:40]
        await session.flush()
        return result


# --- applying what the provider reports ---------------------------------------------------


async def _attempt_for(
    session: AsyncSession, provider: str, provider_order_id: str | None
) -> PaymentAttempt | None:
    if not provider_order_id:
        return None
    return (
        await session.scalars(
            select(PaymentAttempt).where(
                PaymentAttempt.provider == provider,
                PaymentAttempt.provider_order_id == provider_order_id,
            )
        )
    ).one_or_none()


def _observed(payment: GatewayPayment) -> dict[str, Any]:
    return {
        "payment_id": payment.payment_id,
        "order_id": payment.order_id,
        "amount_paise": payment.amount_paise,
        "currency": payment.currency,
        "status": payment.status,
    }


async def _record_payment(
    session: AsyncSession,
    attempt: PaymentAttempt,
    provider: str,
    payment: GatewayPayment,
    *,
    applied: bool,
    source: str,
) -> Payment:
    row = Payment(
        id=new_id(),
        attempt_id=attempt.id,
        provider=provider,
        provider_payment_id=payment.payment_id,
        amount=from_paise(payment.amount_paise),
        currency=payment.currency,
        method=(payment.method or "")[:30] or None,
        fee=from_paise(payment.fee_paise) if payment.fee_paise is not None else None,
        tax_on_fee=from_paise(payment.tax_paise) if payment.tax_paise is not None else None,
        applied=applied,
        source=source,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def apply_capture(
    session: AsyncSession,
    settings: Settings,
    provider: str,
    payment: GatewayPayment,
    *,
    source: str,
) -> str:
    """Apply one captured payment, once, under the order lock. Returns what happened."""
    attempt = await _attempt_for(session, provider, payment.order_id)
    if attempt is None:
        await raise_exception(
            session,
            BillingExceptionKind.UNKNOWN_ORDER,
            provider=provider,
            provider_ref=payment.payment_id,
            expected={},
            observed=_observed(payment),
        )
        return "UNKNOWN_ORDER"
    due = await session.get_one(PaymentDue, attempt.due_id)
    order = await lock_order(session, due.order_id)
    due = await session.get_one(
        PaymentDue, attempt.due_id, with_for_update=True, populate_existing=True
    )
    attempt = await session.get_one(
        PaymentAttempt, attempt.id, with_for_update=True, populate_existing=True
    )
    already = await session.scalar(
        select(Payment.id).where(
            Payment.provider == provider, Payment.provider_payment_id == payment.payment_id
        )
    )
    if already is not None:
        return "ALREADY_APPLIED"
    expected = {
        "amount_paise": to_paise(attempt.amount),
        "currency": attempt.currency,
        "attempt_id": str(attempt.id),
    }

    kind: BillingExceptionKind | None = None
    if payment.amount_paise != to_paise(attempt.amount) or payment.currency != attempt.currency:
        kind = BillingExceptionKind.AMOUNT_MISMATCH
    elif order.state == OS.CANCELLED.value:
        kind = BillingExceptionKind.CAPTURE_AFTER_CANCEL
    elif due.state != DueState.DUE.value:
        kind = BillingExceptionKind.DUPLICATE_CAPTURE
    if kind is not None:
        row = await _record_payment(
            session, attempt, provider, payment, applied=False, source=source
        )
        await raise_exception(
            session,
            kind,
            provider=provider,
            provider_ref=payment.payment_id,
            expected=expected,
            observed=_observed(payment),
            order_id=order.id,
            attempt_id=attempt.id,
            payment_id=row.id,
        )
        return kind.value

    trigger = "capture" if attempt.state == A.CREATED.value else "late_capture"
    attempt.state = ATTEMPT.target(A(attempt.state), trigger).value
    attempt.finished_at = await db_now(session)
    attempt.version += 1
    row = await _record_payment(session, attempt, provider, payment, applied=True, source=source)
    due.state = DueState.PAID.value
    due.paid_at = await db_now(session)
    due.version += 1
    await session.flush()
    remaining = await session.scalar(
        select(func.count()).where(
            PaymentDue.order_id == order.id, PaymentDue.state == DueState.DUE.value
        )
    )
    order.state = ORDER.target(OS(order.state), "pay_part" if remaining else "pay_all").value
    order.version += 1
    # Other open attempts for this due can no longer be applied; a capture on one later is a
    # duplicate for operations to refund.
    for other in await session.scalars(
        select(PaymentAttempt).where(
            PaymentAttempt.due_id == due.id,
            PaymentAttempt.id != attempt.id,
            PaymentAttempt.state == A.CREATED.value,
        )
    ):
        other.state = A.EXPIRED.value
        other.finished_at = await db_now(session)
        other.version += 1
    await session.flush()

    if due.sequence == 1:
        if order.kind == OfferingKind.PACKAGE.value:
            await entitlements.activate(session, order)
        else:
            await credits.grant_credits(
                session,
                account_user_id=order.buyer_user_id,
                order_id=order.id,
                quantity=order.quantity,
            )
    await invoices.issue_tax_invoice(session, order, due, row)
    await record(
        session,
        action="billing.payment_captured",
        entity_type="payment",
        entity_id=row.id,
        project_id=order.project_id,
        actor_type=ActorType.JOB,
        new_value={
            "order": order.code,
            "due": due.sequence,
            "amount": str(row.amount),
            "source": source,
            "late": trigger == "late_capture",
        },
    )
    await publish(
        session,
        event_type="billing.payment_captured",
        aggregate_type="order",
        aggregate_id=order.id,
        payload=PaymentCaptured(order_id=order.id, due_id=due.id, payment_id=row.id),
        dedupe_suffix=f"captured:{row.id}",
    )
    return "APPLIED"


async def apply_failure(session: AsyncSession, provider: str, payment: GatewayPayment) -> str:
    attempt = await _attempt_for(session, provider, payment.order_id)
    if attempt is None:
        return "UNKNOWN_ORDER"
    due = await session.get_one(PaymentDue, attempt.due_id)
    order = await lock_order(session, due.order_id)
    attempt = await session.get_one(
        PaymentAttempt, attempt.id, with_for_update=True, populate_existing=True
    )
    if attempt.state != A.CREATED.value:
        return "IGNORED"
    attempt.state = ATTEMPT.target(A.CREATED, "fail").value
    attempt.failure_code = (payment.error_code or "FAILED")[:60]
    attempt.finished_at = await db_now(session)
    attempt.version += 1
    await session.flush()
    await publish(
        session,
        event_type="billing.payment_failed",
        aggregate_type="payment_attempt",
        aggregate_id=attempt.id,
        payload=PaymentFailed(order_id=order.id, attempt_id=attempt.id),
        dedupe_suffix="failed",
    )
    return "FAILED"


# --- verified fetches and reconciliation ---------------------------------------------------


async def _apply_fetched(
    database: Database, settings: Settings, provider: str, payments: list[GatewayPayment]
) -> list[str]:
    results = []
    for payment in payments:
        if not payment.captured:
            continue
        async with database.transaction() as session:
            results.append(
                await apply_capture(session, settings, provider, payment, source="FETCH")
            )
    return results


async def verify_attempt(
    database: Database, settings: Settings, gateway: PaymentGateway, attempt_id: uuid.UUID
) -> list[str]:
    """The fetch a valid checkout callback asks for: what the provider says, applied."""
    async with database.transaction() as session:
        attempt = await session.get(PaymentAttempt, attempt_id)
        if attempt is None or attempt.provider != gateway.name:
            return []
        provider_order_id = attempt.provider_order_id
    payments = await gateway.order_payments(provider_order_id)
    return await _apply_fetched(database, settings, gateway.name, payments)


async def reconcile_open_attempts(
    database: Database, settings: Settings, gateway: PaymentGateway
) -> dict[str, int]:
    """Every 15 minutes: attempts with no outcome after the check window."""
    counts = {"checked": 0, "applied": 0, "expired": 0, "authorised": 0}
    window = timedelta(minutes=settings.billing_attempt_check_minutes)
    async with database.transaction() as session:
        attempts = list(
            await session.scalars(
                select(PaymentAttempt)
                .where(
                    PaymentAttempt.state == A.CREATED.value,
                    PaymentAttempt.provider == gateway.name,
                    PaymentAttempt.created_at < func.now() - window,
                )
                .order_by(PaymentAttempt.created_at)
                .limit(200)
            )
        )
    for attempt in attempts:
        counts["checked"] += 1
        try:
            payments = await gateway.order_payments(attempt.provider_order_id)
        except GatewayError as exc:
            log.warning(
                "billing.reconcile_fetch_failed", attempt_id=str(attempt.id), error=str(exc)
            )
            continue
        results = await _apply_fetched(database, settings, gateway.name, payments)
        counts["applied"] += results.count("APPLIED")
        async with database.transaction() as session:
            for payment in payments:
                if payment.status == "authorized":
                    counts["authorised"] += 1
                    await raise_exception(
                        session,
                        BillingExceptionKind.AUTHORISED_NOT_CAPTURED,
                        provider=gateway.name,
                        provider_ref=payment.payment_id,
                        expected={"attempt_id": str(attempt.id)},
                        observed=_observed(payment),
                        attempt_id=attempt.id,
                    )
            if not any(p.captured or p.status == "authorized" for p in payments):
                due = await session.get_one(PaymentDue, attempt.due_id)
                await lock_order(session, due.order_id)
                fresh = await session.get_one(
                    PaymentAttempt, attempt.id, with_for_update=True, populate_existing=True
                )
                if fresh.state == A.CREATED.value:
                    fresh.state = ATTEMPT.target(A.CREATED, "expire").value
                    fresh.finished_at = await db_now(session)
                    fresh.version += 1
                    counts["expired"] += 1
    counts["refunds"] = await refunds.reconcile_processing(database, settings, gateway)
    counts["orders_cancelled"] = await sweep_unpaid_orders(database, settings)
    log.info("billing.reconciled", window="frequent", **counts)
    return counts


async def reconcile_daily(
    database: Database, settings: Settings, gateway: PaymentGateway, *, days: int = 3
) -> dict[str, int]:
    """Daily: every capture the provider holds for the last `days` days, matched and applied
    (unknown provider orders become exceptions)."""
    end = datetime.now(UTC)
    payments = await gateway.payments_between(end - timedelta(days=days), end)
    results = await _apply_fetched(database, settings, gateway.name, payments)
    counts = {
        "captured": len([p for p in payments if p.captured]),
        "applied": results.count("APPLIED"),
        "exceptions": len([r for r in results if r not in ("APPLIED", "ALREADY_APPLIED")]),
    }
    log.info("billing.reconciled", window="daily", **counts)
    return counts


async def sweep_unpaid_orders(database: Database, settings: Settings) -> int:
    """O-12: cancel orders left unpaid longer than the configured hours. Off when unset."""
    if settings.billing_unpaid_order_hours is None:
        return 0
    cutoff = timedelta(hours=settings.billing_unpaid_order_hours)
    async with database.transaction() as session:
        stale = list(
            await session.scalars(
                select(Order.id)
                .where(
                    Order.state == OS.AWAITING_PAYMENT.value, Order.created_at < func.now() - cutoff
                )
                .limit(200)
            )
        )
    cancelled = 0
    for order_id in stale:
        async with database.transaction() as session:
            order = await lock_order(session, order_id)
            open_attempt = await session.scalar(
                select(PaymentAttempt.id)
                .join(PaymentDue, PaymentDue.id == PaymentAttempt.due_id)
                .where(PaymentDue.order_id == order_id, PaymentAttempt.state == A.CREATED.value)
            )
            if order.state == OS.AWAITING_PAYMENT.value and open_attempt is None:
                await cancel_order(session, order, reason="unpaid", actor_user_id=None)
                cancelled += 1
    return cancelled
