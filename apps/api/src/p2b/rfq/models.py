"""RFQ to contractor selection (Slice 3.6; SLICE3_6_READINESS section 0, U).

An RFQ names one ACCEPTED Build Plan version and freezes its contractor manifest at issue
(BP-05, BP-08). Invitations ask contractors to quote (QD-01); accepting one is agreeing to quote,
never an engagement. Each submission is an immutable quote version with its lines (QD-06, QD-18).
Plan2Build's review adds adjustments that contractors never see (QD-08). A comparison version is
a frozen, neutrally ordered snapshot (QD-10, QD-11, QD-23). The selection is append-only; the
engagement it starts lives in the engagements module (ADR-024). No construction money, no
contract value (QD-12)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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
MONEY = Numeric(14, 2)


def _fk(target: str, nullable: bool = False) -> Any:
    return mapped_column(ForeignKey(target, ondelete="RESTRICT"), nullable=nullable)


class Rfq(Base):
    __tablename__ = "rfqs"
    __table_args__ = (
        CheckConstraint("state IN ('DRAFT', 'ISSUED', 'CLOSED', 'CANCELLED')", name="state"),
        CheckConstraint("category_code = 'CONTRACTOR'", name="contractor_only"),  # QD-26
        CheckConstraint(
            "cancel_reason IS NULL OR cancel_reason IN ('OWNER', 'OPERATIONS', 'PACKAGE_ENDED', "
            "'BASELINE_SUPERSEDED', 'PROJECT_CLOSED')",
            name="cancel_reason",
        ),
        CheckConstraint(
            "(state = 'CANCELLED') = (cancel_reason IS NOT NULL)", name="cancelled_has_reason"
        ),
        CheckConstraint(
            "state NOT IN ('ISSUED', 'CLOSED') OR (manifest IS NOT NULL "
            "AND manifest_sha256 IS NOT NULL AND issued_at IS NOT NULL "
            "AND quotes_due_at IS NOT NULL)",
            name="issued_is_frozen",
        ),
        CheckConstraint("max_recipients > 0", name="max_recipients"),
        Index(
            "uq_rfqs_one_open",
            "project_id",
            "category_code",
            unique=True,
            postgresql_where=text("state IN ('DRAFT', 'ISSUED')"),
        ),
        Index("ix_rfqs_project_id", "project_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    category_code: Mapped[str] = _fk("service_categories.code")
    build_plan_version_id: Mapped[uuid.UUID] = _fk("build_plan_versions.id")
    state: Mapped[str] = mapped_column(String(10))
    max_recipients: Mapped[int] = mapped_column(Integer)
    quotes_due_at: Mapped[datetime | None]
    manifest: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    requested_by: Mapped[uuid.UUID] = _fk("users.id")
    requested_role: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    issued_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    issued_at: Mapped[datetime | None]
    deadline_noticed_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    cancel_reason: Mapped[str | None] = mapped_column(String(20))
    cancel_note: Mapped[str | None] = mapped_column(Text)
    cancelled_by_role: Mapped[str | None] = mapped_column(String(12))
    cancelled_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class RfqInvitation(Base):
    """One contractor asked to quote. LISTED: a listed contractor who answers on the professionals
    host. OUTSIDE: the family's engaged outside contractor, whose quote operations capture
    (QD-22); it never becomes a platform professional."""

    __tablename__ = "rfq_invitations"
    __table_args__ = (
        CheckConstraint("party IN ('LISTED', 'OUTSIDE')", name="party"),
        CheckConstraint(
            "state IN ('PROPOSED', 'SENT', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'WITHDRAWN')",
            name="state",
        ),
        CheckConstraint("source IN ('NOMINATED', 'INTRODUCED', 'ENGAGED')", name="source"),
        CheckConstraint(
            "(party = 'LISTED' AND profile_id IS NOT NULL AND engagement_id IS NULL) OR "
            "(party = 'OUTSIDE' AND profile_id IS NULL AND engagement_id IS NOT NULL "
            "AND source = 'ENGAGED')",
            name="party_fields",
        ),
        CheckConstraint(
            "source <> 'INTRODUCED' OR length(trim(introduced_reason)) > 0",
            name="introduced_has_reason",
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
            "withdraw_reason IS NULL OR withdraw_reason IN ('REMOVED', 'OPERATIONS', "
            "'RFQ_CANCELLED', 'RFQ_CLOSED', 'NOT_LISTED')",
            name="withdraw_reason",
        ),
        CheckConstraint(
            "(state = 'WITHDRAWN') = (withdraw_reason IS NOT NULL)", name="withdrawn_has_reason"
        ),
        Index(
            "uq_rfq_invitations_one_per_contractor",
            "rfq_id",
            "profile_id",
            unique=True,
            postgresql_where=text("profile_id IS NOT NULL"),
        ),
        Index(
            "uq_rfq_invitations_one_outside",
            "rfq_id",
            unique=True,
            postgresql_where=text("party = 'OUTSIDE'"),
        ),
        Index("ix_rfq_invitations_profile_id", "profile_id", "state"),
        Index("ix_rfq_invitations_open", "respond_by", postgresql_where=text("state = 'SENT'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    rfq_id: Mapped[uuid.UUID] = _fk("rfqs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    party: Mapped[str] = mapped_column(String(8))
    profile_id: Mapped[uuid.UUID | None] = _fk("professional_profiles.id", nullable=True)
    engagement_id: Mapped[uuid.UUID | None] = _fk("project_engagements.id", nullable=True)
    source: Mapped[str] = mapped_column(String(12))
    introduced_reason: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(10))
    brief: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID] = _fk("users.id")
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    sent_at: Mapped[datetime | None]
    respond_by: Mapped[datetime | None]
    responded_at: Mapped[datetime | None]
    professional_contact: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    decline_reason: Mapped[str | None] = mapped_column(String(24))
    decline_note: Mapped[str | None] = mapped_column(Text)
    withdraw_reason: Mapped[str | None] = mapped_column(String(16))
    withdraw_note: Mapped[str | None] = mapped_column(Text)
    withdrawn_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class QuoteDraft(Base):
    """A contractor's working copy, private to them and never part of the record; deleted on
    submission or discard."""

    __tablename__ = "quote_drafts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    invitation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rfq_invitations.id", ondelete="RESTRICT"), unique=True
    )
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_by: Mapped[uuid.UUID] = _fk("users.id")
    updated_at: Mapped[datetime] = mapped_column(server_default=NOW)
    version: Mapped[int] = mapped_column(server_default=text("1"))


class QuoteVersion(Base):
    """One submission, immutable from the moment it exists (only lifecycle columns change)."""

    __tablename__ = "quote_versions"
    __table_args__ = (
        UniqueConstraint("invitation_id", "version_no"),
        CheckConstraint(
            "state IN ('SUBMITTED', 'SUPERSEDED', 'WITHDRAWN', 'EXPIRED', 'SELECTED', "
            "'NOT_SELECTED')",
            name="state",
        ),
        CheckConstraint("kind IN ('STANDARD', 'RENEWAL')", name="kind"),
        CheckConstraint(
            "review_state IN ('PENDING', 'NEEDS_CLARIFICATION', 'REVIEWED', 'CLOSED')",
            name="review_state",
        ),
        CheckConstraint("tax_treatment IN ('INCLUSIVE', 'EXCLUSIVE')", name="tax_treatment"),
        CheckConstraint("valid_to > valid_from", name="validity"),
        CheckConstraint("duration_days > 0", name="duration"),
        CheckConstraint("(kind = 'RENEWAL') = (renewal_of IS NOT NULL)", name="renewal_of"),
        CheckConstraint(
            "NOT captured_by_staff OR evidence_file_id IS NOT NULL", name="capture_has_evidence"
        ),
        CheckConstraint("(state = 'WITHDRAWN') = (withdraw_reason IS NOT NULL)", name="withdrawn"),
        Index("ix_quote_versions_rfq_id", "rfq_id", "state"),
        Index("ix_quote_versions_open", "valid_to", postgresql_where=text("state = 'SUBMITTED'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    invitation_id: Mapped[uuid.UUID] = _fk("rfq_invitations.id")
    rfq_id: Mapped[uuid.UUID] = _fk("rfqs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    version_no: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(8))
    renewal_of: Mapped[uuid.UUID | None] = _fk("quote_versions.id", nullable=True)
    state: Mapped[str] = mapped_column(String(12))
    review_state: Mapped[str] = mapped_column(String(20))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    tax_treatment: Mapped[str] = mapped_column(String(10))
    tax_note: Mapped[str | None] = mapped_column(Text)
    duration_days: Mapped[int] = mapped_column(Integer)
    stage_durations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    payment_terms: Mapped[str | None] = mapped_column(Text)
    warranty: Mapped[str | None] = mapped_column(Text)
    materials: Mapped[str | None] = mapped_column(Text)
    exclusions: Mapped[list[str]] = mapped_column(JSONB)
    assumptions: Mapped[list[str]] = mapped_column(JSONB)
    comment: Mapped[str | None] = mapped_column(Text)
    attachment_file_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid))
    comparable_total: Mapped[Decimal] = mapped_column(MONEY)
    additional_total: Mapped[Decimal] = mapped_column(MONEY)
    content_sha256: Mapped[str] = mapped_column(String(64))
    submitted_by: Mapped[uuid.UUID] = _fk("users.id")
    submitted_at: Mapped[datetime] = mapped_column(server_default=NOW)
    captured_by_staff: Mapped[bool] = mapped_column(Boolean)
    evidence_file_id: Mapped[uuid.UUID | None] = _fk("file_objects.id", nullable=True)
    withdraw_reason: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None]
    reviewed_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    reviewed_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class QuoteLine(Base):
    """A priced or excluded line of a submission; written once with its version."""

    __tablename__ = "quote_lines"
    __table_args__ = (
        UniqueConstraint("quote_version_id", "kind", "line_no"),
        CheckConstraint("kind IN ('RFQ_LINE', 'ADDITIONAL')", name="kind"),
        CheckConstraint(
            "(is_excluded AND rate IS NULL AND amount IS NULL "
            "AND length(trim(exclusion_reason)) > 0) OR "
            "(NOT is_excluded AND rate > 0 AND amount IS NOT NULL AND exclusion_reason IS NULL)",
            name="priced_or_excluded",
        ),
        CheckConstraint("kind = 'RFQ_LINE' OR NOT is_excluded", name="additional_priced"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    quote_version_id: Mapped[uuid.UUID] = _fk("quote_versions.id")
    kind: Mapped[str] = mapped_column(String(10))
    line_no: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    rate: Mapped[Decimal | None] = mapped_column(MONEY)
    amount: Mapped[Decimal | None] = mapped_column(MONEY)
    is_excluded: Mapped[bool] = mapped_column(Boolean)
    exclusion_reason: Mapped[str | None] = mapped_column(Text)
    alternate_spec: Mapped[str | None] = mapped_column(Text)


class QuoteAdjustment(Base):
    """Plan2Build's normalisation finding on one quote version: never shown to any contractor
    (QD-08), never changing the contractor's prices. Editable only while the review is open."""

    __tablename__ = "quote_adjustments"
    __table_args__ = (
        CheckConstraint(
            "deviation_type IN ('EXCLUDED', 'GRADE', 'QUANTITY', 'ADDITIONAL', 'OTHER')",
            name="deviation_type",
        ),
        CheckConstraint(
            "clarification_status IN ('NONE', 'OPEN', 'RESOLVED')", name="clarification_status"
        ),
        Index("ix_quote_adjustments_quote_version_id", "quote_version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    quote_version_id: Mapped[uuid.UUID] = _fk("quote_versions.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    line_no: Mapped[int | None] = mapped_column(Integer)
    spec_line_code: Mapped[str | None] = mapped_column(String(8))
    deviation_type: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(Text)
    rupee_impact: Mapped[Decimal] = mapped_column(MONEY)
    basis_note: Mapped[str | None] = mapped_column(Text)
    clarification_status: Mapped[str] = mapped_column(String(10))
    created_by: Mapped[uuid.UUID] = _fk("users.id")
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)


class RfqClarification(Base):
    """One structured question and its answer, through Plan2Build (QD-17). Never chat, never a
    change to the RFQ or a quote."""

    __tablename__ = "rfq_clarifications"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('CONTRACTOR_ASKS', 'PLAN2BUILD_ASKS')", name="direction"
        ),
        CheckConstraint("state IN ('OPEN', 'ANSWERED', 'CLOSED')", name="state"),
        CheckConstraint("(state = 'ANSWERED') = (answer IS NOT NULL)", name="answered"),
        CheckConstraint(
            "NOT shared_with_all OR direction = 'CONTRACTOR_ASKS'", name="shared_questions"
        ),
        Index("ix_rfq_clarifications_rfq_id", "rfq_id", "asked_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    rfq_id: Mapped[uuid.UUID] = _fk("rfqs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    invitation_id: Mapped[uuid.UUID] = _fk("rfq_invitations.id")
    quote_version_id: Mapped[uuid.UUID | None] = _fk("quote_versions.id", nullable=True)
    direction: Mapped[str] = mapped_column(String(16))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    shared_with_all: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    state: Mapped[str] = mapped_column(String(10))
    asked_by: Mapped[uuid.UUID] = _fk("users.id")
    asked_at: Mapped[datetime] = mapped_column(server_default=NOW)
    answered_by: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    answered_at: Mapped[datetime | None]
    close_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(server_default=text("1"))


class Comparison(Base):
    """A frozen comparison version: the reviewed quote versions as submitted, their adjustments
    and totals, in an order drawn from a stored seed (QD-11). Never re-rendered (QD-23)."""

    __tablename__ = "comparisons"
    __table_args__ = (
        UniqueConstraint("rfq_id", "version_no"),
        CheckConstraint("state IN ('PUBLISHED', 'SUPERSEDED', 'DECIDED')", name="state"),
        CheckConstraint("cardinality(quote_version_ids) >= 1", name="not_empty"),  # QD-24
        Index(
            "uq_comparisons_one_current",
            "rfq_id",
            unique=True,
            postgresql_where=text("state IN ('PUBLISHED', 'DECIDED')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    rfq_id: Mapped[uuid.UUID] = _fk("rfqs.id")
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    version_no: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(10))
    quote_version_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid))
    order_seed: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    document_file_id: Mapped[uuid.UUID] = _fk("file_objects.id")
    published_by: Mapped[uuid.UUID] = _fk("users.id")
    published_at: Mapped[datetime]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class SelectionStatement(Base):
    """The statement the owner confirms when selecting a quote (QD-12): versioned configuration
    like the acceptance statement; a template with $project_code, $contractor and $version_no.
    Version 1 is IMPLEMENTED / PENDING FINAL CLIENT + LEGAL CONFIRMATION."""

    __tablename__ = "selection_statements"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
        Index(
            "uq_selection_statements_one_active",
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
    # Reference data: user ids without foreign keys, as for the other statements.
    created_by: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=NOW)
    activated_by: Mapped[uuid.UUID | None]
    activated_at: Mapped[datetime | None]


class Selection(Base):
    """The homeowner's choice of one quote version (QD-12). Append-only; one per RFQ. It records
    no contract value: the commercial agreement is between the homeowner and the contractor."""

    __tablename__ = "selections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    rfq_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rfqs.id", ondelete="RESTRICT"), unique=True
    )
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    comparison_id: Mapped[uuid.UUID] = _fk("comparisons.id")
    quote_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quote_versions.id", ondelete="RESTRICT"), unique=True
    )
    invitation_id: Mapped[uuid.UUID] = _fk("rfq_invitations.id")
    engagement_id: Mapped[uuid.UUID] = _fk("project_engagements.id")
    engagement_created: Mapped[bool] = mapped_column(Boolean)
    selected_by: Mapped[uuid.UUID] = _fk("users.id")
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("otp_challenges.id", ondelete="RESTRICT"), unique=True
    )
    statement_id: Mapped[uuid.UUID] = _fk("selection_statements.id")
    statement_text: Mapped[str] = mapped_column(Text)
    ip_hash: Mapped[str] = mapped_column(String(64))
    selected_at: Mapped[datetime] = mapped_column(server_default=NOW)


