"""The requirement review queue and the submission detail (API 18; SLICE2_READINESS sections 1, 3).

Covers: a submission reaches the queue through the outbox, once; claiming and releasing; the
detail operations see (answers, review flags, contact, files); downloads logged; and who cannot
reach any of it."""

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select

from p2b.audit.models import AuditEvent
from p2b.core.db import Database
from p2b.core.outbox import HandlerRegistry, OutboxEvent, relay_batch
from p2b.core.vocabulary import Audience, QueueKind, StaffRole
from p2b.documents.models import DocumentAccessLog, FileObject
from p2b.operations import handlers as operations_handlers
from p2b.operations.models import OpsQueueItem
from p2b.operations.service import enqueue_review, open_items
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.staff_support import OPS_HEADERS, Staff, verified_staff
from tests.test_projects import homeowner, new_project, save, submit
from tests.test_questions import COMPLETE

QUEUE = "/api/v1/ops/queues/requirement-review"


async def submitted_project(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, **changes: Any
) -> tuple[AsyncClient, str]:
    client = await homeowner(client_for, make_user, sign_in)
    project_id = (await new_project(client))["project"]["project_id"]
    await save(client, project_id, {**COMPLETE, **changes}, 1)
    assert (await submit(client, project_id, 2)).status_code == 200
    return client, project_id


async def relay(database: Database) -> None:
    """What the worker does after a commit: deliver outbox events to subscribed handlers."""
    registry = HandlerRegistry()
    operations_handlers.register(registry, None)  # type: ignore[arg-type]  # no jobs deferred
    while await relay_batch(database, registry):
        pass
    async with database.transaction() as session:
        failed = list(
            await session.scalars(
                select(OutboxEvent.last_error).where(OutboxEvent.last_error.is_not(None))
            )
        )
    assert not failed, failed  # a handler failure must fail the test, not hide in a log


async def ops_staff(database: Database, client_for: ClientFactory, sign_in: SignIn) -> Staff:
    return await verified_staff(database, client_for, sign_in, StaffRole.OPS)


