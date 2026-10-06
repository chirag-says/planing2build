"""Billing tables (Slice 3.3; SLICE3_3_READINESS section H). Money is numeric(14,2) INR with a
currency column; paise only on the wire. Configuration versions are immutable once published;
orders, dues, payments, invoices and the credit ledger keep their amounts for ever. Triggers in
migration 0011 enforce both: append-only tables refuse UPDATE and DELETE, and the others accept
changes to their lifecycle columns only.

Nothing here refers to a professional, a quote, a contract, a lead, a milestone or a stage:
Plan2Build never collects construction money (G.1)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base

Money = Numeric(14, 2)
NOW = text("now()")
STATUS_CHECK = "status IN ('DRAFT', 'ACTIVE', 'RETIRED')"


def _user(nullable: bool = False) -> Any:
    return mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=nullable)


class Offering(Base):
    """What Plan2Build sells: a closed set (L-03, L-04; G.1)."""

    __tablename__ = "offerings"
    __table_args__ = (CheckConstraint("kind IN ('PACKAGE', 'AI_CREDIT')", name="kind"),)

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    kind: Mapped[str] = mapped_column(String(12), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class PricingRuleVersion(Base):
    __tablename__ = "pricing_rule_versions"
    __table_args__ = (
        UniqueConstraint("offering_code", "version"),
        CheckConstraint(STATUS_CHECK, name="status"),
        Index(
            "uq_pricing_rule_versions_one_active",
            "offering_code",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    offering_code: Mapped[str] = mapped_column(ForeignKey("offerings.code", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))
    rule: Mapped[dict[str, Any]] = mapped_column(JSONB)
    currency: Mapped[str] = mapped_column(String(3))
    is_test: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = _user()
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    published_by: Mapped[uuid.UUID | None] = _user(nullable=True)
    published_at: Mapped[datetime | None]


class InstalmentPlanVersion(Base):
    __tablename__ = "instalment_plan_versions"
    __table_args__ = (
        UniqueConstraint("version"),
        CheckConstraint(STATUS_CHECK, name="status"),
        Index(
            "uq_instalment_plan_versions_one_active",
            "status",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))
    instalments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    is_test: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = _user()
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    published_by: Mapped[uuid.UUID | None] = _user(nullable=True)
    published_at: Mapped[datetime | None]


class TaxConfigurationVersion(Base):
    """The accountant's values (O-05). Every field may be empty in a draft; publishing refuses an
    incomplete version, and billing refuses orders while none is ACTIVE."""

    __tablename__ = "tax_configuration_versions"
    __table_args__ = (
        UniqueConstraint("version"),
        CheckConstraint(STATUS_CHECK, name="status"),
        Index(
            "uq_tax_configuration_versions_one_active",
            "status",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))
    legal_name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(Text)
    gstin: Mapped[str] = mapped_column(String(20))
    state_code: Mapped[str] = mapped_column(String(2))
    invoice_series: Mapped[str] = mapped_column(String(20))
    prices_include_tax: Mapped[bool] = mapped_column(Boolean)
    lines: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_test: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = _user()
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    published_by: Mapped[uuid.UUID | None] = _user(nullable=True)
    published_at: Mapped[datetime | None]


class OfferingVersion(Base):
    __tablename__ = "offering_versions"
    __table_args__ = (
        UniqueConstraint("offering_code", "version"),
        CheckConstraint(STATUS_CHECK, name="status"),
        CheckConstraint(
            "cardinality(payment_modes) > 0 AND payment_modes <@ "
            "ARRAY['FULL', 'INSTALMENTS']::varchar[]",
            name="payment_modes",
        ),
        CheckConstraint(
            "('INSTALMENTS' = ANY(payment_modes)) = (instalment_plan_version_id IS NOT NULL)",
            name="instalments_need_plan",
        ),
        Index(
            "uq_offering_versions_one_active",
            "offering_code",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    offering_code: Mapped[str] = mapped_column(ForeignKey("offerings.code", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))
    pricing_rule_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pricing_rule_versions.id", ondelete="RESTRICT")
    )
    payment_modes: Mapped[list[str]] = mapped_column(ARRAY(String(12)))
    instalment_plan_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("instalment_plan_versions.id", ondelete="RESTRICT")
    )
    terms_version: Mapped[str] = mapped_column(String(40))
    is_test: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = _user()
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    published_by: Mapped[uuid.UUID | None] = _user(nullable=True)
    published_at: Mapped[datetime | None]


class Order(Base):
    """The commercial record. Amounts, tax, versions and the buyer snapshot never change after
    creation (trigger); only the state moves."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("kind IN ('PACKAGE', 'AI_CREDIT')", name="kind"),
        CheckConstraint(
            "(kind = 'PACKAGE') = (project_id IS NOT NULL)", name="package_has_project"
        ),
        CheckConstraint("quantity = 1", name="single_quantity"),  # L-04: no bundles
        CheckConstraint("payment_mode IN ('FULL', 'INSTALMENTS')", name="payment_mode"),
        CheckConstraint(
            "state IN ('AWAITING_PAYMENT', 'PART_PAID', 'PAID', 'CANCELLED', "
            "'PARTLY_REFUNDED', 'REFUNDED')",
            name="state",
        ),
        CheckConstraint("total > 0 AND total = taxable_total + tax_total", name="total"),
        Index(
            "uq_orders_one_open_package",
            "project_id",
            unique=True,
            postgresql_where=text("kind = 'PACKAGE' AND state = 'AWAITING_PAYMENT'"),
        ),
        Index("ix_orders_buyer_user_id", "buyer_user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True)
    buyer_user_id: Mapped[uuid.UUID] = _user()
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT")
    )
    kind: Mapped[str] = mapped_column(String(12))
    offering_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offering_versions.id", ondelete="RESTRICT")
    )
    quantity: Mapped[int] = mapped_column(SmallInteger)
    pricing_rule_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pricing_rule_versions.id", ondelete="RESTRICT")
    )
    pricing_inputs: Mapped[dict[str, Any]] = mapped_column(JSONB)
    price: Mapped[Decimal] = mapped_column(Money)
    taxable_total: Mapped[Decimal] = mapped_column(Money)
    tax: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    tax_total: Mapped[Decimal] = mapped_column(Money)
    total: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    payment_mode: Mapped[str] = mapped_column(String(12))
    instalment_plan: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    tax_configuration_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tax_configuration_versions.id", ondelete="RESTRICT")
    )
    terms_version: Mapped[str] = mapped_column(String(40))
    buyer: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_test: Mapped[bool] = mapped_column(Boolean)
    state: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    cancelled_at: Mapped[datetime | None]
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(server_default=text("1"))