class RfqEvent(Base):
    """History of every RFQ transition: subject, from and to state, actor, role and reason."""

    __tablename__ = "rfq_events"
    __table_args__ = (
        CheckConstraint(
            "subject IN ('RFQ', 'INVITATION', 'QUOTE_VERSION', 'REVIEW', 'CLARIFICATION', "
            "'COMPARISON', 'SELECTION')",
            name="subject",
        ),
        Index("ix_rfq_events_rfq_id", "rfq_id", "at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = _fk("projects.id")
    rfq_id: Mapped[uuid.UUID] = _fk("rfqs.id")
    subject: Mapped[str] = mapped_column(String(14))
    subject_id: Mapped[uuid.UUID]
    from_state: Mapped[str | None] = mapped_column(String(20))
    to_state: Mapped[str] = mapped_column(String(20))
    actor_user_id: Mapped[uuid.UUID | None] = _fk("users.id", nullable=True)
    actor_role: Mapped[str] = mapped_column(String(12))
    reason: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(server_default=NOW)


APPEND_ONLY = ("quote_lines", "selections", "rfq_events")
MUTABLE_COLUMNS = {
    "rfqs": (
        "state", "quotes_due_at", "manifest", "manifest_sha256", "issued_by", "issued_at",
        "deadline_noticed_at", "closed_at", "cancel_reason", "cancel_note", "cancelled_by_role",
        "cancelled_at", "version",
    ),
    "rfq_invitations": (
        "state", "sent_at", "respond_by", "responded_at", "professional_contact",
        "decline_reason", "decline_note", "withdraw_reason", "withdraw_note", "withdrawn_at",
        "version",
    ),
    "quote_versions": (
        "state", "review_state", "withdraw_reason", "closed_at", "reviewed_by", "reviewed_at",
        "version",
    ),
    "rfq_clarifications": (
        "answer", "shared_with_all", "state", "answered_by", "answered_at", "close_reason",
        "version",
    ),
    "comparisons": ("state", "version"),
    "selection_statements": ("status", "activated_by", "activated_at"),
}  # fmt: skip
# Set once: the frozen pack, and the times that close a record.
SET_ONCE = {
    "rfqs": ("manifest", "manifest_sha256", "issued_at", "closed_at", "cancelled_at"),
    "quote_versions": ("closed_at", "reviewed_at"),
    "rfq_clarifications": ("answer", "answered_at"),
}
