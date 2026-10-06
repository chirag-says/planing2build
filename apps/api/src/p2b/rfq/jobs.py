"""RFQ jobs, every 15 minutes on `maintenance`: unanswered invitations expire (QD-05), quotes
past their validity expire (QD-06), and operations get one email per passed quote deadline.
Idempotent: each step only touches records still in the state it changes."""

from procrastinate import Blueprint, JobContext

from p2b.core.jobs import RESOURCES_KEY, JobResources
from p2b.rfq import quotes, rfqs

blueprint = Blueprint()


@blueprint.periodic(cron="*/15 * * * *")
@blueprint.task(
    name="sweep_rfqs", queue="maintenance", pass_context=True, queueing_lock="rfq-sweep"
)
async def sweep_rfqs_job(context: JobContext, timestamp: int) -> None:
    resources: JobResources = context.additional_context[RESOURCES_KEY]
    await sweep(resources)


async def sweep(resources: JobResources) -> None:
    for step in (rfqs.expire_due, quotes.expire_due, rfqs.notice_deadlines):
        while True:
            async with resources.database.transaction() as session:
                if await step(session) == 0:
                    break
