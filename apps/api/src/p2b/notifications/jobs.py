"""Notification jobs (EVENT_AND_BACKGROUND_JOB_ARCHITECTURE sections 3 and 5)."""

import uuid
from typing import Any

from procrastinate import Blueprint, JobContext, RetryStrategy

from p2b.core.jobs import RESOURCES_KEY, JobResources
from p2b.notifications.service import Kind, send_notification

blueprint = Blueprint()

SEND_RETRY = RetryStrategy(max_attempts=5, exponential_wait=10)


@blueprint.task(
    name="send_notification", queue="notifications", pass_context=True, retry=SEND_RETRY
)
async def send(
    context: JobContext, kind: str, event_id: str, ref_id: str, payload: dict[str, Any]
) -> None:
    resources: JobResources = context.additional_context[RESOURCES_KEY]
    await send_notification(
        resources.database,
        resources.settings,
        resources.message_provider,
        kind=Kind(kind),
        event_id=uuid.UUID(event_id),
        ref_id=uuid.UUID(ref_id),
        payload=payload,
    )
