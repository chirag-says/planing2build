"""Handover and Build Record tables (Slice 3.7C; SLICE3_7_READINESS H, I, K, P.D, P.E).

A handover opens once Gate 6 is cleared with no open finding (EX-15); documents and warranties
are recorded while it is OPEN; operations confirm it READY; the owner acknowledges it with a
one-time code against the ACTIVE statement version, or operations issue it without the owner's
acknowledgement, with a reason, never shown as an acknowledgement. The Build Record is a versioned
snapshot (EX-16, EX-17): DRAFT, ISSUED with its hash, PDF and JSON, then SUPERSEDED by a newer
version and still readable."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base, Timestamps

HANDOVER_STATES = "'OPEN', 'READY', 'ACKNOWLEDGED', 'ISSUED_BY_OPERATIONS'"
DOCUMENT_KINDS = "'WARRANTY', 'MANUAL', 'DRAWING', 'CERTIFICATE', 'PHOTO', 'OTHER'"


class AcknowledgementStatement(Base):
    """The statement the owner confirms at handover (EX-15): versioned configuration like the
    acceptance and selection statements; a template with $project_code. Version 1 is IMPLEMENTED
    / PENDING FINAL CLIENT + LEGAL CONFIRMATION."""

    __tablename__ = "acknowledgement_statements"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
        Index("uq_acknowledgement_statements_one_active", "status", unique=True,
              postgresql_where=text("status = 'ACTIVE'")),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(Text)
    # Reference data: user ids without foreign keys, as for the other statements.
    created_by: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    activated_by: Mapped[uuid.UUID | None]
    activated_at: Mapped[datetime | None]


class Handover(Timestamps, Base):
    """One per project. Frozen once ACKNOWLEDGED or ISSUED_BY_OPERATIONS."""

    __tablename__ = "handovers"
    __table_args__ = (
        UniqueConstraint("project_id"),
        CheckConstraint(f"state IN ({HANDOVER_STATES})", name="state"),
        CheckConstraint(
            "state <> 'ACKNOWLEDGED' OR (acknowledged_by IS NOT NULL AND acknowledged_at IS NOT "
            "NULL AND challenge_id IS NOT NULL AND statement_id IS NOT NULL AND statement_text "
            "IS NOT NULL)",
            name="acknowledged_complete",
        ),
        # EX-15: an operations issue carries actor, time and reason, and no acknowledgement.
        CheckConstraint(
            "state <> 'ISSUED_BY_OPERATIONS' OR (forced_by IS NOT NULL AND forced_at IS NOT NULL "
            "AND forced_reason IS NOT NULL AND acknowledged_by IS NULL AND challenge_id IS NULL)",
            name="forced_is_not_acknowledgement",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    state: Mapped[str] = mapped_column(String(25))
    opened_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    opened_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    ready_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    ready_at: Mapped[datetime | None]
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    acknowledged_at: Mapped[datetime | None]
    challenge_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
    statement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("acknowledgement_statements.id", ondelete="RESTRICT")
    )
    statement_text: Mapped[str | None] = mapped_column(Text)
    forced_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    forced_at: Mapped[datetime | None]
    forced_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(server_default=text("1"))


class HandoverDocument(Base):
    """A document handed over (MVP P8). Added or removed only while the handover is OPEN."""

    __tablename__ = "handover_documents"
    __table_args__ = (
        CheckConstraint(f"kind IN ({DOCUMENT_KINDS})", name="kind"),
        UniqueConstraint("handover_id", "file_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    handover_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("handovers.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(15))
    title: Mapped[str] = mapped_column(String(200))
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("file_objects.id", ondelete="RESTRICT"))
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    added_role: Mapped[str] = mapped_column(String(12))
    added_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Warranty(Base):
    """A warranty with its term, expiry and installer (MVP P8). Recorded only while OPEN."""

    __tablename__ = "warranties"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    handover_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("handovers.id", ondelete="RESTRICT"))
    item: Mapped[str] = mapped_column(String(200))
    term: Mapped[str] = mapped_column(String(120))
    expiry_date: Mapped[date]
    installer: Mapped[str] = mapped_column(String(200))
    spec_line_code: Mapped[str | None] = mapped_column(String(3))
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("handover_documents.id", ondelete="RESTRICT")
    )
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    added_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class BuildRecord(Timestamps, Base):
    """A version of the project's Build Record (EX-17). Frozen from ISSUED; a correction is a new
    version naming its reason; the earlier version becomes SUPERSEDED and stays readable."""

    __tablename__ = "build_records"
    __table_args__ = (
        UniqueConstraint("project_id", "version_no"),
        CheckConstraint("state IN ('DRAFT', 'ISSUED', 'SUPERSEDED')", name="state"),
        CheckConstraint("basis IN ('ACKNOWLEDGED', 'ISSUED_BY_OPERATIONS')", name="basis"),
        CheckConstraint(
            "state = 'DRAFT' OR (snapshot_sha256 IS NOT NULL AND pdf_file_id IS NOT NULL AND "
            "json_file_id IS NOT NULL AND issued_at IS NOT NULL)",
            name="issued_complete",
        ),
        CheckConstraint("(version_no = 1) = (correction_reason IS NULL)", name="correction_reason"),
        Index("uq_build_records_one_draft", "project_id", unique=True,
              postgresql_where=text("state = 'DRAFT'")),
        Index("uq_build_records_one_issued", "project_id", unique=True,
              postgresql_where=text("state = 'ISSUED'")),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    handover_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("handovers.id", ondelete="RESTRICT"))
    version_no: Mapped[int] = mapped_column(SmallInteger)
    state: Mapped[str] = mapped_column(String(10))
    basis: Mapped[str] = mapped_column(String(25))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    snapshot_sha256: Mapped[str | None] = mapped_column(String(64))
    pdf_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("file_objects.id", ondelete="RESTRICT")
    )
    pdf_sha256: Mapped[str | None] = mapped_column(String(64))
    json_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("file_objects.id", ondelete="RESTRICT")
    )
    json_sha256: Mapped[str | None] = mapped_column(String(64))
    correction_reason: Mapped[str | None] = mapped_column(Text)
    assembled_by_role: Mapped[str] = mapped_column(String(12))
    issued_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    issued_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class RecordsEvent(Base):
    """History of handovers and Build Record versions. Append-only."""

    __tablename__ = "records_events"
    __table_args__ = (
        CheckConstraint("subject IN ('HANDOVER', 'BUILD_RECORD')", name="subject"),
        Index("ix_records_events_project", "project_id", "at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    subject: Mapped[str] = mapped_column(String(15))
    subject_id: Mapped[uuid.UUID]
    from_state: Mapped[str | None] = mapped_column(String(25))
    to_state: Mapped[str] = mapped_column(String(25))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    actor_role: Mapped[str] = mapped_column(String(12))
    reason: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    at: Mapped[datetime] = mapped_column(server_default=text("now()"))


APPEND_ONLY = ("records_events",)
MUTABLE_COLUMNS = {
    "acknowledgement_statements": ("status", "activated_by", "activated_at"),
    "handovers": (
        "state", "ready_by", "ready_at", "acknowledged_by", "acknowledged_at", "challenge_id",
        "statement_id", "statement_text", "forced_by", "forced_at", "forced_reason",
        "updated_at", "version",
    ),
    "build_records": (
        "state", "snapshot", "snapshot_sha256", "pdf_file_id", "pdf_sha256", "json_file_id",
        "json_sha256", "issued_by", "issued_at", "updated_at", "version",
    ),
}  # fmt: skip
