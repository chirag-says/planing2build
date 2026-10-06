"""Tables owned by the professionals module (Slice 3.2; SLICE3_2_READINESS K0).

Professional → professional category → verification (cases, checks, evidence) → listing state.
Listing is per professional and category; nothing here links a professional to a project. There
is no membership, tier or class (PD-18; D-05 open)."""

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    ARRAY,
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

LISTING_STATES = "'DRAFT', 'PENDING_REVIEW', 'CHANGES_REQUESTED', 'LISTED', 'REJECTED', 'SUSPENDED'"
CHECK_KINDS = "'IDENTITY', 'BUSINESS', 'REGISTRATION', 'PORTFOLIO', 'REFERENCE', 'SITE_VISIT'"


class ProfessionalProfile(Timestamps, Base):
    """One per professional account. Public fields are listed in D-01; the base point is
    private (the public sees the locality and the radius)."""

    __tablename__ = "professional_profiles"
    __table_args__ = (
        CheckConstraint(
            "service_radius_km IS NULL OR service_radius_km BETWEEN 1 AND 300", name="radius"
        ),
        CheckConstraint(
            "years_experience IS NULL OR years_experience BETWEEN 0 AND 80", name="experience"
        ),
        CheckConstraint("team_size IS NULL OR team_size BETWEEN 1 AND 10000", name="team_size"),
        Index("ix_professional_profiles_base_geom", "base_geom", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), unique=True
    )
    display_name: Mapped[str | None] = mapped_column(String(120))
    firm_name: Mapped[str | None] = mapped_column(String(160))
    bio: Mapped[str | None] = mapped_column(Text)
    years_experience: Mapped[int | None] = mapped_column(SmallInteger)
    team_size: Mapped[int | None] = mapped_column(Integer)
    base_locality: Mapped[str | None] = mapped_column(String(120))
    base_geom: Mapped[Any | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    service_radius_km: Mapped[int | None] = mapped_column(SmallInteger)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )  # set when operations created the account (D-04)
    version: Mapped[int] = mapped_column(server_default=text("1"))


