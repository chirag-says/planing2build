"""Tables owned by the houseplans module (Checkpoint 1; ADR-025, migration 0019)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base

RULESET_STATUSES = "'DRAFT', 'APPROVED', 'PUBLISHED', 'RETIRED'"
STATES = "'QUEUED', 'RUNNING', 'VALID', 'INFEASIBLE', 'FAILED'"
FAILURES = "'ENGINE_ERROR', 'ENGINE_INVALID_OUTPUT', 'ENGINE_TIMEOUT', 'STALE'"
VALIDITIES = "'VALID', 'INVALID'"
OP_REASONS = "'USER', 'AUTO_REPAIR', 'REVERT'"


class LayoutRuleset(Base):
    """Versioned layout rules (AD-05). Content never changes: a change is a new version. Only a
    PUBLISHED ruleset may serve production, and a synthetic one (test data, CP1-06) can never be
    approved or published."""

    __tablename__ = "layout_rulesets"
    __table_args__ = (
        UniqueConstraint("version"),
        CheckConstraint(f"status IN ({RULESET_STATUSES})", name="status"),
        CheckConstraint(
            "NOT (is_synthetic AND status IN ('APPROVED', 'PUBLISHED'))",
            name="synthetic_never_approved",
        ),
        CheckConstraint(
            "status NOT IN ('APPROVED', 'PUBLISHED', 'RETIRED') OR approved_by IS NOT NULL",
            name="approval_named",
        ),
        CheckConstraint(
            "status <> 'PUBLISHED' OR published_by IS NOT NULL", name="publication_named"
        ),
        CheckConstraint(
            "(content ->> 'synthetic')::boolean = is_synthetic", name="synthetic_matches_content"
        ),
        Index(
            "uq_layout_rulesets_one_published",
            "status",
            unique=True,
            postgresql_where=text("status = 'PUBLISHED'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    schema_version: Mapped[str] = mapped_column(String(16))
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None]
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    published_at: Mapped[datetime | None]
    retired_at: Mapped[datetime | None]


class HousePlanRecord(Base):
    """One concept plan generation and its working head. VALID is the only state that carries a
    document, and only one the validator passed (CP1-04). Never authoritative (PD-28, CHECK)."""

    __tablename__ = "house_plans"
    __table_args__ = (
        UniqueConstraint("project_id", "sequence"),
        CheckConstraint(f"state IN ({STATES})", name="state"),
        CheckConstraint(
            f"failure_reason IS NULL OR failure_reason IN ({FAILURES})", name="failure_reason"
        ),
        CheckConstraint(
            f"head_validity IS NULL OR head_validity IN ({VALIDITIES})", name="head_validity"
        ),
        CheckConstraint("is_authoritative = false", name="never_authoritative"),
        CheckConstraint(
            "(state = 'VALID') = (head_document IS NOT NULL)", name="document_iff_valid"
        ),
        CheckConstraint(
            "(head_document IS NULL) = (head_validity IS NULL)", name="validity_with_document"
        ),
        CheckConstraint(
            "(head_document IS NULL) = (head_report IS NULL)", name="report_with_document"
        ),
        CheckConstraint(
            "(state = 'INFEASIBLE') = (infeasibility IS NOT NULL)", name="reasons_iff_infeasible"
        ),
        CheckConstraint(
            "(state = 'FAILED') = (failure_reason IS NOT NULL)", name="reason_iff_failed"
        ),
        Index("ix_house_plans_project_id_state", "project_id", "state"),
        Index(
            "uq_house_plans_one_in_flight",
            "project_id",
            unique=True,
            postgresql_where=text("state IN ('QUEUED', 'RUNNING')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    sequence: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(12))
    design_inputs: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # PROVISIONAL (CP1-03)
    intent: Mapped[dict[str, Any]] = mapped_column(JSONB)
    intent_sha256: Mapped[str] = mapped_column(String(64))
    question_set_version: Mapped[int] = mapped_column(Integer)
    requirement_version: Mapped[int] = mapped_column(Integer)
    ruleset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("layout_rulesets.id", ondelete="RESTRICT")
    )
    ruleset_version: Mapped[int] = mapped_column(Integer)
    engine_version: Mapped[str] = mapped_column(String(20))
    solver: Mapped[str] = mapped_column(String(20))
    seed: Mapped[int] = mapped_column(BigInteger)
    head_revision_no: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    head_document: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    head_validity: Mapped[str | None] = mapped_column(String(8))
    head_report: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    infeasibility: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    failure_reason: Mapped[str | None] = mapped_column(String(32))
    failure_detail: Mapped[str | None] = mapped_column(Text)  # internal; never sent to the family
    solve_ms: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    is_authoritative: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class HousePlanVersion(Base):
    """An immutable snapshot of a plan. Version 1 is the generated result."""

    __tablename__ = "house_plan_versions"
    __table_args__ = (
        UniqueConstraint("plan_id", "version_no"),
        CheckConstraint(f"validity IN ({VALIDITIES})", name="validity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("house_plans.id", ondelete="RESTRICT"))
    version_no: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(80))
    revision_no: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(16))
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(String(64))
    validity: Mapped[str] = mapped_column(String(8))
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class HousePlanOp(Base):
    """One applied operation batch (Checkpoint 3, migration 0020): the operations, their inverse
    batch and who applied them. Revision n of a plan is revision n-1 with `ops` applied, so
    every head is reproducible from version 1 and the log. Append-only. Only batches the
    validator passed are applied and logged (IC 18.7)."""

    __tablename__ = "house_plan_ops"
    __table_args__ = (
        UniqueConstraint("plan_id", "revision_no"),
        CheckConstraint(f"reason IN ({OP_REASONS})", name="reason"),
        CheckConstraint("revision_no >= 1", name="revision_no_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("house_plans.id", ondelete="RESTRICT"))
    revision_no: Mapped[int] = mapped_column(Integer)
    ops: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    inverse: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(String(12))
    content_sha256: Mapped[str] = mapped_column(String(64))  # the resulting body
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


APPEND_ONLY = ("house_plan_versions", "house_plan_ops")
MUTABLE_COLUMNS = {
    "layout_rulesets": (
        "status",
        "approved_by",
        "approved_at",
        "published_by",
        "published_at",
        "retired_at",
    ),
    "house_plans": (
        "state",
        "started_at",
        "completed_at",
        "head_revision_no",
        "head_document",
        "head_validity",
        "head_report",
        "infeasibility",
        "failure_reason",
        "failure_detail",
        "solve_ms",
        "attempts",
        "version",
    ),
}
