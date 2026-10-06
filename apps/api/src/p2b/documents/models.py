"""Tables owned by the documents module (DATA_ARCHITECTURE 4.14; ADR-011)."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base, Timestamps

FILE_STATES = (
    "'PENDING_UPLOAD', 'UPLOADED', 'SCANNING', 'AVAILABLE', 'QUARANTINED', 'FAILED', 'DELETED'"
)


class FileObject(Timestamps, Base):
    """Metadata for one immutable object. The original file name is metadata only; it never
    reaches a storage key."""

    __tablename__ = "file_objects"
    __table_args__ = (
        CheckConstraint(f"state IN ({FILE_STATES})", name="state"),
        CheckConstraint(
            "purpose IN ('REQUIREMENT_UPLOAD', 'AI_CONCEPT', 'VERIFICATION_EVIDENCE', "
            "'PORTFOLIO', 'INVOICE', 'QUOTE_DOCUMENT', 'DRAWING', 'BUILD_PLAN_EVIDENCE', "
            "'BUILD_PLAN_DOCUMENT', 'QUOTE_ATTACHMENT', 'COMPARISON_DOCUMENT')",
            name="purpose",
        ),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        Index("ix_file_objects_project_id", "project_id"),
        Index(
            "ix_file_objects_open_states",
            "state",
            postgresql_where=text("state IN ('PENDING_UPLOAD', 'UPLOADED', 'SCANNING')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    bucket: Mapped[str] = mapped_column(String(100))
    object_key: Mapped[str] = mapped_column(String(300), unique=True)
    purpose: Mapped[str] = mapped_column(String(40))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT")
    )
    original_name: Mapped[str] = mapped_column(String(200))
    declared_mime: Mapped[str] = mapped_column(String(100))
    detected_mime: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20))
    rejection_reason: Mapped[str | None] = mapped_column(String(60))
    available_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class DocumentAccessLog(Base):
    """Every issued download URL for a private file (SECURITY 8). Append-only (trigger)."""

    __tablename__ = "document_access_log"
    __table_args__ = (Index("ix_document_access_log_file_at", "file_id", "at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("file_objects.id", ondelete="RESTRICT"))
    viewer_user_id: Mapped[uuid.UUID | None]
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    at: Mapped[datetime] = mapped_column(server_default=text("now()"))
