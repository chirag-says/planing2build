"""Concept floor plan operation log, Checkpoint 3 (ADR-025; AI_DESIGN_ENGINE_CHECKPOINT_3).

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-07

Additive only (rung M1): `house_plan_ops`, one row per applied operation batch (the operations,
their inverse batch, the reason, the resulting body hash and the actor). Append-only, like
`house_plan_versions`. The head document stays on `house_plans` under optimistic locking; this
log makes every revision reproducible from version 1. Nothing existing changes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "house_plan_ops",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("ops", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("inverse", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.String(length=12), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "reason IN ('USER', 'AUTO_REPAIR', 'REVERT')", name=op.f("ck_house_plan_ops_reason")
        ),
        sa.CheckConstraint("revision_no >= 1", name=op.f("ck_house_plan_ops_revision_no_positive")),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_house_plan_ops_actor_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["house_plans.id"],
            name=op.f("fk_house_plan_ops_plan_id_house_plans"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_house_plan_ops")),
        sa.UniqueConstraint(
            "plan_id", "revision_no", name=op.f("uq_house_plan_ops_plan_id_revision_no")
        ),
    )
    op.execute(
        "CREATE TRIGGER house_plan_ops_append_only BEFORE UPDATE OR DELETE ON house_plan_ops "
        "FOR EACH ROW EXECUTE FUNCTION p2b_forbid_mutation()"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT SELECT, INSERT ON house_plan_ops TO app_rw;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """The table goes with its trigger; nothing outside it was changed."""
    op.drop_table("house_plan_ops")
