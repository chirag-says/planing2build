"""Service needs, engagements and connections (Slice 3.4; SLICE3_4_READINESS section 0).

A project holds one need per professional category; a category may have several candidate
connection requests, and at most one ACTIVE engagement (N-02). Nothing here is project-level: no
contractor, route or path on the project. No money: the package gates the actions; payments
between the family and professionals never pass through Plan2Build."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
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


class ProjectServiceNeed(Base):
    __tablename__ = "project_service_needs"
    __table_args__ = (
        UniqueConstraint("project_id", "category_code"),
        CheckConstraint("state IN ('UNDECIDED', 'NEEDED', 'NOT_NEEDED')", name="state"),
        CheckConstraint("source IN ('REQUIREMENT', 'FAMILY')", name="source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    category_code: Mapped[str] = _fk("service_categories.code")
    state: Mapped[str] = mapped_column(String(12))
    subtypes: Mapped[list[str]] = mapped_column(ARRAY(String(40)), server_default=text("'{}'"))
    source: Mapped[str] = mapped_column(String(12))
    updated_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(server_default=NOW)
    version: Mapped[int] = mapped_column(server_default=text("1"))


class Connection(Base):
    """The family's formal request to one listed professional for one category (a candidate).
    The brief carries no identity; the family's contact is shown to the professional only once
    the request is ACCEPTED (N-08)."""

    __tablename__ = "connections"
    __table_args__ = (
        CheckConstraint(
            "state IN ('SENT', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'WITHDRAWN')", name="state"
        ),
        CheckConstraint(
            "decline_reason IS NULL OR decline_reason IN ('UNAVAILABLE', 'OUTSIDE_SERVICE_AREA', "
            "'SCOPE_MISMATCH', 'SCHEDULE_MISMATCH', 'COMPLIANCE', 'ALREADY_ENGAGED', 'OTHER')",
            name="decline_reason",
        ),
        CheckConstraint(
            "(state = 'DECLINED') = (decline_reason IS NOT NULL)", name="declined_has_reason"
        ),
        CheckConstraint(
            "decline_reason IS DISTINCT FROM 'OTHER' OR length(trim(decline_note)) > 0",
            name="other_needs_note",
        ),
        CheckConstraint(
            "withdraw_reason IS NULL OR withdraw_reason IN ('FAMILY', 'ANOTHER_ENGAGED', "
            "'PACKAGE_ENDED', 'PROFESSIONAL_UNAVAILABLE', 'PROJECT_CLOSED', 'OPERATIONS')",
            name="withdraw_reason",
        ),
        CheckConstraint(
            "(state = 'WITHDRAWN') = (withdraw_reason IS NOT NULL)", name="withdrawn_has_reason"
        ),
        Index(
            "uq_connections_one_open_per_professional",
            "project_id",
            "category_code",
            "profile_id",
            unique=True,
            postgresql_where=text("state = 'SENT'"),
        ),
        Index("ix_connections_profile_id", "profile_id", "sent_at"),
        Index("ix_connections_open", "respond_by", postgresql_where=text("state = 'SENT'")),
        Index("ix_connections_project_id", "project_id", "category_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    category_code: Mapped[str] = _fk("service_categories.code")
    profile_id: Mapped[uuid.UUID] = _fk("professional_profiles.id")
    state: Mapped[str] = mapped_column(String(10))
    brief: Mapped[dict[str, Any]] = mapped_column(JSONB)
    family_contact: Mapped[dict[str, Any]] = mapped_column(JSONB)
    professional_contact: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sent_by: Mapped[uuid.UUID] = _fk("users.id")
    sent_at: Mapped[datetime] = mapped_column(server_default=NOW)
    respond_by: Mapped[datetime]
    responded_at: Mapped[datetime | None]
    decline_reason: Mapped[str | None] = mapped_column(String(24))
    decline_note: Mapped[str | None] = mapped_column(Text)
    withdrawn_by_role: Mapped[str | None] = mapped_column(String(12))
    withdraw_reason: Mapped[str | None] = mapped_column(String(24))
    withdraw_note: Mapped[str | None] = mapped_column(Text)
    engagement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_engagements.id", ondelete="RESTRICT", use_alter=True)
    )
    version: Mapped[int] = mapped_column(server_default=text("1"))


class ProjectEngagement(Base):
    """Who provides a category on a project: a listed professional (from an accepted connection,
    or from the homeowner's selection of an RFQ quote, ADR-024) or an outside professional the
    family recorded. One ACTIVE per category (N-02). An engagement from an RFQ selection carries
    the contacts exchanged at selection (N-08 after acceptance); one from a connection reads them
    from the connection."""

    __tablename__ = "project_engagements"
    __table_args__ = (
        CheckConstraint("party IN ('LISTED', 'OUTSIDE')", name="party"),
        CheckConstraint("state IN ('ACTIVE', 'ENDED')", name="state"),
        CheckConstraint("origin IN ('CONNECTION', 'OUTSIDE', 'RFQ_SELECTION')", name="origin"),
        CheckConstraint(
            "(party = 'LISTED' AND origin = 'CONNECTION' AND profile_id IS NOT NULL "
            "AND connection_id IS NOT NULL AND selection_id IS NULL AND outside_name IS NULL) OR "
            "(party = 'LISTED' AND origin = 'RFQ_SELECTION' AND profile_id IS NOT NULL "
            "AND connection_id IS NULL AND selection_id IS NOT NULL AND outside_name IS NULL "
            "AND family_contact IS NOT NULL) OR "
            "(party = 'OUTSIDE' AND origin = 'OUTSIDE' AND profile_id IS NULL "
            "AND connection_id IS NULL AND selection_id IS NULL AND outside_name IS NOT NULL)",
            name="party_fields",
        ),
        CheckConstraint("(state = 'ENDED') = (ended_at IS NOT NULL)", name="ended"),
        Index(
            "uq_project_engagements_one_active",
            "project_id",
            "category_code",
            unique=True,
            postgresql_where=text("state = 'ACTIVE'"),
        ),
        Index("ix_project_engagements_profile_id", "profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    category_code: Mapped[str] = _fk("service_categories.code")
    party: Mapped[str] = mapped_column(String(10))
    profile_id: Mapped[uuid.UUID | None] = _fk("professional_profiles.id", nullable=True)
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connections.id", ondelete="RESTRICT"), unique=True
    )
    outside_name: Mapped[str | None] = mapped_column(String(120))
    outside_firm: Mapped[str | None] = mapped_column(String(160))
    outside_contact: Mapped[str | None] = mapped_column(String(200))
    origin: Mapped[str] = mapped_column(String(14))
    # The RFQ selection that started it (rfq module; no foreign key back into rfq, ADR-024).
    selection_id: Mapped[uuid.UUID | None] = mapped_column(unique=True)
    family_contact: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    professional_contact: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(8))
    created_by: Mapped[uuid.UUID] = _fk("users.id")
    started_at: Mapped[datetime] = mapped_column(server_default=NOW)
    ended_at: Mapped[datetime | None]
    ended_by_role: Mapped[str | None] = mapped_column(String(12))
    end_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(server_default=text("1"))


class EngagementDocument(Base):
    """A requirement upload the family shared with one ACTIVE engagement (N-08). Nothing is
    shared by default; unsharing keeps the row."""

    __tablename__ = "engagement_documents"
    __table_args__ = (
        Index(
            "uq_engagement_documents_one_active",
            "engagement_id",
            "file_id",
            unique=True,
            postgresql_where=text("unshared_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    engagement_id: Mapped[uuid.UUID] = _fk("project_engagements.id")
    file_id: Mapped[uuid.UUID] = _fk("file_objects.id")
    shared_by: Mapped[uuid.UUID] = _fk("users.id")
    shared_at: Mapped[datetime] = mapped_column(server_default=NOW)
    unshared_at: Mapped[datetime | None]


class EngagementEvent(Base):
    """Connection and engagement history: every transition, with actor, role and reason.
    Append-only."""

    __tablename__ = "engagement_events"
    __table_args__ = (
        CheckConstraint("subject IN ('CONNECTION', 'ENGAGEMENT')", name="subject"),
        Index("ix_engagement_events_project_id", "project_id", "at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    subject: Mapped[str] = mapped_column(String(12))
    subject_id: Mapped[uuid.UUID]
    category_code: Mapped[str] = mapped_column(String(40))
    from_state: Mapped[str | None] = mapped_column(String(12))
    to_state: Mapped[str] = mapped_column(String(12))
    actor_user_id: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    actor_role: Mapped[str] = mapped_column(String(12))
    reason: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(server_default=NOW)


class QuoteReviewRequest(Base):
    """Quote-holder review intake (Slice 3.4): a quote the family already holds, submitted for
    Plan2Build's review with the package. `file_ids` are the family's QUOTE_DOCUMENT files,
    checked by the service (Postgres has no foreign keys on array elements). Review, normalisation
    and comparison are the later quote workflow."""

    __tablename__ = "quote_review_requests"
    __table_args__ = (
        CheckConstraint("state IN ('SUBMITTED')", name="state"),
        CheckConstraint("cardinality(file_ids) BETWEEN 1 AND 5", name="files"),
        Index("ix_quote_review_requests_project_id", "project_id", "submitted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    category_code: Mapped[str] = _fk("service_categories.code")
    quoted_by: Mapped[str] = mapped_column(String(160))
    note: Mapped[str | None] = mapped_column(Text)
    file_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid))
    state: Mapped[str] = mapped_column(String(10))
    submitted_by: Mapped[uuid.UUID] = _fk("users.id")
    submitted_at: Mapped[datetime] = mapped_column(server_default=NOW)


APPEND_ONLY = ("engagement_events",)
MUTABLE_COLUMNS = {
    "connections": (
        "state", "professional_contact", "responded_at", "decline_reason",
        "decline_note", "withdrawn_by_role", "withdraw_reason", "withdraw_note", "engagement_id",
        "version",
    ),
    "project_engagements": ("state", "ended_at", "ended_by_role", "end_reason", "version"),
    "engagement_documents": ("unshared_at",),
    "quote_review_requests": ("state",),
}  # fmt: skip
