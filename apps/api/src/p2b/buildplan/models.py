"""Authoritative design and the Build Plan (Slice 3.5; SLICE3_5_READINESS section 0).

Drawings come only from professionals or the family, through design requests and drawing sets
that an appointed checker approves (BP-01 to BP-03); Plan2Build generates no drawing and no AI
image is ever an input. One Build Plan per project holds versions; a version's content is
editable only while DRAFT and is frozen by database triggers afterwards. Structural sign-offs
bind to the version's content hash; acceptance records the exact version and hash. The schedule
holds durations and explicit dependencies only: no date is calculated until BP-07A is decided."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base

NOW = text("now()")


def _fk(target: str, nullable: bool = False) -> Any:
    return mapped_column(ForeignKey(target, ondelete="RESTRICT"), nullable=nullable)


class CheckerAppointment(Base):
    """A qualified drawing checker Plan2Build appoints (BP-01); not necessarily an employee. A
    checker with a platform account may record checks; otherwise operations record them with the
    checker's signed note as evidence."""

    __tablename__ = "drawing_checker_appointments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    qualification: Mapped[str] = mapped_column(String(200))
    registration_reference: Mapped[str | None] = mapped_column(String(200))
    user_id: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    appointed_by: Mapped[uuid.UUID] = _fk("users.id")
    appointed_at: Mapped[datetime] = mapped_column(server_default=NOW)
    ended_at: Mapped[datetime | None]
    ended_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)


