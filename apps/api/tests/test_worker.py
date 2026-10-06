"""Worker loops: heartbeat (CLOUD_AND_HOSTING 2.1) and outbox relay (EVENT_AND_BACKGROUND_JOB 2)."""

import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.outbox import DeliveredEvent, EventPayload, HandlerRegistry, OutboxEvent, publish
from p2b.worker import heartbeat_forever, relay_forever


async def test_relay_loop_drains_the_outbox_and_stops_on_request(database: Database) -> None:
    registry = HandlerRegistry()
    handled = asyncio.Event()

    @registry.subscribe("thing.done")
    async def handle(_: AsyncSession, __: DeliveredEvent) -> None:
        handled.set()

    async with database.transaction() as session:
        await publish(
            session, event_type="thing.done", aggregate_type="thing", aggregate_id=new_id(),
            payload=EventPayload(), dedupe_suffix="done",
        )  # fmt: skip
    stop = asyncio.Event()
    loop = asyncio.create_task(relay_forever(database, registry, stop))
    await asyncio.wait_for(handled.wait(), timeout=5)
    stop.set()
    await asyncio.wait_for(loop, timeout=5)
    async with database.transaction() as session:
        assert (await session.scalars(select(OutboxEvent.processed_at))).one() is not None


async def test_heartbeat_touches_its_file_until_stopped(tmp_path: Path) -> None:
    beat = tmp_path / "heartbeat"
    stop = asyncio.Event()
    task = asyncio.create_task(heartbeat_forever(beat, stop))
    for _ in range(50):
        if beat.exists():
            break
        await asyncio.sleep(0.02)
    assert beat.exists()
    stop.set()
    await asyncio.wait_for(task, timeout=5)
