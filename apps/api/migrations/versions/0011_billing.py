"""Slice 3.3: package eligibility checklist, the billing core and AI credits.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-05

Seeds (SLICE3_3_READINESS section 0, locked by Chirag on 2026-10-05):
- `offerings`: the closed set of what Plan2Build sells, the package and the single AI credit.
- `eligibility_checklist_versions` v1: the five initial POC checks of L-02 (F-05).
No price, instalment share, tax rate, GSTIN, SAC or legal entity: those are published
configuration versions (O-01 to O-07), never migration data.

Guards: append-only tables refuse UPDATE and DELETE (`p2b_forbid_mutation`); orders, dues,
attempts, payment events, invoices and published configuration accept changes to their lifecycle
columns only (`p2b_allow_only_columns`), so an order's amounts can never change.
"""

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

ELIGIBILITY_V1 = [
    {
        "id": "new_individual_house",
        "label": "New individual house",
        "help": "The project is a new individual house.",
    },
    {
        "id": "service_geography",
        "label": "Within Plan2Build's current service geography and capability",
        "help": "Plan2Build can serve this location and this kind of project now.",
    },
    {
        "id": "requirement_complete",
        "label": "Requirement sufficiently complete",
        "help": "The answers are complete enough for Plan2Build to proceed.",
    },
    {
        "id": "review_flags_resolved",
        "label": "Material review flags resolved",
        "help": "Every review flag that matters has been looked into and resolved.",
    },
    {
        "id": "information_plausible",
        "label": "Project information plausible enough to proceed",
        "help": "The plot, size, budget and timing are plausible together.",
    },
]
APPEND_ONLY = (
    "payments",
    "invoice_lines",
    "invoice_tax_lines",
    "refund_decisions",
    "package_entitlement_history",
    "ai_credit_ledger",
    "eligibility_assessments",
)
MUTABLE_COLUMNS = {
    "eligibility_checklist_versions": ("status", "published_by", "published_at"),
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
revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eligibility_checklist_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')",
            name=op.f("ck_eligibility_checklist_versions_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eligibility_checklist_versions")),
        sa.UniqueConstraint("version", name=op.f("uq_eligibility_checklist_versions_version")),
    )
    op.create_index(
        "uq_eligibility_checklist_versions_one_active",
        "eligibility_checklist_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "fake_gateway_records",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("parent_id", sa.String(length=40), nullable=True),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fake_gateway_records")),
    )
    op.create_index(
        op.f("ix_fake_gateway_records_parent_id"),
        "fake_gateway_records",
        ["parent_id"],
        unique=False,
    )
    op.create_table(
        "invoice_sequences",
        sa.Column("series", sa.String(length=20), nullable=False),
        sa.Column("financial_year", sa.String(length=7), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("series", "financial_year", name=op.f("pk_invoice_sequences")),
    )
    op.create_table(
        "offerings",
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.CheckConstraint("kind IN ('PACKAGE', 'AI_CREDIT')", name=op.f("ck_offerings_kind")),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_offerings")),
        sa.UniqueConstraint("kind", name=op.f("uq_offerings_kind")),
    )
    op.create_table(
        "payment_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_event_id", sa.String(length=80), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_events")),
        sa.UniqueConstraint(
            "provider",
            "provider_event_id",
            name=op.f("uq_payment_events_provider_provider_event_id"),
        ),
    )
    op.create_index(
        "ix_payment_events_unprocessed",
        "payment_events",
        ["received_at"],
        unique=False,
        postgresql_where=sa.text("processed_at IS NULL"),
    )
    op.create_table(
        "instalment_plan_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("instalments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')",
            name=op.f("ck_instalment_plan_versions_status"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_instalment_plan_versions_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["published_by"],
            ["users.id"],
            name=op.f("fk_instalment_plan_versions_published_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_instalment_plan_versions")),
        sa.UniqueConstraint("version", name=op.f("uq_instalment_plan_versions_version")),
    )
    op.create_index(
        "uq_instalment_plan_versions_one_active",
        "instalment_plan_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "pricing_rule_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("offering_code", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("rule", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name=op.f("ck_pricing_rule_versions_status")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_pricing_rule_versions_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["offering_code"],
            ["offerings.code"],
            name=op.f("fk_pricing_rule_versions_offering_code_offerings"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["published_by"],
            ["users.id"],
            name=op.f("fk_pricing_rule_versions_published_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pricing_rule_versions")),
        sa.UniqueConstraint(
            "offering_code", "version", name=op.f("uq_pricing_rule_versions_offering_code_version")
        ),
    )
    op.create_index(
        "uq_pricing_rule_versions_one_active",
        "pricing_rule_versions",
        ["offering_code"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "tax_configuration_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("gstin", sa.String(length=20), nullable=False),
        sa.Column("state_code", sa.String(length=2), nullable=False),
        sa.Column("invoice_series", sa.String(length=20), nullable=False),
        sa.Column("prices_include_tax", sa.Boolean(), nullable=False),
        sa.Column("lines", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')",
            name=op.f("ck_tax_configuration_versions_status"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_tax_configuration_versions_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["published_by"],
            ["users.id"],
            name=op.f("fk_tax_configuration_versions_published_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tax_configuration_versions")),
        sa.UniqueConstraint("version", name=op.f("uq_tax_configuration_versions_version")),
    )
    op.create_index(
        "uq_tax_configuration_versions_one_active",
        "tax_configuration_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "eligibility_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("checklist_version_id", sa.Uuid(), nullable=False),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("assessed_by", sa.Uuid(), nullable=False),
        sa.Column(
            "assessed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assessed_by"],
            ["users.id"],
            name=op.f("fk_eligibility_assessments_assessed_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["checklist_version_id"],
            ["eligibility_checklist_versions.id"],
            name=op.f(
                "fk_eligibility_assessments_checklist_version_id_eligibility_checklist_versions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_eligibility_assessments_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eligibility_assessments")),
        sa.UniqueConstraint("project_id", name=op.f("uq_eligibility_assessments_project_id")),
    )
    op.create_table(
        "offering_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("offering_code", sa.String(length=30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("pricing_rule_version_id", sa.Uuid(), nullable=False),
        sa.Column("payment_modes", postgresql.ARRAY(sa.String(length=12)), nullable=False),
        sa.Column("instalment_plan_version_id", sa.Uuid(), nullable=True),
        sa.Column("terms_version", sa.String(length=40), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "('INSTALMENTS' = ANY(payment_modes)) = (instalment_plan_version_id IS NOT NULL)",
            name=op.f("ck_offering_versions_instalments_need_plan"),
        ),
        sa.CheckConstraint(
            "cardinality(payment_modes) > 0 AND payment_modes <@ ARRAY['FULL', 'INSTALMENTS']::varchar[]",
            name=op.f("ck_offering_versions_payment_modes"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name=op.f("ck_offering_versions_status")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_offering_versions_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["instalment_plan_version_id"],
            ["instalment_plan_versions.id"],
            name=op.f("fk_offering_versions_instalment_plan_version_id_instalment_plan_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["offering_code"],
            ["offerings.code"],
            name=op.f("fk_offering_versions_offering_code_offerings"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pricing_rule_version_id"],
            ["pricing_rule_versions.id"],
            name=op.f("fk_offering_versions_pricing_rule_version_id_pricing_rule_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["published_by"],
            ["users.id"],
            name=op.f("fk_offering_versions_published_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_offering_versions")),
        sa.UniqueConstraint(
            "offering_code", "version", name=op.f("uq_offering_versions_offering_code_version")
        ),
    )
    op.create_index(
        "uq_offering_versions_one_active",
        "offering_versions",
        ["offering_code"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column("buyer_user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("offering_version_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.SmallInteger(), nullable=False),
        sa.Column("pricing_rule_version_id", sa.Uuid(), nullable=False),
        sa.Column("pricing_inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("taxable_total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("tax", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tax_total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("payment_mode", sa.String(length=12), nullable=False),
        sa.Column("instalment_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tax_configuration_version_id", sa.Uuid(), nullable=False),
        sa.Column("terms_version", sa.String(length=40), nullable=False),
        sa.Column("buyer", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "(kind = 'PACKAGE') = (project_id IS NOT NULL)",
            name=op.f("ck_orders_package_has_project"),
        ),
        sa.CheckConstraint("kind IN ('PACKAGE', 'AI_CREDIT')", name=op.f("ck_orders_kind")),
        sa.CheckConstraint(
            "payment_mode IN ('FULL', 'INSTALMENTS')", name=op.f("ck_orders_payment_mode")
        ),
        sa.CheckConstraint(
            "state IN ('AWAITING_PAYMENT', 'PART_PAID', 'PAID', 'CANCELLED', 'PARTLY_REFUNDED', 'REFUNDED')",
            name=op.f("ck_orders_state"),
        ),
        sa.CheckConstraint("quantity = 1", name=op.f("ck_orders_single_quantity")),
        sa.CheckConstraint(
            "total > 0 AND total = taxable_total + tax_total", name=op.f("ck_orders_total")
        ),
        sa.ForeignKeyConstraint(
            ["buyer_user_id"],
            ["users.id"],
            name=op.f("fk_orders_buyer_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["offering_version_id"],
            ["offering_versions.id"],
            name=op.f("fk_orders_offering_version_id_offering_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pricing_rule_version_id"],
            ["pricing_rule_versions.id"],
            name=op.f("fk_orders_pricing_rule_version_id_pricing_rule_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_orders_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tax_configuration_version_id"],
            ["tax_configuration_versions.id"],
            name=op.f("fk_orders_tax_configuration_version_id_tax_configuration_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("code", name=op.f("uq_orders_code")),
    )
    op.create_index(
        "ix_orders_buyer_user_id", "orders", ["buyer_user_id", "created_at"], unique=False
    )
    op.create_index(
        "uq_orders_one_open_package",
        "orders",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'PACKAGE' AND state = 'AWAITING_PAYMENT'"),
    )
    op.create_table(
        "package_entitlements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "(state = 'ACTIVE') = (ended_at IS NULL)", name=op.f("ck_package_entitlements_ended")
        ),
        sa.CheckConstraint(
            "state IN ('ACTIVE', 'CANCELLED', 'REFUNDED')",
            name=op.f("ck_package_entitlements_state"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_package_entitlements_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_package_entitlements_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_package_entitlements")),
        sa.UniqueConstraint("order_id", name=op.f("uq_package_entitlements_order_id")),
    )
    op.create_index(
        "uq_package_entitlements_one_active",
        "package_entitlements",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("state = 'ACTIVE'"),
    )
    op.create_table(
        "payment_dues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.SmallInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("taxable_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("tax", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("due_rule", sa.String(length=24), nullable=False),
        sa.Column("due_days", sa.SmallInteger(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "(due_rule = 'DAYS_AFTER_ACTIVATION') = (due_days IS NOT NULL)",
            name=op.f("ck_payment_dues_days_for_later_dues"),
        ),
        sa.CheckConstraint(
            "due_rule IN ('ON_ORDER', 'DAYS_AFTER_ACTIVATION')",
            name=op.f("ck_payment_dues_due_rule"),
        ),
        sa.CheckConstraint(
            "state IN ('DUE', 'PAID', 'CANCELLED')", name=op.f("ck_payment_dues_state")
        ),
        sa.CheckConstraint(
            "amount > 0 AND amount = taxable_amount + tax_amount",
            name=op.f("ck_payment_dues_amount"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_payment_dues_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_dues")),
        sa.UniqueConstraint("order_id", "sequence", name=op.f("uq_payment_dues_order_id_sequence")),
    )
    op.create_table(
        "refund_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("amount_requested", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("requested_role", sa.String(length=10), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "requested_role IN ('BUYER', 'OPS', 'ADMIN')",
            name=op.f("ck_refund_requests_requested_role"),
        ),
        sa.CheckConstraint(
            "state IN ('REQUESTED', 'APPROVED', 'DECLINED', 'REFUNDED', 'FAILED')",
            name=op.f("ck_refund_requests_state"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_refund_requests_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name=op.f("fk_refund_requests_requested_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refund_requests")),
    )
    op.create_index(
        "uq_refund_requests_one_open",
        "refund_requests",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('REQUESTED', 'APPROVED')"),
    )
    op.create_table(
        "ai_credit_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_user_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("entry", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.SmallInteger(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("generation_id", sa.Uuid(), nullable=True),
        sa.Column("refund_request_id", sa.Uuid(), nullable=True),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "(entry = 'GRANT' AND order_id IS NOT NULL AND generation_id IS NULL AND refund_request_id IS NULL) OR (entry IN ('CONSUME', 'RETURN') AND generation_id IS NOT NULL AND order_id IS NULL AND refund_request_id IS NULL) OR (entry = 'REVOKE' AND refund_request_id IS NOT NULL AND order_id IS NOT NULL AND generation_id IS NULL)",
            name=op.f("ck_ai_credit_ledger_references"),
        ),
        sa.CheckConstraint(
            "(entry IN ('GRANT', 'RETURN')) = (quantity > 0) AND quantity <> 0",
            name=op.f("ck_ai_credit_ledger_quantity_sign"),
        ),
        sa.CheckConstraint(
            "entry IN ('GRANT', 'CONSUME', 'RETURN', 'REVOKE')",
            name=op.f("ck_ai_credit_ledger_entry"),
        ),
        sa.CheckConstraint("balance_after >= 0", name=op.f("ck_ai_credit_ledger_balance")),
        sa.ForeignKeyConstraint(
            ["account_user_id"],
            ["users.id"],
            name=op.f("fk_ai_credit_ledger_account_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_ai_credit_ledger_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["refund_request_id"],
            ["refund_requests.id"],
            name=op.f("fk_ai_credit_ledger_refund_request_id_refund_requests"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_credit_ledger")),
        sa.UniqueConstraint(
            "account_user_id", "sequence", name=op.f("uq_ai_credit_ledger_account_user_id_sequence")
        ),
    )
    op.create_index(
        "uq_ai_credit_ledger_generation_entry",
        "ai_credit_ledger",
        ["generation_id", "entry"],
        unique=True,
        postgresql_where=sa.text("generation_id IS NOT NULL"),
    )
    op.create_index(
        "uq_ai_credit_ledger_order_grant",
        "ai_credit_ledger",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("entry = 'GRANT'"),
    )
    op.create_table(
        "package_entitlement_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=False),
        sa.Column("from_state", sa.String(length=10), nullable=True),
        sa.Column("to_state", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_role", sa.String(length=10), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_package_entitlement_history_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["entitlement_id"],
            ["package_entitlements.id"],
            name=op.f("fk_package_entitlement_history_entitlement_id_package_entitlements"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_package_entitlement_history")),
    )
    op.create_index(
        op.f("ix_package_entitlement_history_entitlement_id"),
        "package_entitlement_history",
        ["entitlement_id"],
        unique=False,
    )
    op.create_table(
        "package_service_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=False),
        sa.Column("service", sa.String(length=30), nullable=False),
        sa.Column("ref_id", sa.Uuid(), nullable=True),
        sa.Column(
            "first_used_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["entitlement_id"],
            ["package_entitlements.id"],
            name=op.f("fk_package_service_usage_entitlement_id_package_entitlements"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_package_service_usage")),
        sa.UniqueConstraint(
            "entitlement_id",
            "service",
            name=op.f("uq_package_service_usage_entitlement_id_service"),
        ),
    )
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("due_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_order_id", sa.String(length=60), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("failure_code", sa.String(length=60), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "state IN ('CREATED', 'CAPTURED', 'FAILED', 'EXPIRED')",
            name=op.f("ck_payment_attempts_state"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_payment_attempts_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["due_id"],
            ["payment_dues.id"],
            name=op.f("fk_payment_attempts_due_id_payment_dues"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_attempts")),
        sa.UniqueConstraint(
            "provider",
            "provider_order_id",
            name=op.f("uq_payment_attempts_provider_provider_order_id"),
        ),
    )
    op.create_index("ix_payment_attempts_due_id", "payment_attempts", ["due_id"], unique=False)
    op.create_index(
        "ix_payment_attempts_open",
        "payment_attempts",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("state = 'CREATED'"),
    )
    op.create_table(
        "refund_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=10), nullable=False),
        sa.Column("approved_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("ends_package", sa.Boolean(), nullable=False),
        sa.Column("credits_revoked", sa.SmallInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(decision = 'APPROVED') = (approved_amount IS NOT NULL AND approved_amount > 0)",
            name=op.f("ck_refund_decisions_approved_amount"),
        ),
        sa.CheckConstraint(
            "decision IN ('APPROVED', 'DECLINED')", name=op.f("ck_refund_decisions_decision")
        ),
        sa.CheckConstraint("role IN ('OPS', 'ADMIN')", name=op.f("ck_refund_decisions_role")),
        sa.CheckConstraint(
            "credits_revoked >= 0", name=op.f("ck_refund_decisions_credits_revoked")
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.id"],
            name=op.f("fk_refund_decisions_decided_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["refund_requests.id"],
            name=op.f("fk_refund_decisions_request_id_refund_requests"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refund_decisions")),
        sa.UniqueConstraint("request_id", name=op.f("uq_refund_decisions_request_id")),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=60), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("method", sa.String(length=30), nullable=True),
        sa.Column("fee", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("tax_on_fee", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("applied", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("source IN ('WEBHOOK', 'FETCH')", name=op.f("ck_payments_source")),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["payment_attempts.id"],
            name=op.f("fk_payments_attempt_id_payment_attempts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint(
            "provider", "provider_payment_id", name=op.f("uq_payments_provider_provider_payment_id")
        ),
    )
    op.create_index("ix_payments_attempt_id", "payments", ["attempt_id"], unique=False)
    op.create_table(
        "billing_exceptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_ref", sa.String(length=80), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("expected", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("observed", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "(state = 'RESOLVED') = (resolved_at IS NOT NULL AND resolution IS NOT NULL)",
            name=op.f("ck_billing_exceptions_resolution"),
        ),
        sa.CheckConstraint(
            "kind IN ('AMOUNT_MISMATCH', 'UNKNOWN_ORDER', 'DUPLICATE_CAPTURE', 'CAPTURE_AFTER_CANCEL', 'AUTHORISED_NOT_CAPTURED', 'REFUND_MISMATCH')",
            name=op.f("ck_billing_exceptions_kind"),
        ),
        sa.CheckConstraint(
            "state IN ('OPEN', 'RESOLVED')", name=op.f("ck_billing_exceptions_state")
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["payment_attempts.id"],
            name=op.f("fk_billing_exceptions_attempt_id_payment_attempts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_billing_exceptions_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_billing_exceptions_payment_id_payments"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"],
            ["users.id"],
            name=op.f("fk_billing_exceptions_resolved_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_exceptions")),
        sa.UniqueConstraint(
            "kind",
            "provider",
            "provider_ref",
            name=op.f("uq_billing_exceptions_kind_provider_provider_ref"),
        ),
    )
    op.create_index(
        "ix_billing_exceptions_open",
        "billing_exceptions",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("state = 'OPEN'"),
    )
    op.create_table(
        "refunds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_refund_id", sa.String(length=60), nullable=True),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column("failure", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "state IN ('PROCESSING', 'REFUNDED', 'FAILED')", name=op.f("ck_refunds_state")
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_refunds_amount")),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["refund_decisions.id"],
            name=op.f("fk_refunds_decision_id_refund_decisions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_refunds_payment_id_payments"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refunds")),
        sa.UniqueConstraint(
            "provider", "provider_refund_id", name=op.f("uq_refunds_provider_provider_refund_id")
        ),
    )
    op.create_index(
        "ix_refunds_open",
        "refunds",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("state = 'PROCESSING'"),
    )
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("series", sa.String(length=20), nullable=False),
        sa.Column("financial_year", sa.String(length=7), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("due_id", sa.Uuid(), nullable=True),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("refund_id", sa.Uuid(), nullable=True),
        sa.Column("original_invoice_id", sa.Uuid(), nullable=True),
        sa.Column("seller", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("buyer", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("taxable_total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("tax_total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "(kind = 'TAX_INVOICE') = (payment_id IS NOT NULL AND refund_id IS NULL AND original_invoice_id IS NULL)",
            name=op.f("ck_invoices_kind_refs"),
        ),
        sa.CheckConstraint("kind IN ('TAX_INVOICE', 'CREDIT_NOTE')", name=op.f("ck_invoices_kind")),
        sa.CheckConstraint("total = taxable_total + tax_total", name=op.f("ck_invoices_total")),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["file_objects.id"],
            name=op.f("fk_invoices_document_id_file_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["due_id"],
            ["payment_dues.id"],
            name=op.f("fk_invoices_due_id_payment_dues"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_invoices_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["original_invoice_id"],
            ["invoices.id"],
            name=op.f("fk_invoices_original_invoice_id_invoices"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_invoices_payment_id_payments"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["refund_id"],
            ["refunds.id"],
            name=op.f("fk_invoices_refund_id_refunds"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoices")),
        sa.UniqueConstraint("code", name=op.f("uq_invoices_code")),
        sa.UniqueConstraint(
            "series",
            "financial_year",
            "number",
            name=op.f("uq_invoices_series_financial_year_number"),
        ),
    )
    op.create_index("ix_invoices_order_id", "invoices", ["order_id"], unique=False)
    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.SmallInteger(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("sac", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.SmallInteger(), nullable=False),
        sa.Column("taxable_value", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name=op.f("fk_invoice_lines_invoice_id_invoices"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice_lines")),
        sa.UniqueConstraint(
            "invoice_id", "sequence", name=op.f("uq_invoice_lines_invoice_id_sequence")
        ),
    )
    op.create_table(
        "invoice_tax_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("component", sa.String(length=20), nullable=False),
        sa.Column("rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name=op.f("fk_invoice_tax_lines_invoice_id_invoices"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice_tax_lines")),
        sa.UniqueConstraint(
            "invoice_id", "component", name=op.f("uq_invoice_tax_lines_invoice_id_component")
        ),
    )
    op.execute("ALTER TABLE file_objects DROP CONSTRAINT ck_file_objects_purpose")
    op.execute(
        "ALTER TABLE file_objects ADD CONSTRAINT ck_file_objects_purpose CHECK (purpose IN "
        "('REQUIREMENT_UPLOAD', 'AI_CONCEPT', 'VERIFICATION_EVIDENCE', 'PORTFOLIO', 'INVOICE'))"
    )

    offerings = sa.table("offerings", sa.column("code"), sa.column("kind"), sa.column("name"))
    op.bulk_insert(
        offerings,
        [
            {"code": "P2B_PACKAGE", "kind": "PACKAGE", "name": "Plan2Build package"},
            {"code": "AI_CREDIT_SINGLE", "kind": "AI_CREDIT", "name": "AI design credit"},
        ],
    )
    op.execute(
        sa.text(
            "INSERT INTO eligibility_checklist_versions (id, version, status, items, note, "
            "published_at) VALUES (:id, 1, 'ACTIVE', CAST(:items AS jsonb), :note, now())"
        ).bindparams(
            id=uuid.UUID("01a10c00-0000-7000-8000-000000000001"),
            items=json.dumps(ELIGIBILITY_V1),
            note="Initial POC eligibility checks (F-05; SLICE3_3_READINESS L-02), locked by Chirag "
            "on 2026-10-05. Configurable and versioned.",
        )
    )

    op.execute(
        """
        CREATE FUNCTION p2b_allow_only_columns() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            old_row jsonb := to_jsonb(OLD);
            new_row jsonb := to_jsonb(NEW);
            allowed text;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION '% rows are never deleted', TG_TABLE_NAME;
            END IF;
            FOREACH allowed IN ARRAY TG_ARGV LOOP
                old_row := old_row - allowed;
                new_row := new_row - allowed;
            END LOOP;
            IF old_row IS DISTINCT FROM new_row THEN
                RAISE EXCEPTION 'only % may change on %', array_to_string(TG_ARGV, ', '),
                    TG_TABLE_NAME;
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    for table, columns in MUTABLE_COLUMNS.items():
        arguments = ", ".join(f"'{c}'" for c in columns)
        op.execute(
            f"CREATE TRIGGER {table}_lifecycle_only BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION p2b_allow_only_columns({arguments})"
        )
    for table in APPEND_ONLY:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION p2b_forbid_mutation()"
        )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT SELECT ON offerings TO app_rw;
                GRANT SELECT, INSERT, UPDATE ON eligibility_checklist_versions,
                    pricing_rule_versions, instalment_plan_versions, tax_configuration_versions,
                    offering_versions, orders, payment_dues, payment_attempts, payment_events,
                    invoice_sequences, invoices, refund_requests, refunds, package_entitlements,
                    billing_exceptions, fake_gateway_records TO app_rw;
                GRANT SELECT, INSERT ON payments, invoice_lines, invoice_tax_lines,
                    refund_decisions, package_entitlement_history, package_service_usage,
                    ai_credit_ledger, eligibility_assessments TO app_rw;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Invoice files go with the feature; the access log is append-only, so its guard is
    # lifted for exactly this delete.
    op.execute("ALTER TABLE document_access_log DISABLE TRIGGER document_access_log_append_only")
    op.execute(
        "DELETE FROM document_access_log WHERE file_id IN (SELECT id FROM file_objects "
        "WHERE purpose = 'INVOICE')"
    )
    op.execute("ALTER TABLE document_access_log ENABLE TRIGGER document_access_log_append_only")
    op.drop_table("invoice_tax_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_invoices_order_id", table_name="invoices")
    op.drop_table("invoices")
    op.drop_index(
        "ix_refunds_open", table_name="refunds", postgresql_where=sa.text("state = 'PROCESSING'")
    )
    op.drop_table("refunds")
    op.drop_index(
        "ix_billing_exceptions_open",
        table_name="billing_exceptions",
        postgresql_where=sa.text("state = 'OPEN'"),
    )
    op.drop_table("billing_exceptions")
    op.drop_index("ix_payments_attempt_id", table_name="payments")
    op.drop_table("payments")
    op.drop_table("refund_decisions")
    op.drop_index(
        "ix_payment_attempts_open",
        table_name="payment_attempts",
        postgresql_where=sa.text("state = 'CREATED'"),
    )
    op.drop_index("ix_payment_attempts_due_id", table_name="payment_attempts")
    op.drop_table("payment_attempts")
    op.drop_table("package_service_usage")
    op.drop_index(
        op.f("ix_package_entitlement_history_entitlement_id"),
        table_name="package_entitlement_history",
    )
    op.drop_table("package_entitlement_history")
    op.drop_index(
        "uq_ai_credit_ledger_order_grant",
        table_name="ai_credit_ledger",
        postgresql_where=sa.text("entry = 'GRANT'"),
    )
    op.drop_index(
        "uq_ai_credit_ledger_generation_entry",
        table_name="ai_credit_ledger",
        postgresql_where=sa.text("generation_id IS NOT NULL"),
    )
    op.drop_table("ai_credit_ledger")
    op.drop_index(
        "uq_refund_requests_one_open",
        table_name="refund_requests",
        postgresql_where=sa.text("state IN ('REQUESTED', 'APPROVED')"),
    )
    op.drop_table("refund_requests")
    op.drop_table("payment_dues")
    op.drop_index(
        "uq_package_entitlements_one_active",
        table_name="package_entitlements",
        postgresql_where=sa.text("state = 'ACTIVE'"),
    )
    op.drop_table("package_entitlements")
    op.drop_index(
        "uq_orders_one_open_package",
        table_name="orders",
        postgresql_where=sa.text("kind = 'PACKAGE' AND state = 'AWAITING_PAYMENT'"),
    )
    op.drop_index("ix_orders_buyer_user_id", table_name="orders")
    op.drop_table("orders")
    op.drop_index(
        "uq_offering_versions_one_active",
        table_name="offering_versions",
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.drop_table("offering_versions")
    op.drop_table("eligibility_assessments")
    op.drop_index(
        "uq_tax_configuration_versions_one_active",
        table_name="tax_configuration_versions",
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.drop_table("tax_configuration_versions")
    op.drop_index(
        "uq_pricing_rule_versions_one_active",
        table_name="pricing_rule_versions",
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.drop_table("pricing_rule_versions")
    op.drop_index(
        "uq_instalment_plan_versions_one_active",
        table_name="instalment_plan_versions",
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.drop_table("instalment_plan_versions")
    op.drop_index(
        "ix_payment_events_unprocessed",
        table_name="payment_events",
        postgresql_where=sa.text("processed_at IS NULL"),
    )
    op.drop_table("payment_events")
    op.drop_table("offerings")
    op.drop_table("invoice_sequences")
    op.drop_index(op.f("ix_fake_gateway_records_parent_id"), table_name="fake_gateway_records")
    op.drop_table("fake_gateway_records")
    op.drop_index(
        "uq_eligibility_checklist_versions_one_active",
        table_name="eligibility_checklist_versions",
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.drop_table("eligibility_checklist_versions")
    op.execute("DROP FUNCTION p2b_allow_only_columns()")
    op.execute("DELETE FROM file_objects WHERE purpose = 'INVOICE'")
    op.execute("ALTER TABLE file_objects DROP CONSTRAINT ck_file_objects_purpose")
    op.execute(
        "ALTER TABLE file_objects ADD CONSTRAINT ck_file_objects_purpose CHECK (purpose IN "
        "('REQUIREMENT_UPLOAD', 'AI_CONCEPT', 'VERIFICATION_EVIDENCE', 'PORTFOLIO'))"
    )
