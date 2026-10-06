"""Billing routes for families (homeowner host), the provider's webhook, and the fake gateway's
development checkout (SLICE3_3_READINESS I). Every creating or transition POST takes an
`Idempotency-Key`; nothing a client sends is a charge amount."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from p2b.audit.interface import record_security_event
from p2b.billing import credits as credit_service
from p2b.billing import entitlements, orders, payments, refunds
from p2b.billing.configuration import active_offer
from p2b.billing.models import Invoice, Order, PaymentAttempt, PaymentDue
from p2b.billing.orders import Buyer
from p2b.billing.schemas import (
    AttemptStateOut,
    BillingOverviewOut,
    CheckoutOut,
    CheckoutReturnIn,
    CreditEntryOut,
    CreditOrderIn,
    CreditsOut,
    DownloadOut,
    EntitlementOut,
    FakePayIn,
    FakePayOut,
    OrderOut,
    PackageOrderIn,
    PackageViewOut,
    RefundRequestIn,
    UnavailableOut,
    WebhookAck,
)
from p2b.billing.tax import STATE_CODES
from p2b.billing.views import offer_out, order_out, summary
from p2b.core.authz import public_route
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import Database, DbSession
from p2b.core.errors import (
    AppError,
    BillingNotConfigured,
    NotFound,
    PriceUnavailable,
    SignatureInvalid,
    ValidationFailed,
)
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.payments import PaymentGateway, PaymentStatus
from p2b.core.ratelimit import Limit, enforce
from p2b.core.storage import DOWNLOAD_URL_TTL_SECONDS
from p2b.core.vocabulary import Audience, OfferingKind, PackageState, PaymentMode, SecuritySeverity
from p2b.documents.interface import personal_file_url
from p2b.identity.interface import Actor, require_actor
from p2b.projects.interface import billing_facts

router = APIRouter(tags=["billing"])

HOMEOWNER = require_actor(Audience.IHB)
CHECKOUT_LIMIT = Limit("checkout_due", 5, 3600)  # INTEGRATION 75: 5 attempts per due per hour
ORDER_LIMIT = Limit("billing_orders_session", 20, 600)  # T2
WEBHOOK_LIMIT = Limit("webhook_ip", 120, 60)  # T4
WEBHOOK_MAX_BYTES = 256 * 1024


def _gateway(request: Request) -> PaymentGateway:
    gateway: PaymentGateway = request.app.state.payment_gateway
    return gateway


def _ip_hash(request: Request) -> str:
    settings: Settings = request.app.state.settings
    peer = request.client.host if request.client else None
    return keyed_hash(
        settings.identifier_pepper.get_secret_value(), client_ip(request.headers, peer)
    )


def _buyer(body: PackageOrderIn | CreditOrderIn) -> Buyer:
    try:
        return Buyer.model_validate(body.buyer.model_dump())
    except ValueError as exc:
        raise ValidationFailed(details={"fields": {"buyer": [str(exc)[:300]]}}) from None


def _unavailable(exc: AppError) -> UnavailableOut:
    return UnavailableOut(code=exc.code, missing=[str(m) for m in exc.details.get("missing", [])])


# --- the package ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/package", response_model=PackageViewOut)
async def get_package(
    project_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
    buyer_state: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
) -> PackageViewOut:
    """The package on the project: availability, state, and when it can be bought, the price
    the server computes now (tax for `buyer_state`, the seller's state by default)."""
    facts = await billing_facts(db, project_id)
    if facts is None or facts.owner_user_id != actor.user_id:
        raise NotFound
    settings: Settings = request.app.state.settings
    entitlement = await entitlements.active_entitlement(db, project_id)
    state = await entitlements.package_state(db, project_id)
    project_orders = await orders.orders_of(db, actor.user_id, project_id=project_id)
    offer = unavailable = None
    if state != PackageState.ACTIVE and facts.availability.value == "ELIGIBLE":
        try:
            active = await active_offer(db, settings, OfferingKind.PACKAGE)
            quotes = {
                PaymentMode(mode): await orders.package_quote(
                    db,
                    settings,
                    actor,
                    project_id,
                    PaymentMode(mode),
                    buyer_state if buyer_state in STATE_CODES else None,
                )
                for mode in active.version.payment_modes
            }
            offer = offer_out(active, quotes)
        except (BillingNotConfigured, PriceUnavailable) as exc:
            unavailable = _unavailable(exc)
    open_order = next((o.id for o in project_orders if o.state == "AWAITING_PAYMENT"), None)
    return PackageViewOut(
        project_id=project_id,
        availability=facts.availability,
        state=state,
        entitlement=EntitlementOut(
            state=PackageState(entitlement.state),
            activated_at=entitlement.activated_at,
            ended_at=entitlement.ended_at,
        )
        if entitlement
        else None,
        offer=offer,
        unavailable=unavailable,
        open_order_id=open_order,
        orders=[summary(o) for o in project_orders],
        states=STATE_CODES,
    )


@router.post("/projects/{project_id}/package/orders", response_model=OrderOut, status_code=201)
async def post_package_order(
    project_id: uuid.UUID,
    body: PackageOrderIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    await enforce(request.app.state.database, ORDER_LIMIT, str(actor.session_id))

    async def act() -> tuple[int, dict[str, object]]:
        order = await orders.create_package_order(
            db,
            request.app.state.settings,
            actor,
            project_id,
            offering_version_id=body.offering_version_id,
            payment_mode=body.payment_mode,
            buyer=_buyer(body),
            accept_terms_version=body.accept_terms_version,
        )
        return 201, (await order_out(db, order)).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body={"project": str(project_id), **body.model_dump(mode="json")},
        action=act,
    )


# --- AI credits ----------------------------------------------------------------------------


@router.get("/me/ai-credits", response_model=CreditsOut)
async def get_credits(
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
    buyer_state: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
) -> CreditsOut:
    settings: Settings = request.app.state.settings
    offer = unavailable = None
    try:
        active = await active_offer(db, settings, OfferingKind.AI_CREDIT)
        quote = await orders.credit_quote(
            db, settings, buyer_state if buyer_state in STATE_CODES else None
        )
        offer = offer_out(active, {PaymentMode.FULL: quote})
    except (BillingNotConfigured, PriceUnavailable) as exc:
        unavailable = _unavailable(exc)
    entries = await credit_service.ledger(db, actor.user_id)
    return CreditsOut(
        balance=entries[0].balance_after if entries else 0,
        entries=[
            CreditEntryOut(
                entry=e.entry,
                quantity=e.quantity,
                balance_after=e.balance_after,
                at=e.at,
            )
            for e in entries
        ],
        offer=offer,
        unavailable=unavailable,
        states=STATE_CODES,
    )


@router.post("/ai-credits/orders", response_model=OrderOut, status_code=201)
async def post_credit_order(
    body: CreditOrderIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    await enforce(request.app.state.database, ORDER_LIMIT, str(actor.session_id))

    async def act() -> tuple[int, dict[str, object]]:
        order = await orders.create_credit_order(
            db,
            request.app.state.settings,
            actor,
            offering_version_id=body.offering_version_id,
            buyer=_buyer(body),
            accept_terms_version=body.accept_terms_version,
        )
        return 201, (await order_out(db, order)).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body=body.model_dump(mode="json"),
        action=act,
    )


# --- orders, checkout and the callback hint -----------------------------------------------


@router.get("/me/billing", response_model=BillingOverviewOut)
async def get_billing(db: DbSession, actor: Annotated[Actor, HOMEOWNER]) -> BillingOverviewOut:
    return BillingOverviewOut(
        orders=[summary(o) for o in await orders.orders_of(db, actor.user_id)],
        credit_balance=await credit_service.credit_balance(db, actor.user_id),
    )


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> OrderOut:
    return await order_out(db, await orders.own_order(db, actor, order_id))


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
async def post_cancel_order(
    order_id: uuid.UUID,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """The buyer ends an unpaid order (to choose another payment mode, or not to buy)."""

    async def act() -> tuple[int, dict[str, object]]:
        order = await orders.own_order(db, actor, order_id)
        order = await orders.cancel_order(
            db, order, reason="cancelled by the buyer", actor_user_id=actor.user_id
        )
        return 200, (await order_out(db, order)).model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key, request_body={"cancel": str(order_id)}, action=act
    )


@router.post("/payment-dues/{due_id}/checkout", response_model=CheckoutOut)
async def post_checkout(
    due_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> CheckoutOut:
    """An attempt and the provider order for the due's exact amount (reused while open)."""

    async def limit() -> None:
        await enforce(request.app.state.database, CHECKOUT_LIMIT, str(due_id))

    ticket = await payments.start_checkout(
        db, request.app.state.settings, _gateway(request), actor, due_id, on_new_attempt=limit
    )
    return CheckoutOut(
        attempt_id=ticket.attempt.id,
        provider=ticket.provider,
        key_id=ticket.key_id,
        provider_order_id=ticket.attempt.provider_order_id,
        amount_paise=ticket.amount_paise,
        currency=ticket.attempt.currency,
        order_code=ticket.order.code,
        description=f"Plan2Build {ticket.order.kind.replace('_', ' ').lower()} {ticket.order.code}",
    )


@router.post("/payment-attempts/{attempt_id}/confirm", response_model=AttemptStateOut)
async def post_checkout_returned(
    attempt_id: uuid.UUID,
    body: CheckoutReturnIn,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> AttemptStateOut:
    """The checkout callback. A hint only: it verifies the signature and queues a verified fetch
    from the provider; it never marks anything paid."""
    try:
        attempt = await payments.checkout_returned(
            db,
            _gateway(request),
            actor,
            attempt_id,
            provider_order_id=body.provider_order_id,
            provider_payment_id=body.provider_payment_id,
            signature=body.signature,
        )
    except SignatureInvalid:
        await record_security_event(
            request.app.state.database,
            kind="CHECKOUT_SIGNATURE_INVALID",
            severity=SecuritySeverity.WARNING,
            audience=Audience.IHB,
            user_id=actor.user_id,
            ip_hash=_ip_hash(request),
            details={"attempt_id": str(attempt_id)},
        )
        raise
    return AttemptStateOut(attempt_id=attempt.id, state=attempt.state, verifying=True)


@router.post("/orders/{order_id}/refund-requests", response_model=OrderOut, status_code=201)
async def post_refund_request(
    order_id: uuid.UUID,
    body: RefundRequestIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    async def act() -> tuple[int, dict[str, object]]:
        await refunds.request_refund(db, actor, order_id, reason=body.reason)
        order = await orders.own_order(db, actor, order_id)
        return 201, (await order_out(db, order)).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body={"order": str(order_id), **body.model_dump()},
        action=act,
    )


@router.get("/invoices/{invoice_id}/document", response_model=DownloadOut)
async def get_invoice_document(
    invoice_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> DownloadOut:
    invoice = await db.get(Invoice, invoice_id)
    if invoice is None or invoice.document_id is None:
        raise NotFound
    await orders.own_order(db, actor, invoice.order_id)
    url = await personal_file_url(
        db, request.app.state.storage, actor, invoice.document_id, _ip_hash(request)
    )
    return DownloadOut(url=url, expires_in_seconds=DOWNLOAD_URL_TTL_SECONDS)


# --- the provider's webhook ---------------------------------------------------------------


@router.post("/webhooks/razorpay", response_model=WebhookAck, dependencies=[public_route])
async def post_razorpay_webhook(
    request: Request,
    db: DbSession,
    signature: Annotated[str, Header(alias="X-Razorpay-Signature")] = "",
    event_id: Annotated[str, Header(alias="X-Razorpay-Event-Id")] = "",
) -> WebhookAck:
    """Signature on the raw body, then stored once and processed by a job. 200 for a replay."""
    database: Database = request.app.state.database
    await enforce(database, WEBHOOK_LIMIT, _ip_hash(request))
    body = await request.body()
    if len(body) > WEBHOOK_MAX_BYTES or not event_id:
        raise ValidationFailed(details={"webhook": "body too large or no event id"})
    try:
        await payments.receive_webhook(
            db, _gateway(request), body=body, signature=signature, event_id=event_id
        )
    except SignatureInvalid:
        await record_security_event(
            database,
            kind="WEBHOOK_SIGNATURE_INVALID",
            severity=SecuritySeverity.WARNING,
            ip_hash=_ip_hash(request),
            details={"provider": _gateway(request).name},
        )
        raise
    return WebhookAck()


# --- the fake gateway's checkout (local development and tests only) -----------------------

dev_router = APIRouter(tags=["billing-development"])


@dev_router.post("/dev/fake-gateway/attempts/{attempt_id}/pay", response_model=FakePayOut)
async def post_fake_pay(
    attempt_id: uuid.UUID,
    body: FakePayIn,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> FakePayOut:
    """Stands in for the shopper and for Razorpay: the fake provider records a payment, sends
    its signed webhook to the real webhook path, and returns what the checkout widget would
    hand the page. Registered only with the fake gateway, never in staging or production."""
    from p2b.integrations.fake_gateway import FakeGateway

    gateway = _gateway(request)
    if not isinstance(gateway, FakeGateway):
        raise NotFound
    attempt = await db.get(PaymentAttempt, attempt_id)
    if attempt is None:
        raise NotFound
    due = await db.get_one(PaymentDue, attempt.due_id)
    order = await db.get_one(Order, due.order_id)
    if order.buyer_user_id != actor.user_id:
        raise NotFound
    status: PaymentStatus = "captured" if body.outcome == "capture" else "failed"
    payment = await gateway.simulate_payment(attempt.provider_order_id, status=status)
    event = "payment.captured" if status == "captured" else "payment.failed"
    raw, signature, event_id = gateway.signed_webhook(event, payment=payment)
    database: Database = request.app.state.database
    async with database.transaction() as session:
        await payments.receive_webhook(
            session, gateway, body=raw, signature=signature, event_id=event_id
        )
    return FakePayOut(
        provider_order_id=attempt.provider_order_id,
        provider_payment_id=payment.payment_id,
        signature=gateway.checkout_signature(attempt.provider_order_id, payment.payment_id)
        if status == "captured"
        else None,
    )
