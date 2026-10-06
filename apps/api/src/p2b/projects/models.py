"""Tables owned by the projects module (DATA_ARCHITECTURE 4.3, 4.15)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base, Timestamps

PROJECT_STATUSES = (
    "'DRAFT', 'SUBMITTED', 'NEEDS_INFO', 'ACCEPTED', 'PLANNING', 'PLAN_ISSUED', 'SOURCING', "
    "'CONTRACTED', 'BUILDING', 'HANDOVER_PENDING', 'COMPLETED', 'ARCHIVED', 'ON_HOLD', 'CANCELLED'"
)
MEMBERSHIP_ROLES = (
    "'OWNER', 'HOUSEHOLD', 'CONTRACTOR', 'ARCHITECT', "
    "'OPS_ADVISOR', 'OPS_FIELD', 'AUDITOR_ASSIGNED'"
)


class Project(Timestamps, Base):
    """The homeowner's aggregate root. The fact columns are filled from the requirement at
    submission; until then the requirement row holds the draft answers."""

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(f"status IN ({PROJECT_STATUSES})", name="status"),
        CheckConstraint("project_type IN ('NEW_HOME')", name="project_type"),
        Index("ix_projects_owner_user_id", "owner_user_id"),
        Index("ix_projects_status", "status"),
        Index("ix_projects_plot_geom", "plot_geom", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20))
    project_type: Mapped[str] = mapped_column(String(20))
    city_code: Mapped[str] = mapped_column(ForeignKey("cities.code", ondelete="RESTRICT"))
    locality: Mapped[str | None] = mapped_column(String(120))
    plot_geom: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    plot_area_sqft: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    built_up_area_sqft: Mapped[int | None] = mapped_column(Integer)
    floors: Mapped[int | None] = mapped_column(SmallInteger)
    has_basement: Mapped[bool | None] = mapped_column(Boolean)
    quality_tier: Mapped[str | None] = mapped_column(String(20))
    budget_band: Mapped[str | None] = mapped_column(String(20))
    start_window: Mapped[str | None] = mapped_column(String(20))
    submitted_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class ProjectRequirement(Timestamps, Base):
    """The family's answers, validated against the question set version they were saved under."""

    __tablename__ = "project_requirements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), unique=True
    )
    question_set_version: Mapped[int] = mapped_column(
        ForeignKey("requirement_question_sets.version", ondelete="RESTRICT")
    )
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    review_flags: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), server_default=text("'{}'::varchar[]")
    )
    submitted_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class ProjectMembership(Base):
    """Per-project roles; the authorisation primitive for every project-scoped request."""

    __tablename__ = "project_memberships"
    __table_args__ = (
        CheckConstraint(f"role IN ({MEMBERSHIP_ROLES})", name="role"),
        UniqueConstraint("project_id", "user_id", "role"),
        Index("ix_project_memberships_active_user", "user_id",
              postgresql_where=text("revoked_at IS NULL")),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    role: Mapped[str] = mapped_column(String(20))
    granted_by: Mapped[uuid.UUID | None]
    granted_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    revoked_at: Mapped[datetime | None]


class ProjectStatusHistory(Base):
    """Append-only (trigger)."""

    __tablename__ = "project_status_history"
    __table_args__ = (Index("ix_project_status_history_project_at", "project_id", "at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    actor_user_id: Mapped[uuid.UUID | None]
    reason: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Enquiry(Base):
    """Contact captured before an account exists (REQUIREMENT_QUESTIONS_V1 L.3). Email is P2."""

    __tablename__ = "enquiries"
    __table_args__ = (
        CheckConstraint("kind IN ('COMING_SOON_HELP', 'OTHER_CITY')", name="kind"),
        CheckConstraint(
            "work_type IS NULL OR work_type IN ('RENOVATION', 'INTERIORS', 'REPAIRS')",
            name="work_type",
        ),
        CheckConstraint(
            "(kind = 'COMING_SOON_HELP') = (work_type IS NOT NULL)", name="work_type_for_help"
        ),
        Index("ix_enquiries_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    work_type: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(320))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    converted_user_id: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class GeocodeCache(Base):
    """Reverse-geocoding results by rounded coordinates (INTEGRATION section 5)."""

    __tablename__ = "geocode_cache"

    query_normalised: Mapped[str] = mapped_column(String(80), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    locality: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(200))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class ProjectEstimate(Base):
    """The indicative construction estimate stored against a project at each submission (Slice
    3.0; PD-04: never a quote and never the package fee). Immutable (append-only trigger): a
    resubmission adds a row, so every figure can be traced to the rate card version it used."""

    __tablename__ = "project_estimates"
    __table_args__ = (
        UniqueConstraint("project_id", "requirement_version"),
        CheckConstraint("status IN ('AVAILABLE', 'UNAVAILABLE')", name="status"),
        CheckConstraint(
            "unavailable_reason IS NULL OR "
            "unavailable_reason IN ('BUILT_UP_AREA_NOT_GIVEN', 'NO_RATE_CARD')",
            name="unavailable_reason",
        ),
        CheckConstraint(
            "(status = 'AVAILABLE') = (result IS NOT NULL AND rate_card_id IS NOT NULL "
            "AND unavailable_reason IS NULL)",
            name="available_has_result",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    requirement_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12))
    unavailable_reason: Mapped[str | None] = mapped_column(String(30))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rate_card_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rate_cards.id", ondelete="RESTRICT")
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class EligibilityAssessment(Base):
    """Operations' record of the package-eligibility checklist when accepting a project (F-05,
    L-02): the checklist version and every item's outcome and note. Accepting needs every item
    PASSED. Append-only (trigger). Projects accepted before checklist version 1 have none."""

    __tablename__ = "eligibility_assessments"
    __table_args__ = (UniqueConstraint("project_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    checklist_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eligibility_checklist_versions.id", ondelete="RESTRICT")
    )
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    assessed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assessed_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
