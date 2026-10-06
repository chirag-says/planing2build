"""Assurance outbox subscriptions, in the relay's transaction. Each only touches open records, so
a redelivered event changes nothing.

- `billing.package_changed` to REFUNDED or CANCELLED: inspections not yet started are cancelled
  (EX-18); in-progress and submitted ones stay, and none is approved while the package is
  inactive.
- `project.cancelled`: open inspections are cancelled (PROJECT_CLOSED)."""

import uuid

from procrastinate import App
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.assurance.common import SYSTEM
from p2b.assurance.inspections import cancel_open
from p2b.core.outbox import DeliveredEvent, HandlerRegistry
from p2b.core.vocabulary import InspectionCancelReason, PackageState

PACKAGE_ENDED = {PackageState.REFUNDED.value, PackageState.CANCELLED.value}


def register(registry: HandlerRegistry, job_app: App) -> None:
    @registry.subscribe("billing.package_changed")
    async def package_changed(session: AsyncSession, event: DeliveredEvent) -> None:
        if event.payload.get("state") in PACKAGE_ENDED:
            await cancel_open(
                session, uuid.UUID(str(event.payload["project_id"])),
                InspectionCancelReason.PACKAGE_ENDED, SYSTEM,
            )  # fmt: skip

    @registry.subscribe("project.cancelled")
    async def project_cancelled(session: AsyncSession, event: DeliveredEvent) -> None:
        await cancel_open(
            session, uuid.UUID(str(event.payload["project_id"])),
            InspectionCancelReason.PROJECT_CLOSED, SYSTEM,
        )  # fmt: skip
