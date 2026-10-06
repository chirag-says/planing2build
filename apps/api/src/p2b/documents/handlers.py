"""Documents' outbox subscriptions: a completed upload queues its processing job."""

from procrastinate import App
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.outbox import DeliveredEvent, HandlerRegistry

JOB_NAMESPACE = "documents"


def register(registry: HandlerRegistry, job_app: App) -> None:
    @registry.subscribe("documents.upload_completed")
    async def defer_processing(_: AsyncSession, event: DeliveredEvent) -> None:
        await job_app.configure_task(f"{JOB_NAMESPACE}:process_file").defer_async(
            file_id=str(event.payload["file_id"])
        )
