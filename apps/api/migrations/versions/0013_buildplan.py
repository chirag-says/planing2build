"""Slice 3.5: authoritative design intake and the Build Plan.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-05

SLICE3_5_READINESS section 0 (BP-01 to BP-20; BP-07A deferred). Tables for item rate cards,
drawing checker appointments, versioned sign-off statements, design requests, drawing sets and
files, Build Plans and versions with their specification values, BOQ lines and schedule entries,
structural sign-offs, homeowner acceptances and history.

Guards (database triggers, so no code path can bypass them):
- a version's content columns change only while it is DRAFT; afterwards only lifecycle columns;
- values, BOQ lines and schedule entries change only while their version is DRAFT;
- drawing files change only while their set is DRAFT; a set's content hash is set once;
- rate card lines change only while their card is DRAFT; published cards change only to retire;
- sign-offs change only from SIGNED to VOID; acceptances and history are append-only;
- schedule entries hold no dates (CHECK; BP-07A deferred, lifted later with date calculation).

Seed: sign-off statement version 1, the BP-04 baseline wording, ACTIVE, marked as pending final
client and legal confirmation before production launch. No rate, duration or value is seeded.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

STATEMENT_V1 = (
    "I confirm that I have reviewed the structural information and drawings identified in this "
    "Build Plan version for the stated project inputs and assumptions, and that the structural "
    "items covered by this sign-off are acceptable for issue, subject to the assumptions and "
    "conditions recorded with the project."
)
VERSION_LIFECYCLE = (
    "state", "content_hash", "submitted_by", "submitted_at", "issued_by", "issued_at",
    "issued_document_id", "accepted_at", "accepted_document_id", "closed_at", "close_reason",
    "version",
)  # fmt: skip
DRAFT_CHILDREN = (
    ("build_plan_spec_values", "build_plan_versions", "version_id"),
    ("boq_lines", "build_plan_versions", "version_id"),
    ("build_plan_schedule_entries", "build_plan_versions", "version_id"),
    ("drawing_files", "drawing_sets", "set_id"),
    ("item_rate_card_lines", "item_rate_cards", "card_id"),
)
MUTABLE_COLUMNS = {
    "drawing_checker_appointments": ("ended_at", "ended_by"),
    "signoff_statements": ("status", "activated_by", "activated_at"),
    "item_rate_cards": ("status", "published_by", "published_at", "retired_at"),
    "drawing_sets": (
        "state", "content_hash", "submitted_by", "submitted_at", "family_decided_at",
        "family_note", "checker_appointment_id", "checked_by", "checked_at", "check_note",
        "check_evidence_file_id", "superseded_at", "version",
    ),
    "build_plans": ("accepted_version_id", "version"),
    "structural_signoffs": ("state", "voided_at", "voided_by", "void_reason"),
}  # fmt: skip
APPEND_ONLY = ("design_requests", "build_plan_acceptances", "build_plan_events")
PURPOSES_BEFORE = (
    "'REQUIREMENT_UPLOAD', 'AI_CONCEPT', 'VERIFICATION_EVIDENCE', 'PORTFOLIO', 'INVOICE', "
    "'QUOTE_DOCUMENT'"
)
revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drawing_checker_appointments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("qualification", sa.String(length=200), nullable=False),
        sa.Column("registration_reference", sa.String(length=200), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("appointed_by", sa.Uuid(), nullable=False),
        sa.Column(
            "appointed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["appointed_by"],
            ["users.id"],
            name=op.f("fk_drawing_checker_appointments_appointed_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ended_by"],
            ["users.id"],
            name=op.f("fk_drawing_checker_appointments_ended_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_drawing_checker_appointments_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_drawing_checker_appointments")),
    )
    op.create_table(
        "item_rate_cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("geography", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("prepared_by", sa.Uuid(), nullable=False),
        sa.Column(
            "prepared_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status = 'DRAFT' OR (published_by IS NOT NULL AND published_at IS NOT NULL)",
            name=op.f("ck_item_rate_cards_published_has_publisher"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PUBLISHED', 'RETIRED')", name=op.f("ck_item_rate_cards_status")
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name=op.f("ck_item_rate_cards_effective_range"),
        ),
        sa.ForeignKeyConstraint(
            ["prepared_by"],
            ["users.id"],
            name=op.f("fk_item_rate_cards_prepared_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["published_by"],
            ["users.id"],
            name=op.f("fk_item_rate_cards_published_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_item_rate_cards")),
        sa.UniqueConstraint(
            "geography", "version", name=op.f("uq_item_rate_cards_geography_version")
        ),
    )
    op.create_table(
        "signoff_statements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("activated_by", sa.Uuid(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name=op.f("ck_signoff_statements_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signoff_statements")),
        sa.UniqueConstraint("version", name=op.f("uq_signoff_statements_version")),
    )
    op.create_index(
        "uq_signoff_statements_one_active",
        "signoff_statements",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "build_plan_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=16), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("from_state", sa.String(length=30), nullable=True),
        sa.Column("to_state", sa.String(length=30), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_role", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "subject IN ('DESIGN_REQUEST', 'DRAWING_SET', 'VERSION', 'SIGNOFF')",
            name=op.f("ck_build_plan_events_subject"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_build_plan_events_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_build_plan_events_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_build_plan_events")),
    )
    op.create_index(
        "ix_build_plan_events_project_id", "build_plan_events", ["project_id", "at"], unique=False
    )
    op.create_table(
        "build_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("accepted_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_build_plans_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_build_plans")),
        sa.UniqueConstraint("project_id", name=op.f("uq_build_plans_project_id")),
    )
    op.create_table(
        "item_rate_card_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.Uuid(), nullable=False),
        sa.Column("item_code", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("rate", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.CheckConstraint("rate >= 0", name=op.f("ck_item_rate_card_lines_rate")),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["item_rate_cards.id"],
            name=op.f("fk_item_rate_card_lines_card_id_item_rate_cards"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_item_rate_card_lines")),
        sa.UniqueConstraint(
            "card_id", "item_code", name=op.f("uq_item_rate_card_lines_card_id_item_code")
        ),
    )
    op.create_table(
        "design_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=True),
        sa.Column("provider_name", sa.String(length=160), nullable=True),
        sa.Column("provider_qualification", sa.String(length=200), nullable=True),
        sa.Column("scope_note", sa.Text(), nullable=False),
        sa.Column(
            "reference_design_ids",
            postgresql.ARRAY(sa.Uuid()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("opened_by", sa.Uuid(), nullable=False),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "(kind IN ('LISTED_PROFESSIONAL', 'OUTSIDE_PROFESSIONAL')) = (engagement_id IS NOT NULL)",
            name=op.f("ck_design_requests_engagement_for_professionals"),
        ),
        sa.CheckConstraint(
            "kind IN ('LISTED_PROFESSIONAL', 'OUTSIDE_PROFESSIONAL', 'HOMEOWNER_PROVIDED', 'PLAN2BUILD_ARRANGED')",
            name=op.f("ck_design_requests_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["project_engagements.id"],
            name=op.f("fk_design_requests_engagement_id_project_engagements"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["opened_by"],
            ["users.id"],
            name=op.f("fk_design_requests_opened_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_design_requests_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_design_requests")),
    )
    op.create_index(
        "ix_design_requests_project_id", "design_requests", ["project_id"], unique=False
    )
    op.create_table(
        "drawing_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("set_no", sa.SmallInteger(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("submitted_by", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("family_decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("family_note", sa.Text(), nullable=True),
        sa.Column("checker_appointment_id", sa.Uuid(), nullable=True),
        sa.Column("checked_by", sa.Uuid(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_note", sa.Text(), nullable=True),
        sa.Column("check_evidence_file_id", sa.Uuid(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "state IN ('DRAFT') OR content_hash IS NOT NULL",
            name=op.f("ck_drawing_sets_submitted_has_hash"),
        ),
        sa.CheckConstraint(
            "state IN ('DRAFT', 'SUBMITTED', 'IN_CHECK', 'CHANGES_REQUESTED', 'APPROVED', 'REJECTED', 'SUPERSEDED')",
            name=op.f("ck_drawing_sets_state"),
        ),
        sa.CheckConstraint(
            "state NOT IN ('APPROVED', 'SUPERSEDED') OR (checker_appointment_id IS NOT NULL AND checked_at IS NOT NULL)",
            name=op.f("ck_drawing_sets_approved_was_checked"),
        ),
        sa.ForeignKeyConstraint(
            ["check_evidence_file_id"],
            ["file_objects.id"],
            name=op.f("fk_drawing_sets_check_evidence_file_id_file_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["checked_by"],
            ["users.id"],
            name=op.f("fk_drawing_sets_checked_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["checker_appointment_id"],
            ["drawing_checker_appointments.id"],
            name=op.f("fk_drawing_sets_checker_appointment_id_drawing_checker_appointments"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_drawing_sets_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_drawing_sets_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["design_requests.id"],
            name=op.f("fk_drawing_sets_request_id_design_requests"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"],
            ["users.id"],
            name=op.f("fk_drawing_sets_submitted_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_drawing_sets")),
        sa.UniqueConstraint("request_id", "set_no", name=op.f("uq_drawing_sets_request_id_set_no")),
    )
    op.create_index("ix_drawing_sets_project_id", "drawing_sets", ["project_id"], unique=False)
    op.create_index(
        "uq_drawing_sets_one_open",
        "drawing_sets",
        ["request_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('DRAFT', 'SUBMITTED', 'IN_CHECK')"),
    )
    op.create_table(
        "build_plan_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("build_plan_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.SmallInteger(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("created_from_id", sa.Uuid(), nullable=True),
        sa.Column("requirement_version", sa.Integer(), nullable=False),
        sa.Column("drawing_set_id", sa.Uuid(), nullable=True),
        sa.Column("rate_card_id", sa.Uuid(), nullable=True),
        sa.Column(
            "inclusions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "exclusions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "assumptions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("explanation_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_edited_by", sa.Uuid(), nullable=False),
        sa.Column(
            "last_edited_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("submitted_by", sa.Uuid(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by", sa.Uuid(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_document_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_document_id", sa.Uuid(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "state IN ('DRAFT', 'IN_REVIEW', 'ISSUED', 'ACCEPTED', 'CHANGES_REQUESTED', 'SUPERSEDED', 'WITHDRAWN')",
            name=op.f("ck_build_plan_versions_state"),
        ),
        sa.CheckConstraint(
            "state IN ('DRAFT', 'WITHDRAWN') OR content_hash IS NOT NULL",
            name=op.f("ck_build_plan_versions_frozen_has_hash"),
        ),
        sa.CheckConstraint(
            "state NOT IN ('ISSUED', 'ACCEPTED', 'CHANGES_REQUESTED') OR (issued_at IS NOT NULL AND issued_document_id IS NOT NULL)",
            name=op.f("ck_build_plan_versions_issued_has_document"),
        ),
        sa.CheckConstraint(
            "issued_by IS NULL OR issued_by <> last_edited_by",
            name=op.f("ck_build_plan_versions_four_eyes"),
        ),
        sa.ForeignKeyConstraint(
            ["accepted_document_id"],
            ["file_objects.id"],
            name=op.f("fk_build_plan_versions_accepted_document_id_file_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["build_plan_id"],
            ["build_plans.id"],
            name=op.f("fk_build_plan_versions_build_plan_id_build_plans"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_build_plan_versions_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_from_id"],
            ["build_plan_versions.id"],
            name=op.f("fk_build_plan_versions_created_from_id_build_plan_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["drawing_set_id"],
            ["drawing_sets.id"],
            name=op.f("fk_build_plan_versions_drawing_set_id_drawing_sets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["issued_by"],
            ["users.id"],
            name=op.f("fk_build_plan_versions_issued_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["issued_document_id"],
            ["file_objects.id"],
            name=op.f("fk_build_plan_versions_issued_document_id_file_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["last_edited_by"],
            ["users.id"],
            name=op.f("fk_build_plan_versions_last_edited_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_build_plan_versions_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rate_card_id"],
            ["item_rate_cards.id"],
            name=op.f("fk_build_plan_versions_rate_card_id_item_rate_cards"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"],
            ["users.id"],
            name=op.f("fk_build_plan_versions_submitted_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_build_plan_versions")),
        sa.UniqueConstraint(
            "build_plan_id",
            "version_no",
            name=op.f("uq_build_plan_versions_build_plan_id_version_no"),
        ),
    )
    op.create_index(
        "ix_build_plan_versions_project_id", "build_plan_versions", ["project_id"], unique=False
    )
    op.create_index(
        "uq_build_plan_versions_one_accepted",
        "build_plan_versions",
        ["build_plan_id"],
        unique=True,
        postgresql_where=sa.text("state = 'ACCEPTED'"),
    )
    op.create_index(
        "uq_build_plan_versions_one_open",
        "build_plan_versions",
        ["build_plan_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('DRAFT', 'IN_REVIEW')"),
    )
    op.create_table(
        "drawing_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("set_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("drawing_class", sa.String(length=12), nullable=False),
        sa.Column("floor", sa.SmallInteger(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("sheet_no", sa.String(length=40), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "drawing_class IN ('SITE_PLAN', 'FLOOR_PLAN', 'ELEVATION', 'SECTION', 'STRUCTURAL', 'OTHER')",
            name=op.f("ck_drawing_files_drawing_class"),
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["file_objects.id"],
            name=op.f("fk_drawing_files_file_id_file_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_drawing_files_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["set_id"],
            ["drawing_sets.id"],
            name=op.f("fk_drawing_files_set_id_drawing_sets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_drawing_files")),
        sa.UniqueConstraint("set_id", "file_id", name=op.f("uq_drawing_files_set_id_file_id")),
    )
    op.create_table(
        "boq_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("rate_card_id", sa.Uuid(), nullable=False),
        sa.Column("item_code", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("quantity_basis", sa.String(length=26), nullable=False),
        sa.Column("drawing_file_id", sa.Uuid(), nullable=True),
        sa.Column("basis_note", sa.Text(), nullable=True),
        sa.Column("rate", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("amount", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("stage_number", sa.SmallInteger(), nullable=True),
        sa.Column("floor", sa.SmallInteger(), nullable=True),
        sa.Column(
            "spec_line_codes",
            postgresql.ARRAY(sa.String(length=3)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("assumptions", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "quantity_basis <> 'ADVISOR_ESTIMATE' OR length(trim(basis_note)) > 0",
            name=op.f("ck_boq_lines_estimate_has_reason"),
        ),
        sa.CheckConstraint(
            "quantity_basis <> 'MEASURED_FROM_DRAWING' OR drawing_file_id IS NOT NULL",
            name=op.f("ck_boq_lines_measured_names_drawing"),
        ),
        sa.CheckConstraint(
            "quantity_basis IN ('MEASURED_FROM_DRAWING', 'PROVIDED_BY_PROFESSIONAL', 'ADVISOR_ESTIMATE')",
            name=op.f("ck_boq_lines_quantity_basis"),
        ),
        sa.CheckConstraint("quantity > 0 AND rate >= 0", name=op.f("ck_boq_lines_positive")),
        sa.CheckConstraint(
            "stage_number IS NULL OR stage_number BETWEEN 1 AND 16", name=op.f("ck_boq_lines_stage")
        ),
        sa.ForeignKeyConstraint(
            ["drawing_file_id"],
            ["drawing_files.id"],
            name=op.f("fk_boq_lines_drawing_file_id_drawing_files"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_boq_lines_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rate_card_id"],
            ["item_rate_cards.id"],
            name=op.f("fk_boq_lines_rate_card_id_item_rate_cards"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["build_plan_versions.id"],
            name=op.f("fk_boq_lines_version_id_build_plan_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_boq_lines")),
        sa.UniqueConstraint("version_id", "line_no", name=op.f("uq_boq_lines_version_id_line_no")),
    )
    op.create_table(
        "build_plan_acceptances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.SmallInteger(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("issued_document_sha256", sa.String(length=64), nullable=False),
        sa.Column("accepted_by", sa.Uuid(), nullable=False),
        sa.Column("challenge_id", sa.Uuid(), nullable=False),
        sa.Column("statement_text", sa.Text(), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["accepted_by"],
            ["users.id"],
            name=op.f("fk_build_plan_acceptances_accepted_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["challenge_id"],
            ["otp_challenges.id"],
            name=op.f("fk_build_plan_acceptances_challenge_id_otp_challenges"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_build_plan_acceptances_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["build_plan_versions.id"],
            name=op.f("fk_build_plan_acceptances_version_id_build_plan_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_build_plan_acceptances")),
        sa.UniqueConstraint("challenge_id", name=op.f("uq_build_plan_acceptances_challenge_id")),
        sa.UniqueConstraint("version_id", name=op.f("uq_build_plan_acceptances_version_id")),
    )
    op.create_table(
        "build_plan_schedule_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("entry_key", sa.String(length=8), nullable=False),
        sa.Column("stage_instance_id", sa.Uuid(), nullable=False),
        sa.Column("stage_number", sa.SmallInteger(), nullable=False),
        sa.Column("floor", sa.SmallInteger(), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column(
            "predecessors",
            postgresql.ARRAY(sa.String(length=8)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("planned_start", sa.Date(), nullable=True),
        sa.Column("planned_end", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "duration_days IS NULL OR duration_days > 0",
            name=op.f("ck_build_plan_schedule_entries_duration"),
        ),
        sa.CheckConstraint(
            "planned_start IS NULL AND planned_end IS NULL",
            name=op.f("ck_build_plan_schedule_entries_dates_not_calculated_bp07a"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_build_plan_schedule_entries_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["stage_instance_id"],
            ["stage_instances.id"],
            name=op.f("fk_build_plan_schedule_entries_stage_instance_id_stage_instances"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["build_plan_versions.id"],
            name=op.f("fk_build_plan_schedule_entries_version_id_build_plan_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_build_plan_schedule_entries")),
        sa.UniqueConstraint(
            "version_id",
            "entry_key",
            name=op.f("uq_build_plan_schedule_entries_version_id_entry_key"),
        ),
    )
    op.create_table(
        "build_plan_spec_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("line_code", sa.String(length=3), nullable=False),
        sa.Column("master_version_id", sa.Uuid(), nullable=False),
        sa.Column("criteria_text", sa.Text(), nullable=False),
        sa.Column("is_structural", sa.Boolean(), nullable=False),
        sa.Column("applicability", sa.String(length=16), nullable=False),
        sa.Column("not_applicable_reason", sa.Text(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("basis", sa.String(length=20), nullable=True),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column(
            "evidence_file_ids",
            postgresql.ARRAY(sa.Uuid()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("entered_by", sa.Uuid(), nullable=True),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("carried_from_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "applicability = 'APPLICABLE' OR length(trim(not_applicable_reason)) > 0",
            name=op.f("ck_build_plan_spec_values_not_applicable_has_reason"),
        ),
        sa.CheckConstraint(
            "applicability IN ('APPLICABLE', 'NOT_APPLICABLE')",
            name=op.f("ck_build_plan_spec_values_applicability"),
        ),
        sa.CheckConstraint(
            "basis IS NULL OR basis IN ('STRUCTURAL_DESIGN', 'ARCHITECT_DRAWING', 'HOMEOWNER_PROVIDED', 'ADVISOR', 'STANDARD_REFERENCE')",
            name=op.f("ck_build_plan_spec_values_basis"),
        ),
        sa.ForeignKeyConstraint(
            ["carried_from_id"],
            ["build_plan_spec_values.id"],
            name=op.f("fk_build_plan_spec_values_carried_from_id_build_plan_spec_values"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["entered_by"],
            ["users.id"],
            name=op.f("fk_build_plan_spec_values_entered_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["master_version_id"],
            ["spec_line_master_versions.id"],
            name=op.f("fk_build_plan_spec_values_master_version_id_spec_line_master_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_build_plan_spec_values_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["build_plan_versions.id"],
            name=op.f("fk_build_plan_spec_values_version_id_build_plan_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_build_plan_spec_values")),
        sa.UniqueConstraint(
            "version_id", "line_code", name=op.f("uq_build_plan_spec_values_version_id_line_code")
        ),
    )
    op.create_table(
        "structural_signoffs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("line_code", sa.String(length=3), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("signer_kind", sa.String(length=8), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=True),
        sa.Column("category_code", sa.String(length=40), nullable=False),
        sa.Column("engineer_name", sa.String(length=160), nullable=False),
        sa.Column("engineer_firm", sa.String(length=160), nullable=True),
        sa.Column("registration_number", sa.String(length=80), nullable=True),
        sa.Column("registration_issuer", sa.String(length=160), nullable=True),
        sa.Column("credential_reference", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("credential_file_id", sa.Uuid(), nullable=True),
        sa.Column("statement_id", sa.Uuid(), nullable=False),
        sa.Column("statement_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("drawing_set_id", sa.Uuid(), nullable=False),
        sa.Column("drawing_hashes", postgresql.ARRAY(sa.String(length=64)), nullable=False),
        sa.Column("line_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("challenge_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_file_id", sa.Uuid(), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
        sa.Column(
            "signed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("state", sa.String(length=8), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", sa.Uuid(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(mode = 'ONE_TIME_CODE' AND challenge_id IS NOT NULL AND profile_id IS NOT NULL) OR (mode = 'SIGNED_DOCUMENT' AND evidence_file_id IS NOT NULL)",
            name=op.f("ck_structural_signoffs_mode_evidence"),
        ),
        sa.CheckConstraint(
            "(state = 'VOID') = (voided_at IS NOT NULL)", name=op.f("ck_structural_signoffs_void")
        ),
        sa.CheckConstraint(
            "mode IN ('ONE_TIME_CODE', 'SIGNED_DOCUMENT')", name=op.f("ck_structural_signoffs_mode")
        ),
        sa.CheckConstraint(
            "signer_kind IN ('LISTED', 'OUTSIDE')", name=op.f("ck_structural_signoffs_signer_kind")
        ),
        sa.CheckConstraint(
            "state IN ('SIGNED', 'VOID')", name=op.f("ck_structural_signoffs_state")
        ),
        sa.ForeignKeyConstraint(
            ["category_code"],
            ["service_categories.code"],
            name=op.f("fk_structural_signoffs_category_code_service_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["challenge_id"],
            ["otp_challenges.id"],
            name=op.f("fk_structural_signoffs_challenge_id_otp_challenges"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["credential_file_id"],
            ["file_objects.id"],
            name=op.f("fk_structural_signoffs_credential_file_id_file_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["drawing_set_id"],
            ["drawing_sets.id"],
            name=op.f("fk_structural_signoffs_drawing_set_id_drawing_sets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_file_id"],
            ["file_objects.id"],
            name=op.f("fk_structural_signoffs_evidence_file_id_file_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["professional_profiles.id"],
            name=op.f("fk_structural_signoffs_profile_id_professional_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_structural_signoffs_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"],
            ["users.id"],
            name=op.f("fk_structural_signoffs_recorded_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["statement_id"],
            ["signoff_statements.id"],
            name=op.f("fk_structural_signoffs_statement_id_signoff_statements"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["build_plan_versions.id"],
            name=op.f("fk_structural_signoffs_version_id_build_plan_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["voided_by"],
            ["users.id"],
            name=op.f("fk_structural_signoffs_voided_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_structural_signoffs")),
    )
    op.create_index(
        "uq_structural_signoffs_one_signed",
        "structural_signoffs",
        ["version_id", "line_code"],
        unique=True,
        postgresql_where=sa.text("state = 'SIGNED'"),
    )
    op.add_column("otp_challenges", sa.Column("subject_id", sa.Uuid(), nullable=True))
    op.add_column("project_spec_lines", sa.Column("accepted_value_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_project_spec_lines_accepted_value_id_build_plan_spec_values"),
        "project_spec_lines",
        "build_plan_spec_values",
        ["accepted_value_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_build_plans_accepted_version_id_build_plan_versions"), "build_plans",
        "build_plan_versions", ["accepted_version_id"], ["id"], ondelete="RESTRICT",
    )  # fmt: skip
    op.execute("ALTER TABLE otp_challenges DROP CONSTRAINT ck_otp_challenges_purpose")
    op.execute(
        "ALTER TABLE otp_challenges ADD CONSTRAINT ck_otp_challenges_purpose CHECK (purpose IN "
        "('LOGIN', 'ACCEPT_BUILD_PLAN', 'SIGN_STRUCTURAL'))"
    )
    op.execute(
        "ALTER TABLE otp_challenges ADD CONSTRAINT ck_otp_challenges_confirmation_has_subject "
        "CHECK ((purpose = 'LOGIN') = (subject_id IS NULL))"
    )
    op.execute("ALTER TABLE file_objects DROP CONSTRAINT ck_file_objects_purpose")
    op.execute(
        "ALTER TABLE file_objects ADD CONSTRAINT ck_file_objects_purpose CHECK (purpose IN "
        f"({PURPOSES_BEFORE}, 'DRAWING', 'BUILD_PLAN_EVIDENCE', 'BUILD_PLAN_DOCUMENT'))"
    )
    op.execute(
        """
        CREATE FUNCTION p2b_child_editable() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            row_data jsonb := CASE WHEN TG_OP = 'DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
            parent_state text;
        BEGIN
            EXECUTE format('SELECT state FROM %I WHERE id = $1', TG_ARGV[0])
                INTO parent_state USING (row_data ->> TG_ARGV[1])::uuid;
            IF parent_state IS DISTINCT FROM TG_ARGV[2] THEN
                RAISE EXCEPTION '% rows change only while their % is %', TG_TABLE_NAME,
                    TG_ARGV[0], TG_ARGV[2];
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION p2b_status_child_editable() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            row_data jsonb := CASE WHEN TG_OP = 'DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
            parent_status text;
        BEGIN
            EXECUTE format('SELECT status FROM %I WHERE id = $1', TG_ARGV[0])
                INTO parent_status USING (row_data ->> TG_ARGV[1])::uuid;
            IF parent_status IS DISTINCT FROM TG_ARGV[2] THEN
                RAISE EXCEPTION '% rows change only while their % is %', TG_TABLE_NAME,
                    TG_ARGV[0], TG_ARGV[2];
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$;
        """
    )
    lifecycle = ", ".join(f"'{c}'" for c in VERSION_LIFECYCLE)
    op.execute(
        f"""
        CREATE FUNCTION p2b_build_plan_version_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            old_row jsonb := to_jsonb(OLD);
            new_row jsonb := to_jsonb(NEW);
            allowed text;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'build plan versions are never deleted';
            END IF;
            IF OLD.state = 'DRAFT' THEN
                RETURN NEW;
            END IF;
            FOREACH allowed IN ARRAY ARRAY[{lifecycle}] LOOP
                old_row := old_row - allowed;
                new_row := new_row - allowed;
            END LOOP;
            IF old_row IS DISTINCT FROM new_row THEN
                RAISE EXCEPTION 'a % build plan version is frozen', OLD.state;
            END IF;
            IF OLD.content_hash IS DISTINCT FROM NEW.content_hash AND NEW.state <> 'DRAFT' THEN
                RAISE EXCEPTION 'the content hash of a frozen version never changes';
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION p2b_set_once() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            col text;
        BEGIN
            FOREACH col IN ARRAY TG_ARGV LOOP
                IF (to_jsonb(OLD) ->> col) IS NOT NULL
                   AND (to_jsonb(OLD) ->> col) IS DISTINCT FROM (to_jsonb(NEW) ->> col) THEN
                    RAISE EXCEPTION '%.% is set once', TG_TABLE_NAME, col;
                END IF;
            END LOOP;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "CREATE TRIGGER build_plan_versions_frozen BEFORE UPDATE OR DELETE ON build_plan_versions "
        "FOR EACH ROW EXECUTE FUNCTION p2b_build_plan_version_guard()"
    )
    for table, parent, column in DRAFT_CHILDREN:
        function = (
            "p2b_status_child_editable" if parent == "item_rate_cards" else "p2b_child_editable"
        )
        op.execute(
            f"CREATE TRIGGER {table}_draft_only BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}('{parent}', '{column}', 'DRAFT')"
        )
    for table, columns in MUTABLE_COLUMNS.items():
        arguments = ", ".join(f"'{c}'" for c in columns)
        op.execute(
            f"CREATE TRIGGER {table}_lifecycle_only BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION p2b_allow_only_columns({arguments})"
        )
    op.execute(
        "CREATE TRIGGER drawing_sets_set_once BEFORE UPDATE ON drawing_sets FOR EACH ROW "
        "EXECUTE FUNCTION p2b_set_once('content_hash', 'checked_at', 'superseded_at')"
    )
    op.execute(
        "CREATE TRIGGER item_rate_cards_set_once BEFORE UPDATE ON item_rate_cards FOR EACH ROW "
        "EXECUTE FUNCTION p2b_set_once('published_by', 'published_at', 'retired_at')"
    )
    op.execute(
        "CREATE TRIGGER structural_signoffs_set_once BEFORE UPDATE ON structural_signoffs "
        "FOR EACH ROW EXECUTE FUNCTION p2b_set_once('voided_at', 'voided_by', 'void_reason')"
    )
    op.execute(
        "CREATE TRIGGER drawing_checker_appointments_set_once BEFORE UPDATE ON "
        "drawing_checker_appointments FOR EACH ROW EXECUTE FUNCTION p2b_set_once('ended_at')"
    )
    for table in APPEND_ONLY:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION p2b_forbid_mutation()"
        )
    statements = sa.table(
        "signoff_statements",
        sa.column("id", sa.Uuid),
        sa.column("version", sa.Integer),
        sa.column("text", sa.Text),
        sa.column("status", sa.String),
        sa.column("note", sa.Text),
    )
    op.bulk_insert(
        statements,
        [
            {
                "id": "35000000-0000-7000-8000-000000000001",
                "version": 1,
                "text": STATEMENT_V1,
                "status": "ACTIVE",
                "note": "BP-04 baseline wording (Chirag, 2026-10-05). Product and legal copy: "
                "final client and legal confirmation required before production launch.",
            }
        ],
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT SELECT, INSERT, UPDATE ON item_rate_cards, drawing_checker_appointments,
                    signoff_statements, drawing_sets, build_plans, build_plan_versions,
                    structural_signoffs TO app_rw;
                GRANT SELECT, INSERT, UPDATE, DELETE ON item_rate_card_lines, drawing_files,
                    build_plan_spec_values, boq_lines, build_plan_schedule_entries TO app_rw;
                GRANT SELECT, INSERT ON design_requests, build_plan_acceptances,
                    build_plan_events TO app_rw;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Build Plan files go with the feature; the access log is append-only, so its guard is
    # lifted for exactly this delete.
    op.execute("ALTER TABLE document_access_log DISABLE TRIGGER document_access_log_append_only")
    op.execute(
        "DELETE FROM document_access_log WHERE file_id IN (SELECT id FROM file_objects WHERE "
        "purpose IN ('DRAWING', 'BUILD_PLAN_EVIDENCE', 'BUILD_PLAN_DOCUMENT'))"
    )
    op.execute("ALTER TABLE document_access_log ENABLE TRIGGER document_access_log_append_only")
    op.execute(
        "ALTER TABLE otp_challenges DROP CONSTRAINT ck_otp_challenges_confirmation_has_subject"
    )
    op.execute("ALTER TABLE otp_challenges DROP CONSTRAINT ck_otp_challenges_purpose")
    op.drop_constraint(
        op.f("fk_build_plans_accepted_version_id_build_plan_versions"), "build_plans",
        type_="foreignkey",
    )  # fmt: skip
    op.drop_constraint(
        op.f("fk_project_spec_lines_accepted_value_id_build_plan_spec_values"),
        "project_spec_lines",
        type_="foreignkey",
    )
    op.drop_column("project_spec_lines", "accepted_value_id")
    op.drop_column("otp_challenges", "subject_id")
    op.drop_index(
        "uq_structural_signoffs_one_signed",
        table_name="structural_signoffs",
        postgresql_where=sa.text("state = 'SIGNED'"),
    )
    op.drop_table("structural_signoffs")
    op.drop_table("build_plan_spec_values")
    op.drop_table("build_plan_schedule_entries")
    op.drop_table("build_plan_acceptances")
    op.drop_table("boq_lines")
    op.drop_table("drawing_files")
    op.drop_index(
        "uq_build_plan_versions_one_open",
        table_name="build_plan_versions",
        postgresql_where=sa.text("state IN ('DRAFT', 'IN_REVIEW')"),
    )
    op.drop_index(
        "uq_build_plan_versions_one_accepted",
        table_name="build_plan_versions",
        postgresql_where=sa.text("state = 'ACCEPTED'"),
    )
    op.drop_index("ix_build_plan_versions_project_id", table_name="build_plan_versions")
    op.drop_table("build_plan_versions")
    op.drop_index(
        "uq_drawing_sets_one_open",
        table_name="drawing_sets",
        postgresql_where=sa.text("state IN ('DRAFT', 'SUBMITTED', 'IN_CHECK')"),
    )
    op.drop_index("ix_drawing_sets_project_id", table_name="drawing_sets")
    op.drop_table("drawing_sets")
    op.drop_index("ix_design_requests_project_id", table_name="design_requests")
    op.drop_table("design_requests")
    op.drop_table("item_rate_card_lines")
    op.drop_table("build_plans")
    op.drop_index("ix_build_plan_events_project_id", table_name="build_plan_events")
    op.drop_table("build_plan_events")
    op.drop_index(
        "uq_signoff_statements_one_active",
        table_name="signoff_statements",
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.drop_table("signoff_statements")
    op.drop_table("item_rate_cards")
    op.drop_table("drawing_checker_appointments")
    op.execute("DROP FUNCTION p2b_child_editable()")
    op.execute("DROP FUNCTION p2b_status_child_editable()")
    op.execute("DROP FUNCTION p2b_build_plan_version_guard()")
    op.execute("DROP FUNCTION p2b_set_once()")
    op.execute("DELETE FROM otp_challenges WHERE purpose <> 'LOGIN'")
    op.execute(
        "ALTER TABLE otp_challenges ADD CONSTRAINT ck_otp_challenges_purpose CHECK (purpose IN "
        "('LOGIN'))"
    )
    op.execute(
        "DELETE FROM file_objects WHERE purpose IN "
        "('DRAWING', 'BUILD_PLAN_EVIDENCE', 'BUILD_PLAN_DOCUMENT')"
    )
    op.execute("ALTER TABLE file_objects DROP CONSTRAINT ck_file_objects_purpose")
    op.execute(
        "ALTER TABLE file_objects ADD CONSTRAINT ck_file_objects_purpose CHECK (purpose IN "
        f"({PURPOSES_BEFORE}))"
    )
