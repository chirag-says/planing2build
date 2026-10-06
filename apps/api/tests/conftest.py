"""Shared fixtures. Tests run against a real PostgreSQL with PostGIS (TESTING_ARCHITECTURE 2):
the `p2b_test` database of the local Compose stack, or the CI service container.

Isolation: every test starts from empty application tables (TRUNCATE after each test). Rollback
isolation would not cover the relay and the job queue, which open their own connections.
"""

import asyncio
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from procrastinate import App

API_ROOT = Path(__file__).resolve().parents[1]

if sys.platform == "win32":
    # psycopg (the job queue's driver) cannot run on the Proactor loop. Linux is unaffected.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined,unused-ignore]

os.environ.setdefault(
    "P2B_DATABASE_URL",
    os.environ.get(
        "P2B_TEST_DATABASE_URL", "postgresql+asyncpg://p2b:p2b_local@127.0.0.1:55432/p2b_test"
    ),
)
os.environ.update(
    {
        "P2B_ENV": "test",
        "P2B_HOST_IHB": "ihb.test",
        "P2B_HOST_PRO": "pro.test",
        "P2B_HOST_OPS": "ops.test",
        "P2B_COOKIE_SECURE": "true",
        "P2B_LOG_LEVEL": "WARNING",
        # Test-only secrets; never used outside this suite.
        "P2B_OTP_PEPPER": "test-otp-pepper",
        "P2B_IDENTIFIER_PEPPER": "test-identifier-pepper",
        "P2B_ENCRYPTION_KEY": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        "P2B_EMAIL_PROVIDER": "memory",
        "P2B_STORAGE_PROVIDER": "memory",
        "P2B_AI_IMAGE_PROVIDER": "demo",
        "P2B_SCANNER_PROVIDER": "accept_all",
        "P2B_GEOCODER_PROVIDER": "none",
        # The fake payment gateway; test-only keys, never live (Settings refuses rzp_live_).
        "P2B_PAYMENT_PROVIDER": "fake",
        "P2B_PAYMENT_KEY_ID": "fake_key_test",
        "P2B_PAYMENT_KEY_SECRET": "test-payment-key-secret",
        "P2B_PAYMENT_WEBHOOK_SECRET": "test-payment-webhook-secret",
    }
)

from fastapi import FastAPI  # noqa: E402  (environment must be set before the app is built)
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from p2b.core.config import get_settings  # noqa: E402
from p2b.core.db import Database  # noqa: E402
from p2b.core.http import session_cookie_name  # noqa: E402
from p2b.core.ids import new_id  # noqa: E402
from p2b.core.vocabulary import Audience, UserStatus  # noqa: E402
from p2b.identity.models import User  # noqa: E402
from p2b.identity.service import create_session  # noqa: E402
from p2b.main import create_app  # noqa: E402

HOSTS = {Audience.IHB: "ihb.test", Audience.PRO: "pro.test", Audience.OPS: "ops.test"}
# Application data only; seeded reference data (cities, stage masters, question sets) stays.
APP_TABLES = (
    "users, user_contacts, otp_challenges, sessions, audit_events, security_events, "
    "outbox_events, rate_counters, rate_cards, procrastinate_jobs, projects, "
    "project_requirements, project_memberships, project_status_history, enquiries, "
    "geocode_cache, idempotency_keys, file_objects, document_access_log, staff_roles, "
    "mfa_secrets, ops_queue_items, stage_instances, project_spec_lines, spec_line_events, "
    "project_estimates, design_generations, design_references, professional_profiles, "
    "professional_categories, verification_cases, verification_checks, professional_documents, "
    "professional_references, portfolio_items, professional_listing_history, "
    "eligibility_assessments, pricing_rule_versions, instalment_plan_versions, "
    "tax_configuration_versions, offering_versions, orders, payment_dues, payment_attempts, "
    "payments, payment_events, invoice_sequences, invoices, invoice_lines, invoice_tax_lines, "
    "refund_requests, refund_decisions, refunds, package_entitlements, "
    "package_entitlement_history, package_service_usage, ai_credit_ledger, billing_exceptions, "
    "fake_gateway_records, project_service_needs, connections, project_engagements, "
    "engagement_documents, engagement_events, quote_review_requests, item_rate_cards, "
    "item_rate_card_lines, drawing_checker_appointments, design_requests, "
    "drawing_sets, drawing_files, build_plans, build_plan_versions, build_plan_spec_values, "
    "boq_lines, build_plan_schedule_entries, structural_signoffs, build_plan_acceptances, "
    "build_plan_events, rfqs, rfq_invitations, quote_drafts, quote_versions, quote_lines, "
    "quote_adjustments, rfq_clarifications, comparisons, selections, rfq_events, "
    "stage_updates, construction_events, payment_marks, auditor_appointments, inspections, "
    "inspection_results, non_conformances, inspection_reports, test_results, assurance_events"
)


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_ROOT,
        check=True,
        env={**os.environ},
    )


