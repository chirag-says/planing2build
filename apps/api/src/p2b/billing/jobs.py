"""Billing jobs. Payment events, verified fetches and refunds run on `priority`; rendering on
`render`; reconciliation on `maintenance`, every 15 minutes for open attempts and refunds and
daily at 03:00 IST for the last 3 days of captures. Every job is idempotent; provider failures
that may pass are retried with backoff."""

import uuid

from procrastinate import Blueprint, JobContext, RetryStrategy

from p2b.billing.invoices import render_and_store
from p2b.billing.payments import (
    process_event,
    reconcile_daily,
    reconcile_open_attempts,
    verify_attempt,
)
from p2b.billing.refunds import execute_refund
from p2b.core.jobs import RESOURCES_KEY, JobResources

blueprint = Blueprint()

RETRY = RetryStrategy(max_attempts=5, exponential_wait=30)


def _resources(context: JobContext) -> JobResources:
    resources: JobResources = context.additional_context[RESOURCES_KEY]
    return resources


@blueprint.task(name="process_payment_event", queue="priority", pass_context=True, retry=RETRY)
async def process_payment_event_job(context: JobContext, payment_event_id: str) -> None:
    r = _resources(context)
    await process_event(r.database, r.settings, uuid.UUID(payment_event_id))


@blueprint.task(name="verify_attempt", queue="priority", pass_context=True, retry=RETRY)
async def verify_attempt_job(context: JobContext, attempt_id: str) -> None:
    r = _resources(context)
    await verify_attempt(r.database, r.settings, r.payment_gateway, uuid.UUID(attempt_id))


@blueprint.task(name="render_invoice", queue="render", pass_context=True, retry=RETRY)
async def render_invoice_job(context: JobContext, invoice_id: str) -> None:
    r = _resources(context)
    await render_and_store(r.database, r.settings, r.storage, uuid.UUID(invoice_id))


@blueprint.task(name="execute_refund", queue="priority", pass_context=True, retry=RETRY)
async def execute_refund_job(context: JobContext, refund_id: str) -> None:
    r = _resources(context)
    await execute_refund(r.database, r.settings, r.payment_gateway, uuid.UUID(refund_id))


@blueprint.periodic(cron="*/15 * * * *")
@blueprint.task(
    name="reconcile_frequent",
    queue="maintenance",
    pass_context=True,
    queueing_lock="billing-reconcile-frequent",
)
async def reconcile_frequent_job(context: JobContext, timestamp: int) -> None:
    r = _resources(context)
    await reconcile_open_attempts(r.database, r.settings, r.payment_gateway)


@blueprint.periodic(cron="30 21 * * *")  # 03:00 IST
@blueprint.task(
    name="reconcile_daily",
    queue="maintenance",
    pass_context=True,
    queueing_lock="billing-reconcile-daily",
)
async def reconcile_daily_job(context: JobContext, timestamp: int) -> None:
    r = _resources(context)
    await reconcile_daily(r.database, r.settings, r.payment_gateway)