class ProfessionalCategory(Timestamps, Base):
    """The listing unit: one professional in one category (D-06). `listing_state` changes only
    through the transition table; `hidden` is the professional's own visibility switch (D-11),
    separate from the state, so a suspension and reinstatement keep the professional's choice.
    Public means LISTED and not hidden."""

    __tablename__ = "professional_categories"
    __table_args__ = (
        UniqueConstraint("profile_id", "category_code"),
        CheckConstraint(f"listing_state IN ({LISTING_STATES})", name="listing_state"),
        Index(
            "ix_professional_categories_listed",
            "category_code",
            postgresql_where=text("listing_state = 'LISTED' AND NOT hidden"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("professional_profiles.id", ondelete="RESTRICT")
    )
    category_code: Mapped[str] = mapped_column(
        ForeignKey("service_categories.code", ondelete="RESTRICT")
    )
    subtypes: Mapped[list[str]] = mapped_column(ARRAY(String(40)), server_default="{}")
    listing_state: Mapped[str] = mapped_column(String(20))
    hidden: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    requirement_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("listing_requirement_versions.id", ondelete="RESTRICT")
    )
    submitted_at: Mapped[datetime | None]
    listed_at: Mapped[datetime | None]
    review_due_at: Mapped[datetime | None]
    reapply_after: Mapped[datetime | None]
    message: Mapped[str | None] = mapped_column(Text)  # what operations told the professional
    version: Mapped[int] = mapped_column(server_default=text("1"))


class VerificationCase(Base):
    """One review of one category against one requirement version. At most one open case per
    category. `internal_note` is for operations only."""

    __tablename__ = "verification_cases"
    __table_args__ = (
        CheckConstraint(
            "decision IS NULL OR decision IN ('APPROVED', 'CHANGES_REQUESTED', 'REJECTED')",
            name="decision",
        ),
        CheckConstraint("(decision IS NULL) = (decided_at IS NULL)", name="decided_together"),
        Index(
            "uq_verification_cases_one_open",
            "professional_category_id",
            unique=True,
            postgresql_where=text("decided_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    professional_category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("professional_categories.id", ondelete="RESTRICT")
    )
    requirement_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listing_requirement_versions.id", ondelete="RESTRICT")
    )
    opened_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    decision: Mapped[str | None] = mapped_column(String(20))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    decided_at: Mapped[datetime | None]
    message_to_professional: Mapped[str | None] = mapped_column(Text)
    internal_note: Mapped[str | None] = mapped_column(Text)


class VerificationCheck(Base):
    """One check result recorded by operations. Append-only (trigger): a correction is a new
    row; the latest row per kind and subject counts."""

    __tablename__ = "verification_checks"
    __table_args__ = (
        CheckConstraint(f"kind IN ({CHECK_KINDS})", name="kind"),
        CheckConstraint("outcome IN ('PASSED', 'FAILED', 'NOT_APPLICABLE')", name="outcome"),
        Index("ix_verification_checks_case_id", "case_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("verification_cases.id", ondelete="RESTRICT")
    )
    kind: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(80))  # what was checked: a reference id, "visit"
    outcome: Mapped[str] = mapped_column(String(20))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    internal_note: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    recorded_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class ProfessionalDocument(Base):
    """A document the professional supplies (identity, business, registration). `category_code`
    null means it serves every category (identity, for example). Never public."""

    __tablename__ = "professional_documents"
    __table_args__ = (
        CheckConstraint("kind IN ('IDENTITY', 'BUSINESS', 'REGISTRATION')", name="kind"),
        Index("ix_professional_documents_profile_id", "profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("professional_profiles.id", ondelete="RESTRICT")
    )
    category_code: Mapped[str | None] = mapped_column(
        ForeignKey("service_categories.code", ondelete="RESTRICT")
    )
    kind: Mapped[str] = mapped_column(String(20))
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("file_objects.id", ondelete="RESTRICT"))
    # Optional particulars: issuing body and number for a registration, GSTIN for a business.
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    removed_at: Mapped[datetime | None]


class ProfessionalReference(Base):
    """A client or peer operations may call. Personal data (P2): operations only."""

    __tablename__ = "professional_references"
    __table_args__ = (Index("ix_professional_references_profile_id", "profile_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("professional_profiles.id", ondelete="RESTRICT")
    )
    category_code: Mapped[str] = mapped_column(
        ForeignKey("service_categories.code", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))
    project_note: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    removed_at: Mapped[datetime | None]


class PortfolioItem(Base):
    """A work image. Public only once operations approve it."""

    __tablename__ = "portfolio_items"
    __table_args__ = (
        CheckConstraint("review_state IN ('PENDING', 'APPROVED', 'REJECTED')", name="review_state"),
        Index("ix_portfolio_items_profile_id", "profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("professional_profiles.id", ondelete="RESTRICT")
    )
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("file_objects.id", ondelete="RESTRICT"))
    caption: Mapped[str] = mapped_column(String(200))
    review_state: Mapped[str] = mapped_column(String(10), server_default="PENDING")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    reviewed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    removed_at: Mapped[datetime | None]


class ListingHistory(Base):
    """Every change of a category's listing state or visibility, with who and why. Append-only
    (trigger); operations see it whole, the professional sees state and the message only."""

    __tablename__ = "professional_listing_history"
    __table_args__ = (
        Index("ix_professional_listing_history_category", "professional_category_id", "at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    professional_category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("professional_categories.id", ondelete="RESTRICT")
    )
    event: Mapped[str] = mapped_column(String(30))  # transition trigger, or hide / show
    from_state: Mapped[str | None] = mapped_column(String(20))
    to_state: Mapped[str] = mapped_column(String(20))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    actor_role: Mapped[str] = mapped_column(String(20))  # PROFESSIONAL, OPS, ADMIN
    reason: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(server_default=text("now()"))