@pytest.fixture(scope="session")
def app() -> FastAPI:
    return create_app(get_settings())


@pytest.fixture(scope="session")
def database(app: FastAPI) -> Database:
    db: Database = app.state.database
    return db


@pytest.fixture(autouse=True)
async def _clean_tables(database: Database) -> AsyncIterator[None]:
    yield
    async with database.transaction() as session:
        await session.execute(text(f"TRUNCATE {APP_TABLES} CASCADE"))


ClientFactory = Callable[[Audience], AsyncClient]


@pytest.fixture
async def client_for(app: FastAPI) -> AsyncIterator[ClientFactory]:
    clients: list[AsyncClient] = []

    def make(audience: Audience) -> AsyncClient:
        client = AsyncClient(
            transport=ASGITransport(app=app), base_url=f"https://{HOSTS[audience]}"
        )
        clients.append(client)
        return client

    yield make
    for client in clients:
        await client.aclose()


UserFactory = Callable[..., Awaitable[uuid.UUID]]


@pytest.fixture
def make_user(database: Database) -> UserFactory:
    async def make(
        audience: Audience = Audience.IHB, status: UserStatus = UserStatus.ACTIVE
    ) -> uuid.UUID:
        user_id = new_id()
        async with database.transaction() as session:
            session.add(User(id=user_id, audience=audience.value, status=status.value))
        return user_id

    return make


SignIn = Callable[[AsyncClient, uuid.UUID, Audience], Awaitable[str]]


@pytest.fixture
def sign_in(database: Database) -> SignIn:
    """Create a session through the service (the OTP flow arrives in slice 1) and set the cookie."""

    async def sign(client: AsyncClient, user_id: uuid.UUID, audience: Audience) -> str:
        async with database.transaction() as session:
            issued = await create_session(session, user_id=user_id)
        client.cookies.set(session_cookie_name(audience, secure=True), issued.token)
        return issued.token

    return sign


def csrf_headers(audience: Audience) -> dict[str, str]:
    """Headers the web client sends on every state-changing request (API_ARCHITECTURE 1)."""
    return {"X-Requested-With": "plan2build", "Origin": f"https://{HOSTS[audience]}"}


@pytest.fixture(scope="session")
def billing_app() -> "App":
    """One job app for billing's blueprint in the whole session: a Procrastinate blueprint binds
    its tasks to the first app it is added to."""
    from p2b.billing import handlers as billing_handlers
    from p2b.billing import jobs as billing_jobs
    from p2b.core.jobs import build_job_app

    return build_job_app(get_settings(), [(billing_handlers.JOB_NAMESPACE, billing_jobs.blueprint)])


@pytest.fixture(scope="session")
def notify_app() -> "App":
    """One job app with the notifications blueprint, shared by every test module that sends
    notifications (a blueprint binds to the first app)."""
    from p2b.core.jobs import build_job_app
    from p2b.notifications import handlers as notifications_handlers
    from p2b.notifications import jobs as notifications_jobs

    return build_job_app(
        get_settings(), [(notifications_handlers.JOB_NAMESPACE, notifications_jobs.blueprint)]
    )


