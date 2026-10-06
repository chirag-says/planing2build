"""Building billing responses from records. The buyer's views never show internal notes,
provider references or other buyers' data; staff views add payments, refunds and history."""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.billing import refunds as refund_service
from p2b.billing.configuration import ActiveOffer
from p2b.billing.models import (
    Invoice,
    Offering,
    OfferingVersion,
    Order,
    PackageEntitlement,
    PackageEntitlementHistory,
    PackageServiceUsage,
    Payment,
    PaymentAttempt,
    PaymentDue,
    Refund,
    RefundDecision,
    RefundRequest,
)
from p2b.billing.orders import OS, Quote, dues_of
from p2b.billing.schemas import (
    AttemptOut,
    DueOut,
    DuePreviewOut,
    EntitlementHistoryOut,
    InvoiceOut,
    OfferOut,
    OpsOrderOut,
    OrderOut,
    OrderSummaryOut,
    PaymentOut,
    RefundDecisionOut,
    RefundOut,
    RefundRequestOut,
    StaffRefundRequestOut,
    TaxLineOut,
)
from p2b.core.vocabulary import (
    DueRule,
    DueState,
    OfferingKind,
    PackageState,
    PaymentMode,
    RefundRequestState,
)


def tax_lines(lines: list[dict[str, str]]) -> list[TaxLineOut]:
    return [
        TaxLineOut(component=t["component"], rate=Decimal(t["rate"]), amount=Decimal(t["amount"]))
        for t in lines
    ]


def offer_out(offer: ActiveOffer, quotes: dict[PaymentMode, Quote]) -> OfferOut:
    first = next(iter(quotes.values()))
    return OfferOut(
        offering_version_id=offer.version.id,
        offering_name=offer.offering.name,
        kind=OfferingKind(offer.offering.kind),
        terms_version=offer.version.terms_version,
        payment_modes=[PaymentMode(m) for m in offer.version.payment_modes],
        is_test=offer.is_test,
        price=first.price,
        taxable_total=first.tax.taxable,
        tax=tax_lines(first.tax.lines),
        tax_total=first.tax.tax_total,
        total=first.tax.total,
        currency="INR",
        prices_include_tax=offer.tax.prices_include_tax,
        pricing_inputs=first.inputs,
        dues={
            mode: [
                DuePreviewOut(
                    sequence=index,
                    amount=amount,
                    taxable_amount=taxable,
                    tax_amount=amount - taxable,
                    due_rule=DueRule.ON_ORDER if index == 1 else DueRule.DAYS_AFTER_ACTIVATION,
                    due_days=None
                    if index == 1 or offer.plan is None
                    else offer.plan.instalments[index - 1].days,
                )
                for index, (amount, _, taxable) in enumerate(quote.dues, start=1)
            ]
            for mode, quote in quotes.items()
        },
    )


def summary(order: Order) -> OrderSummaryOut:
    return OrderSummaryOut(
        order_id=order.id,
        code=order.code,
        kind=OfferingKind(order.kind),
        project_id=order.project_id,
        state=OS(order.state),
        total=order.total,
        currency=order.currency,
        is_test=order.is_test,
        created_at=order.created_at,
    )


async def _requests(
    session: AsyncSession, order_id: uuid.UUID
) -> list[tuple[RefundRequest, RefundDecision | None]]:
    rows = await refund_service.requests_for(session, order_id)
    decisions = {
        d.request_id: d
        for d in await session.scalars(
            select(RefundDecision).where(RefundDecision.request_id.in_([r.id for r in rows]))
        )
    }
    return [(r, decisions.get(r.id)) for r in rows]


def _request_out(request: RefundRequest, decision: RefundDecision | None) -> RefundRequestOut:
    return RefundRequestOut(
        request_id=request.id,
        state=RefundRequestState(request.state),
        reason=request.reason,
        requested_role=request.requested_role,
        created_at=request.created_at,
        decision=RefundDecisionOut(
            decision=decision.decision,
            amount=decision.approved_amount,
            reason=decision.reason,
            decided_at=decision.decided_at,
        )
        if decision
        else None,
    )


