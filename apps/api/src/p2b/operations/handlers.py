"""Operations' outbox subscriptions: a submitted requirement, or a professional category
submitted for review (Slice 3.2), opens a review item (EVENT map)."""

from procrastinate import App
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.outbox import DeliveredEvent, HandlerRegistry
from p2b.operations.service import enqueue_professional_review, enqueue_review


def register(registry: HandlerRegistry, _job_app: App) -> None:
    @registry.subscribe("requirement.submitted")
    async def open_review(session: AsyncSession, event: DeliveredEvent) -> None:
        await enqueue_review(session, event.aggregate_id)

    @registry.subscribe("professional.category_submitted")
    async def open_professional_review(session: AsyncSession, event: DeliveredEvent) -> None:
        await enqueue_professional_review(session, event.aggregate_id)
