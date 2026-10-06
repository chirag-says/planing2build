"""Designs' outbox subscription: a committed generation request queues its job (one per
generation, however often the event is delivered)."""

from procrastinate import App
from procrastinate.exceptions import AlreadyEnqueued
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.outbox import DeliveredEvent, HandlerRegistry

JOB_NAMESPACE = "designs"


def register(registry: HandlerRegistry, job_app: App) -> None:
    @registry.subscribe("design.generation_requested")
    async def defer_generation(_: AsyncSession, event: DeliveredEvent) -> None:
        generation_id = str(event.payload["generation_id"])
        task = job_app.configure_task(
            f"{JOB_NAMESPACE}:generate_design", queueing_lock=f"design:{generation_id}"
        )
        try:
            await task.defer_async(generation_id=generation_id)
        except AlreadyEnqueued:
            return
