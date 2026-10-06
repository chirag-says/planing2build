"""Billing API contracts (SLICE3_3_READINESS I). Money is a decimal string in rupees; nothing a
client sends is an amount the server will charge (requests carry versions and choices only, and
unknown fields are refused)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from p2b.core.vocabulary import (
    AttemptState,
    BillingExceptionKind,
    BillingExceptionState,
    ConfigStatus,
    CreditEntry,
    DueRule,
    DueState,
    InvoiceKind,
    OfferingKind,
    OrderState,
    PackageAvailability,
    PackageState,
    PaymentMode,
    RefundRequestState,
    RefundState,
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaxLineOut(BaseModel):
    component: str
    rate: Decimal
    amount: Decimal


class DuePreviewOut(BaseModel):
    sequence: int
    amount: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal
    due_rule: DueRule
    due_days: int | None


class OfferOut(BaseModel):
    """The price now, computed by the server for the buyer's state (the seller's by default)."""

    offering_version_id: uuid.UUID
    offering_name: str
    kind: OfferingKind
    terms_version: str
    payment_modes: list[PaymentMode]
    is_test: bool = Field(description="Development values: never a real price")
    price: Decimal
    taxable_total: Decimal
    tax: list[TaxLineOut]
    tax_total: Decimal
    total: Decimal
    currency: str
    prices_include_tax: bool
    pricing_inputs: dict[str, Any]
    dues: dict[PaymentMode, list[DuePreviewOut]]


class UnavailableOut(BaseModel):
    code: str = Field(description="BILLING_NOT_CONFIGURED or PRICE_UNAVAILABLE")
    missing: list[str]


class OrderSummaryOut(BaseModel):
    order_id: uuid.UUID
    code: str
    kind: OfferingKind
    project_id: uuid.UUID | None
    state: OrderState
    total: Decimal
    currency: str
    is_test: bool
    created_at: datetime


class EntitlementOut(BaseModel):
    state: PackageState
    activated_at: datetime
    ended_at: datetime | None


class PackageViewOut(BaseModel):
    project_id: uuid.UUID
    availability: PackageAvailability
    state: PackageState
    entitlement: EntitlementOut | None
    offer: OfferOut | None
    unavailable: UnavailableOut | None
    open_order_id: uuid.UUID | None
    orders: list[OrderSummaryOut]
    states: dict[str, str] = Field(description="GST state codes and names for billing details")


class BuyerIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=500)
    state_code: str = Field(min_length=2, max_length=2)
    gstin: str = Field(default="", max_length=15)


class PackageOrderIn(Strict):
    offering_version_id: uuid.UUID
    payment_mode: PaymentMode
    buyer: BuyerIn
    accept_terms_version: str = Field(min_length=1, max_length=40)


class CreditOrderIn(Strict):
    offering_version_id: uuid.UUID
    buyer: BuyerIn
    accept_terms_version: str = Field(min_length=1, max_length=40)


class DueOut(BaseModel):
    due_id: uuid.UUID
    sequence: int
    amount: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal
    tax: list[TaxLineOut]
    due_rule: DueRule
    due_days: int | None
    due_at: datetime | None
    state: DueState
    paid_at: datetime | None
    payable: bool = Field(description="The next due the buyer can pay now")


class AttemptOut(BaseModel):
    attempt_id: uuid.UUID
    due_sequence: int
    state: AttemptState
    created_at: datetime
    finished_at: datetime | None
    failure_code: str | None


class InvoiceOut(BaseModel):
    invoice_id: uuid.UUID
    kind: InvoiceKind
    code: str
    total: Decimal
    issued_at: datetime
    document_ready: bool


class RefundDecisionOut(BaseModel):
    decision: Literal["APPROVED", "DECLINED"]
    amount: Decimal | None
    reason: str
    decided_at: datetime


class RefundRequestOut(BaseModel):
    request_id: uuid.UUID
    state: RefundRequestState
    reason: str
    requested_role: str
    created_at: datetime
    decision: RefundDecisionOut | None


class OrderOut(BaseModel):
    order_id: uuid.UUID
    code: str
    kind: OfferingKind
    project_id: uuid.UUID | None
    state: OrderState
    offering_name: str
    price: Decimal
    taxable_total: Decimal
    tax: list[TaxLineOut]
    tax_total: Decimal
    total: Decimal
    currency: str
    payment_mode: PaymentMode
    terms_version: str
    buyer: dict[str, str]
    is_test: bool
    created_at: datetime
    dues: list[DueOut]
    attempts: list[AttemptOut]
    invoices: list[InvoiceOut]
    refund_requests: list[RefundRequestOut]
    refundable: Decimal
    can_cancel: bool
    can_request_refund: bool


class CheckoutOut(BaseModel):
    """What the browser needs to open the provider's checkout; the amount is the server's."""

    attempt_id: uuid.UUID
    provider: str
    key_id: str
    provider_order_id: str
    amount_paise: int
    currency: str
    order_code: str
    description: str


class CheckoutReturnIn(Strict):
    """The checkout callback's ids and signature: a hint, verified, never applied."""

    provider_order_id: str = Field(min_length=1, max_length=60)
    provider_payment_id: str = Field(min_length=1, max_length=60)
    signature: str = Field(min_length=1, max_length=200)


class AttemptStateOut(BaseModel):
    attempt_id: uuid.UUID
    state: AttemptState
    verifying: bool = Field(description="A verified fetch from the provider is queued")


