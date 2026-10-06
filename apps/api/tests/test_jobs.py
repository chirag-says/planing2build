"""Job queue foundation (ADR-009): a relay handler defers a job; a worker runs it."""

from procrastinate import Blueprint
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.jobs import QUEUES, build_job_app
from p2b.core.outbox import DeliveredEvent, EventPayload, HandlerRegistry, publish, relay_batch

executed: list[str] = []
blueprint = Blueprint()


@blueprint.task(name="record_thing", queue="maintenance")
async def record_thing(thing_id: str) -> None:
    executed.append(thing_id)


async def test_event_to_job_to_execution(database: Database) -> None:
    job_app = build_job_app(get_settings(), [("test", blueprint)])
    registry = HandlerRegistry()

    @registry.subscribe("thing.done")
    async def defer_job(_: AsyncSession, event: DeliveredEvent) -> None:
        await job_app.configure_task("test:record_thing").defer_async(
            thing_id=str(event.aggregate_id)
        )

    thing_id = new_id()
    async with database.transaction() as session:
        await publish(
            session, event_type="thing.done", aggregate_type="thing", aggregate_id=thing_id,
            payload=EventPayload(), dedupe_suffix="done",
        )  # fmt: skip

    async with job_app.open_async():
        assert await relay_batch(database, registry) == 1
        await job_app.run_worker_async(
            queues=["maintenance"], wait=False, install_signal_handlers=False
        )
    assert executed == [str(thing_id)]


def test_queue_names_match_the_architecture() -> None:
    assert QUEUES == ("priority", "notify", "render", "files", "ai", "engine", "maintenance")
