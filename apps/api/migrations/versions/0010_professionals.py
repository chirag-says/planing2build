"""Slice 3.2: professional registration, verification, listing and the public directory.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-05

Seeds (SLICE3_2_READINESS K0, confirmed by Chirag on 2026-10-05):
- `service_categories`: the seven POC categories (D-06) and the specialist subtypes the sources
  name (S01 §3, S23b, S24), configurable.
- `listing_requirement_versions` v1: the initial POC checklist per category (D-02), with a
  12-month re-verification target and a 6-month reapply wait; data, not code, and not
  permanent legal rules.
No membership, tier or class (PD-18; D-05 open).
"""

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql as pg

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = [
    ("CONTRACTOR", None, "Contractor", 10),
    ("ARCHITECT", None, "Architect", 20),
    ("STRUCTURAL_ENGINEER", None, "Structural engineer", 30),
    ("SITE_CIVIL_ENGINEER", None, "Site/civil engineer", 40),
    ("MEP", None, "MEP (electrical, plumbing, HVAC)", 50),
    ("INTERIOR_DESIGNER", None, "Interior designer", 60),
    ("SPECIALIST", None, "Specialist", 70),
    ("WATERPROOFING", "SPECIALIST", "Waterproofing", 71),
    ("SOLAR", "SPECIALIST", "Solar", 72),
    ("LANDSCAPING", "SPECIALIST", "Landscaping", 73),
    ("FABRICATION", "SPECIALIST", "Fabrication", 74),
    ("PAINTING", "SPECIALIST", "Painting", 75),
]


def req(id_: str, label: str, accepts: list[str], level: str = "REQUIRED", count: int = 1) -> dict:
    return {"id": id_, "label": label, "accepts": accepts, "level": level, "count": count}


IDENTITY = req("identity", "Identity", ["IDENTITY"])
WORK = req("work_evidence", "Portfolio and/or references", ["PORTFOLIO", "REFERENCE"])
REGISTRATION = req("registration", "Applicable professional registration or credential",
                   ["REGISTRATION"])  # fmt: skip
REQUIREMENTS = {
    "CONTRACTOR": [
        IDENTITY,
        req("business", "Business details, with GST where applicable", ["BUSINESS"]),
        req("portfolio", "Portfolio", ["PORTFOLIO"]),
        req("references", "Two references", ["REFERENCE"], count=2),
        req("site_visit", "Site verification", ["SITE_VISIT"]),
    ],
    "ARCHITECT": [IDENTITY, REGISTRATION, req("portfolio", "Portfolio", ["PORTFOLIO"])],
    "STRUCTURAL_ENGINEER": [IDENTITY, REGISTRATION, WORK],
    "SITE_CIVIL_ENGINEER": [IDENTITY, REGISTRATION, WORK],
    "MEP": [
        IDENTITY,
        req(
            "qualification",
            "Relevant qualification or licence, where applicable",
            ["REGISTRATION"],
            "WHERE_APPLICABLE",
        ),
        WORK,
    ],
    "INTERIOR_DESIGNER": [
        IDENTITY,
        req("portfolio", "Portfolio", ["PORTFOLIO"]),
        req("reference", "Reference", ["REFERENCE"]),
    ],
    "SPECIALIST": [
        IDENTITY,
        req("portfolio", "Portfolio", ["PORTFOLIO"]),
        req(
            "licence",
            "Relevant licence or credential, where applicable",
            ["REGISTRATION"],
            "WHERE_APPLICABLE",
        ),
        req("reference", "Reference, where appropriate", ["REFERENCE"], "WHERE_APPLICABLE"),
    ],
}
STATES = "'DRAFT', 'PENDING_REVIEW', 'CHANGES_REQUESTED', 'LISTED', 'REJECTED', 'SUSPENDED'"
KINDS = "'IDENTITY', 'BUSINESS', 'REGISTRATION', 'PORTFOLIO', 'REFERENCE', 'SITE_VISIT'"


def _stamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    ]  # fmt: skip


def _fk(column: str, target: str, nullable: bool = False) -> sa.Column[object]:
    return sa.Column(column, sa.Uuid(), sa.ForeignKey(target, ondelete="RESTRICT"),
                     nullable=nullable)  # fmt: skip