async def test_a_submission_reaches_the_queue_once_through_the_outbox(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    _, project_id = await submitted_project(client_for, make_user, sign_in)
    await relay(database)
    async with database.transaction() as session:
        await enqueue_review(session, uuid.UUID(project_id))  # a redelivery changes nothing
    async with database.transaction() as session:
        items = list(await session.scalars(select(OpsQueueItem)))
    assert [(i.kind, i.ref_id, i.state) for i in items] == [
        ("REQUIREMENT_REVIEW", uuid.UUID(project_id), "OPEN")
    ]


async def test_the_queue_lists_submissions_oldest_first_with_their_flags(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    _, first = await submitted_project(client_for, make_user, sign_in)
    _, second = await submitted_project(
        client_for, make_user, sign_in, property_type="OTHER", property_type_other="A hostel",
        construction_started=True,
    )  # fmt: skip
    draft_client = await homeowner(client_for, make_user, sign_in)
    await new_project(draft_client)  # a draft is never queued
    await relay(database)
    staff = await ops_staff(database, client_for, sign_in)
    entries = (await staff.client.get(QUEUE)).json()["entries"]
    assert [e["project"]["project_id"] for e in entries] == [first, second]
    assert entries[0]["project"]["review_flags"] == []
    assert entries[1]["project"]["review_flags"] == ["PROPERTY_TYPE_OTHER", "CONSTRUCTION_STARTED"]
    assert entries[0]["item"]["state"] == "OPEN"


async def test_the_queue_pages_with_a_cursor(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    for _ in range(3):
        await submitted_project(client_for, make_user, sign_in)
    await relay(database)
    async with database.transaction() as session:
        first = await open_items(session, QueueKind.REQUIREMENT_REVIEW, limit=2)
        rest = await open_items(session, QueueKind.REQUIREMENT_REVIEW, first.next_cursor, limit=2)
    assert len(first.items) == 2
    assert first.next_cursor is not None
    assert len(rest.items) == 1
    assert rest.next_cursor is None
    staff = await ops_staff(database, client_for, sign_in)
    bad = await staff.client.get(QUEUE, params={"cursor": "not-a-cursor"})
    assert bad.status_code == 422


async def test_claiming_and_releasing_is_one_person_at_a_time_and_audited(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    _, project_id = await submitted_project(client_for, make_user, sign_in)
    await relay(database)
    alice = await ops_staff(database, client_for, sign_in)
    bob = await ops_staff(database, client_for, sign_in)
    item_id = (await alice.client.get(QUEUE)).json()["entries"][0]["item"]["item_id"]
    claim = f"/api/v1/ops/queue-items/{item_id}/claim"
    release = f"/api/v1/ops/queue-items/{item_id}/release"

    claimed = (await alice.client.post(claim, headers=OPS_HEADERS)).json()
    assert (claimed["state"], claimed["claimed_by_me"], claimed["claimed_by_email"]) == (
        "CLAIMED", True, alice.email,
    )  # fmt: skip
    assert (await alice.client.post(claim, headers=OPS_HEADERS)).status_code == 200  # no-op
    assert (await bob.client.post(claim, headers=OPS_HEADERS)).status_code == 409
    assert (await bob.client.post(release, headers=OPS_HEADERS)).status_code == 409
    seen_by_bob = (await bob.client.get(QUEUE)).json()["entries"][0]["item"]
    assert (seen_by_bob["claimed_by_me"], seen_by_bob["claimed_by_email"]) == (False, alice.email)

    released = (await alice.client.post(release, headers=OPS_HEADERS)).json()
    assert (released["state"], released["claimed_by_email"]) == ("OPEN", None)
    assert (await bob.client.post(claim, headers=OPS_HEADERS)).json()["claimed_by_me"] is True

    async with database.transaction() as session:
        audit = list(
            await session.execute(
                select(AuditEvent.action, AuditEvent.project_id, AuditEvent.actor_user_id)
                .where(AuditEvent.entity_type == "ops_queue_item")
                .order_by(AuditEvent.at)
            )
        )
    assert [(a, p, u) for a, p, u in audit] == [
        ("ops_queue_item.claimed", uuid.UUID(project_id), alice.user_id),
        ("ops_queue_item.released", uuid.UUID(project_id), alice.user_id),
        ("ops_queue_item.claimed", uuid.UUID(project_id), bob.user_id),
    ]
    assert (
        await alice.client.post(
            f"/api/v1/ops/queue-items/{uuid.uuid4()}/claim", headers=OPS_HEADERS
        )
    ).status_code == 404


async def test_operations_see_the_whole_submission_read_only(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    family, project_id = await submitted_project(
        client_for, make_user, sign_in, property_type="OTHER", property_type_other="A hostel"
    )
    await relay(database)
    staff = await ops_staff(database, client_for, sign_in)
    detail = (await staff.client.get(f"/api/v1/ops/projects/{project_id}")).json()
    assert detail["project"]["status"] == "SUBMITTED"
    assert detail["project"]["review_flags"] == ["PROPERTY_TYPE_OTHER"]
    assert detail["requirement"]["answers"]["property_type_other"] == "A hostel"
    assert detail["requirement"]["question_set_version"] == 1
    assert detail["owner_email"] is None  # test homeowners are created without a contact
    assert detail["queue_item"]["state"] == "OPEN"
    assert detail["files"] == []
    # The homeowner never sees the review flags.
    mine = (await family.get(f"/api/v1/projects/{project_id}")).json()
    assert "review_flags" not in str(mine)
    assert (await staff.client.get(f"/api/v1/ops/projects/{uuid.uuid4()}")).status_code == 404


async def test_operations_downloads_are_logged_and_limited_to_available_requirement_files(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    _, project_id = await submitted_project(client_for, make_user, sign_in)
    staff = await ops_staff(database, client_for, sign_in)
    file_ids = {}
    async with database.transaction() as session:  # one file row per state, written directly
        for state in ("AVAILABLE", "SCANNING"):
            file_id = uuid.uuid4()
            session.add(
                FileObject(
                    id=file_id, bucket="test", object_key=f"test/{file_id}",
                    purpose="REQUIREMENT_UPLOAD", owner_user_id=staff.user_id,
                    project_id=uuid.UUID(project_id), original_name="plan.pdf",
                    declared_mime="application/pdf", size_bytes=10, state=state,
                )
            )  # fmt: skip
            file_ids[state] = file_id
    listed = (await staff.client.get(f"/api/v1/ops/projects/{project_id}")).json()["files"]
    assert {f["state"] for f in listed} == {"AVAILABLE", "SCANNING"}
    link = await staff.client.get(f"/api/v1/ops/files/{file_ids['AVAILABLE']}/url")
    assert link.status_code == 200
    assert link.json()["expires_in_seconds"] == 900
    assert (
        await staff.client.get(f"/api/v1/ops/files/{file_ids['SCANNING']}/url")
    ).status_code == 409
    assert (await staff.client.get(f"/api/v1/ops/files/{uuid.uuid4()}/url")).status_code == 404
    async with database.transaction() as session:
        viewers = list(await session.scalars(select(DocumentAccessLog.viewer_user_id)))
    assert viewers == [staff.user_id]


async def test_nobody_else_reaches_the_review_routes(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    await relay(database)
    admin = await verified_staff(database, client_for, sign_in, StaffRole.ADMIN)
    paths = [QUEUE, f"/api/v1/ops/projects/{project_id}"]
    for path in paths:
        assert (await family.get(path)).status_code == 404  # homeowner host: no such route
        assert (await admin.client.get(path)).status_code == 403  # ADMIN is not OPS
        anonymous = client_for(Audience.OPS)
        assert (await anonymous.get(path)).status_code == 401
    async with database.transaction() as session:
        assert await session.scalar(select(func.count()).select_from(OpsQueueItem)) == 1


async def test_enqueueing_keeps_working_after_the_statement_is_planned_generically(
    database: Database,
) -> None:
    """Regression: with a bound parameter in the partial-index predicate, Postgres stopped
    matching the index from the sixth execution on a connection ("no unique or exclusion
    constraint matching the ON CONFLICT specification")."""
    refs = [uuid.uuid4() for _ in range(8)]
    async with database.transaction() as session:
        for ref in refs + refs:  # each twice: the second is the idempotent no-op
            await enqueue_review(session, ref)
    async with database.transaction() as session:
        assert await session.scalar(select(func.count()).select_from(OpsQueueItem)) == 8