class SignoffStatement(Base):
    """The structural sign-off statement, configurable and versioned (BP-04). Version 1 is the
    baseline wording, pending final client and legal confirmation before production launch."""

    __tablename__ = "signoff_statements"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
        Index(
            "uq_signoff_statements_one_active",
            "status",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(Text)
    # Reference data (like the question sets): user ids without foreign keys, so the seed is not
    # tied to any account.
    created_by: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    activated_by: Mapped[uuid.UUID | None]
    activated_at: Mapped[datetime | None]


class AcceptanceStatement(Base):
    """The statement the owner confirms when accepting a Build Plan version (BP-05), versioned and
    configurable like the sign-off statement. Text is a template with $version_no, $project_code
    and $content_hash. Version 1 is functional wording: implemented, pending final client and
    legal confirmation; the launch wording replaces it as a new version without changing the
    acceptance model."""

    __tablename__ = "acceptance_statements"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
        Index(
            "uq_acceptance_statements_one_active",
            "status",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(Text)
    # Reference data: user ids without foreign keys, as for the sign-off statement.
    created_by: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    activated_by: Mapped[uuid.UUID | None]
    activated_at: Mapped[datetime | None]


class DesignRequest(Base):
    """A request for authoritative drawings for a project, naming who provides them."""

    __tablename__ = "design_requests"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('LISTED_PROFESSIONAL', 'OUTSIDE_PROFESSIONAL', 'HOMEOWNER_PROVIDED', "
            "'PLAN2BUILD_ARRANGED')",
            name="kind",
        ),
        CheckConstraint(
            "(kind IN ('LISTED_PROFESSIONAL', 'OUTSIDE_PROFESSIONAL')) = "
            "(engagement_id IS NOT NULL)",
            name="engagement_for_professionals",
        ),
        Index("ix_design_requests_project_id", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    kind: Mapped[str] = mapped_column(String(24))
    engagement_id: Mapped[uuid.UUID | None] = _fk("project_engagements.id", nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(160))
    provider_qualification: Mapped[str | None] = mapped_column(String(200))
    scope_note: Mapped[str] = mapped_column(Text)
    reference_design_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid), server_default=text("'{}'")
    )  # AI concepts named as illustrative references only; never files of a drawing set
    opened_by: Mapped[uuid.UUID] = _fk("users.id")
    opened_at: Mapped[datetime] = mapped_column(server_default=NOW)


class DrawingSet(Base):
    """One version of the drawings of a request. Files are frozen from SUBMITTED; an APPROVED
    set is authoritative and immutable; a later approved set supersedes it."""

    __tablename__ = "drawing_sets"
    __table_args__ = (
        UniqueConstraint("request_id", "set_no"),
        CheckConstraint(
            "state IN ('DRAFT', 'SUBMITTED', 'IN_CHECK', 'CHANGES_REQUESTED', 'APPROVED', "
            "'REJECTED', 'SUPERSEDED')",
            name="state",
        ),
        CheckConstraint(
            "state IN ('DRAFT') OR content_hash IS NOT NULL", name="submitted_has_hash"
        ),
        CheckConstraint(
            "state NOT IN ('APPROVED', 'SUPERSEDED') OR "
            "(checker_appointment_id IS NOT NULL AND checked_at IS NOT NULL)",
            name="approved_was_checked",
        ),
        Index(
            "uq_drawing_sets_one_open",
            "request_id",
            unique=True,
            postgresql_where=text("state IN ('DRAFT', 'SUBMITTED', 'IN_CHECK')"),
        ),
        Index("ix_drawing_sets_project_id", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    request_id: Mapped[uuid.UUID] = _fk("design_requests.id")
    set_no: Mapped[int] = mapped_column(SmallInteger)
    state: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[uuid.UUID] = _fk("users.id")
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    submitted_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    submitted_at: Mapped[datetime | None]
    family_decided_at: Mapped[datetime | None]
    family_note: Mapped[str | None] = mapped_column(Text)
    checker_appointment_id: Mapped[uuid.UUID | None] = _fk(
        "drawing_checker_appointments.id", nullable=True
    )
    checked_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    checked_at: Mapped[datetime | None]
    check_note: Mapped[str | None] = mapped_column(Text)
    check_evidence_file_id: Mapped[uuid.UUID | None] = _fk("file_objects.id", nullable=True)
    superseded_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class DrawingFile(Base):
    __tablename__ = "drawing_files"
    __table_args__ = (
        UniqueConstraint("set_id", "file_id"),
        CheckConstraint(
            "drawing_class IN ('SITE_PLAN', 'FLOOR_PLAN', 'ELEVATION', 'SECTION', 'STRUCTURAL', "
            "'OTHER')",
            name="drawing_class",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    set_id: Mapped[uuid.UUID] = _fk("drawing_sets.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    file_id: Mapped[uuid.UUID] = _fk("file_objects.id")
    drawing_class: Mapped[str] = mapped_column(String(12))
    floor: Mapped[int | None] = mapped_column(SmallInteger)
    title: Mapped[str] = mapped_column(String(200))
    sheet_no: Mapped[str | None] = mapped_column(String(40))
    sha256: Mapped[str | None] = mapped_column(String(64))  # copied when the set is submitted


class BuildPlan(Base):
    __tablename__ = "build_plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), unique=True
    )
    accepted_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("build_plan_versions.id", ondelete="RESTRICT", use_alter=True)
    )
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    version: Mapped[int] = mapped_column(server_default=text("1"))


class BuildPlanVersion(Base):
    """SLICE3_5_READINESS 0.2. Content columns change only while DRAFT (trigger)."""

    __tablename__ = "build_plan_versions"
    __table_args__ = (
        UniqueConstraint("build_plan_id", "version_no"),
        CheckConstraint(
            "state IN ('DRAFT', 'IN_REVIEW', 'ISSUED', 'ACCEPTED', 'CHANGES_REQUESTED', "
            "'SUPERSEDED', 'WITHDRAWN')",
            name="state",
        ),
        CheckConstraint(
            "state IN ('DRAFT', 'WITHDRAWN') OR content_hash IS NOT NULL", name="frozen_has_hash"
        ),
        CheckConstraint(
            "state NOT IN ('ISSUED', 'ACCEPTED', 'CHANGES_REQUESTED') OR "
            "(issued_at IS NOT NULL AND issued_document_id IS NOT NULL)",
            name="issued_has_document",
        ),
        CheckConstraint("issued_by IS NULL OR issued_by <> last_edited_by", name="four_eyes"),
        Index(
            "uq_build_plan_versions_one_open",
            "build_plan_id",
            unique=True,
            postgresql_where=text("state IN ('DRAFT', 'IN_REVIEW')"),
        ),
        Index(
            "uq_build_plan_versions_one_accepted",
            "build_plan_id",
            unique=True,
            postgresql_where=text("state = 'ACCEPTED'"),
        ),
        Index("ix_build_plan_versions_project_id", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    build_plan_id: Mapped[uuid.UUID] = _fk("build_plans.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    version_no: Mapped[int] = mapped_column(SmallInteger)
    state: Mapped[str] = mapped_column(String(20))
    created_from_id: Mapped[uuid.UUID | None] = _fk("build_plan_versions.id", nullable=True)
    requirement_version: Mapped[int] = mapped_column(Integer)
    drawing_set_id: Mapped[uuid.UUID | None] = _fk("drawing_sets.id", nullable=True)
    rate_card_id: Mapped[uuid.UUID | None] = _fk("item_rate_cards.id", nullable=True)
    inclusions: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    exclusions: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    assumptions: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    explanation_note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = _fk("users.id")
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    last_edited_by: Mapped[uuid.UUID] = _fk("users.id")
    last_edited_at: Mapped[datetime] = mapped_column(server_default=NOW)
    # Lifecycle columns (the only ones that change once the version leaves DRAFT).
    content_hash: Mapped[str | None] = mapped_column(String(64))
    submitted_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    submitted_at: Mapped[datetime | None]
    issued_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    issued_at: Mapped[datetime | None]
    issued_document_id: Mapped[uuid.UUID | None] = _fk("file_objects.id", nullable=True)
    accepted_at: Mapped[datetime | None]
    accepted_document_id: Mapped[uuid.UUID | None] = _fk("file_objects.id", nullable=True)
    closed_at: Mapped[datetime | None]  # superseded or withdrawn
    close_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(server_default=text("1"))


class BuildPlanSpecValue(Base):
    """A project value for one S04 line in one version (PD-14). Criteria text is copied from the
    master version; the master never receives a project value."""

    __tablename__ = "build_plan_spec_values"
    __table_args__ = (
        UniqueConstraint("version_id", "line_code"),
        CheckConstraint("applicability IN ('APPLICABLE', 'NOT_APPLICABLE')", name="applicability"),
        CheckConstraint(
            "basis IS NULL OR basis IN ('STRUCTURAL_DESIGN', 'ARCHITECT_DRAWING', "
            "'HOMEOWNER_PROVIDED', 'ADVISOR', 'STANDARD_REFERENCE')",
            name="basis",
        ),
        CheckConstraint(
            "applicability = 'APPLICABLE' OR length(trim(not_applicable_reason)) > 0",
            name="not_applicable_has_reason",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version_id: Mapped[uuid.UUID] = _fk("build_plan_versions.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    line_code: Mapped[str] = mapped_column(String(3))
    master_version_id: Mapped[uuid.UUID] = _fk("spec_line_master_versions.id")
    criteria_text: Mapped[str] = mapped_column(Text)
    is_structural: Mapped[bool]
    applicability: Mapped[str] = mapped_column(String(16))
    not_applicable_reason: Mapped[str | None] = mapped_column(Text)
    value_text: Mapped[str | None] = mapped_column(Text)
    basis: Mapped[str | None] = mapped_column(String(20))
    source_note: Mapped[str | None] = mapped_column(Text)
    evidence_file_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid), server_default=text("'{}'")
    )
    entered_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    entered_at: Mapped[datetime | None]
    carried_from_id: Mapped[uuid.UUID | None] = _fk("build_plan_spec_values.id", nullable=True)


class BoqLine(Base):
    """A BOQ line priced from the version's one item rate card (BP-06). No manual rates; amounts
    are computed by the server. Never AI quantities."""

    __tablename__ = "boq_lines"
    __table_args__ = (
        UniqueConstraint("version_id", "line_no"),
        CheckConstraint(
            "quantity_basis IN ('MEASURED_FROM_DRAWING', 'PROVIDED_BY_PROFESSIONAL', "
            "'ADVISOR_ESTIMATE')",
            name="quantity_basis",
        ),
        CheckConstraint(
            "quantity_basis <> 'MEASURED_FROM_DRAWING' OR drawing_file_id IS NOT NULL",
            name="measured_names_drawing",
        ),
        CheckConstraint(
            "quantity_basis <> 'ADVISOR_ESTIMATE' OR length(trim(basis_note)) > 0",
            name="estimate_has_reason",
        ),
        CheckConstraint("quantity > 0 AND rate >= 0", name="positive"),
        CheckConstraint("stage_number IS NULL OR stage_number BETWEEN 1 AND 16", name="stage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version_id: Mapped[uuid.UUID] = _fk("build_plan_versions.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    line_no: Mapped[int] = mapped_column(Integer)
    rate_card_id: Mapped[uuid.UUID] = _fk("item_rate_cards.id")
    item_code: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    quantity_basis: Mapped[str] = mapped_column(String(26))
    drawing_file_id: Mapped[uuid.UUID | None] = _fk("drawing_files.id", nullable=True)
    basis_note: Mapped[str | None] = mapped_column(Text)
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    stage_number: Mapped[int | None] = mapped_column(SmallInteger)
    floor: Mapped[int | None] = mapped_column(SmallInteger)
    spec_line_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String(3)), server_default=text("'{}'")
    )
    assumptions: Mapped[str | None] = mapped_column(Text)


class ScheduleEntry(Base):
    """One stage instance's duration and explicitly entered predecessors. Dates are not
    calculated: the canonical build order (BP-07A) is deferred, so the CHECK keeps them empty
    until a later migration lifts it with the date calculation."""

    __tablename__ = "build_plan_schedule_entries"
    __table_args__ = (
        UniqueConstraint("version_id", "entry_key"),
        CheckConstraint("duration_days IS NULL OR duration_days > 0", name="duration"),
        CheckConstraint(
            "planned_start IS NULL AND planned_end IS NULL", name="dates_not_calculated_bp07a"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version_id: Mapped[uuid.UUID] = _fk("build_plan_versions.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    entry_key: Mapped[str] = mapped_column(String(8))  # S05 or S05F1 (floor -1 is "F-1")
    stage_instance_id: Mapped[uuid.UUID] = _fk("stage_instances.id")
    stage_number: Mapped[int] = mapped_column(SmallInteger)
    floor: Mapped[int | None] = mapped_column(SmallInteger)
    duration_days: Mapped[int | None] = mapped_column(Integer)
    predecessors: Mapped[list[str]] = mapped_column(ARRAY(String(8)), server_default=text("'{}'"))
    note: Mapped[str | None] = mapped_column(Text)
    planned_start: Mapped[date | None]
    planned_end: Mapped[date | None]


class StructuralSignoff(Base):
    """A structural sign-off of one line of one version (BP-04): who, which credential, what
    content (the version's content hash and the set's structural drawing hashes), which
    statement, the evidence and when. SIGNED rows change only to VOID, and only before issue."""

    __tablename__ = "structural_signoffs"
    __table_args__ = (
        CheckConstraint("mode IN ('ONE_TIME_CODE', 'SIGNED_DOCUMENT')", name="mode"),
        CheckConstraint("signer_kind IN ('LISTED', 'OUTSIDE')", name="signer_kind"),
        CheckConstraint("state IN ('SIGNED', 'VOID')", name="state"),
        CheckConstraint(
            "(mode = 'ONE_TIME_CODE' AND challenge_id IS NOT NULL AND profile_id IS NOT NULL) OR "
            "(mode = 'SIGNED_DOCUMENT' AND evidence_file_id IS NOT NULL)",
            name="mode_evidence",
        ),
        CheckConstraint("(state = 'VOID') = (voided_at IS NOT NULL)", name="void"),
        Index(
            "uq_structural_signoffs_one_signed",
            "version_id",
            "line_code",
            unique=True,
            postgresql_where=text("state = 'SIGNED'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version_id: Mapped[uuid.UUID] = _fk("build_plan_versions.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    line_code: Mapped[str] = mapped_column(String(3))
    mode: Mapped[str] = mapped_column(String(16))
    signer_kind: Mapped[str] = mapped_column(String(8))
    profile_id: Mapped[uuid.UUID | None] = _fk("professional_profiles.id", nullable=True)
    category_code: Mapped[str] = _fk("service_categories.code")
    engineer_name: Mapped[str] = mapped_column(String(160))
    engineer_firm: Mapped[str | None] = mapped_column(String(160))
    registration_number: Mapped[str | None] = mapped_column(String(80))
    registration_issuer: Mapped[str | None] = mapped_column(String(160))
    credential_reference: Mapped[dict[str, Any]] = mapped_column(JSONB)
    credential_file_id: Mapped[uuid.UUID | None] = _fk("file_objects.id", nullable=True)
    statement_id: Mapped[uuid.UUID] = _fk("signoff_statements.id")
    statement_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    drawing_set_id: Mapped[uuid.UUID] = _fk("drawing_sets.id")
    drawing_hashes: Mapped[list[str]] = mapped_column(ARRAY(String(64)))
    line_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    challenge_id: Mapped[uuid.UUID | None] = _fk("otp_challenges.id", nullable=True)
    evidence_file_id: Mapped[uuid.UUID | None] = _fk("file_objects.id", nullable=True)
    recorded_by: Mapped[uuid.UUID] = _fk("users.id")
    signed_at: Mapped[datetime] = mapped_column(server_default=NOW)
    state: Mapped[str] = mapped_column(String(8))
    voided_at: Mapped[datetime | None]
    voided_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text)


class BuildPlanAcceptance(Base):
    """The owner's acceptance of one issued version (BP-05), confirmed by one-time code."""

    __tablename__ = "build_plan_acceptances"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("build_plan_versions.id", ondelete="RESTRICT"), unique=True
    )
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    version_no: Mapped[int] = mapped_column(SmallInteger)
    content_hash: Mapped[str] = mapped_column(String(64))
    issued_document_sha256: Mapped[str] = mapped_column(String(64))
    accepted_by: Mapped[uuid.UUID] = _fk("users.id")
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("otp_challenges.id", ondelete="RESTRICT"), unique=True
    )
    statement_id: Mapped[uuid.UUID] = _fk("acceptance_statements.id")
    statement_text: Mapped[str] = mapped_column(Text)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    accepted_at: Mapped[datetime] = mapped_column(server_default=NOW)


class BuildPlanEvent(Base):
    """History of design requests, drawing sets, versions and sign-offs. Append-only."""

    __tablename__ = "build_plan_events"
    __table_args__ = (
        CheckConstraint(
            "subject IN ('DESIGN_REQUEST', 'DRAWING_SET', 'VERSION', 'SIGNOFF')", name="subject"
        ),
        Index("ix_build_plan_events_project_id", "project_id", "at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    subject: Mapped[str] = mapped_column(String(16))
    subject_id: Mapped[uuid.UUID]
    from_state: Mapped[str | None] = mapped_column(String(30))
    to_state: Mapped[str] = mapped_column(String(30))
    actor_user_id: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    actor_role: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(server_default=NOW)


APPEND_ONLY = ("build_plan_events", "build_plan_acceptances")
VERSION_LIFECYCLE = (
    "state", "content_hash", "submitted_by", "submitted_at", "issued_by", "issued_at",
    "issued_document_id", "accepted_at", "accepted_document_id", "closed_at", "close_reason",
    "version",
)  # fmt: skip
