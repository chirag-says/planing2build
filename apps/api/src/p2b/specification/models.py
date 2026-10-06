"""Specification tables (DATA_ARCHITECTURE 4.5 `project_spec_lines`, `spec_line_events`)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base, Timestamps

LINE_STATES = "'SPECIFIED', 'OPTIONS_ISSUED', 'CHOSEN', 'PURCHASED', 'INSTALLED', 'VERIFIED'"


class ProjectSpecLine(Timestamps, Base):
    """One of the 67 lines on one project: exactly one per code (ruling 2.3), whatever the number
    of floors. The issued criteria are copied from the master version at instantiation, so a
    later master never changes an issued line (S05 F1). The decide-by date waits for a schedule."""

    __tablename__ = "project_spec_lines"
    __table_args__ = (
        UniqueConstraint("project_id", "code"),
        CheckConstraint(f"state IN ({LINE_STATES})", name="state"),
        CheckConstraint("engineer_signoff IN ('PENDING', 'SIGNED', 'NOT_REQUIRED')",
                        name="engineer_signoff"),
        Index("ix_project_spec_lines_project_state", "project_id", "state"),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    code: Mapped[str] = mapped_column(ForeignKey("spec_line_masters.code", ondelete="RESTRICT"))
    master_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("spec_line_master_versions.id", ondelete="RESTRICT")
    )
    issued_criteria: Mapped[str] = mapped_column(Text)
    engineer_signoff: Mapped[str] = mapped_column(String(15))
    state: Mapped[str] = mapped_column(String(20))
    is_long_lead: Mapped[bool] = mapped_column(Boolean)
    decide_by: Mapped[date | None]
    consuming_stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_instances.id", ondelete="RESTRICT")
    )
    # The project value of the homeowner-accepted Build Plan version (Slice 3.5, PD-14).
    accepted_value_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("build_plan_spec_values.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(server_default=text("1"))


class SpecLineEvent(Base):
    """Append-only history of every line transition (DATA 4.5; STATE_MODEL 1 rule 3)."""

    __tablename__ = "spec_line_events"
    __table_args__ = (Index("ix_spec_line_events_line_at", "line_id", "at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project_spec_lines.id", ondelete="RESTRICT")
    )
    from_state: Mapped[str | None] = mapped_column(String(20))
    to_state: Mapped[str] = mapped_column(String(20))
    actor_user_id: Mapped[uuid.UUID | None]
    actor_role: Mapped[str | None] = mapped_column(String(30))
    at: Mapped[datetime] = mapped_column(server_default=func.now())
    reason: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
