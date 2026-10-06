"""Assurance tables (Slice 3.7B; SLICE3_7_READINESS F, G, K, P.B, P.C, Q).

Auditor appointments (EX-09), versioned gate checklists (EX-08), one inspection per gate stage
instance (EX-07) frozen at submission with a content hash, checkpoint results written only while
the inspection is in progress, non-conformances with severity that close only through an
approved re-inspection (EX-11), immutable reports with corrections as new versions (EX-14), later
test results, and an append-only history."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base, Timestamps

INSPECTION_STATES = "'SCHEDULED', 'IN_PROGRESS', 'SUBMITTED', 'APPROVED', 'RETURNED', 'CANCELLED'"
RESULTS = "'PASS', 'OBSERVATION', 'NON_CONFORMANCE', 'NOT_APPLICABLE'"
SEVERITIES = "'MINOR', 'MAJOR', 'CRITICAL'"
NC_STATES = "'OPEN', 'RECTIFICATION_SUBMITTED', 'REINSPECTION_SCHEDULED', 'CLOSED'"


class AuditorAppointment(Timestamps, Base):
    """An appointed independent auditor (EX-09). Ended, never deleted. `auditor_code` is the
    unique identifier shown on reports; `user_id` links an optional professionals-host account."""

    __tablename__ = "auditor_appointments"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'ENDED')", name="status"),
        CheckConstraint(
            "(status = 'ENDED') = (ended_at IS NOT NULL AND end_reason IS NOT NULL)", name="ended"
        ),
        UniqueConstraint("auditor_code"),
        Index("uq_auditor_appointments_active_user", "user_id", unique=True,
              postgresql_where=text("status = 'ACTIVE' AND user_id IS NOT NULL")),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    auditor_code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    qualification: Mapped[str] = mapped_column(String(300))
    registration_reference: Mapped[str | None] = mapped_column(String(120))
    credential_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("file_objects.id", ondelete="RESTRICT")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(10))
    appointed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    ended_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    ended_at: Mapped[datetime | None]
    end_reason: Mapped[str | None] = mapped_column(Text)


class ChecklistVersion(Timestamps, Base):
    """A versioned set of gate checkpoints (EX-08). One PUBLISHED at a time; PUBLISHED and RETIRED
    versions never change; their checkpoints change only while DRAFT (trigger)."""

    __tablename__ = "checklist_versions"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'PUBLISHED', 'RETIRED')", name="status"),
        UniqueConstraint("version"),
        Index("uq_checklist_versions_one_published", "status", unique=True,
              postgresql_where=text("status = 'PUBLISHED'")),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(Text)
    # Plain ids, no foreign key: reference data outlives any account (the audit log names who).
    prepared_by: Mapped[uuid.UUID | None]
    published_by: Mapped[uuid.UUID | None]
    published_at: Mapped[datetime | None]


class Checkpoint(Base):
    """One checkpoint of a gate in a checklist version (DATA `checkpoint_masters`)."""

    __tablename__ = "checkpoints"
    __table_args__ = (
        CheckConstraint("gate BETWEEN 1 AND 6", name="gate"),
        UniqueConstraint("checklist_version_id", "code"),
        UniqueConstraint("checklist_version_id", "gate", "sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    checklist_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checklist_versions.id", ondelete="RESTRICT")
    )
    gate: Mapped[int] = mapped_column(SmallInteger)
    sequence: Mapped[int] = mapped_column(SmallInteger)
    code: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    expected_evidence: Mapped[str | None] = mapped_column(String(200))
    is_critical: Mapped[bool] = mapped_column(Boolean, server_default=false())
    spec_line_code: Mapped[str | None] = mapped_column(String(3))


class Inspection(Timestamps, Base):
    """One visit to a gate stage instance (EX-07). Content is frozen from SUBMITTED and hashed;
    an INITIAL inspection returned for amendment is replaced by a new one that names it; a
    re-inspection names the inspection whose findings it re-checks."""

    __tablename__ = "inspections"
    __table_args__ = (
        CheckConstraint(f"state IN ({INSPECTION_STATES})", name="state"),
        CheckConstraint("kind IN ('INITIAL', 'REINSPECTION')", name="kind"),
        CheckConstraint("gate BETWEEN 1 AND 6", name="gate"),
        CheckConstraint("(kind = 'REINSPECTION') = (cardinality(nc_ids) > 0)",
                        name="reinspection_set"),
        CheckConstraint(
            "state NOT IN ('SUBMITTED', 'APPROVED', 'RETURNED') OR "
            "(content_sha256 IS NOT NULL AND submitted_at IS NOT NULL)",
            name="submitted_is_hashed",
        ),
        CheckConstraint("state <> 'RETURNED' OR return_reason IS NOT NULL", name="returned_reason"),
        CheckConstraint("state <> 'CANCELLED' OR cancel_reason IS NOT NULL",
                        name="cancelled_reason"),
        CheckConstraint(
            "cancel_reason IS NULL OR cancel_reason IN ('OPERATIONS', 'PACKAGE_ENDED', "
            "'PROJECT_CLOSED')",
            name="cancel_reason_values",
        ),
        CheckConstraint("NOT staff_capture OR capture_evidence_file_id IS NOT NULL",
                        name="capture_has_evidence"),
        # EX-07: one live initial inspection per gate stage instance.
        Index("uq_inspections_one_initial", "stage_instance_id", unique=True,
              postgresql_where=text("kind = 'INITIAL' AND state NOT IN ('RETURNED', 'CANCELLED')")),
        Index("ix_inspections_project", "project_id", "created_at"),
        Index("ix_inspections_appointment_state", "appointment_id", "state"),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_instances.id", ondelete="RESTRICT")
    )
    gate: Mapped[int] = mapped_column(SmallInteger)
    kind: Mapped[str] = mapped_column(String(15))
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("auditor_appointments.id", ondelete="RESTRICT")
    )
    checklist_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checklist_versions.id", ondelete="RESTRICT")
    )
    amends_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inspections.id", ondelete="RESTRICT")
    )
    reinspects_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inspections.id", ondelete="RESTRICT")
    )
    nc_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), server_default=text("'{}'"))
    state: Mapped[str] = mapped_column(String(15))
    visit_note: Mapped[str | None] = mapped_column(Text)
    scheduled_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    scheduled_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    readiness_at: Mapped[datetime | None]
    summary: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None]
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    submitted_role: Mapped[str | None] = mapped_column(String(12))
    submit_challenge_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
    staff_capture: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    capture_evidence_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("file_objects.id", ondelete="RESTRICT")
    )
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None]
    return_reason: Mapped[str | None] = mapped_column(Text)
    cancel_reason: Mapped[str | None] = mapped_column(String(20))
    cancel_note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(server_default=text("1"))


class InspectionResult(Base):
    """A checkpoint's result. Written only while its inspection is IN_PROGRESS (trigger), so it is
    frozen with the submission. A NON_CONFORMANCE on an initial inspection carries the finding:
    severity, description, corrective action and due date (EX-11)."""

    __tablename__ = "inspection_results"
    __table_args__ = (
        UniqueConstraint("inspection_id", "checkpoint_id"),
        CheckConstraint(f"result IN ({RESULTS})", name="result"),
        CheckConstraint(f"severity IS NULL OR severity IN ({SEVERITIES})", name="severity"),
        CheckConstraint("result <> 'NOT_APPLICABLE' OR na_reason IS NOT NULL", name="na_reason"),
        CheckConstraint(
            "(severity IS NOT NULL) = (description IS NOT NULL AND corrective_action IS NOT NULL "
            "AND due_date IS NOT NULL)",
            name="finding_complete",
        ),
        CheckConstraint("severity IS NULL OR result = 'NON_CONFORMANCE'", name="finding_is_nc"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inspections.id", ondelete="RESTRICT")
    )
    checkpoint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checkpoints.id", ondelete="RESTRICT")
    )
    result: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    na_reason: Mapped[str | None] = mapped_column(Text)
    measurement: Mapped[str | None] = mapped_column(Text)
    room_tag: Mapped[str | None] = mapped_column(String(80))
    file_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), server_default=text("'{}'"))
    severity: Mapped[str | None] = mapped_column(String(10))
    description: Mapped[str | None] = mapped_column(Text)
    corrective_action: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None]


class NonConformance(Timestamps, Base):
    """A finding of an approved inspection (EX-11). The finding columns are set once; the state
    and due date move; it closes only with the approved re-inspection that closed it."""

    __tablename__ = "non_conformances"
    __table_args__ = (
        CheckConstraint(f"state IN ({NC_STATES})", name="state"),
        CheckConstraint(f"severity IN ({SEVERITIES})", name="severity"),
        CheckConstraint(
            "(state = 'CLOSED') = (closed_by_inspection_id IS NOT NULL AND closed_at IS NOT NULL)",
            name="closed_by_reinspection",
        ),
        UniqueConstraint("result_id"),
        Index("ix_non_conformances_project_state", "project_id", "state"),
        Index("ix_non_conformances_stage", "stage_instance_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_instances.id", ondelete="RESTRICT")
    )
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inspections.id", ondelete="RESTRICT")
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inspection_results.id", ondelete="RESTRICT")
    )
    checkpoint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checkpoints.id", ondelete="RESTRICT")
    )
    severity: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(Text)
    corrective_action: Mapped[str] = mapped_column(Text)
    engagement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_engagements.id", ondelete="RESTRICT")
    )
    due_date: Mapped[date]
    state: Mapped[str] = mapped_column(String(25))
    closed_by_inspection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inspections.id", ondelete="RESTRICT")
    )
    closed_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class InspectionReport(Base):
    """The rendered report of an approved inspection (EX-14). Never re-rendered; a correction is
    a new version naming the reason."""

    __tablename__ = "inspection_reports"
    __table_args__ = (
        UniqueConstraint("inspection_id", "version"),
        CheckConstraint("(version = 1) = (correction_reason IS NULL)", name="correction_reason"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inspections.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(SmallInteger)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("file_objects.id", ondelete="RESTRICT"))
    sha256: Mapped[str] = mapped_column(String(64))
    correction_reason: Mapped[str | None] = mapped_column(Text)
    rendered_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    rendered_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class TestResult(Base):
    """A later result on a checkpoint (cube tests at 7 and 28 days), never an edit of the
    inspection (F.5)."""

    __tablename__ = "test_results"
    __test__ = False  # not a pytest class

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inspection_results.id", ondelete="RESTRICT")
    )
    test_kind: Mapped[str] = mapped_column(String(120))
    value: Mapped[str] = mapped_column(Text)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("file_objects.id", ondelete="RESTRICT")
    )
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    recorded_role: Mapped[str] = mapped_column(String(12))
    recorded_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class AssuranceEvent(Base):
    """History of appointments, checklists, inspections and non-conformances. Append-only."""

    __tablename__ = "assurance_events"
    __table_args__ = (
        CheckConstraint(
            "subject IN ('APPOINTMENT', 'CHECKLIST', 'INSPECTION', 'NON_CONFORMANCE')",
            name="subject",
        ),
        Index("ix_assurance_events_subject", "subject_id", "at"),
        Index("ix_assurance_events_project", "project_id", "at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT")
    )
    subject: Mapped[str] = mapped_column(String(20))
    subject_id: Mapped[uuid.UUID]
    from_state: Mapped[str | None] = mapped_column(String(30))
    to_state: Mapped[str] = mapped_column(String(30))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    actor_role: Mapped[str] = mapped_column(String(12))
    reason: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    file_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), server_default=text("'{}'"))
    at: Mapped[datetime] = mapped_column(server_default=text("now()"))


APPEND_ONLY = ("assurance_events", "test_results", "inspection_reports")
MUTABLE_COLUMNS = {
    "auditor_appointments": ("status", "ended_by", "ended_at", "end_reason", "updated_at"),
    "checklist_versions": ("status", "note", "published_by", "published_at", "updated_at"),
    "inspections": (
        "state", "readiness_at", "summary", "submitted_at", "submitted_by", "submitted_role",
        "submit_challenge_id", "staff_capture", "capture_evidence_file_id", "content_sha256",
        "approved_by", "approved_at", "return_reason", "cancel_reason", "cancel_note",
        "updated_at", "version",
    ),
    "non_conformances": (
        "state", "due_date", "closed_by_inspection_id", "closed_at", "updated_at", "version",
    ),
}  # fmt: skip
