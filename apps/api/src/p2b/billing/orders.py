"""Orders and dues (SLICE3_3_READINESS B, C, D). The server prices the order from the published
offer and the project's characteristics, computes tax from the published tax configuration for
the buyer's state, splits it into dues per the payment mode, and stamps every input. Nothing
the browser sends is an amount. An order's amounts never change after creation (trigger)."""

import secrets
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.billing.clock import db_now
from p2b.billing.configuration import ActiveOffer, active_offer, instalment_amounts
from p2b.billing.entitlements import active_entitlement
from p2b.billing.invoices import due_split
from p2b.billing.models import Order, PaymentAttempt, PaymentDue
from p2b.billing.pricing import evaluate
from p2b.billing.tax import STATE_CODES, TaxBreakdown, compute
from p2b.core.config import Settings
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import (
    ActorType,
    AttemptState,
    DueRule,
    DueState,
    OfferingKind,
    OrderState,
    PackageAvailability,
    PaymentMode,
)
from p2b.identity.interface import Actor
from p2b.projects.interface import BillingFacts, billing_facts

OS = OrderState
ORDER = TransitionTable[OrderState](
    "order",
    [
        Transition(None, OS.AWAITING_PAYMENT, "create"),
        Transition(OS.AWAITING_PAYMENT, OS.PART_PAID, "pay_part"),
        Transition(OS.PART_PAID, OS.PART_PAID, "pay_part"),
        Transition(OS.AWAITING_PAYMENT, OS.PAID, "pay_all"),
        Transition(OS.PART_PAID, OS.PAID, "pay_all"),
        Transition(OS.AWAITING_PAYMENT, OS.CANCELLED, "cancel"),
        *(
            Transition(s, OS.PARTLY_REFUNDED, "refund_part")
            for s in (OS.PART_PAID, OS.PAID, OS.PARTLY_REFUNDED)
        ),
        *(
            Transition(s, OS.REFUNDED, "refund_all")
            for s in (OS.PART_PAID, OS.PAID, OS.PARTLY_REFUNDED)
        ),
    ],
)
OPEN_ORDER_STATES = (OS.AWAITING_PAYMENT.value, OS.PART_PAID.value)


