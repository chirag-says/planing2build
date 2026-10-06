"""OTP sign-in (B-03) and rate cards: user_contacts, otp_challenges, rate_counters, rate_cards;
contact and IP hashes on security_events.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-04

Additive only (expand step). State values are literals copied from p2b.core.vocabulary on this
date; tests/test_schema.py fails if they drift.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[sa.DateTime]]:
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
        "user_contacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("audience", sa.String(3), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("value", sa.String(320), nullable=False),
        sa.Column("normalized", sa.String(320), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("audience IN ('ihb', 'pro', 'ops')", name="audience"),
        sa.CheckConstraint("kind IN ('EMAIL', 'PHONE')", name="kind"),
    )
    op.create_index(
        "uq_user_contacts_audience_kind_normalized",
        "user_contacts",
        ["audience", "kind", "normalized"],
        unique=True,
    )
    op.create_index("ix_user_contacts_user_id", "user_contacts", ["user_id"])

    op.create_table(
        "otp_challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("audience", sa.String(3), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("contact_kind", sa.String(10), nullable=False),
        sa.Column("contact_normalized", sa.String(320), nullable=False),
        sa.Column("code_hash", sa.String(200), nullable=False),
        sa.Column("code_ciphertext", sa.LargeBinary()),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.SmallInteger(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("delivery_failed_at", sa.DateTime(timezone=True)),
        sa.Column("ip_hash", sa.String(64)),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        *_timestamps(),
        sa.CheckConstraint("audience IN ('ihb', 'pro', 'ops')", name="audience"),
        sa.CheckConstraint("purpose IN ('LOGIN')", name="purpose"),
        sa.CheckConstraint("contact_kind IN ('EMAIL', 'PHONE')", name="contact_kind"),
        sa.CheckConstraint("state IN ('ISSUED', 'VERIFIED', 'EXPIRED', 'LOCKED')", name="state"),
    )
    op.create_index(
        "ix_otp_challenges_contact",
        "otp_challenges",
        ["audience", "contact_kind", "contact_normalized", "created_at"],
    )

    op.create_table(
        "rate_counters",
        sa.Column("bucket_key", sa.String(200), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
    )

    op.create_table(
        "rate_cards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("city", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.SmallInteger(), nullable=False),
        sa.Column("rates", pg.JSONB(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by", sa.Uuid()),
        *_timestamps(),
        sa.UniqueConstraint("city", "version"),
        sa.CheckConstraint(
            "is_demo OR published_by IS NOT NULL", name="approved_card_has_publisher"
        ),
    )
    op.create_index("ix_rate_cards_city_valid_from", "rate_cards", ["city", "valid_from"])

    op.add_column("security_events", sa.Column("contact_hash", sa.String(64)))
    op.add_column("security_events", sa.Column("ip_hash", sa.String(64)))
    op.create_index(
        "ix_security_events_kind_contact_at", "security_events", ["kind", "contact_hash", "at"]
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT SELECT, INSERT, UPDATE ON user_contacts, otp_challenges TO app_rw;
                GRANT SELECT, INSERT, UPDATE, DELETE ON rate_counters TO app_rw;
                GRANT SELECT, INSERT ON rate_cards TO app_rw;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_readonly') THEN
                GRANT SELECT ON user_contacts, otp_challenges, rate_counters, rate_cards
                    TO app_readonly;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_security_events_kind_contact_at", table_name="security_events")
    op.drop_column("security_events", "ip_hash")
    op.drop_column("security_events", "contact_hash")
    op.drop_table("rate_cards")
    op.drop_table("rate_counters")
    op.drop_table("otp_challenges")
    op.drop_table("user_contacts")
