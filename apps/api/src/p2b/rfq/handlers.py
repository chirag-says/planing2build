"""RFQ outbox subscriptions, in the relay's transaction. Each only touches open records, so a
redelivered event changes nothing.

- `billing.package_changed` to REFUNDED or CANCELLED: open RFQs are CANCELLED (QD-14).
- `buildplan.accepted`: open RFQs on any other version are CANCELLED (QD-15).
- `project.cancelled`: open RFQs are CANCELLED.
- `professional.listing_changed` out of LISTED: unanswered invitations are withdrawn."""

import uuid

from procrastinate import App
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.outbox import DeliveredEvent, HandlerRegistry
from p2b.core.vocabulary import ListingState, PackageState, RfqCancelReason
from p2b.professionals.interface import category_of_listing
from p2b.rfq.common import CATEGORY
from p2b.rfq.rfqs import cancel_open, withdraw_for_profile

JOB_NAMESPACE = "rfq"

PACKAGE_ENDED = {PackageState.REFUNDED.value, PackageState.CANCELLED.value}


def register(registry: HandlerRegistry, job_app: App) -> None:
    @registry.subscribe("billing.package_changed")
    async def package_changed(session: AsyncSession, event: DeliveredEvent) -> None:
        if event.payload.get("state") in PACKAGE_ENDED:
            await cancel_open(
                session, RfqCancelReason.PACKAGE_ENDED,
                project_id=uuid.UUID(str(event.payload["project_id"])),
            )  # fmt: skip

    @registry.subscribe("buildplan.accepted")
    async def build_plan_accepted(session: AsyncSession, event: DeliveredEvent) -> None:
        await cancel_open(
            session, RfqCancelReason.BASELINE_SUPERSEDED,
            project_id=uuid.UUID(str(event.payload["project_id"])),
            keep_version_id=uuid.UUID(str(event.payload["version_id"])),
        )  # fmt: skip

    @registry.subscribe("project.cancelled")
    async def project_cancelled(session: AsyncSession, event: DeliveredEvent) -> None:
        await cancel_open(
            session, RfqCancelReason.PROJECT_CLOSED,
            project_id=uuid.UUID(str(event.payload["project_id"])),
        )  # fmt: skip

    @registry.subscribe("professional.listing_changed")
    async def listing_changed(session: AsyncSession, event: DeliveredEvent) -> None:
        if event.payload.get("listing_state") == ListingState.LISTED.value:
            return
        listing = await category_of_listing(
            session, uuid.UUID(str(event.payload["professional_category_id"]))
        )
        if listing is None or listing[1] != CATEGORY:
            return
        await withdraw_for_profile(session, listing[0])
