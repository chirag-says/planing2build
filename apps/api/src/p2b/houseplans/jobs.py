"""Houseplans jobs (queue `engine`). The engine is deterministic, so an infrastructure retry gives
the same answer; the job is idempotent on the plan's state."""

import uuid

from procrastinate import Blueprint, JobContext, RetryStrategy

from p2b.core.jobs import RESOURCES_KEY, JobResources
from p2b.houseplans.service import run_generation

blueprint = Blueprint()

INFRASTRUCTURE_RETRY = RetryStrategy(max_attempts=3, exponential_wait=5)


@blueprint.task(name="generate_plan", queue="engine", pass_context=True, retry=INFRASTRUCTURE_RETRY)
async def generate_plan_job(context: JobContext, plan_id: str) -> None:
    resources: JobResources = context.additional_context[RESOURCES_KEY]
    await run_generation(resources.database, resources.settings, uuid.UUID(plan_id))
