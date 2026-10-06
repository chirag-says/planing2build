"""Handover 1 data: cities, versioned stage masters, the locked requirement question set,
projects and requirements, memberships, status history, enquiries, geocode cache, idempotency
keys, file objects and the document access log.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-04

Seeds (data migration, DATA_ARCHITECTURE section 12):
- City Raipur, the POC market (CD-07; Chirag 2026-10-04: pan-India in phase 2).
- Stage master version 1: the 16 stages with names, audit gates, payment milestones and
  repeats-per-floor from S04 section 4 (as tabled in IHB_FLOW 8.9). Default durations and cost
  shares are NULL: none are approved, and none are invented (Chirag, 2026-10-04).
- Requirement question set version 1 from migrations/data/requirement_questions_v1.json, which
  equals REQUIREMENT_QUESTIONS_V1.md section L (locked 2026-10-04). The file is frozen; a change
  is a new version and a new migration.
"""

import json
import uuid
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql as pg

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QUESTIONS_V1 = Path(__file__).resolve().parents[1] / "data" / "requirement_questions_v1.json"

PROJECT_STATUSES = (
    "'DRAFT', 'SUBMITTED', 'NEEDS_INFO', 'ACCEPTED', 'PLANNING', 'PLAN_ISSUED', 'SOURCING', "
    "'CONTRACTED', 'BUILDING', 'HANDOVER_PENDING', 'COMPLETED', 'ARCHIVED', 'ON_HOLD', 'CANCELLED'"
)
ROLES = "'OWNER', 'HOUSEHOLD', 'CONTRACTOR', 'ARCHITECT', 'OPS_ADVISOR', 'OPS_FIELD', 'AUDITOR_ASSIGNED'"
FILE_STATES = (
    "'PENDING_UPLOAD', 'UPLOADED', 'SCANNING', 'AVAILABLE', 'QUARANTINED', 'FAILED', 'DELETED'"
)

# number, name, audit gate, payment milestone, repeats per floor (S04 section 4; IHB_FLOW 8.9)
STAGES = [
    (1, "Pre-construction, drawings and approvals", False, True, False),
    (2, "Site preparation and excavation", False, False, False),
    (3, "Foundation and footings", True, True, False),
    (4, "Plinth and backfilling", True, True, False),
    (5, "Superstructure: columns and beams", False, False, True),
    (6, "Slab casting", True, True, True),
    (7, "Blockwork and brickwork", False, True, False),
    (8, "Roof, parapet and staircase", False, False, False),
    (9, "First-fix electrical and plumbing conduiting", True, False, True),
    (10, "Waterproofing", True, True, False),
    (11, "Internal and external plastering", False, True, False),
    (12, "Doors, windows and fabrication", False, False, False),
    (13, "Flooring and tiling", False, True, False),
    (14, "Second-fix electrical, plumbing and sanitary", False, True, False),
    (15, "Painting and finishes", False, False, False),
    (16, "External works, snagging and handover", True, True, False),
]

APPEND_ONLY = ("project_status_history", "document_access_log")


