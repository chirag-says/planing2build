"""Slice 3.1: AI design concepts.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-05

- `design_prompt_templates`, seeded with version 1 for EXTERIOR and INTERIOR views (F-08 first
  version: concept views only; no floor plans, drawings, dimensions or text).
- `design_generations`: one row per request, reproducible from its snapshot, template version and
  provider request; never authoritative (CHECK); `credit_ref` left for Slice 3.3.
- `design_references`: the family's illustrative references (authority fixed by CHECK).
- `file_objects.purpose` accepts AI_CONCEPT.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATES = "'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED'"
VIEWS = "'EXTERIOR', 'INTERIOR'"
REASONS = (
    "'PROVIDER_UNAVAILABLE', 'PROVIDER_TIMEOUT', 'PROVIDER_REJECTED', 'PROVIDER_ERROR', "
    "'INVALID_OUTPUT', 'STALE'"
)
NEGATIVE = (
    "floor plan, blueprint, technical drawing, construction drawing, section, elevation drawing, "
    "dimensions, measurements, text, labels, letters, numbers, watermark, logo, people"
)
TEMPLATES = {
    "EXTERIOR": (
        "Illustrative architectural concept image of a new residential home in India. "
        "Exterior view of the whole building from the street side, in daylight. $facts "
        "Photorealistic concept visualisation only. Do not show any text, labels, dimensions, "
        "floor plans, drawings or people."
    ),
    "INTERIOR": (
        "Illustrative interior concept image of the main living room of a new residential home "
        "in India, in natural daylight. $facts Photorealistic concept visualisation only. Do not "
        "show any text, labels, dimensions, floor plans, drawings or people."
    ),
}


def upgrade() -> None:
    op.execute("ALTER TABLE file_objects DROP CONSTRAINT ck_file_objects_purpose")
    op.execute(
        "ALTER TABLE file_objects ADD CONSTRAINT ck_file_objects_purpose "
        "CHECK (purpose IN ('REQUIREMENT_UPLOAD', 'AI_CONCEPT'))"
    )

    templates = op.create_table(
        "design_prompt_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("view", sa.String(10), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.UniqueConstraint("view", "version"),
        sa.CheckConstraint(f"view IN ({VIEWS})", name="view"),
        sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
    )  # fmt: skip
    op.create_index(
        "uq_design_prompt_templates_one_active", "design_prompt_templates", ["view"],
        unique=True, postgresql_where=sa.text("status = 'ACTIVE'"),
    )  # fmt: skip
    op.bulk_insert(
        templates,
        [
            {
                "id": uuid.uuid4(), "view": view, "version": 1, "status": "ACTIVE", "body": body,
                "negative_prompt": NEGATIVE,
                "note": "Slice 3.1 first version (F-08): concept views only.",
            }
            for view, body in TEMPLATES.items()
        ],
    )  # fmt: skip

    op.create_table(
        "design_generations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("view", sa.String(10), nullable=False),
        sa.Column("funding", sa.String(4), nullable=False),
        sa.Column("credit_ref", sa.Uuid()),
        sa.Column("free_quota", sa.SmallInteger(), nullable=False),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("prompt_template_id", sa.Uuid(),
                  sa.ForeignKey("design_prompt_templates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("prompt_template_version", sa.Integer(), nullable=False),
        sa.Column("question_set_version", sa.Integer(), nullable=False),
        sa.Column("requirement_version", sa.Integer(), nullable=False),
        sa.Column("snapshot", pg.JSONB(), nullable=False),
        sa.Column("provider_request", pg.JSONB(), nullable=False),
        sa.Column("output_file_id", sa.Uuid(),
                  sa.ForeignKey("file_objects.id", ondelete="RESTRICT")),
        sa.Column("failure_reason", sa.String(30)),
        sa.Column("failure_detail", sa.Text()),
        sa.Column("provider_usage", pg.JSONB()),
        sa.Column("attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_authoritative", sa.Boolean(), server_default=sa.text("false"),
                  nullable=False),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.UniqueConstraint("project_id", "sequence"),
        sa.CheckConstraint(f"state IN ({STATES})", name="state"),
        sa.CheckConstraint(f"view IN ({VIEWS})", name="view"),
        sa.CheckConstraint("funding IN ('FREE', 'PAID')", name="funding"),
        sa.CheckConstraint(f"failure_reason IS NULL OR failure_reason IN ({REASONS})",
                           name="failure_reason"),
        sa.CheckConstraint("is_authoritative = false", name="never_authoritative"),
        sa.CheckConstraint("(state = 'SUCCEEDED') = (output_file_id IS NOT NULL)",
                           name="output_iff_succeeded"),
        sa.CheckConstraint("(state = 'FAILED') = (failure_reason IS NOT NULL)",
                           name="reason_iff_failed"),
        sa.CheckConstraint("funding = 'FREE' OR credit_ref IS NOT NULL", name="paid_names_credit"),
    )  # fmt: skip
    op.create_index("ix_design_generations_requested_by_created_at", "design_generations",
                    ["requested_by", "created_at"])  # fmt: skip
    op.create_index("ix_design_generations_project_id_state", "design_generations",
                    ["project_id", "state"])  # fmt: skip

    op.create_table(
        "design_references",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("generation_id", sa.Uuid(),
                  sa.ForeignKey("design_generations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("authority", sa.String(20), server_default="ILLUSTRATIVE_ONLY", nullable=False),
        sa.Column("marked_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("marked_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.UniqueConstraint("generation_id"),
        sa.CheckConstraint("authority = 'ILLUSTRATIVE_ONLY'", name="illustrative_only"),
    )  # fmt: skip
    op.create_index("ix_design_references_project_id", "design_references", ["project_id"])

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT SELECT ON design_prompt_templates TO app_rw;
                GRANT SELECT, INSERT, UPDATE ON design_generations TO app_rw;
                GRANT SELECT, INSERT ON design_references TO app_rw;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("design_references")
    op.drop_table("design_generations")
    op.drop_table("design_prompt_templates")
    # Removing the feature removes its images; the access log is append-only, so its guard is
    # lifted for exactly this delete.
    op.execute("ALTER TABLE document_access_log DISABLE TRIGGER document_access_log_append_only")
    op.execute("DELETE FROM document_access_log WHERE file_id IN "
               "(SELECT id FROM file_objects WHERE purpose = 'AI_CONCEPT')")  # fmt: skip
    op.execute("ALTER TABLE document_access_log ENABLE TRIGGER document_access_log_append_only")
    op.execute("DELETE FROM file_objects WHERE purpose = 'AI_CONCEPT'")
    op.execute("ALTER TABLE file_objects DROP CONSTRAINT ck_file_objects_purpose")
    op.execute(
        "ALTER TABLE file_objects ADD CONSTRAINT ck_file_objects_purpose "
        "CHECK (purpose IN ('REQUIREMENT_UPLOAD'))"
    )