def upgrade() -> None:
    op.execute("ALTER TABLE file_objects DROP CONSTRAINT ck_file_objects_purpose")
    op.execute(
        "ALTER TABLE file_objects ADD CONSTRAINT ck_file_objects_purpose CHECK (purpose IN "
        "('REQUIREMENT_UPLOAD', 'AI_CONCEPT', 'VERIFICATION_EVIDENCE', 'PORTFOLIO'))"
    )
    op.execute("ALTER TABLE ops_queue_items DROP CONSTRAINT ck_ops_queue_items_kind")
    op.execute(
        "ALTER TABLE ops_queue_items ADD CONSTRAINT ck_ops_queue_items_kind "
        "CHECK (kind IN ('REQUIREMENT_REVIEW', 'PROFESSIONAL_REVIEW'))"
    )

    categories = op.create_table(
        "service_categories",
        sa.Column("code", sa.String(40), primary_key=True),
        sa.Column("parent_code", sa.String(40),
                  sa.ForeignKey("service_categories.code", ondelete="RESTRICT")),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("sequence", sa.SmallInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )  # fmt: skip
    op.bulk_insert(categories, [
        {"code": c, "parent_code": p, "name": n, "sequence": s, "active": True}
        for c, p, n, s in CATEGORIES
    ])  # fmt: skip

    versions = op.create_table(
        "listing_requirement_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("category_code", sa.String(40),
                  sa.ForeignKey("service_categories.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("requirements", pg.JSONB(), nullable=False),
        sa.Column("validity_months", sa.SmallInteger(), nullable=False),
        sa.Column("reapply_months", sa.SmallInteger(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        *_stamps(),
        sa.UniqueConstraint("category_code", "version"),
        sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
        sa.CheckConstraint("validity_months > 0 AND reapply_months >= 0", name="periods"),
    )  # fmt: skip
    op.create_index("uq_listing_requirement_versions_one_active", "listing_requirement_versions",
                    ["category_code"], unique=True, postgresql_where=sa.text("status = 'ACTIVE'"))  # fmt: skip
    op.bulk_insert(versions, [
        {"id": uuid.uuid4(), "category_code": code, "version": 1, "status": "ACTIVE",
         "requirements": json.loads(json.dumps(items)), "validity_months": 12, "reapply_months": 6,
         "note": "Initial POC checklist (D-02, Chirag 2026-10-05); not a permanent legal rule."}
        for code, items in REQUIREMENTS.items()
    ])  # fmt: skip

    op.create_table(
        "professional_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False, unique=True),
        sa.Column("display_name", sa.String(120)),
        sa.Column("firm_name", sa.String(160)),
        sa.Column("bio", sa.Text()),
        sa.Column("years_experience", sa.SmallInteger()),
        sa.Column("team_size", sa.Integer()),
        sa.Column("base_locality", sa.String(120)),
        sa.Column("base_geom", Geography(geometry_type="POINT", srid=4326, spatial_index=False)),
        sa.Column("service_radius_km", sa.SmallInteger()),
        _fk("created_by", "users.id", nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *_stamps(),
        sa.CheckConstraint("service_radius_km IS NULL OR service_radius_km BETWEEN 1 AND 300",
                           name="radius"),
        sa.CheckConstraint("years_experience IS NULL OR years_experience BETWEEN 0 AND 80",
                           name="experience"),
        sa.CheckConstraint("team_size IS NULL OR team_size BETWEEN 1 AND 10000", name="team_size"),
    )  # fmt: skip
    op.create_index("ix_professional_profiles_base_geom", "professional_profiles", ["base_geom"],
                    postgresql_using="gist")  # fmt: skip

    op.create_table(
        "professional_categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("profile_id", "professional_profiles.id"),
        sa.Column("category_code", sa.String(40),
                  sa.ForeignKey("service_categories.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("subtypes", pg.ARRAY(sa.String(40)), server_default="{}", nullable=False),
        sa.Column("listing_state", sa.String(20), nullable=False),
        sa.Column("hidden", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _fk("requirement_version_id", "listing_requirement_versions.id", nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("listed_at", sa.DateTime(timezone=True)),
        sa.Column("review_due_at", sa.DateTime(timezone=True)),
        sa.Column("reapply_after", sa.DateTime(timezone=True)),
        sa.Column("message", sa.Text()),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *_stamps(),
        sa.UniqueConstraint("profile_id", "category_code"),
        sa.CheckConstraint(f"listing_state IN ({STATES})", name="listing_state"),
    )  # fmt: skip
    op.create_index("ix_professional_categories_listed", "professional_categories",
                    ["category_code"],
                    postgresql_where=sa.text("listing_state = 'LISTED' AND NOT hidden"))  # fmt: skip

    op.create_table(
        "verification_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("professional_category_id", "professional_categories.id"),
        _fk("requirement_version_id", "listing_requirement_versions.id"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("decision", sa.String(20)),
        _fk("decided_by", "users.id", nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("message_to_professional", sa.Text()),
        sa.Column("internal_note", sa.Text()),
        sa.CheckConstraint(
            "decision IS NULL OR decision IN ('APPROVED', 'CHANGES_REQUESTED', 'REJECTED')",
            name="decision"),
        sa.CheckConstraint("(decision IS NULL) = (decided_at IS NULL)", name="decided_together"),
    )  # fmt: skip
    op.create_index("uq_verification_cases_one_open", "verification_cases",
                    ["professional_category_id"], unique=True,
                    postgresql_where=sa.text("decided_at IS NULL"))  # fmt: skip

    op.create_table(
        "verification_checks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("case_id", "verification_cases.id"),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("detail", pg.JSONB(), server_default="{}", nullable=False),
        sa.Column("internal_note", sa.Text()),
        _fk("recorded_by", "users.id"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.CheckConstraint(f"kind IN ({KINDS})", name="kind"),
        sa.CheckConstraint("outcome IN ('PASSED', 'FAILED', 'NOT_APPLICABLE')", name="outcome"),
    )  # fmt: skip
    op.create_index("ix_verification_checks_case_id", "verification_checks", ["case_id"])

    op.create_table(
        "professional_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("profile_id", "professional_profiles.id"),
        sa.Column("category_code", sa.String(40),
                  sa.ForeignKey("service_categories.code", ondelete="RESTRICT")),
        sa.Column("kind", sa.String(20), nullable=False),
        _fk("file_id", "file_objects.id"),
        sa.Column("details", pg.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("kind IN ('IDENTITY', 'BUSINESS', 'REGISTRATION')", name="kind"),
    )  # fmt: skip
    op.create_index(
        "ix_professional_documents_profile_id", "professional_documents", ["profile_id"]
    )

    op.create_table(
        "professional_references",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("profile_id", "professional_profiles.id"),
        sa.Column("category_code", sa.String(40),
                  sa.ForeignKey("service_categories.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("project_note", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
    )  # fmt: skip
    op.create_index("ix_professional_references_profile_id", "professional_references",
                    ["profile_id"])  # fmt: skip

    op.create_table(
        "portfolio_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("profile_id", "professional_profiles.id"),
        _fk("file_id", "file_objects.id"),
        sa.Column("caption", sa.String(200), nullable=False),
        sa.Column("review_state", sa.String(10), server_default="PENDING", nullable=False),
        _fk("reviewed_by", "users.id", nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("review_state IN ('PENDING', 'APPROVED', 'REJECTED')",
                           name="review_state"),
    )  # fmt: skip
    op.create_index("ix_portfolio_items_profile_id", "portfolio_items", ["profile_id"])

    op.create_table(
        "professional_listing_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("professional_category_id", "professional_categories.id"),
        sa.Column("event", sa.String(30), nullable=False),
        sa.Column("from_state", sa.String(20)),
        sa.Column("to_state", sa.String(20), nullable=False),
        _fk("actor_user_id", "users.id", nullable=True),
        sa.Column("actor_role", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )  # fmt: skip
    op.create_index("ix_professional_listing_history_category", "professional_listing_history",
                    ["professional_category_id", "at"])  # fmt: skip

    for table in ("verification_checks", "professional_listing_history"):
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION p2b_forbid_mutation()"
        )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT SELECT ON service_categories, listing_requirement_versions TO app_rw;
                GRANT SELECT, INSERT, UPDATE ON professional_profiles, professional_categories,
                    verification_cases, professional_documents, professional_references,
                    portfolio_items TO app_rw;
                GRANT SELECT, INSERT ON verification_checks, professional_listing_history TO app_rw;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    for table in (
        "professional_listing_history", "portfolio_items", "professional_references",
        "professional_documents", "verification_checks", "verification_cases",
        "professional_categories", "professional_profiles", "listing_requirement_versions",
        "service_categories",
    ):  # fmt: skip
        op.drop_table(table)
    op.execute("DELETE FROM ops_queue_items WHERE kind = 'PROFESSIONAL_REVIEW'")
    op.execute("ALTER TABLE ops_queue_items DROP CONSTRAINT ck_ops_queue_items_kind")
    op.execute(
        "ALTER TABLE ops_queue_items ADD CONSTRAINT ck_ops_queue_items_kind "
        "CHECK (kind IN ('REQUIREMENT_REVIEW'))"
    )
    # Professional files go with the feature; the access log is append-only, so its guard is
    # lifted for exactly this delete.
    op.execute("ALTER TABLE document_access_log DISABLE TRIGGER document_access_log_append_only")
    op.execute(
        "DELETE FROM document_access_log WHERE file_id IN (SELECT id FROM file_objects "
        "WHERE purpose IN ('VERIFICATION_EVIDENCE', 'PORTFOLIO'))"
    )
    op.execute("ALTER TABLE document_access_log ENABLE TRIGGER document_access_log_append_only")
    op.execute("DELETE FROM file_objects WHERE purpose IN ('VERIFICATION_EVIDENCE', 'PORTFOLIO')")
    op.execute("ALTER TABLE file_objects DROP CONSTRAINT ck_file_objects_purpose")
    op.execute(
        "ALTER TABLE file_objects ADD CONSTRAINT ck_file_objects_purpose "
        "CHECK (purpose IN ('REQUIREMENT_UPLOAD', 'AI_CONCEPT'))"
    )