async def order_out(session: AsyncSession, order: Order) -> OrderOut:
    version = await session.get_one(OfferingVersion, order.offering_version_id)
    offering = await session.get_one(Offering, version.offering_code)
    dues = await dues_of(session, order.id)
    payable_sequence = next((d.sequence for d in dues if d.state == DueState.DUE.value), None)
    active = (
        order.kind != OfferingKind.PACKAGE.value
        or await session.scalar(
            select(PackageEntitlement.id).where(
                PackageEntitlement.order_id == order.id,
                PackageEntitlement.state == PackageState.ACTIVE.value,
            )
        )
        is not None
    )
    attempts = list(
        await session.scalars(
            select(PaymentAttempt)
            .where(PaymentAttempt.due_id.in_([d.id for d in dues]))
            .order_by(PaymentAttempt.created_at.desc())
            .limit(20)
        )
    )
    sequence = {d.id: d.sequence for d in dues}
    invoices = list(
        await session.scalars(
            select(Invoice).where(Invoice.order_id == order.id).order_by(Invoice.issued_at)
        )
    )
    requests = await _requests(session, order.id)
    refundable = await refund_service.refundable(session, order.id)
    live = order.state in (OS.AWAITING_PAYMENT.value, OS.PART_PAID.value)
    return OrderOut(
        order_id=order.id,
        code=order.code,
        kind=OfferingKind(order.kind),
        project_id=order.project_id,
        state=OS(order.state),
        offering_name=offering.name,
        price=order.price,
        taxable_total=order.taxable_total,
        tax=tax_lines(order.tax),
        tax_total=order.tax_total,
        total=order.total,
        currency=order.currency,
        payment_mode=PaymentMode(order.payment_mode),
        terms_version=order.terms_version,
        buyer=order.buyer,
        is_test=order.is_test,
        created_at=order.created_at,
        dues=[
            DueOut(
                due_id=d.id,
                sequence=d.sequence,
                amount=d.amount,
                taxable_amount=d.taxable_amount,
                tax_amount=d.tax_amount,
                tax=tax_lines(d.tax),
                due_rule=DueRule(d.due_rule),
                due_days=d.due_days,
                due_at=d.due_at,
                state=DueState(d.state),
                paid_at=d.paid_at,
                payable=live and d.sequence == payable_sequence and (d.sequence == 1 or active),
            )
            for d in dues
        ],
        attempts=[
            AttemptOut(
                attempt_id=a.id,
                due_sequence=sequence[a.due_id],
                state=a.state,
                created_at=a.created_at,
                finished_at=a.finished_at,
                failure_code=a.failure_code,
            )
            for a in attempts
        ],
        invoices=[
            InvoiceOut(
                invoice_id=i.id,
                kind=i.kind,
                code=i.code,
                total=i.total,
                issued_at=i.issued_at,
                document_ready=i.document_id is not None,
            )
            for i in invoices
        ],
        refund_requests=[_request_out(r, d) for r, d in requests],
        refundable=refundable,
        can_cancel=order.state == OS.AWAITING_PAYMENT.value,
        can_request_refund=refundable > 0
        and not any(
            r.state in (RefundRequestState.REQUESTED.value, RefundRequestState.APPROVED.value)
            for r, _ in requests
        ),
    )


async def staff_requests(
    session: AsyncSession, requests: list[RefundRequest], emails: dict[uuid.UUID, str]
) -> list[StaffRefundRequestOut]:
    result = []
    for request in requests:
        order = await session.get_one(Order, request.order_id)
        decision = (
            await session.scalars(
                select(RefundDecision).where(RefundDecision.request_id == request.id)
            )
        ).one_or_none()
        refunds = (
            list(
                await session.scalars(
                    select(Refund)
                    .where(Refund.decision_id == decision.id)
                    .order_by(Refund.created_at)
                )
            )
            if decision
            else []
        )
        used: list[str] = []
        if order.kind == OfferingKind.PACKAGE.value:
            used = list(
                await session.scalars(
                    select(PackageServiceUsage.service)
                    .join(
                        PackageEntitlement,
                        PackageEntitlement.id == PackageServiceUsage.entitlement_id,
                    )
                    .where(PackageEntitlement.order_id == order.id)
                )
            )
        base = _request_out(request, decision)
        result.append(
            StaffRefundRequestOut(
                **base.model_dump(),
                order_id=order.id,
                order_code=order.code,
                kind=OfferingKind(order.kind),
                project_id=order.project_id,
                buyer_email=emails.get(order.buyer_user_id),
                refundable=await refund_service.refundable(session, order.id),
                refunds=[refund_out(r) for r in refunds],
                package_services_used=used,
            )
        )
    return result


def refund_out(refund: Refund) -> RefundOut:
    return RefundOut(
        refund_id=refund.id,
        payment_id=refund.payment_id,
        amount=refund.amount,
        state=refund.state,
        provider_refund_id=refund.provider_refund_id,
        failure=refund.failure,
        created_at=refund.created_at,
    )


async def ops_order_out(
    session: AsyncSession, order: Order, emails: dict[uuid.UUID, str]
) -> OpsOrderOut:
    base = await order_out(session, order)
    payments = list(
        await session.scalars(
            select(Payment)
            .join(PaymentAttempt, PaymentAttempt.id == Payment.attempt_id)
            .join(PaymentDue, PaymentDue.id == PaymentAttempt.due_id)
            .where(PaymentDue.order_id == order.id)
            .order_by(Payment.captured_at)
        )
    )
    refunds = list(
        await session.scalars(
            select(Refund)
            .where(Refund.payment_id.in_([p.id for p in payments]))
            .order_by(Refund.created_at)
        )
    )
    history = list(
        await session.scalars(
            select(PackageEntitlementHistory)
            .join(
                PackageEntitlement,
                PackageEntitlement.id == PackageEntitlementHistory.entitlement_id,
            )
            .where(PackageEntitlement.order_id == order.id)
            .order_by(PackageEntitlementHistory.at)
        )
    )
    requests = await refund_service.requests_for(session, order.id)
    return OpsOrderOut(
        **base.model_dump(),
        buyer_email=emails.get(order.buyer_user_id),
        payments=[
            PaymentOut(
                payment_id=p.id,
                provider_payment_id=p.provider_payment_id,
                amount=p.amount,
                method=p.method,
                applied=p.applied,
                source=p.source,
                captured_at=p.captured_at,
            )
            for p in payments
        ],
        refunds=[refund_out(r) for r in refunds],
        package_history=[
            EntitlementHistoryOut(
                from_state=h.from_state,
                to_state=h.to_state,
                reason=h.reason,
                actor_role=h.actor_role,
                at=h.at,
            )
            for h in history
        ],
        staff_refund_requests=await staff_requests(session, requests, emails),
    )
