"""Slice 2 foundation: staff roles, TOTP secrets, operations work queue.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-04

- `staff_roles`: global OPS and ADMIN roles per operations account (gap G-01;
  SLICE2_READINESS section 1). One active grant per user and role; revoked rows are history.
- `mfa_secrets`: TOTP secrets, AES-GCM encrypted, with argon2id recovery-code hashes (SECURITY
  3.3; DATA 4.2).
- `ops_queue_items`: console work queues (DATA 4.14). Data migration: every project already in
  SUBMITTED gets an open review item, dated by its submission, so nothing submitted in Slice 1
  is missing from the queue.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "staff_roles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("granted_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.CheckConstraint("role IN ('OPS', 'ADMIN')", name="role"),
    )
    op.create_index(
        "uq_staff_roles_active",
        "staff_roles",
        ["user_id", "role"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "mfa_secrets",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("secret_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("enabled_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_step", sa.BigInteger()),
        sa.Column(
            "recovery_code_hashes",
            pg.ARRAY(sa.String(200)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "ops_queue_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("ref_type", sa.String(40), nullable=False),
        sa.Column("ref_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("priority", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("claimed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("kind IN ('REQUIREMENT_REVIEW')", name="kind"),
        sa.CheckConstraint("state IN ('OPEN', 'CLAIMED', 'RESOLVED')", name="state"),
        sa.CheckConstraint(
            "(state = 'CLAIMED') = (claimed_by IS NOT NULL)", name="claimed_has_claimer"
        ),
    )
    op.create_index(
        "uq_ops_queue_items_open_ref",
        "ops_queue_items",
        ["kind", "ref_type", "ref_id"],
        unique=True,
        postgresql_where=sa.text("state <> 'RESOLVED'"),
    )
    op.create_index(
        "ix_ops_queue_items_kind_state_created", "ops_queue_items", ["kind", "state", "created_at"]
    )

    op.execute(
        """
        INSERT INTO ops_queue_items (id, kind, ref_type, ref_id, state, created_at, updated_at)
        SELECT gen_random_uuid(), 'REQUIREMENT_REVIEW', 'project', p.id, 'OPEN',
               coalesce(p.submitted_at, p.updated_at), now()
        FROM projects p
        WHERE p.status = 'SUBMITTED'
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT SELECT, INSERT, UPDATE ON staff_roles, mfa_secrets, ops_queue_items TO app_rw;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    for table in ("ops_queue_items", "mfa_secrets", "staff_roles"):
        op.drop_table(table)
