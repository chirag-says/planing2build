"""Informational payment marks (Slice 3.7A, EX-05). Plan2Build never handles construction money
(CD-01): a mark records only that the owner says a milestone was paid, or the contractor says it
was received. There is no amount column, no contract value, no percentage and no settled state;
a mark never blocks or changes anything else."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base


class PaymentMark(Base):
    """Append-only; the latest mark per stage instance and side is the current one."""

    __tablename__ = "payment_marks"
    __table_args__ = (
        CheckConstraint("side IN ('PAID', 'RECEIVED')", name="side"),
        CheckConstraint("value IN ('YES', 'NO')", name="value"),
        CheckConstraint("marked_role IN ('FAMILY', 'PROFESSIONAL', 'OPS', 'ADMIN')", name="role"),
        # The owner marks PAID; the contractor (or operations for an OUTSIDE one) RECEIVED.
        CheckConstraint(
            "(side = 'PAID' AND marked_role = 'FAMILY') OR "
            "(side = 'RECEIVED' AND marked_role IN ('PROFESSIONAL', 'OPS', 'ADMIN'))",
            name="side_role",
        ),
        CheckConstraint("(side = 'RECEIVED') = (engagement_id IS NOT NULL)", name="engagement"),
        Index("ix_payment_marks_stage", "stage_instance_id", "side", "marked_at"),
        Index("ix_payment_marks_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    stage_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stage_instances.id", ondelete="RESTRICT")
    )
    side: Mapped[str] = mapped_column(String(10))
    value: Mapped[str] = mapped_column(String(3))
    engagement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_engagements.id", ondelete="RESTRICT")
    )
    note: Mapped[str | None] = mapped_column(Text)
    marked_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    marked_role: Mapped[str] = mapped_column(String(12))
    marked_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


APPEND_ONLY = ("payment_marks",)
