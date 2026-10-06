"""Slice 3.1 close-out: design references become reversible.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-05

Removing a reference sets `removed_at` and `removed_by`; the row stays as history. At most one
active reference per concept (partial unique index). Authority stays ILLUSTRATIVE_ONLY.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("design_references", sa.Column("removed_at", sa.DateTime(timezone=True)))
    op.add_column(
        "design_references",
        sa.Column("removed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
    )
    op.create_check_constraint(
        "removal_named", "design_references", "(removed_at IS NULL) = (removed_by IS NULL)"
    )
    op.drop_constraint("uq_design_references_generation_id", "design_references", type_="unique")
    op.create_index(
        "uq_design_references_active", "design_references", ["generation_id"], unique=True,
        postgresql_where=sa.text("removed_at IS NULL"),
    )  # fmt: skip
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT UPDATE ON design_references TO app_rw;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Removed references are history only; the earlier schema has no place for them.
    op.execute("DELETE FROM design_references WHERE removed_at IS NOT NULL")
    op.drop_index("uq_design_references_active", table_name="design_references")
    op.create_unique_constraint(
        "uq_design_references_generation_id", "design_references", ["generation_id"]
    )
    op.drop_constraint("removal_named", "design_references", type_="check")
    op.drop_column("design_references", "removed_by")
    op.drop_column("design_references", "removed_at")
