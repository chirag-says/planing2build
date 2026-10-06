"""Slice 3.4: service needs, connections, engagements and quote-review intake.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-05

Seed (SLICE3_4_READINESS N-01, confirmed by Chirag on 2026-10-05): `service_value_categories`
maps question set v1's services answer to professional categories. Construction and civil work
are the Contractor (civil work is never the Site/Civil Engineer); project management and approvals
create no need, so they have no row.

Guards: `engagement_events` is append-only; connections, engagements, shared files and quote
reviews accept changes to their lifecycle columns only, and are never deleted.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

SERVICE_VALUE_CATEGORIES_V1 = [
    ("CONSTRUCTION", "CONTRACTOR"),
    ("CIVIL_WORK", "CONTRACTOR"),
    ("ARCHITECTURAL_DESIGN", "ARCHITECT"),
    ("STRUCTURAL_DESIGN", "STRUCTURAL_ENGINEER"),
    ("MEP", "MEP"),
    ("INTERIOR_DESIGN", "INTERIOR_DESIGNER"),
]
APPEND_ONLY = ("engagement_events",)
MUTABLE_COLUMNS = {
    "connections": (
        "state", "professional_contact", "responded_at", "decline_reason", "decline_note",
        "withdrawn_by_role", "withdraw_reason", "withdraw_note", "engagement_id", "version",
    ),
    "project_engagements": ("state", "ended_at", "ended_by_role", "end_reason", "version"),
    "engagement_documents": ("unshared_at",),
    "quote_review_requests": ("state",),
}  # fmt: skip
PURPOSES_BEFORE = (
    "'REQUIREMENT_UPLOAD', 'AI_CONCEPT', 'VERIFICATION_EVIDENCE', 'PORTFOLIO', 'INVOICE'"
)
revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_value_categories",
        sa.Column("question_set_version", sa.Integer(), nullable=False),
        sa.Column("service_value", sa.String(length=40), nullable=False),
        sa.Column("category_code", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_code"],
            ["service_categories.code"],
            name=op.f("fk_service_value_categories_category_code_service_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_set_version"],
            ["requirement_question_sets.version"],
            name=op.f("fk_service_value_categories_question_set_version_requirement_question_sets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "question_set_version", "service_value", name=op.f("pk_service_value_categories")
        ),
    )
    op.create_table(
        "connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("category_code", sa.String(length=40), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("brief", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("family_contact", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("professional_contact", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sent_by", sa.Uuid(), nullable=False),
        sa.Column(
            "sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("respond_by", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.String(length=24), nullable=True),
        sa.Column("decline_note", sa.Text(), nullable=True),
        sa.Column("withdrawn_by_role", sa.String(length=12), nullable=True),
        sa.Column("withdraw_reason", sa.String(length=24), nullable=True),
        sa.Column("withdraw_note", sa.Text(), nullable=True),
        sa.Column("engagement_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "(state = 'DECLINED') = (decline_reason IS NOT NULL)",
            name=op.f("ck_connections_declined_has_reason"),
        ),
        sa.CheckConstraint(
            "(state = 'WITHDRAWN') = (withdraw_reason IS NOT NULL)",
            name=op.f("ck_connections_withdrawn_has_reason"),
        ),
        sa.CheckConstraint(
            "decline_reason IS DISTINCT FROM 'OTHER' OR length(trim(decline_note)) > 0",
            name=op.f("ck_connections_other_needs_note"),
        ),
        sa.CheckConstraint(
            "decline_reason IS NULL OR decline_reason IN ('UNAVAILABLE', 'OUTSIDE_SERVICE_AREA', 'SCOPE_MISMATCH', 'SCHEDULE_MISMATCH', 'COMPLIANCE', 'ALREADY_ENGAGED', 'OTHER')",
            name=op.f("ck_connections_decline_reason"),
        ),
        sa.CheckConstraint(
            "state IN ('SENT', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'WITHDRAWN')",
            name=op.f("ck_connections_state"),
        ),
        sa.CheckConstraint(
            "withdraw_reason IS NULL OR withdraw_reason IN ('FAMILY', 'ANOTHER_ENGAGED', 'PACKAGE_ENDED', 'PROFESSIONAL_UNAVAILABLE', 'PROJECT_CLOSED', 'OPERATIONS')",
            name=op.f("ck_connections_withdraw_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["category_code"],
            ["service_categories.code"],
            name=op.f("fk_connections_category_code_service_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["professional_profiles.id"],
            name=op.f("fk_connections_profile_id_professional_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_connections_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sent_by"],
            ["users.id"],
            name=op.f("fk_connections_sent_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connections")),
    )
    op.create_index(
        "ix_connections_open",
        "connections",
        ["respond_by"],
        unique=False,
        postgresql_where=sa.text("state = 'SENT'"),
    )
    op.create_index(
        "ix_connections_profile_id", "connections", ["profile_id", "sent_at"], unique=False
    )
    op.create_index(
        "ix_connections_project_id", "connections", ["project_id", "category_code"], unique=False
    )
    op.create_index(
        "uq_connections_one_open_per_professional",
        "connections",
        ["project_id", "category_code", "profile_id"],
        unique=True,
        postgresql_where=sa.text("state = 'SENT'"),
    )
    op.create_table(
        "engagement_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=12), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("category_code", sa.String(length=40), nullable=False),
        sa.Column("from_state", sa.String(length=12), nullable=True),
        sa.Column("to_state", sa.String(length=12), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_role", sa.String(length=12), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "subject IN ('CONNECTION', 'ENGAGEMENT')", name=op.f("ck_engagement_events_subject")
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_engagement_events_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_engagement_events_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_engagement_events")),
    )
    op.create_index(
        "ix_engagement_events_project_id", "engagement_events", ["project_id", "at"], unique=False
    )
    op.create_table(
        "project_service_needs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("category_code", sa.String(length=40), nullable=False),
        sa.Column("state", sa.String(length=12), nullable=False),
        sa.Column(
            "subtypes",
            postgresql.ARRAY(sa.String(length=40)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=12), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "source IN ('REQUIREMENT', 'FAMILY')", name=op.f("ck_project_service_needs_source")
        ),
        sa.CheckConstraint(
            "state IN ('UNDECIDED', 'NEEDED', 'NOT_NEEDED')",
            name=op.f("ck_project_service_needs_state"),
        ),
        sa.ForeignKeyConstraint(
            ["category_code"],
            ["service_categories.code"],
            name=op.f("fk_project_service_needs_category_code_service_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_service_needs_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_project_service_needs_updated_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_service_needs")),
        sa.UniqueConstraint(
            "project_id",
            "category_code",
            name=op.f("uq_project_service_needs_project_id_category_code"),
        ),
    )
    op.create_table(
        "quote_review_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("category_code", sa.String(length=40), nullable=False),
        sa.Column("quoted_by", sa.String(length=160), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("file_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("submitted_by", sa.Uuid(), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("state IN ('SUBMITTED')", name=op.f("ck_quote_review_requests_state")),
        sa.CheckConstraint(
            "cardinality(file_ids) BETWEEN 1 AND 5", name=op.f("ck_quote_review_requests_files")
        ),
        sa.ForeignKeyConstraint(
            ["category_code"],
            ["service_categories.code"],
            name=op.f("fk_quote_review_requests_category_code_service_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_quote_review_requests_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"],
            ["users.id"],
            name=op.f("fk_quote_review_requests_submitted_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quote_review_requests")),
    )
    op.create_index(
        "ix_quote_review_requests_project_id",
        "quote_review_requests",
        ["project_id", "submitted_at"],
        unique=False,
    )
    op.create_table(
        "project_engagements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("category_code", sa.String(length=40), nullable=False),
        sa.Column("party", sa.String(length=10), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=True),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("outside_name", sa.String(length=120), nullable=True),
        sa.Column("outside_firm", sa.String(length=160), nullable=True),
        sa.Column("outside_contact", sa.String(length=200), nullable=True),
        sa.Column("state", sa.String(length=8), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by_role", sa.String(length=12), nullable=True),
        sa.Column("end_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "(party = 'LISTED' AND profile_id IS NOT NULL AND connection_id IS NOT NULL AND outside_name IS NULL) OR (party = 'OUTSIDE' AND profile_id IS NULL AND connection_id IS NULL AND outside_name IS NOT NULL)",
            name=op.f("ck_project_engagements_party_fields"),
        ),
        sa.CheckConstraint(
            "(state = 'ENDED') = (ended_at IS NOT NULL)", name=op.f("ck_project_engagements_ended")
        ),
        sa.CheckConstraint(
            "party IN ('LISTED', 'OUTSIDE')", name=op.f("ck_project_engagements_party")
        ),
        sa.CheckConstraint(
            "state IN ('ACTIVE', 'ENDED')", name=op.f("ck_project_engagements_state")
        ),
        sa.ForeignKeyConstraint(
            ["category_code"],
            ["service_categories.code"],
            name=op.f("fk_project_engagements_category_code_service_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["connections.id"],
            name=op.f("fk_project_engagements_connection_id_connections"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_project_engagements_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["professional_profiles.id"],
            name=op.f("fk_project_engagements_profile_id_professional_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_engagements_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_engagements")),
        sa.UniqueConstraint("connection_id", name=op.f("uq_project_engagements_connection_id")),
    )
    op.create_index(
        "ix_project_engagements_profile_id", "project_engagements", ["profile_id"], unique=False
    )
    op.create_index(
        "uq_project_engagements_one_active",
        "project_engagements",
        ["project_id", "category_code"],
        unique=True,
        postgresql_where=sa.text("state = 'ACTIVE'"),
    )
    op.create_table(
        "engagement_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("engagement_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("shared_by", sa.Uuid(), nullable=False),
        sa.Column(
            "shared_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("unshared_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["project_engagements.id"],
            name=op.f("fk_engagement_documents_engagement_id_project_engagements"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["file_objects.id"],
            name=op.f("fk_engagement_documents_file_id_file_objects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shared_by"],
            ["users.id"],
            name=op.f("fk_engagement_documents_shared_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_engagement_documents")),
    )
    op.create_index(
        "uq_engagement_documents_one_active",
        "engagement_documents",
        ["engagement_id", "file_id"],
        unique=True,
        postgresql_where=sa.text("unshared_at IS NULL"),
    )
    op.create_foreign_key(
        op.f("fk_connections_engagement_id_project_engagements"),
        "connections",
        "project_engagements",
        ["engagement_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    mapping = sa.table(
        "service_value_categories",
        sa.column("question_set_version", sa.Integer),
        sa.column("service_value", sa.String),
        sa.column("category_code", sa.String),
    )
    op.bulk_insert(
        mapping,
        [
            {"question_set_version": 1, "service_value": value, "category_code": code}
            for value, code in SERVICE_VALUE_CATEGORIES_V1
        ],
    )
    op.execute("ALTER TABLE file_objects DROP CONSTRAINT ck_file_objects_purpose")
    op.execute(
        "ALTER TABLE file_objects ADD CONSTRAINT ck_file_objects_purpose CHECK (purpose IN "
        f"({PURPOSES_BEFORE}, 'QUOTE_DOCUMENT'))"
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
                GRANT SELECT ON service_value_categories TO app_rw;
                GRANT SELECT, INSERT, UPDATE ON project_service_needs, connections,
                    project_engagements, engagement_documents, quote_review_requests TO app_rw;
                GRANT SELECT, INSERT ON engagement_events TO app_rw;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Quote documents go with the feature; the access log is append-only, so its guard is
    # lifted for exactly this delete.
    op.execute("ALTER TABLE document_access_log DISABLE TRIGGER document_access_log_append_only")
    op.execute(
        "DELETE FROM document_access_log WHERE file_id IN (SELECT id FROM file_objects "
        "WHERE purpose = 'QUOTE_DOCUMENT')"
    )
    op.execute("ALTER TABLE document_access_log ENABLE TRIGGER document_access_log_append_only")
    op.drop_constraint(
        op.f("fk_connections_engagement_id_project_engagements"), "connections", type_="foreignkey"
    )
    op.drop_index(
        "uq_engagement_documents_one_active",
        table_name="engagement_documents",
        postgresql_where=sa.text("unshared_at IS NULL"),
    )
    op.drop_table("engagement_documents")
    op.drop_index(
        "uq_project_engagements_one_active",
        table_name="project_engagements",
        postgresql_where=sa.text("state = 'ACTIVE'"),
    )
    op.drop_index("ix_project_engagements_profile_id", table_name="project_engagements")
    op.drop_table("project_engagements")
    op.drop_index("ix_quote_review_requests_project_id", table_name="quote_review_requests")
    op.drop_table("quote_review_requests")
    op.drop_table("project_service_needs")
    op.drop_index("ix_engagement_events_project_id", table_name="engagement_events")
    op.drop_table("engagement_events")
    op.drop_index(
        "uq_connections_one_open_per_professional",
        table_name="connections",
        postgresql_where=sa.text("state = 'SENT'"),
    )
    op.drop_index("ix_connections_project_id", table_name="connections")
    op.drop_index("ix_connections_profile_id", table_name="connections")
    op.drop_index(
        "ix_connections_open", table_name="connections", postgresql_where=sa.text("state = 'SENT'")
    )
    op.drop_table("connections")
    op.drop_table("service_value_categories")
    op.execute("DELETE FROM file_objects WHERE purpose = 'QUOTE_DOCUMENT'")
    op.execute("ALTER TABLE file_objects DROP CONSTRAINT ck_file_objects_purpose")
    op.execute(
        "ALTER TABLE file_objects ADD CONSTRAINT ck_file_objects_purpose CHECK (purpose IN "
        f"({PURPOSES_BEFORE}))"
    )