class RefundRequestIn(Strict):
    reason: str = Field(min_length=1, max_length=2000)


class CreditEntryOut(BaseModel):
    entry: CreditEntry
    quantity: int
    balance_after: int
    at: datetime


class CreditsOut(BaseModel):
    balance: int
    entries: list[CreditEntryOut]
    offer: OfferOut | None
    unavailable: UnavailableOut | None
    states: dict[str, str]


class BillingOverviewOut(BaseModel):
    orders: list[OrderSummaryOut]
    credit_balance: int


class DownloadOut(BaseModel):
    url: str
    expires_in_seconds: int


class WebhookAck(BaseModel):
    status: Literal["ok"] = "ok"


class FakePayIn(Strict):
    outcome: Literal["capture", "fail"]


class FakePayOut(BaseModel):
    """What the fake checkout widget hands back, like Razorpay's handler (development only)."""

    provider_order_id: str
    provider_payment_id: str
    signature: str | None


# --- operations -----------------------------------------------------------------------------


class PaymentOut(BaseModel):
    payment_id: uuid.UUID
    provider_payment_id: str
    amount: Decimal
    method: str | None
    applied: bool
    source: str
    captured_at: datetime


class RefundOut(BaseModel):
    refund_id: uuid.UUID
    payment_id: uuid.UUID
    amount: Decimal
    state: RefundState
    provider_refund_id: str | None
    failure: str | None
    created_at: datetime


class EntitlementHistoryOut(BaseModel):
    from_state: PackageState | None
    to_state: PackageState
    reason: str | None
    actor_role: str
    at: datetime


class StaffRefundRequestOut(RefundRequestOut):
    order_id: uuid.UUID
    order_code: str
    kind: OfferingKind
    project_id: uuid.UUID | None
    buyer_email: str | None
    refundable: Decimal
    refunds: list[RefundOut]
    package_services_used: list[str]


class OpsOrderOut(OrderOut):
    buyer_email: str | None
    payments: list[PaymentOut]
    refunds: list[RefundOut]
    package_history: list[EntitlementHistoryOut]
    staff_refund_requests: list[StaffRefundRequestOut]


class StaffRefundIn(Strict):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    reason: str = Field(min_length=1, max_length=2000)


class ApproveRefundIn(Strict):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    ends_package: bool = False
    credits_revoked: int = Field(default=0, ge=0, le=1)
    reason: str = Field(min_length=1, max_length=2000)


class ReasonIn(Strict):
    reason: str = Field(min_length=1, max_length=2000)


class ExceptionOut(BaseModel):
    exception_id: uuid.UUID
    kind: BillingExceptionKind
    state: BillingExceptionState
    provider_ref: str
    order_id: uuid.UUID | None
    order_code: str | None
    payment_id: uuid.UUID | None
    expected: dict[str, Any]
    observed: dict[str, Any]
    created_at: datetime
    resolution: str | None
    resolved_at: datetime | None


class ResolveIn(Strict):
    resolution: str = Field(min_length=1, max_length=2000)


class ReconcileOut(BaseModel):
    counts: dict[str, int]


# --- admin configuration --------------------------------------------------------------------


class ConfigVersionOut(BaseModel):
    version_id: uuid.UUID
    kind: str
    version: int
    status: ConfigStatus
    is_test: bool
    note: str
    created_at: datetime
    published_at: datetime | None
    content: dict[str, Any]


class PricingRuleIn(Strict):
    offering_code: str = Field(min_length=1, max_length=30)
    rule: dict[str, Any]
    is_test: bool
    note: str = Field(default="", max_length=2000)


class InstalmentPlanIn(Strict):
    instalments: list[dict[str, Any]]
    is_test: bool
    note: str = Field(default="", max_length=2000)


class TaxConfigurationIn(Strict):
    legal_name: str = Field(default="", max_length=200)
    address: str = Field(default="", max_length=1000)
    gstin: str = Field(default="", max_length=20)
    state_code: str = Field(default="", max_length=2)
    invoice_series: str = Field(default="", max_length=20)
    prices_include_tax: bool
    lines: dict[str, Any]
    is_test: bool
    note: str = Field(default="", max_length=2000)


class OfferingVersionIn(Strict):
    offering_code: str = Field(min_length=1, max_length=30)
    pricing_rule_version_id: uuid.UUID
    payment_modes: list[PaymentMode] = Field(min_length=1)
    instalment_plan_version_id: uuid.UUID | None = None
    terms_version: str = Field(min_length=1, max_length=40)
    is_test: bool
    note: str = Field(default="", max_length=2000)


class PreviewIn(Strict):
    characteristics: dict[str, Any]


class PreviewOut(BaseModel):
    price: Decimal
    inputs: dict[str, Any]


class ChecklistItemIn(Strict):
    id: str = Field(min_length=2, max_length=41)
    label: str = Field(min_length=1, max_length=200)
    help: str = Field(default="", max_length=500)


class ChecklistIn(Strict):
    items: list[ChecklistItemIn] = Field(min_length=1, max_length=20)
    note: str = Field(default="", max_length=2000)


class ChecklistItemOut(BaseModel):
    id: str
    label: str
    help: str


class ChecklistOut(BaseModel):
    version_id: uuid.UUID
    version: int
    status: ConfigStatus
    items: list[ChecklistItemOut]
    note: str
