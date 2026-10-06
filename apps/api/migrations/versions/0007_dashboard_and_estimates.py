"""Slice 3.0: specification groups and project estimates.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-05

- A, B and C are specification groups, never products (PD-09): `spec_packages` becomes
  `spec_groups` and `spec_line_masters.package` becomes `spec_group`. Data unchanged.
- `project_estimates`: the indicative estimate stored with each submission (PD-03, PD-04),
  immutable (append-only trigger), with the rate card it used.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("spec_packages", "spec_groups")
    op.execute("ALTER TABLE spec_groups RENAME CONSTRAINT pk_spec_packages TO pk_spec_groups")
    op.alter_column("spec_line_masters", "package", new_column_name="spec_group")
    op.execute(
        "ALTER TABLE spec_line_masters RENAME CONSTRAINT "
        "fk_spec_line_masters_package_spec_packages TO fk_spec_line_masters_spec_group_spec_groups"
    )

    op.create_table(
        "project_estimates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("requirement_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("unavailable_reason", sa.String(30)),
        sa.Column("inputs", pg.JSONB(), nullable=False),
        sa.Column("rate_card_id", sa.Uuid(), sa.ForeignKey("rate_cards.id", ondelete="RESTRICT")),
        sa.Column("result", pg.JSONB()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("project_id", "requirement_version"),
        sa.CheckConstraint("status IN ('AVAILABLE', 'UNAVAILABLE')", name="status"),
        sa.CheckConstraint(
            "unavailable_reason IS NULL OR "
            "unavailable_reason IN ('BUILT_UP_AREA_NOT_GIVEN', 'NO_RATE_CARD')",
            name="unavailable_reason",
        ),
        sa.CheckConstraint(
            "(status = 'AVAILABLE') = (result IS NOT NULL AND rate_card_id IS NOT NULL "
            "AND unavailable_reason IS NULL)",
            name="available_has_result",
        ),
    )
    op.execute(
        "CREATE TRIGGER project_estimates_append_only BEFORE UPDATE OR DELETE ON project_estimates "
        "FOR EACH ROW EXECUTE FUNCTION p2b_forbid_mutation()"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT SELECT, INSERT ON project_estimates TO app_rw;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("project_estimates")
    op.execute(
        "ALTER TABLE spec_line_masters RENAME CONSTRAINT "
        "fk_spec_line_masters_spec_group_spec_groups TO fk_spec_line_masters_package_spec_packages"
    )
    op.alter_column("spec_line_masters", "spec_group", new_column_name="package")
    op.execute("ALTER TABLE spec_groups RENAME CONSTRAINT pk_spec_groups TO pk_spec_packages")
    op.rename_table("spec_groups", "spec_packages")
