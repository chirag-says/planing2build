import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.models import AuditEvent, SecurityEvent
from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.request_context import current_request_id
from p2b.core.vocabulary import ActorType, Audience, SecuritySeverity


async def record(
    session: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    actor_type: ActorType,
    actor_user_id: uuid.UUID | None = None,
    actor_role: str | None = None,
    session_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    reason: str | None = None,
    is_override: bool = False,
) -> None:
    """Write one audit row in the caller's transaction, so it commits with the change it records."""
    await session.execute(
        insert(AuditEvent).values(
            id=new_id(),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            actor_type=actor_type.value,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            project_id=project_id,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            is_override=is_override,
            request_id=current_request_id(),
            session_id=session_id,
        )
    )


async def record_security_event(
    database: Database,
    *,
    kind: str,
    severity: SecuritySeverity,
    audience: Audience | None = None,
    user_id: uuid.UUID | None = None,
    contact_hash: str | None = None,
    ip_hash: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Security events commit on their own: a rejected request rolls back its business
    transaction, but the rejection itself must stay on record (SECURITY section 11)."""
    async with database.transaction() as session:
        await session.execute(
            insert(SecurityEvent).values(
                id=new_id(),
                kind=kind,
                severity=severity.value,
                audience=audience.value if audience else None,
                user_id=user_id,
                contact_hash=contact_hash,
                ip_hash=ip_hash,
                request_id=current_request_id(),
                details=details or {},
            )
        )


async def count_security_events(
    database: Database, *, kind: str, contact_hash: str, within: timedelta
) -> int:
    """Events of one kind for one contact in a trailing window (database time)."""
    async with database.transaction() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(SecurityEvent)
                .where(
                    SecurityEvent.kind == kind,
                    SecurityEvent.contact_hash == contact_hash,
                    SecurityEvent.at > func.now() - within,
                )
            )
            or 0
        )
