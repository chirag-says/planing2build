"""Append-only audit and security events (DATA_ARCHITECTURE 4.14). No UPDATE or DELETE ever:
the migration revokes those grants from app_rw and adds a trigger that raises on either."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("actor_type IN ('USER', 'SYSTEM', 'JOB')", name="actor_type"),
        Index("ix_audit_events_entity", "entity_type", "entity_id", "at"),
        Index("ix_audit_events_actor", "actor_user_id", "at"),
        Index("ix_audit_events_project", "project_id", "at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(server_default=func.now())
    actor_user_id: Mapped[uuid.UUID | None]
    actor_role: Mapped[str | None] = mapped_column(String(40))
    actor_type: Mapped[str] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[uuid.UUID]
    project_id: Mapped[uuid.UUID | None]
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    is_override: Mapped[bool] = mapped_column(Boolean, server_default="false")
    request_id: Mapped[str | None] = mapped_column(String(64))
    session_id: Mapped[uuid.UUID | None]


class SecurityEvent(Base):
    __tablename__ = "security_events"
    __table_args__ = (
        CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name="severity"),
        Index("ix_security_events_kind_at", "kind", "at"),
        Index("ix_security_events_kind_contact_at", "kind", "contact_hash", "at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(server_default=func.now())
    kind: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(10))
    audience: Mapped[str | None] = mapped_column(String(3))
    user_id: Mapped[uuid.UUID | None]
    contact_hash: Mapped[str | None] = mapped_column(String(64))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
