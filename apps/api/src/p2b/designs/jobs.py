"""Designs jobs (queue `ai`). Provider retries happen inside the job (configured attempts with a
timeout each); Procrastinate retries only for infrastructure failures (database, storage), and
the job is idempotent, so a retry never generates twice."""

import uuid

from procrastinate import Blueprint, JobContext, RetryStrategy

from p2b.core.jobs import RESOURCES_KEY, JobResources
from p2b.designs.service import run_generation

blueprint = Blueprint()

INFRASTRUCTURE_RETRY = RetryStrategy(max_attempts=3, exponential_wait=5)


@blueprint.task(name="generate_design", queue="ai", pass_context=True, retry=INFRASTRUCTURE_RETRY)
async def generate_design_job(context: JobContext, generation_id: str) -> None:
    resources: JobResources = context.additional_context[RESOURCES_KEY]
    await run_generation(
        resources.database,
        resources.settings,
        resources.storage,
        resources.image_provider,
        uuid.UUID(generation_id),
    )
