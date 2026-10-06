"""Documents jobs (EVENT_AND_BACKGROUND_JOB_ARCHITECTURE section 3: queue `files`)."""

import uuid

from procrastinate import Blueprint, JobContext, RetryStrategy

from p2b.core.jobs import RESOURCES_KEY, JobResources
from p2b.documents.service import process_file

blueprint = Blueprint()

# Internal work with a provider in the loop (ClamAV, storage): a few spaced retries.
PROCESS_RETRY = RetryStrategy(max_attempts=5, exponential_wait=5)


@blueprint.task(name="process_file", queue="files", pass_context=True, retry=PROCESS_RETRY)
async def process_file_job(context: JobContext, file_id: str) -> None:
    resources: JobResources = context.additional_context[RESOURCES_KEY]
    await process_file(resources.database, resources.storage, resources.scanner, uuid.UUID(file_id))
