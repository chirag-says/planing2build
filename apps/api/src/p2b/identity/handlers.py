"""Identity's outbox subscriptions. The relay calls these after the business transaction
committed; they only defer jobs (EVENT_AND_BACKGROUND_JOB_ARCHITECTURE section 2)."""

from procrastinate import App
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.outbox import DeliveredEvent, HandlerRegistry

JOB_NAMESPACE = "identity"


def register(registry: HandlerRegistry, job_app: App) -> None:
    @registry.subscribe("otp.issued")
    async def defer_otp_delivery(_: AsyncSession, event: DeliveredEvent) -> None:
        await job_app.configure_task(f"{JOB_NAMESPACE}:deliver_otp").defer_async(
            challenge_id=str(event.payload["challenge_id"])
        )
