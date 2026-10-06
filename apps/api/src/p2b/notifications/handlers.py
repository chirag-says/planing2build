"""Notifications' outbox subscriptions (ruling 2.8): each event becomes one job per notification
kind. The queueing lock stops a redelivered event from queueing a second copy while the first is
waiting; Procrastinate reports that as AlreadyEnqueued, which here means "done already"."""

from procrastinate import App
from procrastinate.exceptions import AlreadyEnqueued
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.outbox import DeliveredEvent, HandlerRegistry
from p2b.notifications.service import BY_EVENT, kinds_for

JOB_NAMESPACE = "notifications"


def register(registry: HandlerRegistry, job_app: App) -> None:
    async def notify(_: AsyncSession, event: DeliveredEvent) -> None:
        for kind in kinds_for(event.event_type, event.payload):
            task = job_app.configure_task(
                f"{JOB_NAMESPACE}:send_notification",
                queueing_lock=f"notify:{kind.value}:{event.id}",
            )
            try:
                await task.defer_async(
                    kind=kind.value,
                    event_id=str(event.id),
                    ref_id=str(event.aggregate_id),
                    payload=event.payload,
                )
            except AlreadyEnqueued:
                continue

    for event_type in BY_EVENT:
        registry.subscribe(event_type)(notify)
