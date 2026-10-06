"""Notifications for review events (ruling 2.8): events become jobs through the outbox, once per
kind; jobs send through the provider to the configured operations mailbox or the family's email,
and operations notices are skipped when no mailbox is configured."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from procrastinate import App
from sqlalchemy import select, text

from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.jobs import RESOURCES_KEY, JobResources
from p2b.core.outbox import DeliveredEvent, HandlerRegistry, OutboxEvent, relay_batch
from p2b.core.vocabulary import Audience, StaffRole
from p2b.identity.models import UserContact
from p2b.integrations.ai_images import DemoImageProvider
from p2b.integrations.clamav import AcceptAllScanner
from p2b.integrations.email import MemoryEmailProvider
from p2b.integrations.razorpay import NoGateway
from p2b.integrations.storage import MemoryStorage
from p2b.notifications import handlers as notifications_handlers
from p2b.notifications.service import Kind, kinds_for
from p2b.operations import handlers as operations_handlers
from p2b.projects.models import Project
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.staff_support import verified_staff
from tests.test_operations import submitted_project
from tests.test_projects import H
from tests.test_review_workspace import accept, ask, cancel, claim

OPS_MAILBOX = "operations@example.in"


Run = Callable[[str | None], Awaitable[MemoryEmailProvider]]


@pytest.fixture
async def run_notifications(database: Database, notify_app: App) -> AsyncIterator[Run]:
    """Relay events with the production subscribers, then run the queued notification jobs."""
    registry = HandlerRegistry()
    operations_handlers.register(registry, notify_app)
    notifications_handlers.register(registry, notify_app)

    async def run(ops_mailbox: str | None) -> MemoryEmailProvider:
        mailbox = MemoryEmailProvider()
        settings = get_settings().model_copy(update={"ops_notification_email": ops_mailbox})
        resources = JobResources(
            database,
            settings,
            mailbox,
            MemoryStorage(),
            AcceptAllScanner(),
            DemoImageProvider(),
            NoGateway(),
        )
        while await relay_batch(database, registry):
            pass
        await notify_app.run_worker_async(
            queues=["notifications"], wait=False, install_signal_handlers=False,
            additional_context={
                RESOURCES_KEY: resources
            },
        )  # fmt: skip
        return mailbox

    async with notify_app.open_async():
        yield run


async def give_email(database: Database, project_id: str, email: str) -> None:
    async with database.transaction() as session:
        project = await session.get_one(Project, uuid.UUID(project_id))
        session.add(
            UserContact(
                id=new_id(), user_id=project.owner_user_id, audience="ihb", kind="EMAIL",
                value=email, normalized=email, is_primary=True,
            )
        )  # fmt: skip


async def queued_kinds(database: Database) -> list[str]:
    async with database.transaction() as session:
        rows = await session.execute(
            text(
                "SELECT args->>'kind' FROM procrastinate_jobs "
                "WHERE task_name = 'notifications:send_notification' ORDER BY id"
            )
        )
        return [row[0] for row in rows]


def test_each_event_maps_to_its_notifications() -> None:
    assert kinds_for("requirement.submitted", {"review_flags": []}) == [
        Kind.OPS_REQUIREMENT_SUBMITTED
    ]
    assert kinds_for("requirement.submitted", {"review_flags": ["CONSTRUCTION_STARTED"]}) == [
        Kind.OPS_REQUIREMENT_SUBMITTED, Kind.OPS_REQUIREMENT_FLAGGED,
    ]  # fmt: skip
    assert kinds_for("enquiry.created", {}) == [Kind.OPS_ENQUIRY_RECEIVED]
    assert kinds_for("project.needs_info", {}) == [Kind.FAMILY_NEEDS_INFO]
    assert kinds_for("project.accepted", {}) == [Kind.FAMILY_ACCEPTED]
    assert kinds_for("project.cancelled", {}) == [Kind.FAMILY_CANCELLED]
    assert kinds_for("session.revoked", {}) == []


async def test_review_events_reach_the_operations_mailbox_and_the_family(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
    run_notifications: Run,
) -> None:  # fmt: skip
    _, project_id = await submitted_project(
        client_for, make_user, sign_in, construction_started=True
    )
    await give_email(database, project_id, "family@example.in")
    mailbox = await run_notifications(OPS_MAILBOX)
    assert [(m.to, m.subject.split(":")[0]) for m in mailbox.sent] == [
        (OPS_MAILBOX, "New requirement submitted"),
        (OPS_MAILBOX, "Requirement needs attention"),
    ]
    assert "Construction started" in mailbox.sent[1].text

    staff = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    await claim(staff, project_id)
    await ask(staff, project_id, "Please send the sanctioned plan.")
    mailbox = await run_notifications(OPS_MAILBOX)
    assert [m.to for m in mailbox.sent] == ["family@example.in"]
    assert "Please send the sanctioned plan." in mailbox.sent[0].text
    assert "Construction started" not in mailbox.sent[0].text  # flags never reach the family

    await cancel(staff, project_id, "The site is outside Raipur.")
    mailbox = await run_notifications(OPS_MAILBOX)
    assert "The site is outside Raipur." in mailbox.sent[0].text
    assert await queued_kinds(database) == [
        "ops_requirement_submitted", "ops_requirement_flagged",
        "family_needs_info", "family_cancelled",
    ]  # fmt: skip


async def test_acceptance_and_enquiries_notify(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
    run_notifications: Run,
) -> None:  # fmt: skip
    _, project_id = await submitted_project(client_for, make_user, sign_in)
    await give_email(database, project_id, "family2@example.in")
    staff = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    await run_notifications(OPS_MAILBOX)
    await claim(staff, project_id)
    await accept(staff, project_id)
    public = client_for(Audience.IHB)
    await public.post(
        "/api/v1/public/enquiries",
        json={"kind": "OTHER_CITY", "email": "lead@example.in"},
        headers=H,
    )
    mailbox = await run_notifications(OPS_MAILBOX)
    by_to = {m.to: m for m in mailbox.sent}
    assert "initial review" in by_to["family2@example.in"].subject
    assert "lead@example.in" in by_to[OPS_MAILBOX].text


async def test_operations_notices_are_skipped_without_a_configured_mailbox(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
    run_notifications: Run,
) -> None:  # fmt: skip
    await submitted_project(client_for, make_user, sign_in)
    mailbox = await run_notifications(None)
    assert mailbox.sent == []
    assert await queued_kinds(database) == ["ops_requirement_submitted"]  # queued, then skipped


async def test_a_redelivered_event_queues_no_second_job(
    database: Database, notify_app: App
) -> None:
    registry = HandlerRegistry()
    notifications_handlers.register(registry, notify_app)
    event = DeliveredEvent(
        id=uuid.uuid4(), event_type="enquiry.created", aggregate_type="enquiry",
        aggregate_id=uuid.uuid4(), payload={"kind": "OTHER_CITY"}, request_id=None,
    )  # fmt: skip
    async with notify_app.open_async(), database.transaction() as session:
        for _ in range(2):
            for handler in registry.handlers_for("enquiry.created"):
                await handler(session, event)
    assert await queued_kinds(database) == ["ops_enquiry_received"]
    async with database.transaction() as session:
        assert list(await session.scalars(select(OutboxEvent))) == []
