"""Engagements jobs: requests past their response window expire every 15 minutes on
`maintenance` (N-07). Idempotent: only SENT requests past `respond_by` change."""

from procrastinate import Blueprint, JobContext

from p2b.core.jobs import RESOURCES_KEY, JobResources
from p2b.engagements.service import expire_due

blueprint = Blueprint()


@blueprint.periodic(cron="*/15 * * * *")
@blueprint.task(
    name="expire_connections",
    queue="maintenance",
    pass_context=True,
    queueing_lock="engagements-expire-connections",
)
async def expire_connections_job(context: JobContext, timestamp: int) -> None:
    resources: JobResources = context.additional_context[RESOURCES_KEY]
    while True:
        async with resources.database.transaction() as session:
            if await expire_due(session) == 0:
                return