class Buyer(BaseModel):
    """Billing details for the invoice (personal data, P2), snapshotted on the order."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=500)
    state_code: str = Field(min_length=2, max_length=2)
    gstin: str = Field(default="", max_length=15, description="Only if registered for GST")

    @field_validator("state_code")
    @classmethod
    def _known_state(cls, value: str) -> str:
        if value not in STATE_CODES:
            raise ValueError("choose a state from the list")
        return value

    @field_validator("gstin")
    @classmethod
    def _gstin(cls, value: str) -> str:
        value = value.upper()
        if value and (len(value) != 15 or not value.isalnum()):
            raise ValueError("a GSTIN has 15 letters and digits")
        return value


class OrderCreated(EventPayload):
    order_id: uuid.UUID
    kind: OfferingKind


@dataclass(frozen=True)
class Quote:
    """What an order would cost now; nothing is stored."""

    offer: ActiveOffer
    price: Decimal
    inputs: dict[str, Any]
    tax: TaxBreakdown
    dues: list[tuple[Decimal, list[dict[str, str]], Decimal]]  # amount, tax lines, taxable
    mode: PaymentMode


def _quote(
    offer: ActiveOffer,
    kind: OfferingKind,
    characteristics: dict[str, Any],
    buyer_state: str,
    mode: PaymentMode,
) -> Quote:
    price, inputs = evaluate(offer.rule, characteristics)
    breakdown = compute(offer.tax, kind.value, price, buyer_state)
    plan = offer.plan if mode == PaymentMode.INSTALMENTS else None
    amounts = instalment_amounts(plan, breakdown.total)
    splits = due_split(breakdown.total, breakdown.lines, amounts)
    dues = [
        (amount, lines, taxable) for amount, (taxable, lines) in zip(amounts, splits, strict=True)
    ]
    return Quote(offer, price, inputs, breakdown, dues, mode)


async def _owned_project(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID
) -> BillingFacts:
    facts = await billing_facts(session, project_id)
    if facts is None or facts.owner_user_id != actor.user_id:
        raise NotFound
    return facts


async def package_quote(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    project_id: uuid.UUID,
    mode: PaymentMode,
    buyer_state: str | None,
) -> Quote:
    facts = await _owned_project(session, actor, project_id)
    offer = await active_offer(session, settings, OfferingKind.PACKAGE)
    if mode not in offer.version.payment_modes:
        raise ValidationFailed(details={"fields": {"payment_mode": ["Not offered."]}})
    return _quote(
        offer,
        OfferingKind.PACKAGE,
        facts.characteristics,
        buyer_state or offer.tax.state_code,
        mode,
    )


async def credit_quote(session: AsyncSession, settings: Settings, buyer_state: str | None) -> Quote:
    offer = await active_offer(session, settings, OfferingKind.AI_CREDIT)
    return _quote(
        offer, OfferingKind.AI_CREDIT, {}, buyer_state or offer.tax.state_code, PaymentMode.FULL
    )


def _code() -> str:
    return f"ORD-{secrets.token_hex(5).upper()}"


async def _insert(
    session: AsyncSession,
    actor: Actor,
    quote: Quote,
    kind: OfferingKind,
    project_id: uuid.UUID | None,
    buyer: Buyer,
) -> Order:
    offer = quote.offer
    order = Order(
        id=new_id(),
        code=_code(),
        buyer_user_id=actor.user_id,
        project_id=project_id,
        kind=kind.value,
        offering_version_id=offer.version.id,
        quantity=1,
        pricing_rule_version_id=offer.rule_version.id,
        pricing_inputs=quote.inputs,
        price=quote.price,
        taxable_total=quote.tax.taxable,
        tax=quote.tax.lines,
        tax_total=quote.tax.tax_total,
        total=quote.tax.total,
        currency="INR",
        payment_mode=quote.mode.value,
        instalment_plan=(
            offer.plan_version.instalments
            if quote.mode == PaymentMode.INSTALMENTS and offer.plan_version
            else None
        ),
        tax_configuration_version_id=offer.tax_version.id,
        terms_version=offer.version.terms_version,
        buyer=buyer.model_dump(),
        is_test=offer.is_test,
        state=ORDER.target(None, "create").value,
    )
    session.add(order)
    await session.flush()
    specs = (
        offer.plan.instalments if quote.mode == PaymentMode.INSTALMENTS and offer.plan else [None]
    )
    for sequence, ((amount, lines, taxable), spec) in enumerate(
        zip(quote.dues, specs, strict=True), start=1
    ):
        later = spec is not None and spec.due == DueRule.DAYS_AFTER_ACTIVATION.value
        session.add(
            PaymentDue(
                id=new_id(),
                order_id=order.id,
                sequence=sequence,
                amount=amount,
                taxable_amount=taxable,
                tax=lines,
                tax_amount=sum((Decimal(t["amount"]) for t in lines), Decimal("0.00")),
                due_rule=(DueRule.DAYS_AFTER_ACTIVATION if later else DueRule.ON_ORDER).value,
                due_days=spec.days if later and spec else None,
                due_at=None if later else func.now(),
                state=DueState.DUE.value,
            )
        )
    await session.flush()
    await session.refresh(order)
    await record(
        session,
        action="billing.order_created",
        entity_type="order",
        entity_id=order.id,
        project_id=project_id,
        actor_type=ActorType.USER,
        actor_user_id=actor.user_id,
        session_id=actor.session_id,
        new_value={
            "code": order.code,
            "total": str(order.total),
            "mode": order.payment_mode,
            "offering_version": offer.version.version,
            "pricing_rule": offer.rule_version.version,
            "is_test": order.is_test,
        },
    )
    await publish(
        session,
        event_type="billing.order_created",
        aggregate_type="order",
        aggregate_id=order.id,
        payload=OrderCreated(order_id=order.id, kind=kind),
        dedupe_suffix="created",
    )
    return order


def _check_terms(offer: ActiveOffer, offering_version_id: uuid.UUID, accepted_terms: str) -> None:
    if offering_version_id != offer.version.id:
        raise StateConflict(
            message="The offer changed. Review the new price before paying.",
            details={"offering_version": "changed", "current": str(offer.version.id)},
        )
    if accepted_terms != offer.version.terms_version:
        raise ValidationFailed(
            details={"fields": {"accept_terms_version": ["Accept the current terms."]}}
        )


async def create_package_order(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    project_id: uuid.UUID,
    *,
    offering_version_id: uuid.UUID,
    payment_mode: PaymentMode,
    buyer: Buyer,
    accept_terms_version: str,
) -> Order:
    facts = await _owned_project(session, actor, project_id)
    await session.execute(
        select(func.pg_advisory_xact_lock(func.hashtext(f"billing-project:{project_id}")))
    )
    if facts.availability != PackageAvailability.ELIGIBLE:
        raise StateConflict(details={"package": facts.availability.value})
    if await active_entitlement(session, project_id) is not None:
        raise StateConflict(details={"package": "ACTIVE"})
    open_order = await session.scalar(
        select(Order.id).where(
            Order.project_id == project_id,
            Order.kind == OfferingKind.PACKAGE.value,
            Order.state == OS.AWAITING_PAYMENT.value,
        )
    )
    if open_order is not None:
        raise StateConflict(details={"open_order_id": str(open_order)})
    offer = await active_offer(session, settings, OfferingKind.PACKAGE)
    _check_terms(offer, offering_version_id, accept_terms_version)
    if payment_mode not in offer.version.payment_modes:
        raise ValidationFailed(details={"fields": {"payment_mode": ["Not offered."]}})
    quote = _quote(
        offer, OfferingKind.PACKAGE, facts.characteristics, buyer.state_code, payment_mode
    )
    return await _insert(session, actor, quote, OfferingKind.PACKAGE, project_id, buyer)


async def create_credit_order(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    *,
    offering_version_id: uuid.UUID,
    buyer: Buyer,
    accept_terms_version: str,
) -> Order:
    offer = await active_offer(session, settings, OfferingKind.AI_CREDIT)
    _check_terms(offer, offering_version_id, accept_terms_version)
    quote = _quote(offer, OfferingKind.AI_CREDIT, {}, buyer.state_code, PaymentMode.FULL)
    return await _insert(session, actor, quote, OfferingKind.AI_CREDIT, None, buyer)


async def lock_order(session: AsyncSession, order_id: uuid.UUID) -> Order:
    """Serialise everything that changes an order: payment processing, reconciliation,
    refunds and cancellation take this lock first."""
    await session.execute(
        select(func.pg_advisory_xact_lock(func.hashtext(f"billing-order:{order_id}")))
    )
    return await session.get_one(Order, order_id, with_for_update=True, populate_existing=True)


async def own_order(session: AsyncSession, actor: Actor, order_id: uuid.UUID) -> Order:
    order = await session.get(Order, order_id)
    if order is None or order.buyer_user_id != actor.user_id:
        raise NotFound
    return order


async def cancel_order(
    session: AsyncSession,
    order: Order,
    *,
    reason: str,
    actor_user_id: uuid.UUID | None,
) -> Order:
    """An unpaid order ends: by its buyer, or by the unpaid-order sweep (O-12). A capture that
    arrives afterwards is never applied; it becomes a CAPTURE_AFTER_CANCEL exception."""
    order = await lock_order(session, order.id)
    order.state = ORDER.target(OS(order.state), "cancel").value
    order.cancelled_at = await db_now(session)
    order.cancel_reason = reason[:500]
    order.version += 1
    dues = list(await session.scalars(select(PaymentDue).where(PaymentDue.order_id == order.id)))
    for due in dues:
        due.state = DueState.CANCELLED.value
        due.version += 1
    for attempt in await session.scalars(
        select(PaymentAttempt).where(
            PaymentAttempt.due_id.in_([d.id for d in dues]),
            PaymentAttempt.state == AttemptState.CREATED.value,
        )
    ):
        attempt.state = AttemptState.EXPIRED.value
        attempt.finished_at = await db_now(session)
        attempt.version += 1
    await session.flush()
    await record(
        session,
        action="billing.order_cancelled",
        entity_type="order",
        entity_id=order.id,
        project_id=order.project_id,
        actor_type=ActorType.USER if actor_user_id else ActorType.JOB,
        actor_user_id=actor_user_id,
        reason=order.cancel_reason,
    )
    return order


async def dues_of(session: AsyncSession, order_id: uuid.UUID) -> list[PaymentDue]:
    return list(
        await session.scalars(
            select(PaymentDue).where(PaymentDue.order_id == order_id).order_by(PaymentDue.sequence)
        )
    )


async def orders_of(
    session: AsyncSession, buyer_user_id: uuid.UUID, *, project_id: uuid.UUID | None = None
) -> list[Order]:
    query = select(Order).where(Order.buyer_user_id == buyer_user_id)
    if project_id is not None:
        query = query.where(Order.project_id == project_id)
    return list(await session.scalars(query.order_by(Order.created_at.desc()).limit(100)))
