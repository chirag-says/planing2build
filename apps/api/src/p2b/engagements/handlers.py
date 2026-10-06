"""Engagements' outbox subscriptions. Open requests are withdrawn, in the relay's transaction,
when the package is refunded or cancelled (N-10), the project is cancelled, or the professional
is no longer listed for the category. Each only touches SENT requests, so a redelivered event
changes nothing. Engagements are never ended here."""

import uuid

from procrastinate import App
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.outbox import DeliveredEvent, HandlerRegistry
from p2b.core.vocabulary import ListingState, PackageState, WithdrawReason
from p2b.engagements.service import withdraw_open
from p2b.professionals.interface import category_of_listing

JOB_NAMESPACE = "engagements"

PACKAGE_ENDED = {PackageState.REFUNDED.value, PackageState.CANCELLED.value}


def register(registry: HandlerRegistry, job_app: App) -> None:
    @registry.subscribe("billing.package_changed")
    async def package_changed(session: AsyncSession, event: DeliveredEvent) -> None:
        if event.payload.get("state") in PACKAGE_ENDED:
            await withdraw_open(
                session,
                WithdrawReason.PACKAGE_ENDED,
                project_id=uuid.UUID(str(event.payload["project_id"])),
            )

    @registry.subscribe("project.cancelled")
    async def project_cancelled(session: AsyncSession, event: DeliveredEvent) -> None:
        await withdraw_open(
            session,
            WithdrawReason.PROJECT_CLOSED,
            project_id=uuid.UUID(str(event.payload["project_id"])),
        )

    @registry.subscribe("professional.listing_changed")
    async def listing_changed(session: AsyncSession, event: DeliveredEvent) -> None:
        """Hiding a listing keeps requests already sent answerable; only leaving LISTED
        withdraws them."""
        if event.payload.get("listing_state") == ListingState.LISTED.value:
            return
        listing = await category_of_listing(
            session, uuid.UUID(str(event.payload["professional_category_id"]))
        )
        if listing is None:
            return
        profile_id, category_code = listing
        await withdraw_open(
            session,
            WithdrawReason.PROFESSIONAL_UNAVAILABLE,
            profile_id=profile_id,
            category_code=category_code,
        )
