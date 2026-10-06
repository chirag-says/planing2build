"""Transactional outbox and relay (EVENT_AND_BACKGROUND_JOB_ARCHITECTURE sections 2 and 7)."""

import asyncio
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.outbox import (
    MAX_ATTEMPTS,
    DeliveredEvent,
    EventPayload,
    HandlerRegistry,
    OutboxEvent,
    publish,
    relay_batch,
)


class ThingDone(EventPayload):
    thing_id: uuid.UUID


async def _publish(
    database: Database, event_type: str = "thing.done", n: int = 1
) -> list[uuid.UUID]:
    ids = [new_id() for _ in range(n)]
    async with database.transaction() as session:
        for thing_id in ids:
            await publish(
                session, event_type=event_type, aggregate_type="thing", aggregate_id=thing_id,
                payload=ThingDone(thing_id=thing_id), dedupe_suffix="done",
            )  # fmt: skip
    return ids


async def _rows(database: Database) -> list[OutboxEvent]:
    async with database.transaction() as session:
        return list((await session.scalars(select(OutboxEvent).order_by(OutboxEvent.id))).all())


async def test_an_event_exists_only_if_the_business_transaction_commits(database: Database) -> None:
    class AbortError(Exception):
        pass

    async def write_then_fail() -> None:
        async with database.transaction() as session:
            await publish(
                session, event_type="thing.done", aggregate_type="thing", aggregate_id=new_id(),
                payload=EventPayload(), dedupe_suffix="done",
            )  # fmt: skip
            raise AbortError

    with pytest.raises(AbortError):
        await write_then_fail()
    assert await _rows(database) == []

    (thing_id,) = await _publish(database)
    (row,) = await _rows(database)
    assert row.payload == {"schema_version": 1, "thing_id": str(thing_id)}
    assert row.dedupe_key == f"thing.done:{thing_id}:done"


async def test_a_duplicate_event_is_rejected_by_its_dedupe_key(database: Database) -> None:
    thing_id = new_id()
    async with database.transaction() as session:
        await publish(
            session, event_type="thing.done", aggregate_type="thing", aggregate_id=thing_id,
            payload=EventPayload(), dedupe_suffix="done",
        )  # fmt: skip
    with pytest.raises(IntegrityError):
        async with database.transaction() as session:
            await publish(
                session, event_type="thing.done", aggregate_type="thing", aggregate_id=thing_id,
                payload=EventPayload(), dedupe_suffix="done",
            )  # fmt: skip


async def test_relay_delivers_each_event_to_its_handlers_and_marks_it_processed(
    database: Database,
) -> None:
    registry = HandlerRegistry()
    seen: list[str] = []

    @registry.subscribe("thing.done")
    async def handle(_: AsyncSession, event: DeliveredEvent) -> None:
        seen.append(event.payload["thing_id"])

    ids = await _publish(database, n=3)
    assert await relay_batch(database, registry) == 3
    assert seen == [str(i) for i in ids]  # in occurrence order
    assert all(row.processed_at is not None for row in await _rows(database))
    assert await relay_batch(database, registry) == 0  # drained


async def test_a_failing_handler_is_retried_and_does_not_block_other_events(
    database: Database,
) -> None:
    registry = HandlerRegistry()

    @registry.subscribe("thing.broken")
    async def explode(session: AsyncSession, _: DeliveredEvent) -> None:
        await session.execute(select(1))
        raise RuntimeError("handler bug")

    @registry.subscribe("thing.done")
    async def fine(_: AsyncSession, __: DeliveredEvent) -> None:
        return None

    await _publish(database, "thing.broken")
    await _publish(database, "thing.done")
    await relay_batch(database, registry)

    broken, done = sorted(await _rows(database), key=lambda r: r.event_type)
    assert broken.processed_at is None
    assert broken.attempts == 1
    assert broken.last_error == "RuntimeError: handler bug"
    assert done.processed_at is not None


async def test_relay_stops_claiming_after_the_attempt_limit(database: Database) -> None:
    registry = HandlerRegistry()

    @registry.subscribe("thing.broken")
    async def explode(_: AsyncSession, __: DeliveredEvent) -> None:
        raise RuntimeError("always")

    await _publish(database, "thing.broken")
    for _ in range(MAX_ATTEMPTS):
        assert await relay_batch(database, registry) == 1
    assert await relay_batch(database, registry) == 0
    (row,) = await _rows(database)
    assert row.attempts == MAX_ATTEMPTS
    assert row.processed_at is None


async def test_concurrent_relays_never_deliver_the_same_event_twice(database: Database) -> None:
    registry = HandlerRegistry()
    deliveries: list[str] = []

    @registry.subscribe("thing.done")
    async def slow(_: AsyncSession, event: DeliveredEvent) -> None:
        await asyncio.sleep(0.01)
        deliveries.append(event.payload["thing_id"])

    ids = await _publish(database, n=20)
    await asyncio.gather(*(relay_batch(database, registry, limit=5) for _ in range(4)))
    while await relay_batch(database, registry, limit=5):
        pass
    assert sorted(deliveries) == sorted(str(i) for i in ids)
