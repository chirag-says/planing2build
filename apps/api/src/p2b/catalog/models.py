"""Catalog tables owned by this module (DATA_ARCHITECTURE 4.4): cities, rate cards, versioned stage
masters and versioned requirement question sets."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base, Timestamps


class RateCard(Timestamps, Base):
    """A versioned city rate card (S05 F2). Published versions are never edited; a new version is a
    new row, so every estimate can be regenerated from the version it used. `is_demo` cards come
    from the S14 prototype values and are never served in production (Chirag, 2026-10-04)."""

    __tablename__ = "rate_cards"
    __table_args__ = (
        UniqueConstraint("city", "version"),
        CheckConstraint("is_demo OR published_by IS NOT NULL", name="approved_card_has_publisher"),
        Index("ix_rate_cards_city_valid_from", "city", "valid_from"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    city: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(SmallInteger)
    rates: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_demo: Mapped[bool] = mapped_column(Boolean)
    label: Mapped[str] = mapped_column(String(200))
    valid_from: Mapped[datetime]
    published_by: Mapped[uuid.UUID | None]


class ItemRateCard(Base):
    """An item rate card for Build Plan BOQs (Slice 3.5, BP-06): per geography and version.
    Operations prepare a DRAFT; an ADMIN publishes it; a published card never changes (its lines
    are frozen by trigger). DEMO cards are development values, never issued in production. These
    rates are Plan2Build's internal costing data and never reach a contractor (BP-08)."""

    __tablename__ = "item_rate_cards"
    __table_args__ = (
        UniqueConstraint("geography", "version"),
        CheckConstraint("status IN ('DRAFT', 'PUBLISHED', 'RETIRED')", name="status"),
        CheckConstraint(
            "status = 'DRAFT' OR (published_by IS NOT NULL AND published_at IS NOT NULL)",
            name="published_has_publisher",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="effective_range"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    geography: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))
    is_demo: Mapped[bool] = mapped_column(Boolean)
    effective_from: Mapped[date]
    effective_to: Mapped[date | None]
    source_reference: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    prepared_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    prepared_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    published_at: Mapped[datetime | None]
    retired_at: Mapped[datetime | None]


class ItemRateCardLine(Base):
    __tablename__ = "item_rate_card_lines"
    __table_args__ = (
        UniqueConstraint("card_id", "item_code"),
        CheckConstraint("rate >= 0", name="rate"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    card_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("item_rate_cards.id", ondelete="RESTRICT")
    )
    item_code: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(20))
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class City(Timestamps, Base):
    """City reference data (S05 section 5: name, state, active flag). Raipur only in the POC
    (CD-07); further cities are rows, not code (Chirag, 2026-10-04: pan-India in phase 2)."""

    __tablename__ = "cities"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    state: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean)


class StageMasterVersion(Timestamps, Base):
    """One version of the stage configuration. Durations and cost shares are nullable on purpose:
    none are approved yet, and planned dates come only from an approved configuration or a
    schedule operations enter (Chirag, 2026-10-04)."""

    __tablename__ = "stage_master_versions"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
        Index("uq_stage_master_versions_one_active", "status", unique=True,
              postgresql_where=text("status = 'ACTIVE'")),
    )  # fmt: skip

    version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    status: Mapped[str] = mapped_column(String(10))
    source_note: Mapped[str] = mapped_column(Text)
    approved_by: Mapped[uuid.UUID | None]
    activated_at: Mapped[datetime | None]


class StageMaster(Base):
    """A stage in one configuration version (S04 section 4; IHB_FLOW 8.9)."""

    __tablename__ = "stage_masters"
    __table_args__ = (
        UniqueConstraint("version", "number"),
        UniqueConstraint("version", "code"),
        CheckConstraint("number BETWEEN 1 AND 16", name="number"),
        CheckConstraint("default_duration_days IS NULL OR default_duration_days > 0",
                        name="duration_positive"),
        CheckConstraint("cost_share_pct IS NULL OR (cost_share_pct >= 0 AND cost_share_pct <= 100)",
                        name="cost_share_range"),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(
        ForeignKey("stage_master_versions.version", ondelete="RESTRICT")
    )
    number: Mapped[int] = mapped_column(SmallInteger)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    sequence: Mapped[int] = mapped_column(SmallInteger)
    is_audit_gate: Mapped[bool] = mapped_column(Boolean)
    is_payment_milestone: Mapped[bool] = mapped_column(Boolean)
    repeats_per_floor: Mapped[bool] = mapped_column(Boolean)
    default_duration_days: Mapped[int | None] = mapped_column(Integer)
    cost_share_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))


class RequirementQuestionSet(Timestamps, Base):
    """A version of the homeowner requirement form (REQUIREMENT_QUESTIONS_V1, locked). Answers are
    always validated against the version they were saved under."""

    __tablename__ = "requirement_question_sets"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
        Index("uq_requirement_question_sets_one_active", "status", unique=True,
              postgresql_where=text("status = 'ACTIVE'")),
    )  # fmt: skip

    version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    status: Mapped[str] = mapped_column(String(10))
    locale: Mapped[str] = mapped_column(String(10))
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source_document: Mapped[str] = mapped_column(String(200))
    approved_note: Mapped[str] = mapped_column(Text)


