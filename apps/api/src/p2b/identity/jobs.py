"""Identity jobs (EVENT_AND_BACKGROUND_JOB_ARCHITECTURE section 3 and 4.1)."""

import uuid

from procrastinate import Blueprint, JobContext, RetryStrategy

from p2b.core.jobs import RESOURCES_KEY, JobResources
from p2b.identity.otp import deliver_otp_code

blueprint = Blueprint()

# "OTP delivery retries every 20 s for 2 minutes then marks the challenge delivery failed."
DELIVERY_RETRY = RetryStrategy(max_attempts=6, wait=20)


@blueprint.task(name="deliver_otp", queue="priority", pass_context=True, retry=DELIVERY_RETRY)
async def deliver_otp(context: JobContext, challenge_id: str) -> None:
    resources: JobResources = context.additional_context[RESOURCES_KEY]
    await deliver_otp_code(
        resources.database,
        resources.settings,
        resources.message_provider,
        uuid.UUID(challenge_id),
        final_attempt=context.job.attempts >= (DELIVERY_RETRY.max_attempts or 0),
    )