class PaymentDue(Base):
    """One instalment (or the whole order for FULL). Never tied to a construction stage."""

    __tablename__ = "payment_dues"
    __table_args__ = (
        UniqueConstraint("order_id", "sequence"),
        CheckConstraint("state IN ('DUE', 'PAID', 'CANCELLED')", name="state"),
        CheckConstraint("due_rule IN ('ON_ORDER', 'DAYS_AFTER_ACTIVATION')", name="due_rule"),
        CheckConstraint(
            "(due_rule = 'DAYS_AFTER_ACTIVATION') = (due_days IS NOT NULL)",
            name="days_for_later_dues",
        ),
        CheckConstraint("amount > 0 AND amount = taxable_amount + tax_amount", name="amount"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    sequence: Mapped[int] = mapped_column(SmallInteger)
    amount: Mapped[Decimal] = mapped_column(Money)
    taxable_amount: Mapped[Decimal] = mapped_column(Money)
    tax: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    tax_amount: Mapped[Decimal] = mapped_column(Money)
    due_rule: Mapped[str] = mapped_column(String(24))
    due_days: Mapped[int | None] = mapped_column(SmallInteger)
    due_at: Mapped[datetime | None]
    state: Mapped[str] = mapped_column(String(10))
    paid_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class PaymentAttempt(Base):
    """One provider order for one due. The browser's callback never changes it."""

    __tablename__ = "payment_attempts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_order_id"),
        CheckConstraint("state IN ('CREATED', 'CAPTURED', 'FAILED', 'EXPIRED')", name="state"),
        Index("ix_payment_attempts_open", "created_at", postgresql_where=text("state = 'CREATED'")),
        Index("ix_payment_attempts_due_id", "due_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    due_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_dues.id", ondelete="RESTRICT"))
    provider: Mapped[str] = mapped_column(String(20))
    provider_order_id: Mapped[str] = mapped_column(String(60))
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    state: Mapped[str] = mapped_column(String(10))
    failure_code: Mapped[str | None] = mapped_column(String(60))
    created_by: Mapped[uuid.UUID] = _user()
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    finished_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class Payment(Base):
    """A captured payment the provider confirmed. `applied` is false when billing refused to
    apply it (a billing exception names it); operations may refund it. Append-only."""

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("provider", "provider_payment_id"),
        CheckConstraint("source IN ('WEBHOOK', 'FETCH')", name="source"),
        Index("ix_payments_attempt_id", "attempt_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_attempts.id", ondelete="RESTRICT")
    )
    provider: Mapped[str] = mapped_column(String(20))
    provider_payment_id: Mapped[str] = mapped_column(String(60))
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    method: Mapped[str | None] = mapped_column(String(30))
    fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    tax_on_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    applied: Mapped[bool] = mapped_column(Boolean)
    source: Mapped[str] = mapped_column(String(10))
    captured_at: Mapped[datetime] = mapped_column(server_default=NOW)