class SpecGroup(Base):
    """The three specification groups: A Structure, B Concealed systems, C Finishes. S04 (table 3)
    calls them packages; they are groupings and timing of the 67 lines only, never products or
    payments (PD-09). `issued` is S04's timing text, kept as written."""

    __tablename__ = "spec_groups"

    code: Mapped[str] = mapped_column(String(1), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    issued: Mapped[str] = mapped_column(String(120))
    sequence: Mapped[int] = mapped_column(SmallInteger)


class SpecLineMaster(Base):
    """One of the 67 specification lines (S04 tables 5 to 7; DATA 4.4). Codes are immutable and
    never reused. A structural line never carries a brand category (S04 R9; rulings D-03, 2.4)."""

    __tablename__ = "spec_line_masters"
    __table_args__ = (
        CheckConstraint("NOT (is_structural AND brand_category IS NOT NULL)",
                        name="structural_has_no_brand"),
        CheckConstraint("decide_by_weeks > 0", name="decide_by_positive"),
        CheckConstraint("cardinality(consuming_stages) >= 1", name="has_consuming_stage"),
    )  # fmt: skip

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    spec_group: Mapped[str] = mapped_column(ForeignKey("spec_groups.code", ondelete="RESTRICT"))
    sequence: Mapped[int] = mapped_column(SmallInteger)
    item: Mapped[str] = mapped_column(String(120))
    consuming_stages: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger))
    decide_by_weeks: Mapped[int] = mapped_column(SmallInteger)
    verified_at: Mapped[str | None] = mapped_column(String(120))
    brand_category: Mapped[str | None] = mapped_column(String(60))
    is_structural: Mapped[bool] = mapped_column(Boolean)
    is_long_lead: Mapped[bool] = mapped_column(Boolean)


class SpecLineMasterVersion(Timestamps, Base):
    """Issued criteria for a line, versioned per line so a structural line can be re-issued once a
    structural engineer signs it, without touching the others. Never edited in place."""

    __tablename__ = "spec_line_master_versions"
    __table_args__ = (
        UniqueConstraint("code", "version"),
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
        CheckConstraint("engineer_signoff IN ('PENDING', 'SIGNED', 'NOT_REQUIRED')",
                        name="engineer_signoff"),
        Index("uq_spec_line_master_versions_one_active", "code", unique=True,
              postgresql_where=text("status = 'ACTIVE'")),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(ForeignKey("spec_line_masters.code", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))
    performance_specification: Mapped[str] = mapped_column(Text)
    engineer_signoff: Mapped[str] = mapped_column(String(15))
    approved_note: Mapped[str] = mapped_column(Text)
    approved_by: Mapped[uuid.UUID | None]
    activated_at: Mapped[datetime | None]


class ServiceCategory(Base):
    """A professional category or a subtype of one (D-06): data, so a category or subtype is
    added without code. Subtypes (`parent_code` set) share their parent's listing requirements."""

    __tablename__ = "service_categories"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    parent_code: Mapped[str | None] = mapped_column(
        ForeignKey("service_categories.code", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(80))
    sequence: Mapped[int] = mapped_column(SmallInteger)
    active: Mapped[bool] = mapped_column(Boolean)


class ListingRequirementVersion(Timestamps, Base):
    """What a category must pass to be listed (D-02), versioned; one ACTIVE per category. Each
    category row records the version it was reviewed against, so a later version never changes
    a past decision. `requirements` is validated by `catalog.listing.RequirementSet`."""

    __tablename__ = "listing_requirement_versions"
    __table_args__ = (
        UniqueConstraint("category_code", "version"),
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
        CheckConstraint("validity_months > 0 AND reapply_months >= 0", name="periods"),
        Index("uq_listing_requirement_versions_one_active", "category_code", unique=True,
              postgresql_where=text("status = 'ACTIVE'")),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    category_code: Mapped[str] = mapped_column(
        ForeignKey("service_categories.code", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))
    requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    validity_months: Mapped[int] = mapped_column(SmallInteger)
    reapply_months: Mapped[int] = mapped_column(SmallInteger)
    note: Mapped[str] = mapped_column(Text)


class EligibilityChecklistVersion(Base):
    """What operations confirm before accepting a project (F-05, L-02), versioned; one ACTIVE.
    Accepting records the version and each item's outcome (projects: eligibility_assessments).
    Immutable once published except for its lifecycle columns."""

    __tablename__ = "eligibility_checklist_versions"
    __table_args__ = (
        UniqueConstraint("version"),
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
        Index("uq_eligibility_checklist_versions_one_active", "status", unique=True,
              postgresql_where=text("status = 'ACTIVE'")),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    note: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    published_by: Mapped[uuid.UUID | None]
    published_at: Mapped[datetime | None]


class ServiceValueCategory(Base):
    """How a requirement's services answer maps to a professional category (Slice 3.4, N-01).
    The requirement's service labels and the category taxonomy stay separate concepts; this
    table is the only bridge, per question-set version. A value with no row (project management,
    approvals) creates no professional need."""

    __tablename__ = "service_value_categories"

    question_set_version: Mapped[int] = mapped_column(
        ForeignKey("requirement_question_sets.version", ondelete="RESTRICT"), primary_key=True
    )
    service_value: Mapped[str] = mapped_column(String(40), primary_key=True)
    category_code: Mapped[str] = mapped_column(
        ForeignKey("service_categories.code", ondelete="RESTRICT")
    )
