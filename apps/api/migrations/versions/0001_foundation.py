"""Foundation: extensions, users, sessions, audit and security events, outbox, append-only guards.

Revision ID: 0001
Revises:
Create Date: 2026-10-04

State values are literals copied from p2b.core.vocabulary on this date; tests/test_schema.py
fails if the vocabulary and these CHECK constraints drift apart.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY = ("audit_events", "security_events")


def _timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]  # fmt: skip


def upgrade() -> None:
    # Extensions (DATA_ARCHITECTURE section 2). On Supabase they are enabled from the dashboard
    # first; IF NOT EXISTS then makes these no-ops. Not dropped on downgrade: other objects and
    # other schemas may depend on them.
    for extension in ("postgis", "pg_trgm", "pgcrypto", "pg_stat_statements"):
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {extension}")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("audience", sa.String(3), nullable=False),
        sa.Column("display_name", sa.String(120)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("locale", sa.String(10), server_default="en", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("audience IN ('ihb', 'pro', 'ops')", name="audience"),
        sa.CheckConstraint(
            "status IN ('PENDING_VERIFICATION', 'ACTIVE', 'SUSPENDED', 'CLOSED')", name="status"
        ),
    )
    op.create_index("ix_users_audience_status", "users", ["audience", "status"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.LargeBinary(32), nullable=False, unique=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("audience", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("mfa_verified_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("audience IN ('ihb', 'pro', 'ops')", name="audience"),
    )  # fmt: skip
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index(
        "ix_sessions_active_user",
        "sessions",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid()),
        sa.Column("actor_role", sa.String(40)),
        sa.Column("actor_type", sa.String(10), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(60), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid()),
        sa.Column("old_value", pg.JSONB()),
        sa.Column("new_value", pg.JSONB()),
        sa.Column("reason", sa.Text()),
        sa.Column("is_override", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("request_id", sa.String(64)),
        sa.Column("session_id", sa.Uuid()),
        sa.CheckConstraint("actor_type IN ('USER', 'SYSTEM', 'JOB')", name="actor_type"),
    )
    op.create_index("ix_audit_events_entity", "audit_events", ["entity_type", "entity_id", "at"])
    op.create_index("ix_audit_events_actor", "audit_events", ["actor_user_id", "at"])
    op.create_index("ix_audit_events_project", "audit_events", ["project_id", "at"])

    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("kind", sa.String(60), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("audience", sa.String(3)),
        sa.Column("user_id", sa.Uuid()),
        sa.Column("request_id", sa.String(64)),
        sa.Column("details", pg.JSONB(), server_default="{}", nullable=False),
        sa.CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name="severity"),
    )
    op.create_index("ix_security_events_kind_at", "security_events", ["kind", "at"])

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("aggregate_type", sa.String(60), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("dedupe_key", sa.String(300), nullable=False, unique=True),
        sa.Column("request_id", sa.String(64)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text()),
    )  # fmt: skip
    op.create_index(
        "ix_outbox_events_unprocessed", "outbox_events", ["occurred_at", "id"],
        postgresql_where=sa.text("processed_at IS NULL"),
    )  # fmt: skip

    # Append-only guards. Grants are the primary control in staging and production; the
    # triggers hold the rule everywhere, including local databases with a single superuser.
    op.execute(
        """
        CREATE FUNCTION p2b_forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
        END $$;
        """
    )
    for table in APPEND_ONLY:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION p2b_forbid_mutation()"
        )
    op.execute(
        """
        CREATE FUNCTION p2b_outbox_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (NEW.id, NEW.event_type, NEW.aggregate_type, NEW.aggregate_id, NEW.payload,
                NEW.dedupe_key, NEW.request_id, NEW.occurred_at)
               IS DISTINCT FROM
               (OLD.id, OLD.event_type, OLD.aggregate_type, OLD.aggregate_id, OLD.payload,
                OLD.dedupe_key, OLD.request_id, OLD.occurred_at) THEN
                RAISE EXCEPTION 'outbox_events: only processing columns may change'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "CREATE TRIGGER outbox_events_guard BEFORE UPDATE ON outbox_events "
        "FOR EACH ROW EXECUTE FUNCTION p2b_outbox_guard()"
    )

    # Least-privilege grants where the roles exist (DATA_ARCHITECTURE section 2, Roles).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT SELECT, INSERT, UPDATE ON users, sessions, outbox_events TO app_rw;
                GRANT SELECT, INSERT ON audit_events, security_events TO app_rw;
                REVOKE UPDATE, DELETE, TRUNCATE ON audit_events, security_events FROM app_rw;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_readonly') THEN
                GRANT SELECT ON users, sessions, audit_events, security_events, outbox_events
                    TO app_readonly;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("security_events")
    op.drop_table("audit_events")
    op.drop_table("sessions")
    op.drop_table("users")
    op.execute("DROP FUNCTION p2b_outbox_guard()")
    op.execute("DROP FUNCTION p2b_forbid_mutation()")
