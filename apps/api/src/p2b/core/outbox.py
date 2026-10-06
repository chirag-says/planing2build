"""Transactional outbox and its relay (EVENT_AND_BACKGROUND_JOB_ARCHITECTURE sections 1 and 2).

`publish` writes an event row through the caller's session, so the event exists if and only if the
business change commits. The relay, running in the worker, claims unprocessed rows with
`FOR UPDATE SKIP LOCKED`, runs the handlers subscribed to each event type, and marks the row
processed. Delivery is at least once; handlers must be idempotent. A failing row keeps
`processed_at` null, counts attempts, and stops being retried after MAX_ATTEMPTS (an alert fires).
"""

import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy import Index, String, Text, func, select, text, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base, Database
from p2b.core.ids import new_id
from p2b.core.request_context import current_request_id

log = structlog.get_logger(__name__)

# Rows reference aggregates by id only; the outbox carries no foreign keys by design.
MAX_ATTEMPTS = 10


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index(
            "ix_outbox_events_unprocessed",
            "occurred_at",
            "id",
            postgresql_where=text("processed_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100))
    aggregate_type: Mapped[str] = mapped_column(String(60))
    aggregate_id: Mapped[uuid.UUID]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    dedupe_key: Mapped[str] = mapped_column(String(300), unique=True)
    request_id: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now())
    processed_at: Mapped[datetime | None]
    attempts: Mapped[int] = mapped_column(server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)


class EventPayload(BaseModel):
    """Base for event payloads: ids and facts only, never personal data (P2, P3)."""

    schema_version: int = 1


async def publish(
    session: AsyncSession,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    payload: EventPayload,
    dedupe_suffix: str,
) -> None:
    """Write an event in the caller's transaction.

    `dedupe_suffix` names the transition or version (`{event_type}:{aggregate_id}:{suffix}`); the
    UNIQUE constraint rejects a second identical event, which signals a duplicated business write.
    """
    await session.execute(
        insert(OutboxEvent).values(
            id=new_id(),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload.model_dump(mode="json"),
            dedupe_key=f"{event_type}:{aggregate_id}:{dedupe_suffix}",
            request_id=current_request_id(),
        )
    )


@dataclass(frozen=True)
class DeliveredEvent:
    id: uuid.UUID
    event_type: str
    aggregate_type: str
    aggregate_id: uuid.UUID
    payload: dict[str, Any]
    request_id: str | None


Handler = Callable[[AsyncSession, DeliveredEvent], Awaitable[None]]


class HandlerRegistry:
    """Event type to handlers. Modules register handlers at worker start-up."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str) -> Callable[[Handler], Handler]:
        def register(handler: Handler) -> Handler:
            self._handlers[event_type].append(handler)
            return handler

        return register

    def handlers_for(self, event_type: str) -> list[Handler]:
        return list(self._handlers.get(event_type, ()))


async def relay_batch(database: Database, registry: HandlerRegistry, *, limit: int = 100) -> int:
    """Process one batch. Returns the number of rows claimed (0 means the outbox is drained).

    Each row's handlers run inside a savepoint: a failing row is rolled back and marked with the
    error, while the rest of the batch commits.
    """
    async with database.transaction() as session:
        rows = (
            await session.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.processed_at.is_(None), OutboxEvent.attempts < MAX_ATTEMPTS)
                .order_by(OutboxEvent.occurred_at, OutboxEvent.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for row in rows:
            event = DeliveredEvent(
                row.id, row.event_type, row.aggregate_type, row.aggregate_id, row.payload,
                row.request_id,
            )  # fmt: skip
            try:
                async with session.begin_nested():
                    for handler in registry.handlers_for(row.event_type):
                        await handler(session, event)
            except Exception as exc:  # noqa: BLE001 (a handler failure must not stop the relay)
                log.error(
                    "outbox.handler_failed", outbox_id=str(row.id), event_type=row.event_type,
                    error_class=type(exc).__name__, attempt=row.attempts + 1,
                )  # fmt: skip
                await session.execute(
                    update(OutboxEvent)
                    .where(OutboxEvent.id == row.id)
                    .values(
                        attempts=OutboxEvent.attempts + 1,
                        last_error=f"{type(exc).__name__}: {exc}"[:2000],
                    )
                )
                continue
            await session.execute(
                update(OutboxEvent).where(OutboxEvent.id == row.id).values(processed_at=func.now())
            )
        return len(rows)
