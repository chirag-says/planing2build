"""Tables owned by the designs module (Slice 3.1)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
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

from p2b.core.db import Base, Timestamps

STATES = "'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED'"
VIEWS = "'EXTERIOR', 'INTERIOR'"
REASONS = (
    "'PROVIDER_UNAVAILABLE', 'PROVIDER_TIMEOUT', 'PROVIDER_REJECTED', 'PROVIDER_ERROR', "
    "'INVALID_OUTPUT', 'STALE'"
)


class DesignPromptTemplate(Timestamps, Base):
    """A versioned prompt per view. Never edited in place: a change is a new version, and every
    generation names the version it used."""

    __tablename__ = "design_prompt_templates"
    __table_args__ = (
        UniqueConstraint("view", "version"),
        CheckConstraint(f"view IN ({VIEWS})", name="view"),
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
        Index("uq_design_prompt_templates_one_active", "view", unique=True,
              postgresql_where=text("status = 'ACTIVE'")),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    view: Mapped[str] = mapped_column(String(10))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))
    body: Mapped[str] = mapped_column(Text)
    negative_prompt: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text)


class DesignGeneration(Base):
    """One request for an illustrative concept image, with everything needed to reproduce it:
    the sanitised requirement snapshot, the template version and the exact provider request.

    Never authoritative (CHECK). A failed generation consumes nothing: quotas count only
    QUEUED, RUNNING and SUCCEEDED rows. `credit_ref` is where Slice 3.3 links a paid AI credit."""

    __tablename__ = "design_generations"
    __table_args__ = (
        UniqueConstraint("project_id", "sequence"),
        CheckConstraint(f"state IN ({STATES})", name="state"),
        CheckConstraint(f"view IN ({VIEWS})", name="view"),
        CheckConstraint("funding IN ('FREE', 'PAID')", name="funding"),
        CheckConstraint(f"failure_reason IS NULL OR failure_reason IN ({REASONS})",
                        name="failure_reason"),
        CheckConstraint("is_authoritative = false", name="never_authoritative"),
        CheckConstraint("(state = 'SUCCEEDED') = (output_file_id IS NOT NULL)",
                        name="output_iff_succeeded"),
        CheckConstraint("(state = 'FAILED') = (failure_reason IS NOT NULL)",
                        name="reason_iff_failed"),
        CheckConstraint("funding = 'FREE' OR credit_ref IS NOT NULL", name="paid_names_credit"),
        Index("ix_design_generations_requested_by_created_at", "requested_by", "created_at"),
        Index("ix_design_generations_project_id_state", "project_id", "state"),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    sequence: Mapped[int] = mapped_column(Integer)
    view: Mapped[str] = mapped_column(String(10))
    funding: Mapped[str] = mapped_column(String(4))
    credit_ref: Mapped[uuid.UUID | None]
    free_quota: Mapped[int] = mapped_column(SmallInteger)  # the quota in force at the request
    state: Mapped[str] = mapped_column(String(10))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    prompt_template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("design_prompt_templates.id", ondelete="RESTRICT")
    )
    prompt_template_version: Mapped[int] = mapped_column(Integer)
    question_set_version: Mapped[int] = mapped_column(Integer)
    requirement_version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    provider_request: Mapped[dict[str, Any]] = mapped_column(JSONB)
    output_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("file_objects.id", ondelete="RESTRICT")
    )
    failure_reason: Mapped[str | None] = mapped_column(String(30))
    failure_detail: Mapped[str | None] = mapped_column(Text)  # internal; never sent to the family
    provider_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    is_authoritative: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class DesignReference(Base):
    """The family marked a concept as a reference for later design work. A reference only: the
    authority column can hold nothing but ILLUSTRATIVE_ONLY, so no reference can be read as a
    drawing, an approval or a BOQ or RFQ input. Reversible: removing it sets `removed_at` (the
    history stays); at most one active reference per concept."""

    __tablename__ = "design_references"
    __table_args__ = (
        CheckConstraint("authority = 'ILLUSTRATIVE_ONLY'", name="illustrative_only"),
        CheckConstraint("(removed_at IS NULL) = (removed_by IS NULL)", name="removal_named"),
        Index("ix_design_references_project_id", "project_id"),
        Index("uq_design_references_active", "generation_id", unique=True,
              postgresql_where=text("removed_at IS NULL")),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    generation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("design_generations.id", ondelete="RESTRICT")
    )
    authority: Mapped[str] = mapped_column(String(20), server_default="ILLUSTRATIVE_ONLY")
    marked_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    marked_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    removed_at: Mapped[datetime | None]
    removed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
