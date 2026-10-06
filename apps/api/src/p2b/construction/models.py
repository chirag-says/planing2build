"""Construction tables (DATA_ARCHITECTURE 4.11 `stage_instances`; Slice 3.7A: progress updates and
the execution history)."""

import uuid
from datetime import date, datetime

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
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base, Timestamps

STAGE_STATES = (
    "'NOT_STARTED', 'IN_PROGRESS', 'COMPLETION_REQUESTED', 'COMPLETED', 'BLOCKED', 'ON_HOLD'"
)
GATE_STATUSES = "'NOT_INSPECTED', 'SCHEDULED', 'OPEN_NC', 'CLEARED'"


class StageInstance(Timestamps, Base):
    """One stage of one project (STATE_MODEL 6). Stages that repeat per floor (5, 6, 9) have one
    instance per floor: `floor` -1 is the basement, 0 the ground floor, 1 to 3 the floors above;
    other stages have `floor` NULL. Planned dates stay NULL until an approved stage configuration
    or an operations-entered schedule exists (ruling 2.9): the UI says "Schedule to be confirmed".
    """

    __tablename__ = "stage_instances"
    __table_args__ = (
        UniqueConstraint("project_id", "stage_number", "floor", postgresql_nulls_not_distinct=True),
        CheckConstraint(f"state IN ({STAGE_STATES})", name="state"),
        CheckConstraint(
            f"gate_status IS NULL OR gate_status IN ({GATE_STATUSES})", name="gate_status"
        ),
        CheckConstraint("(gate_status IS NOT NULL) = is_gate", name="gate_status_on_gates"),
        CheckConstraint("stage_number BETWEEN 1 AND 16", name="stage_number"),
        CheckConstraint("floor IS NULL OR floor BETWEEN -1 AND 3", name="floor"),
        # EX-04 and BP-07A: no authoritative construction dates until the build order exists.
        CheckConstraint(
            "planned_start IS NULL AND planned_end IS NULL", name="dates_not_calculated_bp07a"
        ),
        Index("ix_stage_instances_project_sequence", "project_id", "sequence"),
    )  # fmt: skip

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    stage_master_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_masters.id", ondelete="RESTRICT")
    )
    stage_number: Mapped[int] = mapped_column(SmallInteger)
    floor: Mapped[int | None] = mapped_column(SmallInteger)
    sequence: Mapped[int] = mapped_column(SmallInteger)
    state: Mapped[str] = mapped_column(String(25))
    is_gate: Mapped[bool] = mapped_column(Boolean)
    gate_status: Mapped[str | None] = mapped_column(String(20))
    is_payment_milestone: Mapped[bool] = mapped_column(Boolean)
    planned_start: Mapped[date | None]
    planned_end: Mapped[date | None]
    actual_start: Mapped[date | None]
    actual_end: Mapped[date | None]
    # The latest completion request (Slice 3.7A); the operations exception for an unanswered
    # request reads it (EX-12).
    completion_requested_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class StageUpdate(Base):
    """A progress update in the standard format (EX-02): evidence and history, never a promise
    of schedule completion. Append-only; a correction is a new update naming the one it
    corrects. `engagement_id` is the CONTRACTOR engagement the update was made under, so history
    stays with the contractor who reported it (EX-19)."""

    __tablename__ = "stage_updates"
    __table_args__ = (
        CheckConstraint("kind IN ('PROGRESS', 'COMPLETION_REQUEST')", name="kind"),
        CheckConstraint("cardinality(file_ids) >= 1", name="has_photos"),
        CheckConstraint("posted_role IN ('PROFESSIONAL', 'OPS', 'ADMIN')", name="posted_role"),
        Index("ix_stage_updates_stage", "stage_instance_id", "posted_at"),
        Index("ix_stage_updates_project", "project_id", "posted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_instances.id", ondelete="RESTRICT")
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("project_engagements.id", ondelete="RESTRICT")
    )
    kind: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text)
    materials: Mapped[str | None] = mapped_column(Text)
    open_problems: Mapped[str | None] = mapped_column(Text)
    file_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid))
    corrects_update_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("stage_updates.id", ondelete="RESTRICT")
    )
    posted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    posted_role: Mapped[str] = mapped_column(String(12))
    posted_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class ConstructionEvent(Base):
    """History of stage transitions, contractor changes on a stage (EX-19) and gate status
    changes made by assurance (3.7B). Append-only."""

    __tablename__ = "construction_events"
    __table_args__ = (
        CheckConstraint("subject IN ('STAGE', 'CONTRACTOR', 'GATE')", name="subject"),
        Index("ix_construction_events_project", "project_id", "at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_instances.id", ondelete="RESTRICT")
    )
    subject: Mapped[str] = mapped_column(String(12))
    from_state: Mapped[str | None] = mapped_column(String(40))
    to_state: Mapped[str] = mapped_column(String(40))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    actor_role: Mapped[str] = mapped_column(String(12))
    reason: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(server_default=text("now()"))


APPEND_ONLY = ("stage_updates", "construction_events")
MUTABLE_COLUMNS = {
    "stage_instances": (
        "state",
        "gate_status",
        "actual_start",
        "actual_end",
        "completion_requested_at",
        "updated_at",
        "version",
    ),
}
