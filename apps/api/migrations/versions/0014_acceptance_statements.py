"""Slice 3.5 reconciliation: the homeowner acceptance statement as versioned configuration.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-05

Chirag, 2026-10-05: the acceptance wording is IMPLEMENTED / PENDING FINAL CLIENT + LEGAL
CONFIRMATION, and must be replaceable without changing the acceptance model. `acceptance_statements`
holds versioned templates ($version_no, $project_code, $content_hash), one ACTIVE; version 1 is the
functional wording used since 0013. Each acceptance names the statement version it confirmed;
acceptances recorded before this migration are linked to version 1, whose text they hold.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

V1_ID = "35000000-0000-7000-8000-000000000002"
V1_TEXT = (
    "I accept Build Plan version $version_no for project $project_code, identified by content "
    "hash $content_hash, as the baseline for requesting contractor quotes."
)
revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "acceptance_statements",
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
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name=op.f("ck_acceptance_statements_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_acceptance_statements")),
        sa.UniqueConstraint("version", name=op.f("uq_acceptance_statements_version")),
    )
    op.create_index(
        "uq_acceptance_statements_one_active", "acceptance_statements", ["status"], unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )  # fmt: skip
    op.execute(
        sa.text(
            "INSERT INTO acceptance_statements (id, version, text, status, note) "
            "VALUES (CAST(:id AS uuid), 1, :text, 'ACTIVE', :note)"
        ).bindparams(
            id=V1_ID,
            text=V1_TEXT,
            note="Functional wording. IMPLEMENTED / PENDING FINAL CLIENT + LEGAL CONFIRMATION "
            "(Chirag, 2026-10-05); replace with the launch-approved wording as a new version.",
        )
    )
    op.add_column("build_plan_acceptances", sa.Column("statement_id", sa.Uuid(), nullable=True))
    op.execute(
        "ALTER TABLE build_plan_acceptances DISABLE TRIGGER build_plan_acceptances_append_only"
    )
    op.execute(
        sa.text("UPDATE build_plan_acceptances SET statement_id = CAST(:id AS uuid)").bindparams(
            id=V1_ID
        )
    )
    op.execute(
        "ALTER TABLE build_plan_acceptances ENABLE TRIGGER build_plan_acceptances_append_only"
    )
    op.alter_column("build_plan_acceptances", "statement_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_build_plan_acceptances_statement_id_acceptance_statements"),
        "build_plan_acceptances", "acceptance_statements", ["statement_id"], ["id"],
        ondelete="RESTRICT",
    )  # fmt: skip
    op.execute(
        "CREATE TRIGGER acceptance_statements_lifecycle_only BEFORE UPDATE OR DELETE ON "
        "acceptance_statements FOR EACH ROW EXECUTE FUNCTION "
        "p2b_allow_only_columns('status', 'activated_by', 'activated_at')"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT SELECT, INSERT, UPDATE ON acceptance_statements TO app_rw;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_build_plan_acceptances_statement_id_acceptance_statements"),
        "build_plan_acceptances", type_="foreignkey",
    )  # fmt: skip
    op.drop_column("build_plan_acceptances", "statement_id")
    op.drop_index(
        "uq_acceptance_statements_one_active", table_name="acceptance_statements",
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )  # fmt: skip
    op.drop_table("acceptance_statements")