@pytest.fixture
async def work(app: FastAPI, database: Database, billing_app: "App") -> AsyncIterator[Any]:
    """What the worker does for billing: relay its outbox events to its handlers, then run the
    queued payment, refund and rendering jobs (a few rounds, as jobs publish events)."""
    from sqlalchemy import select

    from p2b.billing import handlers as billing_handlers
    from p2b.core.jobs import RESOURCES_KEY, JobResources
    from p2b.core.outbox import HandlerRegistry, OutboxEvent, relay_batch
    from p2b.integrations.clamav import AcceptAllScanner
    from p2b.integrations.email import MemoryEmailProvider

    registry = HandlerRegistry()
    billing_handlers.register(registry, billing_app)

    async def run() -> None:
        resources = JobResources(
            database,
            app.state.settings,
            MemoryEmailProvider(),
            app.state.storage,
            AcceptAllScanner(),
            app.state.image_provider,
            app.state.payment_gateway,
        )
        for _ in range(3):
            while await relay_batch(database, registry):
                pass
            await billing_app.run_worker_async(
                queues=["priority", "render"],
                wait=False,
                install_signal_handlers=False,
                additional_context={RESOURCES_KEY: resources},
            )
        async with database.transaction() as session:
            failed = list(
                await session.scalars(
                    select(OutboxEvent.last_error).where(OutboxEvent.last_error.is_not(None))
                )
            )
        assert not failed, failed

    async with billing_app.open_async():
        yield run


@pytest.fixture
async def rfq_worker(
    app: FastAPI, database: Database, billing_app: "App", notify_app: "App"
) -> AsyncIterator[Any]:
    """The worker for this slice: billing, engagements, rfq and notification subscribers on the
    outbox, then billing and notification jobs. Returns the mailbox of the run. Slice 3.7 adds
    the assurance subscribers."""
    from sqlalchemy import select

    from p2b.assurance import handlers as assurance_handlers
    from p2b.billing import handlers as billing_handlers
    from p2b.core.jobs import RESOURCES_KEY, JobResources
    from p2b.core.outbox import HandlerRegistry, OutboxEvent, relay_batch
    from p2b.engagements import handlers as engagements_handlers
    from p2b.integrations.clamav import AcceptAllScanner
    from p2b.integrations.email import MemoryEmailProvider
    from p2b.notifications import handlers as notifications_handlers
    from p2b.rfq import handlers as rfq_handlers

    registry = HandlerRegistry()
    billing_handlers.register(registry, billing_app)
    engagements_handlers.register(registry, billing_app)
    rfq_handlers.register(registry, billing_app)
    assurance_handlers.register(registry, billing_app)
    notifications_handlers.register(registry, notify_app)

    async def run() -> MemoryEmailProvider:
        mailbox = MemoryEmailProvider()
        resources = JobResources(
            database, app.state.settings, mailbox, app.state.storage, AcceptAllScanner(),
            app.state.image_provider, app.state.payment_gateway,
        )  # fmt: skip
        for _ in range(3):
            while await relay_batch(database, registry):
                pass
            await billing_app.run_worker_async(
                queues=["priority", "render"], wait=False, install_signal_handlers=False,
                additional_context={RESOURCES_KEY: resources},
            )  # fmt: skip
        await notify_app.run_worker_async(
            queues=["notifications"], wait=False, install_signal_handlers=False,
            additional_context={RESOURCES_KEY: resources},
        )  # fmt: skip
        async with database.transaction() as session:
            failed = list(
                await session.scalars(
                    select(OutboxEvent.last_error).where(OutboxEvent.last_error.is_not(None))
                )
            )
        assert not failed, failed
        return mailbox

    async with billing_app.open_async(), notify_app.open_async():
        yield run
