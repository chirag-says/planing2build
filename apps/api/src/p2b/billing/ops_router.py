"""Operations and ADMIN billing routes (admin host; SLICE3_3_READINESS I, K). Refund decisions,
exceptions and package cancellation need a staff role and MFA verified within the window, with
a reason, an audit row and history. Configuration is ADMIN only: new versions, then a separate
publish; never an edit in place."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.billing import configuration, entitlements, exceptions, payments, refunds
from p2b.billing.models import (
    BillingException,
    InstalmentPlanVersion,
    Invoice,
    Order,
    PricingRuleVersion,
    RefundRequest,
    TaxConfigurationVersion,
)
from p2b.billing.pricing import evaluate, parse_rule
from p2b.billing.schemas import (
    ApproveRefundIn,
    ChecklistIn,
    ChecklistItemOut,
    ChecklistOut,
    ConfigVersionOut,
    DownloadOut,
    ExceptionOut,
    InstalmentPlanIn,
    OfferingVersionIn,
    OpsOrderOut,
    OrderSummaryOut,
    PreviewIn,
    PreviewOut,
    PricingRuleIn,
    ReasonIn,
    ReconcileOut,
    ResolveIn,
    StaffRefundIn,
    StaffRefundRequestOut,
    TaxConfigurationIn,
)
from p2b.billing.views import ops_order_out, staff_requests, summary
from p2b.catalog.interface import (
    ChecklistItem,
    EligibilityChecklist,
    create_eligibility_checklist,
    eligibility_checklists,
    publish_eligibility_checklist,
)
from p2b.core.crypto import keyed_hash
from p2b.core.db import DbSession
from p2b.core.errors import NotFound
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.storage import DOWNLOAD_URL_TTL_SECONDS
from p2b.core.vocabulary import Audience, OrderState, RefundRequestState, StaffRole
from p2b.documents.interface import staff_download_url
from p2b.identity.interface import Actor, active_roles, primary_emails, require_actor

router = APIRouter(tags=["billing-operations"])

STAFF = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.OPS, StaffRole.ADMIN))
ADMIN = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.ADMIN,))


async def _role(db: AsyncSession, actor: Actor) -> str:
    roles = await active_roles(db, actor.user_id)
    return StaffRole.ADMIN.value if StaffRole.ADMIN in roles else StaffRole.OPS.value


async def _order_detail(db: AsyncSession, order: Order) -> OpsOrderOut:
    emails = await primary_emails(db, [order.buyer_user_id])
    return await ops_order_out(db, order, emails)


# --- orders, refunds, exceptions -----------------------------------------------------------


@router.get("/ops/billing/orders", response_model=list[OrderSummaryOut])
async def get_orders(
    db: DbSession,
    _: Annotated[Actor, STAFF],
    state: Annotated[OrderState | None, Query()] = None,
) -> list[OrderSummaryOut]:
    query = select(Order).order_by(Order.created_at.desc()).limit(100)
    if state is not None:
        query = query.where(Order.state == state.value)
    return [summary(o) for o in await db.scalars(query)]


@router.get("/ops/billing/orders/{order_id}", response_model=OpsOrderOut)
async def get_order(order_id: uuid.UUID, db: DbSession, _: Annotated[Actor, STAFF]) -> OpsOrderOut:
    order = await db.get(Order, order_id)
    if order is None:
        raise NotFound
    return await _order_detail(db, order)


@router.get("/ops/billing/invoices/{invoice_id}/document", response_model=DownloadOut)
async def get_invoice_document(
    invoice_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, STAFF]
) -> DownloadOut:
    invoice = await db.get(Invoice, invoice_id)
    if invoice is None or invoice.document_id is None:
        raise NotFound
    settings = request.app.state.settings
    peer = request.client.host if request.client else None
    ip_hash = keyed_hash(
        settings.identifier_pepper.get_secret_value(), client_ip(request.headers, peer)
    )
    url = await staff_download_url(
        db,
        request.app.state.storage,
        viewer_user_id=actor.user_id,
        file_id=invoice.document_id,
        ip_hash=ip_hash,
    )
    return DownloadOut(url=url, expires_in_seconds=DOWNLOAD_URL_TTL_SECONDS)


@router.post(
    "/ops/billing/orders/{order_id}/refund-requests", response_model=OpsOrderOut, status_code=201
)
async def post_staff_refund_request(
    order_id: uuid.UUID,
    body: StaffRefundIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    async def act() -> tuple[int, dict[str, object]]:
        await refunds.staff_request(
            db, actor, await _role(db, actor), order_id, amount=body.amount, reason=body.reason
        )
        order = await db.get_one(Order, order_id)
        return 201, (await _order_detail(db, order)).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body={"order": str(order_id), **body.model_dump(mode="json")},
        action=act,
    )


@router.get("/ops/billing/refund-requests", response_model=list[StaffRefundRequestOut])
async def get_refund_requests(
    db: DbSession,
    _: Annotated[Actor, STAFF],
    state: Annotated[RefundRequestState | None, Query()] = None,
) -> list[StaffRefundRequestOut]:
    query = select(RefundRequest).order_by(RefundRequest.created_at).limit(100)
    if state is not None:
        query = query.where(RefundRequest.state == state.value)
    rows = list(await db.scalars(query))
    buyers = {r.order_id: (await db.get_one(Order, r.order_id)).buyer_user_id for r in rows}
    emails = await primary_emails(db, list(set(buyers.values())))
    return await staff_requests(db, rows, emails)


async def _refund_detail(db: AsyncSession, request_id: uuid.UUID) -> StaffRefundRequestOut:
    request = await db.get(RefundRequest, request_id)
    if request is None:
        raise NotFound
    order = await db.get_one(Order, request.order_id)
    emails = await primary_emails(db, [order.buyer_user_id])
    return (await staff_requests(db, [request], emails))[0]


@router.get("/ops/billing/refund-requests/{request_id}", response_model=StaffRefundRequestOut)
async def get_refund_request(
    request_id: uuid.UUID, db: DbSession, _: Annotated[Actor, STAFF]
) -> StaffRefundRequestOut:
    return await _refund_detail(db, request_id)


@router.post(
    "/ops/billing/refund-requests/{request_id}/approve", response_model=StaffRefundRequestOut
)
async def post_approve_refund(
    request_id: uuid.UUID,
    body: ApproveRefundIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    async def act() -> tuple[int, dict[str, object]]:
        await refunds.decide(
            db,
            actor,
            await _role(db, actor),
            request_id,
            approve=True,
            amount=body.amount,
            ends_package=body.ends_package,
            credits_revoked=body.credits_revoked,
            reason=body.reason,
        )
        return 200, (await _refund_detail(db, request_id)).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body={"approve": str(request_id), **body.model_dump(mode="json")},
        action=act,
    )


@router.post(
    "/ops/billing/refund-requests/{request_id}/decline", response_model=StaffRefundRequestOut
)
async def post_decline_refund(
    request_id: uuid.UUID,
    body: ReasonIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    async def act() -> tuple[int, dict[str, object]]:
        await refunds.decide(
            db,
            actor,
            await _role(db, actor),
            request_id,
            approve=False,
            amount=None,
            ends_package=False,
            credits_revoked=0,
            reason=body.reason,
        )
        return 200, (await _refund_detail(db, request_id)).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body={"decline": str(request_id), **body.model_dump()},
        action=act,
    )


@router.post(
    "/ops/billing/refund-requests/{request_id}/retry", response_model=StaffRefundRequestOut
)
async def post_retry_refund(
    request_id: uuid.UUID, key: IdempotencyKeyHeader, db: DbSession, actor: Annotated[Actor, STAFF]
) -> JSONResponse:
    async def act() -> tuple[int, dict[str, object]]:
        await refunds.retry(db, actor, await _role(db, actor), request_id)
        return 200, (await _refund_detail(db, request_id)).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body={"retry": str(request_id)},
        action=act,
    )


@router.post("/ops/billing/packages/{project_id}/cancel", response_model=OpsOrderOut)
async def post_cancel_package(
    project_id: uuid.UUID,
    body: ReasonIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, ADMIN],
) -> JSONResponse:
    """ACTIVE -> CANCELLED without a refund (ADMIN, MFA, reason)."""

    async def act() -> tuple[int, dict[str, object]]:
        entitlement = await entitlements.cancel_package(
            db,
            project_id,
            reason=body.reason,
            actor_user_id=actor.user_id,
            actor_role=StaffRole.ADMIN.value,
        )
        order = await db.get_one(Order, entitlement.order_id)
        return 200, (await _order_detail(db, order)).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body={"cancel_package": str(project_id), **body.model_dump()},
        action=act,
    )


def _exception_out(row: BillingException, codes: dict[uuid.UUID, str]) -> ExceptionOut:
    return ExceptionOut(
        exception_id=row.id,
        kind=row.kind,
        state=row.state,
        provider_ref=row.provider_ref,
        order_id=row.order_id,
        order_code=codes.get(row.order_id) if row.order_id else None,
        payment_id=row.payment_id,
        expected=row.expected,
        observed=row.observed,
        created_at=row.created_at,
        resolution=row.resolution,
        resolved_at=row.resolved_at,
    )


async def _codes(db: AsyncSession, rows: list[BillingException]) -> dict[uuid.UUID, str]:
    ids = [r.order_id for r in rows if r.order_id]
    return dict((await db.execute(select(Order.id, Order.code).where(Order.id.in_(ids)))).all())


@router.get("/ops/billing/exceptions", response_model=list[ExceptionOut])
async def get_exceptions(db: DbSession, _: Annotated[Actor, STAFF]) -> list[ExceptionOut]:
    rows = await exceptions.open_exceptions(db)
    codes = await _codes(db, rows)
    return [_exception_out(r, codes) for r in rows]


@router.post("/ops/billing/exceptions/{exception_id}/resolve", response_model=ExceptionOut)
async def post_resolve_exception(
    exception_id: uuid.UUID, body: ResolveIn, db: DbSession, actor: Annotated[Actor, STAFF]
) -> ExceptionOut:
    row = await exceptions.resolve_exception(
        db,
        exception_id,
        resolution=body.resolution,
        actor_user_id=actor.user_id,
        actor_role=await _role(db, actor),
        session_id=actor.session_id,
    )
    return _exception_out(row, await _codes(db, [row]))


@router.post("/admin/billing/reconcile", response_model=ReconcileOut)
async def post_reconcile(request: Request, _: Annotated[Actor, ADMIN]) -> ReconcileOut:
    """Runs both reconciliations now (normally every 15 minutes and daily)."""
    database, settings = request.app.state.database, request.app.state.settings
    gateway = request.app.state.payment_gateway
    frequent = await payments.reconcile_open_attempts(database, settings, gateway)
    daily = await payments.reconcile_daily(database, settings, gateway)
    return ReconcileOut(counts={**frequent, **{f"daily_{k}": v for k, v in daily.items()}})


# --- configuration (ADMIN) -----------------------------------------------------------------


def _content(row: Any) -> dict[str, Any]:
    if isinstance(row, PricingRuleVersion):
        return {"offering_code": row.offering_code, "rule": row.rule, "currency": row.currency}
    if isinstance(row, InstalmentPlanVersion):
        return {"instalments": row.instalments}
    if isinstance(row, TaxConfigurationVersion):
        return {
            "legal_name": row.legal_name,
            "address": row.address,
            "gstin": row.gstin,
            "state_code": row.state_code,
            "invoice_series": row.invoice_series,
            "prices_include_tax": row.prices_include_tax,
            "lines": row.lines,
        }
    return {
        "offering_code": row.offering_code,
        "pricing_rule_version_id": str(row.pricing_rule_version_id),
        "payment_modes": row.payment_modes,
        "instalment_plan_version_id": str(row.instalment_plan_version_id)
        if row.instalment_plan_version_id
        else None,
        "terms_version": row.terms_version,
    }


def _version_out(kind: str, row: Any) -> ConfigVersionOut:
    return ConfigVersionOut(
        version_id=row.id,
        kind=kind,
        version=row.version,
        status=row.status,
        is_test=row.is_test,
        note=row.note,
        created_at=row.created_at,
        published_at=row.published_at,
        content=_content(row),
    )


@router.get("/admin/billing/{kind}", response_model=list[ConfigVersionOut])
async def get_versions(
    kind: configuration.ConfigKind, db: DbSession, _: Annotated[Actor, ADMIN]
) -> list[ConfigVersionOut]:
    return [_version_out(kind, row) for row in await configuration.versions(db, kind)]


@router.post("/admin/billing/pricing-rules", response_model=ConfigVersionOut, status_code=201)
async def post_pricing_rule(
    body: PricingRuleIn, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> ConfigVersionOut:
    row = await configuration.create_pricing_rule(
        db,
        offering_code=body.offering_code,
        rule=body.rule,
        is_test=body.is_test,
        note=body.note,
        actor_user_id=actor.user_id,
        session_id=actor.session_id,
    )
    return _version_out("pricing-rules", row)


@router.post("/admin/billing/pricing-rules/{version_id}/preview", response_model=PreviewOut)
async def post_preview(
    version_id: uuid.UUID, body: PreviewIn, db: DbSession, _: Annotated[Actor, ADMIN]
) -> PreviewOut:
    row = await db.get(PricingRuleVersion, version_id)
    if row is None:
        raise NotFound
    price, inputs = evaluate(parse_rule(row.rule), body.characteristics)
    return PreviewOut(price=price, inputs=inputs)


@router.post("/admin/billing/instalment-plans", response_model=ConfigVersionOut, status_code=201)
async def post_instalment_plan(
    body: InstalmentPlanIn, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> ConfigVersionOut:
    row = await configuration.create_instalment_plan(
        db,
        instalments=body.instalments,
        is_test=body.is_test,
        note=body.note,
        actor_user_id=actor.user_id,
        session_id=actor.session_id,
    )
    return _version_out("instalment-plans", row)


@router.post("/admin/billing/tax-configurations", response_model=ConfigVersionOut, status_code=201)
async def post_tax_configuration(
    body: TaxConfigurationIn, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> ConfigVersionOut:
    row = await configuration.create_tax_configuration(
        db, **body.model_dump(), actor_user_id=actor.user_id, session_id=actor.session_id
    )
    return _version_out("tax-configurations", row)


@router.post("/admin/billing/offerings", response_model=ConfigVersionOut, status_code=201)
async def post_offering_version(
    body: OfferingVersionIn, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> ConfigVersionOut:
    row = await configuration.create_offering_version(
        db, **body.model_dump(), actor_user_id=actor.user_id, session_id=actor.session_id
    )
    return _version_out("offerings", row)


@router.post("/admin/billing/{kind}/{version_id}/publish", response_model=ConfigVersionOut)
async def post_publish(
    kind: configuration.ConfigKind,
    version_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, ADMIN],
) -> ConfigVersionOut:
    row = await configuration.publish(
        db,
        request.app.state.settings,
        kind,
        version_id,
        actor_user_id=actor.user_id,
        session_id=actor.session_id,
    )
    return _version_out(kind, row)


def _checklist_out(checklist: EligibilityChecklist) -> ChecklistOut:
    return ChecklistOut(
        version_id=checklist.id,
        version=checklist.version,
        status=checklist.status,
        items=[ChecklistItemOut(id=i.id, label=i.label, help=i.help) for i in checklist.items],
        note=checklist.note,
    )


@router.get("/admin/eligibility-checklists", response_model=list[ChecklistOut])
async def get_checklists(db: DbSession, _: Annotated[Actor, ADMIN]) -> list[ChecklistOut]:
    return [_checklist_out(c) for c in await eligibility_checklists(db)]


@router.post("/admin/eligibility-checklists", response_model=ChecklistOut, status_code=201)
async def post_checklist(
    body: ChecklistIn, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> ChecklistOut:
    checklist = await create_eligibility_checklist(
        db,
        items=[ChecklistItem(i.id, i.label, i.help) for i in body.items],
        note=body.note,
        created_by=actor.user_id,
    )
    return _checklist_out(checklist)


@router.post("/admin/eligibility-checklists/{version_id}/publish", response_model=ChecklistOut)
async def post_publish_checklist(
    version_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> ChecklistOut:
    return _checklist_out(
        await publish_eligibility_checklist(db, version_id, published_by=actor.user_id)
    )