class PaymentEvent(Base):
    """A verified webhook, stored before it is processed. A replay hits the UNIQUE key."""

    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id"),
        Index(
            "ix_payment_events_unprocessed",
            "received_at",
            postgresql_where=text("processed_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    provider_event_id: Mapped[str] = mapped_column(String(80))
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(server_default=NOW)
    processed_at: Mapped[datetime | None]
    result: Mapped[str | None] = mapped_column(String(40))


class InvoiceSequence(Base):
    """Gapless invoice numbers per series and financial year: the row is locked while a number
    is taken, in the transaction that issues the invoice."""

    __tablename__ = "invoice_sequences"

    series: Mapped[str] = mapped_column(String(20), primary_key=True)
    financial_year: Mapped[str] = mapped_column(String(7), primary_key=True)
    next_number: Mapped[int] = mapped_column(Integer)


class RefundRequest(Base):
    __tablename__ = "refund_requests"
    __table_args__ = (
        CheckConstraint(
            "state IN ('REQUESTED', 'APPROVED', 'DECLINED', 'REFUNDED', 'FAILED')", name="state"
        ),
        CheckConstraint("requested_role IN ('BUYER', 'OPS', 'ADMIN')", name="requested_role"),
        Index(
            "uq_refund_requests_one_open",
            "order_id",
            unique=True,
            postgresql_where=text("state IN ('REQUESTED', 'APPROVED')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    amount_requested: Mapped[Decimal | None] = mapped_column(Money)
    reason: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID] = _user()
    requested_role: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    version: Mapped[int] = mapped_column(server_default=text("1"))


class RefundDecision(Base):
    """A staff decision with its reason (L-03). Append-only."""

    __tablename__ = "refund_decisions"
    __table_args__ = (
        UniqueConstraint("request_id"),
        CheckConstraint("decision IN ('APPROVED', 'DECLINED')", name="decision"),
        CheckConstraint(
            "(decision = 'APPROVED') = (approved_amount IS NOT NULL AND approved_amount > 0)",
            name="approved_amount",
        ),
        CheckConstraint("role IN ('OPS', 'ADMIN')", name="role"),
        CheckConstraint("credits_revoked >= 0", name="credits_revoked"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("refund_requests.id", ondelete="RESTRICT")
    )
    decision: Mapped[str] = mapped_column(String(10))
    approved_amount: Mapped[Decimal | None] = mapped_column(Money)
    ends_package: Mapped[bool] = mapped_column(Boolean)
    credits_revoked: Mapped[int] = mapped_column(SmallInteger)
    reason: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID] = _user()
    role: Mapped[str] = mapped_column(String(10))
    decided_at: Mapped[datetime] = mapped_column(server_default=NOW)


class Refund(Base):
    """One provider refund against one payment."""

    __tablename__ = "refunds"
    __table_args__ = (
        UniqueConstraint("provider", "provider_refund_id"),
        CheckConstraint("state IN ('PROCESSING', 'REFUNDED', 'FAILED')", name="state"),
        CheckConstraint("amount > 0", name="amount"),
        Index("ix_refunds_open", "created_at", postgresql_where=text("state = 'PROCESSING'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("refund_decisions.id", ondelete="RESTRICT")
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id", ondelete="RESTRICT"))
    amount: Mapped[Decimal] = mapped_column(Money)
    provider: Mapped[str] = mapped_column(String(20))
    provider_refund_id: Mapped[str | None] = mapped_column(String(60))
    state: Mapped[str] = mapped_column(String(12))
    failure: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    completed_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class Invoice(Base):
    """A tax invoice for a captured due, or a credit note for a completed refund. Issued only
    after a verified capture; immutable except for the rendered document."""

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("series", "financial_year", "number"),
        CheckConstraint("kind IN ('TAX_INVOICE', 'CREDIT_NOTE')", name="kind"),
        CheckConstraint(
            "(kind = 'TAX_INVOICE') = (payment_id IS NOT NULL AND refund_id IS NULL "
            "AND original_invoice_id IS NULL)",
            name="kind_refs",
        ),
        CheckConstraint("total = taxable_total + tax_total", name="total"),
        Index("ix_invoices_order_id", "order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(12))
    series: Mapped[str] = mapped_column(String(20))
    financial_year: Mapped[str] = mapped_column(String(7))
    number: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    due_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_dues.id", ondelete="RESTRICT")
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT")
    )
    refund_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("refunds.id", ondelete="RESTRICT")
    )
    original_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT")
    )
    seller: Mapped[dict[str, Any]] = mapped_column(JSONB)
    buyer: Mapped[dict[str, Any]] = mapped_column(JSONB)
    taxable_total: Mapped[Decimal] = mapped_column(Money)
    tax_total: Mapped[Decimal] = mapped_column(Money)
    total: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    is_test: Mapped[bool] = mapped_column(Boolean)
    issued_at: Mapped[datetime] = mapped_column(server_default=NOW)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("file_objects.id", ondelete="RESTRICT")
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (UniqueConstraint("invoice_id", "sequence"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="RESTRICT"))
    sequence: Mapped[int] = mapped_column(SmallInteger)
    description: Mapped[str] = mapped_column(String(200))
    sac: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[int] = mapped_column(SmallInteger)
    taxable_value: Mapped[Decimal] = mapped_column(Money)


class InvoiceTaxLine(Base):
    __tablename__ = "invoice_tax_lines"
    __table_args__ = (UniqueConstraint("invoice_id", "component"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="RESTRICT"))
    component: Mapped[str] = mapped_column(String(20))
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    amount: Mapped[Decimal] = mapped_column(Money)


class PackageEntitlement(Base):
    """The package on a project (L-05): ACTIVE, then CANCELLED or REFUNDED. No row means
    NOT_ACTIVE. A new purchase after a refund is a new row; one ACTIVE per project. Activation
    never changes the project's status (L-06)."""

    __tablename__ = "package_entitlements"
    __table_args__ = (
        CheckConstraint("state IN ('ACTIVE', 'CANCELLED', 'REFUNDED')", name="state"),
        CheckConstraint("(state = 'ACTIVE') = (ended_at IS NULL)", name="ended"),
        Index(
            "uq_package_entitlements_one_active",
            "project_id",
            unique=True,
            postgresql_where=text("state = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), unique=True
    )
    state: Mapped[str] = mapped_column(String(10))
    activated_at: Mapped[datetime] = mapped_column(server_default=NOW)
    ended_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class PackageEntitlementHistory(Base):
    __tablename__ = "package_entitlement_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    entitlement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("package_entitlements.id", ondelete="RESTRICT"), index=True
    )
    from_state: Mapped[str | None] = mapped_column(String(10))
    to_state: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID | None] = _user(nullable=True)
    actor_role: Mapped[str] = mapped_column(String(10))
    at: Mapped[datetime] = mapped_column(server_default=NOW)


class PackageServiceUsage(Base):
    """When each substantial-work event first happened on an entitlement: the record behind the
    "substantial work" refund question (O-04). Kinds: CONNECTION_ACCEPTED (N-12) and RFQ_SELECTION
    (QD-02, a new product decision)."""

    __tablename__ = "package_service_usage"
    __table_args__ = (
        UniqueConstraint("entitlement_id", "service"),
        CheckConstraint("service IN ('CONNECTION_ACCEPTED', 'RFQ_SELECTION')", name="service"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    entitlement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("package_entitlements.id", ondelete="RESTRICT")
    )
    service: Mapped[str] = mapped_column(String(30))
    ref_id: Mapped[uuid.UUID | None]
    first_used_at: Mapped[datetime] = mapped_column(server_default=NOW)


class AiCreditEntry(Base):
    """The AI credit ledger (L-04): one row per change, append-only, with the running balance;
    the balance can never go below zero and each generation is consumed and returned at most
    once."""

    __tablename__ = "ai_credit_ledger"
    __table_args__ = (
        UniqueConstraint("account_user_id", "sequence"),
        CheckConstraint("entry IN ('GRANT', 'CONSUME', 'RETURN', 'REVOKE')", name="entry"),
        CheckConstraint(
            "(entry IN ('GRANT', 'RETURN')) = (quantity > 0) AND quantity <> 0",
            name="quantity_sign",
        ),
        CheckConstraint("balance_after >= 0", name="balance"),
        CheckConstraint(
            "(entry = 'GRANT' AND order_id IS NOT NULL AND generation_id IS NULL "
            "AND refund_request_id IS NULL) OR "
            "(entry IN ('CONSUME', 'RETURN') AND generation_id IS NOT NULL AND order_id IS NULL "
            "AND refund_request_id IS NULL) OR "
            "(entry = 'REVOKE' AND refund_request_id IS NOT NULL AND order_id IS NOT NULL "
            "AND generation_id IS NULL)",
            name="references",
        ),
        Index(
            "uq_ai_credit_ledger_generation_entry",
            "generation_id",
            "entry",
            unique=True,
            postgresql_where=text("generation_id IS NOT NULL"),
        ),
        Index(
            "uq_ai_credit_ledger_order_grant",
            "order_id",
            unique=True,
            postgresql_where=text("entry = 'GRANT'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    account_user_id: Mapped[uuid.UUID] = _user()
    sequence: Mapped[int] = mapped_column(Integer)
    entry: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[int] = mapped_column(SmallInteger)
    balance_after: Mapped[int] = mapped_column(Integer)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    generation_id: Mapped[uuid.UUID | None]
    refund_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("refund_requests.id", ondelete="RESTRICT")
    )
    at: Mapped[datetime] = mapped_column(server_default=NOW)


class BillingException(Base):
    """A payment or refund billing would not apply automatically. Operations resolve it with a
    reason; the event itself is never edited."""

    __tablename__ = "billing_exceptions"
    __table_args__ = (
        UniqueConstraint("kind", "provider", "provider_ref"),
        CheckConstraint(
            "kind IN ('AMOUNT_MISMATCH', 'UNKNOWN_ORDER', 'DUPLICATE_CAPTURE', "
            "'CAPTURE_AFTER_CANCEL', 'AUTHORISED_NOT_CAPTURED', 'REFUND_MISMATCH')",
            name="kind",
        ),
        CheckConstraint("state IN ('OPEN', 'RESOLVED')", name="state"),
        CheckConstraint(
            "(state = 'RESOLVED') = (resolved_at IS NOT NULL AND resolution IS NOT NULL)",
            name="resolution",
        ),
        Index("ix_billing_exceptions_open", "created_at", postgresql_where=text("state = 'OPEN'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    provider: Mapped[str] = mapped_column(String(20))
    provider_ref: Mapped[str] = mapped_column(String(80))
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_attempts.id", ondelete="RESTRICT")
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT")
    )
    expected: Mapped[dict[str, Any]] = mapped_column(JSONB)
    observed: Mapped[dict[str, Any]] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    resolved_by: Mapped[uuid.UUID | None] = _user(nullable=True)
    resolved_at: Mapped[datetime | None]
    resolution: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(server_default=text("1"))


# Tables whose rows never change, and the lifecycle columns the others may change. Migration
# 0011 installs the matching triggers; tests read these too.
APPEND_ONLY = (
    "payments",
    "invoice_lines",
    "invoice_tax_lines",
    "refund_decisions",
    "package_entitlement_history",
    "ai_credit_ledger",
)
MUTABLE_COLUMNS = {
    "pricing_rule_versions": ("status", "published_by", "published_at"),
    "instalment_plan_versions": ("status", "published_by", "published_at"),
    "tax_configuration_versions": ("status", "published_by", "published_at"),
    "offering_versions": ("status", "published_by", "published_at"),
    "orders": ("state", "cancelled_at", "cancel_reason", "version"),
    "payment_dues": ("state", "due_at", "paid_at", "version"),
    "payment_attempts": ("state", "failure_code", "finished_at", "version"),
    "payment_events": ("processed_at", "result"),
    "invoices": ("document_id",),
}
