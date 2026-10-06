"""Billing's outbox subscriptions: each committed fact queues its job, once (queueing locks), so
a job exists only if the change that needs it committed."""

from procrastinate import App
from procrastinate.exceptions import AlreadyEnqueued
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.outbox import DeliveredEvent, HandlerRegistry

JOB_NAMESPACE = "billing"


async def _defer(job_app: App, task: str, lock: str, **kwargs: str) -> None:
    try:
        await job_app.configure_task(f"{JOB_NAMESPACE}:{task}", queueing_lock=lock).defer_async(
            **kwargs
        )
    except AlreadyEnqueued:
        return


def register(registry: HandlerRegistry, job_app: App) -> None:
    @registry.subscribe("billing.payment_event_received")
    async def process(_: AsyncSession, event: DeliveredEvent) -> None:
        event_id = str(event.payload["payment_event_id"])
        await _defer(
            job_app, "process_payment_event", f"payment-event:{event_id}", payment_event_id=event_id
        )

    @registry.subscribe("billing.checkout_returned")
    async def verify(_: AsyncSession, event: DeliveredEvent) -> None:
        attempt_id = str(event.payload["attempt_id"])
        await _defer(
            job_app, "verify_attempt", f"verify-attempt:{attempt_id}", attempt_id=attempt_id
        )

    @registry.subscribe("billing.invoice_issued")
    async def render(_: AsyncSession, event: DeliveredEvent) -> None:
        invoice_id = str(event.payload["invoice_id"])
        await _defer(job_app, "render_invoice", f"invoice:{invoice_id}", invoice_id=invoice_id)

    @registry.subscribe("billing.refund_approved")
    async def refund(_: AsyncSession, event: DeliveredEvent) -> None:
        for refund_id in event.payload["refund_ids"]:
            await _defer(job_app, "execute_refund", f"refund:{refund_id}", refund_id=str(refund_id))
