"""Houseplans' outbox subscription: a committed generation request queues its job, once per plan
however often the event is delivered. All plan jobs share one Procrastinate `lock`, so the worker
runs them one at a time: the solve is CPU-bound and the VPS has two cores."""

from procrastinate import App
from procrastinate.exceptions import AlreadyEnqueued
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.outbox import DeliveredEvent, HandlerRegistry

JOB_NAMESPACE = "houseplans"
ENGINE_LOCK = "houseplans:engine"


def register(registry: HandlerRegistry, job_app: App) -> None:
    @registry.subscribe("houseplan.generation_requested")
    async def defer_generation(_: AsyncSession, event: DeliveredEvent) -> None:
        plan_id = str(event.payload["plan_id"])
        task = job_app.configure_task(
            f"{JOB_NAMESPACE}:generate_plan", queueing_lock=f"plan:{plan_id}", lock=ENGINE_LOCK
        )
        try:
            await task.defer_async(plan_id=plan_id)
        except AlreadyEnqueued:
            return
