"""Composition root for the worker: Procrastinate jobs, the outbox relay and a heartbeat file
for the container health check (CLOUD_AND_HOSTING section 2.1). Run: `python -m p2b.worker`."""

import asyncio
import contextlib
import signal
import sys
from pathlib import Path

import structlog
from procrastinate import App, Blueprint

from p2b.assurance import handlers as assurance_handlers
from p2b.billing import handlers as billing_handlers
from p2b.billing import jobs as billing_jobs
from p2b.core.config import Settings, get_settings
from p2b.core.db import Database
from p2b.core.jobs import RESOURCES_KEY, JobResources, build_job_app
from p2b.core.logging import configure_logging
from p2b.core.observability import init_sentry
from p2b.core.outbox import HandlerRegistry, relay_batch
from p2b.designs import handlers as designs_handlers
from p2b.designs import jobs as designs_jobs
from p2b.documents import handlers as documents_handlers
from p2b.documents import jobs as documents_jobs
from p2b.engagements import handlers as engagements_handlers
from p2b.engagements import jobs as engagements_jobs
from p2b.identity import handlers as identity_handlers
from p2b.identity import jobs as identity_jobs
from p2b.integrations.ai_images import build_image_provider
from p2b.integrations.clamav import build_scanner
from p2b.integrations.email import build_message_provider
from p2b.integrations.razorpay import build_payment_gateway
from p2b.integrations.storage import build_storage
from p2b.notifications import handlers as notifications_handlers
from p2b.notifications import jobs as notifications_jobs
from p2b.operations import handlers as operations_handlers
from p2b.rfq import handlers as rfq_handlers
from p2b.rfq import jobs as rfq_jobs

log = structlog.get_logger("p2b.worker")

RELAY_IDLE_SECONDS = 2.0
HEARTBEAT_SECONDS = 30.0


def build_registry(job_app: App) -> HandlerRegistry:
    """Modules subscribe their outbox handlers here."""
    registry = HandlerRegistry()
    identity_handlers.register(registry, job_app)
    documents_handlers.register(registry, job_app)
    operations_handlers.register(registry, job_app)
    notifications_handlers.register(registry, job_app)
    designs_handlers.register(registry, job_app)
    billing_handlers.register(registry, job_app)
    engagements_handlers.register(registry, job_app)
    rfq_handlers.register(registry, job_app)
    assurance_handlers.register(registry, job_app)
    return registry


def job_blueprints() -> list[tuple[str, Blueprint]]:
    return [
        (identity_handlers.JOB_NAMESPACE, identity_jobs.blueprint),
        (documents_handlers.JOB_NAMESPACE, documents_jobs.blueprint),
        (notifications_handlers.JOB_NAMESPACE, notifications_jobs.blueprint),
        (designs_handlers.JOB_NAMESPACE, designs_jobs.blueprint),
        (billing_handlers.JOB_NAMESPACE, billing_jobs.blueprint),
        (engagements_handlers.JOB_NAMESPACE, engagements_jobs.blueprint),
        (rfq_handlers.JOB_NAMESPACE, rfq_jobs.blueprint),
    ]


async def relay_forever(database: Database, registry: HandlerRegistry, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            claimed = await relay_batch(database, registry)
        except Exception as exc:
            log.error("outbox.relay_failed", error_class=type(exc).__name__, exc_info=exc)
            claimed = 0
        if claimed == 0:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=RELAY_IDLE_SECONDS)


async def heartbeat_forever(path: Path, stop: asyncio.Event) -> None:
    while not stop.is_set():
        await asyncio.to_thread(path.touch)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_SECONDS)


async def run(settings: Settings) -> None:
    database = Database(settings)
    job_app = build_job_app(settings, job_blueprints())
    resources = JobResources(
        database,
        settings,
        build_message_provider(settings),
        build_storage(settings),
        build_scanner(settings),
        build_image_provider(settings),
        build_payment_gateway(settings, database),
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows has no add_signal_handler
            loop.add_signal_handler(sig, stop.set)

    log.info("worker.started", queue=",".join(settings.worker_queues or ["all"]))
    async with job_app.open_async():
        if settings.worker_queues:
            worker = job_app.run_worker_async(
                queues=settings.worker_queues,
                concurrency=settings.worker_concurrency,
                install_signal_handlers=False,
                additional_context={RESOURCES_KEY: resources},
            )
        else:  # every queue
            worker = job_app.run_worker_async(
                concurrency=settings.worker_concurrency,
                install_signal_handlers=False,
                additional_context={RESOURCES_KEY: resources},
            )
        jobs = asyncio.create_task(worker)
        relay = asyncio.create_task(relay_forever(database, build_registry(job_app), stop))
        heartbeat = asyncio.create_task(
            heartbeat_forever(Path(settings.worker_heartbeat_path), stop)
        )
        await stop.wait()
        jobs.cancel()
        await asyncio.gather(jobs, relay, heartbeat, return_exceptions=True)
    await database.dispose()
    log.info("worker.stopped")


def main() -> None:
    settings = get_settings()
    configure_logging(
        level=settings.log_level, service="p2b-worker", env=settings.env, release=settings.release
    )
    init_sentry(settings)
    # psycopg cannot use the Windows Proactor loop (local development only; production is Linux).
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(run(settings), loop_factory=loop_factory)


if __name__ == "__main__":
    main()
