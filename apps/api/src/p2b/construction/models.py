"""Construction tables (DATA_ARCHITECTURE 4.11 `stage_instances`)."""

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
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
    version: Mapped[int] = mapped_column(server_default=text("1"))
