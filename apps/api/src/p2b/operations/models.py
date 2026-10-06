"""Operations tables (DATA_ARCHITECTURE 4.14 `ops_queue_items`)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base, Timestamps


class OpsQueueItem(Timestamps, Base):
    """One piece of work in a console queue. An open or claimed item is unique per reference;
    resolved items stay as history. Claiming says who is reviewing; it changes no business
    state (SUBMITTED already means "under Plan2Build review", STATE_MODEL 5)."""

    __tablename__ = "ops_queue_items"
    __table_args__ = (
        CheckConstraint("kind IN ('REQUIREMENT_REVIEW', 'PROFESSIONAL_REVIEW')", name="kind"),
        CheckConstraint("state IN ('OPEN', 'CLAIMED', 'RESOLVED')", name="state"),
        CheckConstraint(
            "(state = 'CLAIMED') = (claimed_by IS NOT NULL)", name="claimed_has_claimer"
        ),
        Index(
            "uq_ops_queue_items_open_ref",
            "kind",
            "ref_type",
            "ref_id",
            unique=True,
            postgresql_where=text("state <> 'RESOLVED'"),
        ),
        Index("ix_ops_queue_items_kind_state_created", "kind", "state", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    ref_type: Mapped[str] = mapped_column(String(40))
    ref_id: Mapped[uuid.UUID]
    state: Mapped[str] = mapped_column(String(20))
    priority: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    claimed_at: Mapped[datetime | None]
    resolved_at: Mapped[datetime | None]
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(server_default=text("1"))