def _ts() -> list[sa.Column[sa.DateTime]]:
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
        "cities",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("state", sa.String(80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_ts(),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "stage_master_versions",
        sa.Column("version", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("source_note", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.Uuid()),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        *_ts(),
        sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
    )
    op.create_index(
        "uq_stage_master_versions_one_active",
        "stage_master_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "stage_masters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "version",
            sa.Integer(),
            sa.ForeignKey("stage_master_versions.version", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("number", sa.SmallInteger(), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("sequence", sa.SmallInteger(), nullable=False),
        sa.Column("is_audit_gate", sa.Boolean(), nullable=False),
        sa.Column("is_payment_milestone", sa.Boolean(), nullable=False),
        sa.Column("repeats_per_floor", sa.Boolean(), nullable=False),
        sa.Column("default_duration_days", sa.Integer()),
        sa.Column("cost_share_pct", sa.Numeric(5, 2)),
        sa.UniqueConstraint("version", "number"),
        sa.UniqueConstraint("version", "code"),
        sa.CheckConstraint("number BETWEEN 1 AND 16", name="number"),
        sa.CheckConstraint(
            "default_duration_days IS NULL OR default_duration_days > 0", name="duration_positive"
        ),
        sa.CheckConstraint(
            "cost_share_pct IS NULL OR (cost_share_pct >= 0 AND cost_share_pct <= 100)",
            name="cost_share_range",
        ),
    )

    op.create_table(
        "requirement_question_sets",
        sa.Column("version", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("definition", pg.JSONB(), nullable=False),
        sa.Column("source_document", sa.String(200), nullable=False),
        sa.Column("approved_note", sa.Text(), nullable=False),
        *_ts(),
        sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
    )
    op.create_index(
        "uq_requirement_question_sets_one_active",
        "requirement_question_sets",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    op.execute("CREATE SEQUENCE project_code_seq START 1")
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("project_type", sa.String(20), nullable=False),
        sa.Column(
            "city_code",
            sa.String(10),
            sa.ForeignKey("cities.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("locality", sa.String(120)),
        sa.Column("plot_geom", Geography(geometry_type="POINT", srid=4326, spatial_index=False)),
        sa.Column("plot_area_sqft", sa.Numeric(12, 2)),
        sa.Column("built_up_area_sqft", sa.Integer()),
        sa.Column("floors", sa.SmallInteger()),
        sa.Column("has_basement", sa.Boolean()),
        sa.Column("quality_tier", sa.String(20)),
        sa.Column("budget_band", sa.String(20)),
        sa.Column("start_window", sa.String(20)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("code"),
        sa.CheckConstraint(f"status IN ({PROJECT_STATUSES})", name="status"),
        sa.CheckConstraint("project_type IN ('NEW_HOME')", name="project_type"),
    )
    op.create_index("ix_projects_owner_user_id", "projects", ["owner_user_id"])
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_plot_geom", "projects", ["plot_geom"], postgresql_using="gist")

    op.create_table(
        "project_requirements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "question_set_version",
            sa.Integer(),
            sa.ForeignKey("requirement_question_sets.version", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("answers", pg.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "review_flags",
            pg.ARRAY(sa.String(40)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("project_id"),
    )

    op.create_table(
        "project_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("granted_by", sa.Uuid()),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("project_id", "user_id", "role"),
        sa.CheckConstraint(f"role IN ({ROLES})", name="role"),
    )
    op.create_index(
        "ix_project_memberships_active_user",
        "project_memberships",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "project_status_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(20)),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("actor_user_id", sa.Uuid()),
        sa.Column("reason", sa.Text()),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.create_index(
        "ix_project_status_history_project_at", "project_status_history", ["project_id", "at"]
    )

    op.create_table(
        "enquiries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("work_type", sa.String(20)),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("ip_hash", sa.String(64)),
        sa.Column("converted_user_id", sa.Uuid()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind IN ('COMING_SOON_HELP', 'OTHER_CITY')", name="kind"),
        sa.CheckConstraint(
            "work_type IS NULL OR work_type IN ('RENOVATION', 'INTERIORS', 'REPAIRS')",
            name="work_type",
        ),
        sa.CheckConstraint(
            "(kind = 'COMING_SOON_HELP') = (work_type IS NOT NULL)", name="work_type_for_help"
        ),
    )
    op.create_index("ix_enquiries_created_at", "enquiries", ["created_at"])

    op.create_table(
        "geocode_cache",
        sa.Column("query_normalised", sa.String(80), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("locality", sa.String(200)),
        sa.Column("city", sa.String(200)),
        sa.Column("result", pg.JSONB(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("session_id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer()),
        sa.Column("response_body", pg.JSONB()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "file_objects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bucket", sa.String(100), nullable=False),
        sa.Column("object_key", sa.String(300), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="RESTRICT")),
        sa.Column("original_name", sa.String(200), nullable=False),
        sa.Column("declared_mime", sa.String(100), nullable=False),
        sa.Column("detected_mime", sa.String(100)),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64)),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("rejection_reason", sa.String(60)),
        sa.Column("available_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("object_key"),
        sa.CheckConstraint(f"state IN ({FILE_STATES})", name="state"),
        sa.CheckConstraint("purpose IN ('REQUIREMENT_UPLOAD')", name="purpose"),
        sa.CheckConstraint("size_bytes > 0", name="size_positive"),
    )
    op.create_index("ix_file_objects_project_id", "file_objects", ["project_id"])
    op.create_index(
        "ix_file_objects_open_states",
        "file_objects",
        ["state"],
        postgresql_where=sa.text("state IN ('PENDING_UPLOAD', 'UPLOADED', 'SCANNING')"),
    )

    op.create_table(
        "document_access_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "file_id",
            sa.Uuid(),
            sa.ForeignKey("file_objects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("viewer_user_id", sa.Uuid()),
        sa.Column("ip_hash", sa.String(64)),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.create_index("ix_document_access_log_file_at", "document_access_log", ["file_id", "at"])

    for table in APPEND_ONLY:
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION p2b_forbid_mutation()"
        )

    # Seeds.
    op.bulk_insert(
        sa.table(
            "cities",
            sa.column("code"),
            sa.column("name"),
            sa.column("state"),
            sa.column("is_active"),
        ),
        [{"code": "RPR", "name": "Raipur", "state": "Chhattisgarh", "is_active": True}],
    )
    op.execute(
        "INSERT INTO stage_master_versions (version, status, source_note, activated_at) VALUES "
        "(1, 'ACTIVE', 'Names, audit gates, payment milestones and repeats per floor from S04 "
        "section 4 (IHB_FLOW 8.9). Default durations and cost shares not approved: left empty "
        "(Chirag, 2026-10-04).', now())"
    )
    op.bulk_insert(
        sa.table(
            "stage_masters",
            sa.column("id", sa.Uuid()),
            sa.column("version"),
            sa.column("number"),
            sa.column("code"),
            sa.column("name"),
            sa.column("sequence"),
            sa.column("is_audit_gate"),
            sa.column("is_payment_milestone"),
            sa.column("repeats_per_floor"),
        ),
        [
            {
                "id": uuid.uuid4(),
                "version": 1,
                "number": n,
                "code": f"STAGE_{n:02d}",
                "name": name,
                "sequence": n,
                "is_audit_gate": gate,
                "is_payment_milestone": milestone,
                "repeats_per_floor": repeats,
            }
            for n, name, gate, milestone, repeats in STAGES
        ],
    )
    definition = json.loads(QUESTIONS_V1.read_text(encoding="utf-8"))
    op.bulk_insert(
        sa.table(
            "requirement_question_sets",
            sa.column("version"),
            sa.column("status"),
            sa.column("locale"),
            sa.column("definition", pg.JSONB()),
            sa.column("source_document"),
            sa.column("approved_note"),
        ),
        [
            {
                "version": 1,
                "status": "ACTIVE",
                "locale": "en",
                "definition": definition,
                "source_document": "SYSTEM_BLUEPRINT/02_IMPLEMENTATION/REQUIREMENT_QUESTIONS_V1.md section L",
                "approved_note": "Locked 2026-10-04 by Chirag's final rulings R-1 to R-15; delegated "
                "and default items listed in section L.4.",
            }
        ],
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT SELECT ON cities, stage_master_versions, stage_masters,
                    requirement_question_sets TO app_rw;
                GRANT SELECT, INSERT, UPDATE ON projects, project_requirements,
                    project_memberships, file_objects, geocode_cache, idempotency_keys TO app_rw;
                GRANT SELECT, INSERT ON project_status_history, enquiries, document_access_log
                    TO app_rw;
                GRANT USAGE ON SEQUENCE project_code_seq TO app_rw;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    for table in (
        "document_access_log",
        "file_objects",
        "idempotency_keys",
        "geocode_cache",
        "enquiries",
        "project_status_history",
        "project_memberships",
        "project_requirements",
        "projects",
        "requirement_question_sets",
        "stage_masters",
        "stage_master_versions",
        "cities",
    ):
        op.drop_table(table)
    op.execute("DROP SEQUENCE project_code_seq")
