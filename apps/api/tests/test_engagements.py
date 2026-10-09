"""Slice 3.4 (SLICE3_4_READINESS section 0): service needs from the requirement (N-01), package-
gated connections, the open-request cap per category (N-05), the response window (N-07), accept,
decline with reasons (N-06), withdraw, disclosure only after acceptance (N-08), one active
engagement per category (N-02), outside professionals, shared files, the package ending (N-10),
substantial-work usage (N-12), quote-review intake, notifications (N-11), operations, idempotency
and audit."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from procrastinate import App
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError

from p2b.audit.models import AuditEvent
from p2b.billing import handlers as billing_handlers
from p2b.billing.models import PackageServiceUsage
from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.jobs import RESOURCES_KEY, JobResources
from p2b.core.outbox import HandlerRegistry, OutboxEvent, relay_batch
from p2b.core.vocabulary import Audience, StaffRole
from p2b.documents.models import FileObject
from p2b.engagements import handlers as engagements_handlers
from p2b.engagements.models import Connection, EngagementEvent, ProjectEngagement
from p2b.engagements.service import expire_due
from p2b.identity.models import UserContact
from p2b.integrations.clamav import AcceptAllScanner
from p2b.integrations.email import MemoryEmailProvider
from p2b.notifications import handlers as notifications_handlers
from p2b.projects.models import Project
from tests.billing_support import admin_staff, configure, key, ops_key
from tests.conftest import ClientFactory, SignIn, UserFactory, csrf_headers
from tests.staff_support import OPS_HEADERS, Staff, verified_staff
from tests.test_billing import paid_package, refund_request
from tests.test_review_workspace import accept, review_ready

PRO_H = csrf_headers(Audience.PRO)
SERVICES = ["CONSTRUCTION", "CIVIL_WORK", "ARCHITECTURAL_DESIGN", "PROJECT_MANAGEMENT", "APPROVALS"]
PLOT = (21.2514, 81.6296)  # COMPLETE's location, Raipur
CONTACT = {"contact_name": "Meera Iyer", "contact_phone": "+91 98765 43210"}

Run = Callable[[], Awaitable[MemoryEmailProvider]]


@pytest.fixture
async def worker(
    app: FastAPI, database: Database, billing_app: App, notify_app: App
) -> AsyncIterator[Run]:
    """The worker for this slice: billing, engagements and notification subscribers on the
    outbox, then billing and notification jobs. Returns the mailbox of the run."""
    registry = HandlerRegistry()
    billing_handlers.register(registry, billing_app)
    engagements_handlers.register(registry, billing_app)
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


class World:
    def __init__(self, family: AsyncClient, project_id: str, admin: Staff) -> None:
        self.family = family
        self.project_id = project_id
        self.admin = admin
        self.order: dict[str, Any] = {}

    @property
    def base(self) -> str:
        return f"/api/v1/projects/{self.project_id}"


async def world(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    run: Run | None,
    *,
    services: list[str] | None = None,
) -> World:
    """An eligible project whose requirement names `services`; with the package when `run`."""
    admin = await admin_staff(database, client_for, sign_in)
    await configure(admin)
    family, project_id, ops = await review_ready(
        database, client_for, make_user, sign_in, services_needed=services or SERVICES
    )
    assert (await accept(ops, project_id)).status_code == 200
    w = World(family, project_id, admin)
    if run is not None:

        async def work() -> None:
            await run()

        w.order = await paid_package(app, work, family, client_for(Audience.IHB), project_id)
    return w


async def listed_pro(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    categories: tuple[str, ...] = ("CONTRACTOR",),
    *,
    name: str = "Ravi Builders",
    at: tuple[float, float] = PLOT,
    radius_km: int = 25,
    hidden: bool = False,
) -> tuple[AsyncClient, str, uuid.UUID]:
    """A professional listed in `categories` (approved through review elsewhere; here the rows
    are written directly). Returns the signed-in client, the profile id and the user id."""
    user_id = await make_user(Audience.PRO)
    client = client_for(Audience.PRO)
    await sign_in(client, user_id, Audience.PRO)
    profile_id = new_id()
    async with database.transaction() as session:
        await session.execute(
            text(
                "INSERT INTO professional_profiles (id, user_id, display_name, firm_name, "
                "base_locality, base_geom, service_radius_km) VALUES (:id, :user_id, :name, "
                ":firm, 'Raipur', ST_GeogFromText(:point), :radius)"
            ),
            {
                "id": profile_id, "user_id": user_id, "name": name, "firm": f"{name} & Co",
                "point": f"SRID=4326;POINT({at[1]} {at[0]})", "radius": radius_km,
            },
        )  # fmt: skip
        for code in categories:
            await session.execute(
                text(
                    "INSERT INTO professional_categories (id, profile_id, category_code, "
                    "listing_state, hidden, listed_at) VALUES (:id, :profile_id, :code, "
                    "'LISTED', :hidden, now())"
                ),
                {"id": new_id(), "profile_id": profile_id, "code": code, "hidden": hidden},
            )
    return client, str(profile_id), user_id


async def give_email(database: Database, user_id: uuid.UUID, email: str, audience: str) -> None:
    async with database.transaction() as session:
        session.add(
            UserContact(
                id=new_id(), user_id=user_id, audience=audience, kind="EMAIL", value=email,
                normalized=email, is_primary=True,
            )
        )  # fmt: skip


async def owner_of(database: Database, project_id: str) -> uuid.UUID:
    async with database.transaction() as session:
        return (await session.get_one(Project, uuid.UUID(project_id))).owner_user_id


async def send(w: World, profile_id: str, category: str = "CONTRACTOR", **extra: Any) -> Response:
    return await w.family.post(
        f"{w.base}/connections",
        json={"category": category, "profile_id": profile_id, **CONTACT, **extra},
        headers=key(),
    )


async def sent(w: World, profile_id: str, category: str = "CONTRACTOR") -> str:
    response = await send(w, profile_id, category)
    assert response.status_code == 201, response.text
    row = category_of(response.json(), category)
    return str(next(c["id"] for c in row["connections"] if c["profile_id"] == profile_id))


def category_of(services: dict[str, Any], code: str) -> dict[str, Any]:
    row: dict[str, Any] = next(c for c in services["categories"] if c["code"] == code)
    return row


async def services(w: World) -> dict[str, Any]:
    response = await w.family.get(f"{w.base}/services")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def reason(response: Response) -> str:
    body = response.json()["error"]
    return str(body["details"].get("reason") or body["code"])


async def pro_post(client: AsyncClient, connection_id: str, action: str, **body: Any) -> Response:
    return await client.post(
        f"/api/v1/pro/connections/{connection_id}/{action}",
        json=body,
        headers={**PRO_H, "Idempotency-Key": str(uuid.uuid4())},
    )


async def connection_state(database: Database, connection_id: str) -> tuple[str, str | None]:
    async with database.transaction() as session:
        row = await session.get_one(Connection, uuid.UUID(connection_id))
        return row.state, row.withdraw_reason


async def overdue(database: Database, connection_id: str) -> None:
    """Move a request's window into the past (the lifecycle guard is lifted for the test)."""
    async with database.transaction() as session:
        await session.execute(
            text("ALTER TABLE connections DISABLE TRIGGER connections_lifecycle_only")
        )
        await session.execute(
            update(Connection)
            .where(Connection.id == uuid.UUID(connection_id))
            .values(respond_by=func.now() - text("interval '1 minute'"))
        )
        await session.execute(
            text("ALTER TABLE connections ENABLE TRIGGER connections_lifecycle_only")
        )


def test_connection_events_map_to_the_n11_notifications() -> None:
    from p2b.notifications.service import Kind, kinds_for

    assert kinds_for("connection.sent", {}) == [
        Kind.FAMILY_CONNECTION_SENT,
        Kind.PRO_CONNECTION_RECEIVED,
    ]
    assert kinds_for("connection.accepted", {}) == [Kind.FAMILY_CONNECTION_ACCEPTED]
    assert kinds_for("connection.declined", {}) == [Kind.FAMILY_CONNECTION_DECLINED]
    assert kinds_for("connection.expired", {}) == [Kind.FAMILY_CONNECTION_EXPIRED]
    assert kinds_for("connection.withdrawn", {"reason": "PACKAGE_ENDED"}) == [
        Kind.FAMILY_CONNECTION_WITHDRAWN,
        Kind.PRO_CONNECTION_WITHDRAWN,
    ]
    assert kinds_for("connection.withdrawn", {"reason": "FAMILY"}) == [
        Kind.PRO_CONNECTION_WITHDRAWN
    ]
    assert kinds_for("quote_review.submitted", {}) == [Kind.OPS_QUOTE_REVIEW_SUBMITTED]


# --- needs ---------------------------------------------------------------------------------


async def test_needs_follow_the_requirement_and_the_family_can_change_them(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, None)
    body = await services(w)
    needs = {c["code"]: c["need"] for c in body["categories"]}
    # N-01: construction and civil work are the Contractor; civil work is never the site/civil
    # engineer; project management and approvals create no need.
    assert needs == {
        "CONTRACTOR": "NEEDED", "ARCHITECT": "NEEDED", "STRUCTURAL_ENGINEER": "UNDECIDED",
        "SITE_CIVIL_ENGINEER": "UNDECIDED", "MEP": "UNDECIDED", "INTERIOR_DESIGNER": "UNDECIDED",
        "SPECIALIST": "UNDECIDED",
    }  # fmt: skip
    assert body["can_act"] is True
    assert category_of(body, "SPECIALIST")["subtypes"]["SOLAR"] == "Solar"
    response = await w.family.put(
        f"{w.base}/services/SPECIALIST/need",
        json={"state": "NEEDED", "subtypes": ["SOLAR", "WATERPROOFING"]},
        headers=key(),
    )
    assert response.status_code == 200, response.text
    specialist = category_of(response.json(), "SPECIALIST")
    assert (specialist["need"], specialist["need_source"]) == ("NEEDED", "FAMILY")
    assert specialist["chosen_subtypes"] == ["SOLAR", "WATERPROOFING"]
    async with database.transaction() as session:
        assert "service_need.set" in set(await session.scalars(select(AuditEvent.action)))
    bad = await w.family.put(
        f"{w.base}/services/SPECIALIST/need", json={"state": "NEEDED", "subtypes": ["X"]},
        headers=key(),
    )  # fmt: skip
    assert bad.status_code == 422
    missing = await w.family.put(
        f"{w.base}/services/NOPE/need", json={"state": "NEEDED"}, headers=key()
    )
    assert missing.status_code == 404
    not_needed = await w.family.put(
        f"{w.base}/services/ARCHITECT/need", json={"state": "NOT_NEEDED"}, headers=key()
    )
    assert category_of(not_needed.json(), "ARCHITECT")["need"] == "NOT_NEEDED"


async def test_only_the_projects_owner_sees_and_acts(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, None)
    _, profile_id, _ = await listed_pro(database, client_for, make_user, sign_in)
    stranger = client_for(Audience.IHB)
    await sign_in(stranger, await make_user(), Audience.IHB)
    assert (await stranger.get(f"{w.base}/services")).status_code == 404
    other = World(stranger, w.project_id, w.admin)
    assert (await send(other, profile_id)).status_code == 404
    pro = client_for(Audience.PRO)
    await sign_in(pro, await make_user(Audience.PRO), Audience.PRO)
    assert (await pro.get(f"{w.base}/services")).status_code in (401, 403, 404)
    # A project not yet through the initial review cannot coordinate anything.
    early, early_id = await _submitted(client_for, make_user, sign_in)
    response = await early.post(
        f"/api/v1/projects/{early_id}/engagements",
        json={"category": "CONTRACTOR", "name": "Own builder"},
        headers=key(),
    )
    assert (response.status_code, reason(response)) == (409, "NOT_ELIGIBLE")


async def _submitted(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> tuple[AsyncClient, str]:
    from tests.test_operations import submitted_project

    return await submitted_project(client_for, make_user, sign_in)


# --- sending -------------------------------------------------------------------------------


async def test_a_connection_needs_an_active_package(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, None)
    _, profile_id, _ = await listed_pro(database, client_for, make_user, sign_in)
    response = await send(w, profile_id)
    assert (response.status_code, reason(response)) == (409, "PACKAGE_REQUIRED")
    target = await w.family.get(
        f"{w.base}/connection-target", params={"category": "CONTRACTOR", "profile_id": profile_id}
    )
    assert target.status_code == 200
    assert target.json()["blocked"] == "PACKAGE_REQUIRED"
    # An outside professional needs no package.
    outside = await w.family.post(
        f"{w.base}/engagements", json={"category": "CONTRACTOR", "name": "Own builder"},
        headers=key(),
    )  # fmt: skip
    assert outside.status_code == 201, outside.text


async def test_category_listing_and_service_area_decide_who_can_be_asked(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, worker)
    _, architect, _ = await listed_pro(database, client_for, make_user, sign_in, ("ARCHITECT",))
    _, hidden, _ = await listed_pro(database, client_for, make_user, sign_in, hidden=True)
    _, far, _ = await listed_pro(
        database, client_for, make_user, sign_in, at=(19.0760, 72.8777), radius_km=50
    )
    _, near, _ = await listed_pro(database, client_for, make_user, sign_in)
    for profile_id, expected in ((architect, "NOT_LISTED"), (hidden, "NOT_LISTED"),
                                 (far, "OUTSIDE_AREA")):  # fmt: skip
        response = await send(w, profile_id)
        assert (response.status_code, reason(response)) == (409, expected)
    target = await w.family.get(
        f"{w.base}/connection-target", params={"category": "CONTRACTOR", "profile_id": far}
    )
    assert target.json()["blocked"] == "OUTSIDE_AREA"
    unknown = await send(w, near, "NOPE")
    assert unknown.status_code == 404
    await w.family.put(
        f"{w.base}/services/CONTRACTOR/need", json={"state": "NOT_NEEDED"}, headers=key()
    )
    response = await send(w, near)
    assert (response.status_code, reason(response)) == (409, "NOT_NEEDED")
    # An undecided need becomes NEEDED when the family asks someone.
    _, structural, _ = await listed_pro(
        database, client_for, make_user, sign_in, ("STRUCTURAL_ENGINEER",)
    )
    await sent(w, structural, "STRUCTURAL_ENGINEER")
    assert category_of(await services(w), "STRUCTURAL_ENGINEER")["need"] == "NEEDED"


async def test_three_open_requests_per_category_no_duplicates_and_categories_independent(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, worker)
    pros = [
        await listed_pro(
            database,
            client_for,
            make_user,
            sign_in,
            ("CONTRACTOR", "ARCHITECT"),
            name=f"Builder {i}",
        )
        for i in range(4)
    ]
    ids = [await sent(w, p[1]) for p in pros[:3]]
    duplicate = await send(w, pros[0][1])
    assert (duplicate.status_code, reason(duplicate)) == (409, "DUPLICATE")
    fourth = await send(w, pros[3][1])
    assert (fourth.status_code, reason(fourth)) == (409, "OPEN_LIMIT")
    assert fourth.json()["error"]["details"]["limit"] == 3
    # Another category has its own cap (no global limit, N-05).
    for pro in pros[:3]:
        await sent(w, pro[1], "ARCHITECT")
    # A declined request frees a place.
    declined = await pro_post(pros[0][0], ids[0], "decline", reason="UNAVAILABLE")
    assert declined.status_code == 200, declined.text
    await sent(w, pros[3][1])
    row = category_of(await services(w), "CONTRACTOR")
    assert (row["open_requests"], row["open_limit"]) == (3, 3)


# --- responding ----------------------------------------------------------------------------


async def test_acceptance_reveals_contacts_engages_and_withdraws_the_other_requests(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, worker)
    owner = await owner_of(database, w.project_id)
    await give_email(database, owner, "family@example.in", "ihb")
    chosen, chosen_id, chosen_user = await listed_pro(database, client_for, make_user, sign_in)
    await give_email(database, chosen_user, "ravi@example.in", "pro")
    other, other_id, _ = await listed_pro(database, client_for, make_user, sign_in, name="Other")
    first = await sent(w, chosen_id)
    second = await sent(w, other_id)
    response = await w.family.post(
        f"{w.base}/connections",
        json={"category": "CONTRACTOR", "profile_id": chosen_id, **CONTACT},
        headers=key(),
    )
    assert reason(response) == "DUPLICATE"

    # Before acceptance: the brief only (N-08).
    listing = (await chosen.get("/api/v1/pro/connections")).json()["items"]
    assert [item["id"] for item in listing] == [first]
    before = (await chosen.get(f"/api/v1/pro/connections/{first}")).json()
    assert before["family_contact"] is None
    assert before["location"] is None
    assert before["engagement_id"] is None
    assert before["brief"]["locality"] == "Shankar Nagar"
    assert "Meera" not in str(before)
    assert "98765" not in str(before)
    assert "family@example.in" not in str(before)
    # Another professional cannot see it.
    assert (await other.get(f"/api/v1/pro/connections/{first}")).status_code == 404

    accepted = await pro_post(chosen, first, "accept", phone="+91 90000 11111")
    assert accepted.status_code == 200, accepted.text
    after = accepted.json()
    assert after["state"] == "ACCEPTED"
    assert after["engagement_state"] == "ACTIVE"
    assert after["family_contact"] == {
        "name": "Meera Iyer", "phone": "+91 98765 43210", "email": "family@example.in",
        "site_address": None,
    }  # fmt: skip
    assert after["location"] == {"lat": pytest.approx(PLOT[0]), "lng": pytest.approx(PLOT[1])}

    row = category_of(await services(w), "CONTRACTOR")
    assert row["engagement"]["party"] == "LISTED"
    # The accepted request names its engagement, so the professional reaches the workspace from it.
    assert after["engagement_id"] == row["engagement"]["id"]
    workspace = await chosen.get(f"/api/v1/pro/engagements/{after['engagement_id']}")
    assert workspace.status_code == 200, workspace.text
    again = (await chosen.get(f"/api/v1/pro/connections/{first}")).json()
    assert again["engagement_id"] == after["engagement_id"]
    assert row["engagement"]["professional_contact"] == {
        "name": "Ravi Builders", "firm": "Ravi Builders & Co", "phone": "+91 90000 11111",
        "email": "ravi@example.in",
    }  # fmt: skip
    states = {c["id"]: (c["state"], c["withdraw_reason"]) for c in row["connections"]}
    assert states == {first: ("ACCEPTED", None), second: ("WITHDRAWN", "ANOTHER_ENGAGED")}
    assert (await pro_post(other, second, "accept")).status_code == 409
    # One active engagement per category (N-02).
    _, third_id, _ = await listed_pro(database, client_for, make_user, sign_in, name="Third")
    blocked = await send(w, third_id)
    assert (blocked.status_code, reason(blocked)) == (409, "ENGAGED")
    # Substantial work is recorded once, on acceptance (N-12).
    async with database.transaction() as session:
        usage = list(await session.scalars(select(PackageServiceUsage.service)))
    assert usage == ["CONNECTION_ACCEPTED"]
    # Notifications (N-11): nothing private before acceptance.
    mailbox = await worker()
    by_to = {(m.to, m.subject) for m in mailbox.sent}
    assert ("family@example.in", "Your Plan2Build connection request has been sent") in by_to
    assert ("family@example.in", "Your Plan2Build connection request was accepted") in by_to
    assert ("ravi@example.in", "You have a new Plan2Build connection request") in by_to
    new_request = next(m for m in mailbox.sent if m.to == "ravi@example.in")
    assert "Meera" not in new_request.text
    assert "98765" not in new_request.text


async def test_declining_needs_a_reason_and_the_family_sees_a_neutral_message(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, worker)
    await give_email(database, await owner_of(database, w.project_id), "family@example.in", "ihb")
    pro, profile_id, _ = await listed_pro(database, client_for, make_user, sign_in)
    connection_id = await sent(w, profile_id)
    no_note = await pro_post(pro, connection_id, "decline", reason="OTHER")
    assert no_note.status_code == 422
    unknown = await pro_post(pro, connection_id, "decline", reason="BUSY")
    assert unknown.status_code == 422
    response = await pro_post(pro, connection_id, "decline", reason="OTHER", note="Site too far.")
    assert response.status_code == 200, response.text
    assert response.json()["decline_reason"] == "OTHER"
    family_view = category_of(await services(w), "CONTRACTOR")["connections"][0]
    assert family_view["state"] == "DECLINED"
    assert "decline_reason" not in family_view
    assert "Site too far" not in str(family_view)
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    detail = (await ops.client.get(f"/api/v1/ops/projects/{w.project_id}/engagements")).json()
    assert detail["connections"][0]["decline_note"] == "Site too far."
    assert (await pro_post(pro, connection_id, "accept")).status_code == 409
    mailbox = await worker()
    declined = next(m for m in mailbox.sent if "declined" in m.subject)
    assert declined.subject == "Your Plan2Build connection request was declined"
    assert "far" not in declined.text


async def test_a_request_expires_after_its_window_and_a_new_one_may_be_sent(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, worker)
    await give_email(database, await owner_of(database, w.project_id), "family@example.in", "ihb")
    pro, profile_id, _ = await listed_pro(database, client_for, make_user, sign_in)
    connection_id = await sent(w, profile_id)
    async with database.transaction() as session:
        row = await session.get_one(Connection, uuid.UUID(connection_id))
        window = row.respond_by - row.sent_at
    assert window.total_seconds() == get_settings().connection_response_hours * 3600 == 48 * 3600
    async with database.transaction() as session:
        assert await expire_due(session) == 0  # not yet due
    await overdue(database, connection_id)
    late = await pro_post(pro, connection_id, "accept")
    assert (late.status_code, reason(late)) == (409, "EXPIRED")
    async with database.transaction() as session:
        assert await expire_due(session) == 1
    async with database.transaction() as session:
        assert await expire_due(session) == 0  # once
    assert await connection_state(database, connection_id) == ("EXPIRED", None)
    again = await sent(w, profile_id)  # no auto-accept; a new request is allowed
    assert again != connection_id
    mailbox = await worker()
    expired = [m for m in mailbox.sent if m.subject == "Your Plan2Build connection request expired"]
    assert [m.to for m in expired] == ["family@example.in"]  # once, no reminder before


async def test_the_family_withdraws_an_open_request(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, worker)
    pro, profile_id, _ = await listed_pro(database, client_for, make_user, sign_in)
    connection_id = await sent(w, profile_id)
    url = f"{w.base}/connections/{connection_id}/withdraw"
    assert (await w.family.post(url, headers=key())).status_code == 200
    assert await connection_state(database, connection_id) == ("WITHDRAWN", "FAMILY")
    assert (await w.family.post(url, headers=key())).status_code == 409
    assert (await pro_post(pro, connection_id, "accept")).status_code == 409
    mailbox = await worker()
    subjects = {(m.subject) for m in mailbox.sent}
    assert "Your Plan2Build connection request was withdrawn" not in subjects  # they did it


# --- engagements ---------------------------------------------------------------------------


async def test_listed_and_outside_professionals_side_by_side_one_active_per_category(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, worker)
    architect, architect_id, _ = await listed_pro(
        database, client_for, make_user, sign_in, ("ARCHITECT",)
    )
    _, contractor_id, _ = await listed_pro(database, client_for, make_user, sign_in)
    open_contractor = await sent(w, contractor_id)
    outside = await w.family.post(
        f"{w.base}/engagements",
        json={"category": "CONTRACTOR", "name": "Sharma Constructions", "contact": "0771 400 000"},
        headers=key(),
    )
    assert outside.status_code == 201, outside.text
    contractor = category_of(outside.json(), "CONTRACTOR")
    assert contractor["engagement"]["party"] == "OUTSIDE"
    assert contractor["engagement"]["contact"] == "0771 400 000"
    assert await connection_state(database, open_contractor) == ("WITHDRAWN", "ANOTHER_ENGAGED")
    again = await w.family.post(
        f"{w.base}/engagements", json={"category": "CONTRACTOR", "name": "Second"}, headers=key()
    )
    assert (again.status_code, reason(again)) == (409, "ENGAGED")
    # The architect through Plan2Build on the same project (modularity).
    accepted = await pro_post(architect, await sent(w, architect_id, "ARCHITECT"), "accept")
    assert accepted.status_code == 200, accepted.text
    body = await services(w)
    assert category_of(body, "ARCHITECT")["engagement"]["party"] == "LISTED"
    assert category_of(body, "CONTRACTOR")["engagement"]["party"] == "OUTSIDE"
    # A need with an active engagement cannot be marked not needed.
    refused = await w.family.put(
        f"{w.base}/services/CONTRACTOR/need", json={"state": "NOT_NEEDED"}, headers=key()
    )
    assert (refused.status_code, reason(refused)) == (409, "IN_USE")
    # Ending frees the category; history keeps the ended engagement.
    engagement_id = contractor["engagement"]["id"]
    ended = await w.family.post(
        f"{w.base}/engagements/{engagement_id}/end", json={"reason": "Contract finished."},
        headers=key(),
    )  # fmt: skip
    assert ended.status_code == 200, ended.text
    row = category_of(ended.json(), "CONTRACTOR")
    assert row["engagement"] is None
    assert [e["state"] for e in row["past_engagements"]] == ["ENDED"]
    await sent(w, contractor_id)


async def test_the_family_shares_files_with_an_active_engagement_only(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, worker)
    pro, profile_id, _ = await listed_pro(database, client_for, make_user, sign_in)
    owner = await owner_of(database, w.project_id)
    file_id = await stored_file(database, owner, "REQUIREMENT_UPLOAD", w.project_id)
    connection_id = await sent(w, profile_id)
    file_url = f"/api/v1/pro/connections/{connection_id}/files/{file_id}/url"
    assert (await pro.get(file_url)).status_code == 404  # not accepted, nothing shared
    await pro_post(pro, connection_id, "accept")
    engagement_id = category_of(await services(w), "CONTRACTOR")["engagement"]["id"]
    assert (await pro.get(file_url)).status_code == 404  # nothing shared by default
    share = f"{w.base}/engagements/{engagement_id}/files"
    shared = await w.family.post(share, json={"file_ids": [file_id]}, headers=key())
    assert shared.status_code == 200, shared.text
    again = await w.family.post(share, json={"file_ids": [file_id]}, headers=key())
    assert category_of(again.json(), "CONTRACTOR")["engagement"]["shared_file_ids"] == [file_id]
    detail = (await pro.get(f"/api/v1/pro/connections/{connection_id}")).json()
    assert [f["file_id"] for f in detail["shared_files"]] == [file_id]
    assert (await pro.get(file_url)).status_code == 200
    foreign = await stored_file(database, owner, "REQUIREMENT_UPLOAD", None)
    bad = await w.family.post(share, json={"file_ids": [foreign]}, headers=key())
    assert bad.status_code == 422
    unshared = await w.family.delete(f"{share}/{file_id}", headers=key())
    assert unshared.status_code == 200
    assert (await pro.get(file_url)).status_code == 404
    await w.family.post(share, json={"file_ids": [file_id]}, headers=key())
    ended = await pro_post(pro, connection_id, "end", reason="Work complete.")
    assert ended.status_code == 200, ended.text
    assert ended.json()["family_contact"] is not None  # disclosed once, kept in history
    assert ended.json()["location"] is None
    assert ended.json()["shared_files"] == []
    assert (await pro.get(file_url)).status_code == 404


async def stored_file(
    database: Database, owner: uuid.UUID, purpose: str, project_id: str | None,
    state: str = "AVAILABLE",
) -> str:  # fmt: skip
    file_id = new_id()
    async with database.transaction() as session:
        session.add(
            FileObject(
                id=file_id, bucket="test", object_key=f"test/{file_id}", purpose=purpose,
                owner_user_id=owner, project_id=uuid.UUID(project_id) if project_id else None,
                original_name="quote.pdf", declared_mime="application/pdf", size_bytes=1000,
                state=state,
            )
        )  # fmt: skip
    return str(file_id)


# --- the package ending --------------------------------------------------------------------


async def test_a_refund_withdraws_open_requests_and_keeps_the_engagement(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, worker)
    architect, architect_id, _ = await listed_pro(
        database, client_for, make_user, sign_in, ("ARCHITECT",)
    )
    _, contractor_id, _ = await listed_pro(database, client_for, make_user, sign_in)
    await pro_post(architect, await sent(w, architect_id, "ARCHITECT"), "accept")
    pending = await sent(w, contractor_id)
    request_id = await refund_request(w.family, w.order["order_id"])
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    detail = (await ops.client.get(f"/api/v1/ops/billing/orders/{w.order['order_id']}")).json()
    assert "CONNECTION_ACCEPTED" in str(detail)  # visible to operations for the refund (N-12)
    approved = await ops.client.post(
        f"/api/v1/ops/billing/refund-requests/{request_id}/approve",
        json={"amount": w.order["total"], "ends_package": True, "reason": "Refund agreed."},
        headers=ops_key(),
    )
    assert approved.status_code == 200, approved.text
    await worker()
    assert await connection_state(database, pending) == ("WITHDRAWN", "PACKAGE_ENDED")
    body = await services(w)
    assert body["package_state"] == "REFUNDED"
    architect_row = category_of(body, "ARCHITECT")
    assert architect_row["engagement"]["state"] == "ACTIVE"  # the relationship is theirs
    assert category_of(body, "CONTRACTOR")["connections"][0]["state"] == "WITHDRAWN"
    blocked = await send(w, contractor_id)
    assert (blocked.status_code, reason(blocked)) == (409, "PACKAGE_REQUIRED")
    outside = await w.family.post(
        f"{w.base}/engagements", json={"category": "CONTRACTOR", "name": "Own"}, headers=key()
    )
    assert outside.status_code == 201


async def test_a_suspended_listing_withdraws_open_requests_and_hiding_does_not(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, worker)
    hiding, hiding_id, _ = await listed_pro(database, client_for, make_user, sign_in)
    _, suspended_id, _ = await listed_pro(database, client_for, make_user, sign_in, name="Sus")
    first = await sent(w, hiding_id)
    second = await sent(w, suspended_id)
    hide = await hiding.post("/api/v1/pro/categories/CONTRACTOR/hide", headers=PRO_H)
    assert hide.status_code == 200, hide.text
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    async with database.transaction() as session:
        category_id = await session.scalar(
            text(
                "SELECT id FROM professional_categories WHERE profile_id = :p "
                "AND category_code = 'CONTRACTOR'"
            ),
            {"p": uuid.UUID(suspended_id)},
        )
    suspended = await ops.client.post(
        f"/api/v1/ops/professional-categories/{category_id}/suspend",
        json={"reason": "Licence lapsed."},
        headers=ops_key(),
    )
    assert suspended.status_code == 200, suspended.text
    await worker()
    assert await connection_state(database, first) == ("SENT", None)
    assert await connection_state(database, second) == ("WITHDRAWN", "PROFESSIONAL_UNAVAILABLE")
    assert (await pro_post(hiding, first, "accept")).status_code == 200


# --- quote-holder review intake ------------------------------------------------------------


async def test_a_quote_the_family_holds_reaches_operations_with_the_package(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, None)
    owner = await owner_of(database, w.project_id)
    quote = await stored_file(database, owner, "QUOTE_DOCUMENT", None)
    body = {"category": "CONTRACTOR", "quoted_by": "Sharma Constructions", "file_ids": [quote]}
    without = await w.family.post(f"{w.base}/quote-reviews", json=body, headers=key())
    assert (without.status_code, reason(without)) == (409, "PACKAGE_REQUIRED")

    async def work() -> None:
        await worker()

    await paid_package(app, work, w.family, client_for(Audience.IHB), w.project_id)
    ticket = await w.family.post(
        f"{w.base}/quote-reviews/uploads",
        json={"file_name": "quote.pdf", "content_type": "application/pdf", "size_bytes": 2048},
        headers=key(),
    )
    assert ticket.status_code == 201, ticket.text
    assert ticket.json()["file"]["state"] == "PENDING_UPLOAD"
    pending = ticket.json()["file"]["file_id"]
    state = await w.family.get(f"{w.base}/quote-reviews/uploads/{pending}")
    assert state.json()["state"] == "PENDING_UPLOAD"
    stranger = client_for(Audience.IHB)
    await sign_in(stranger, await make_user(), Audience.IHB)
    assert (await stranger.get(f"{w.base}/quote-reviews/uploads/{pending}")).status_code == 404
    refused = await w.family.post(
        f"{w.base}/quote-reviews", json={**body, "file_ids": [pending]}, headers=key()
    )
    assert refused.status_code == 422  # not uploaded and checked yet
    other_user = await make_user()
    theirs = await stored_file(database, other_user, "QUOTE_DOCUMENT", None)
    assert (
        await w.family.post(f"{w.base}/quote-reviews", json={**body, "file_ids": [theirs]},
                            headers=key())
    ).status_code == 422  # fmt: skip
    submitted = await w.family.post(f"{w.base}/quote-reviews", json=body, headers=key())
    assert submitted.status_code == 201, submitted.text
    review = submitted.json()["quote_reviews"][0]
    assert (review["state"], review["quoted_by"]) == ("SUBMITTED", "Sharma Constructions")
    assert [f["file_id"] for f in review["files"]] == [quote]
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    detail = (await ops.client.get(f"/api/v1/ops/projects/{w.project_id}/engagements")).json()
    assert detail["quote_reviews"][0]["file_ids"] == [quote]
    assert (await ops.client.get(f"/api/v1/ops/files/{quote}/url")).status_code == 200
    async with database.transaction() as session:
        events = list(await session.scalars(select(OutboxEvent.event_type)))
    assert "quote_review.submitted" in events


# --- operations, idempotency, audit --------------------------------------------------------


async def test_operations_withdraw_and_end_with_mfa_and_a_reason(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, worker)
    pro, profile_id, _ = await listed_pro(database, client_for, make_user, sign_in)
    _, other_id, _ = await listed_pro(database, client_for, make_user, sign_in, name="Other")
    open_id = await sent(w, other_id)
    await pro_post(pro, await sent(w, profile_id), "accept")
    unverified = await _unverified_ops(database, client_for, sign_in)
    url = f"/api/v1/ops/projects/{w.project_id}/engagements"
    assert (await unverified.client.get(url)).status_code == 403
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    detail = (await ops.client.get(url)).json()
    assert {c["state"] for c in detail["connections"]} == {"ACCEPTED", "WITHDRAWN"}
    assert await connection_state(database, open_id) == ("WITHDRAWN", "ANOTHER_ENGAGED")
    engagement_id = detail["engagements"][0]["id"]
    no_reason = await ops.client.post(
        f"/api/v1/ops/engagements/{engagement_id}/end", json={"reason": " "}, headers=ops_key()
    )
    assert no_reason.status_code == 422
    ended = await ops.client.post(
        f"/api/v1/ops/engagements/{engagement_id}/end", json={"reason": "Family asked us."},
        headers=ops_key(),
    )  # fmt: skip
    assert ended.status_code == 200, ended.text
    assert ended.json()["engagements"][0]["ended_by_role"] == "OPS"
    new_id_ = await sent(w, other_id)
    withdrawn = await ops.client.post(
        f"/api/v1/ops/connections/{new_id_}/withdraw", json={"reason": "Duplicate request."},
        headers=ops_key(),
    )  # fmt: skip
    assert withdrawn.status_code == 200, withdrawn.text
    assert await connection_state(database, new_id_) == ("WITHDRAWN", "OPERATIONS")
    history = withdrawn.json()["history"]
    assert any(h["actor_role"] == "OPS" and h["to_state"] == "WITHDRAWN" for h in history)
    assert all(h["actor_role"] for h in history)
    _ = OPS_HEADERS


async def _unverified_ops(database: Database, client_for: ClientFactory, sign_in: SignIn) -> Staff:
    from tests.staff_support import make_staff

    return await make_staff(database, client_for, sign_in, StaffRole.OPS)


async def test_sending_is_idempotent_and_every_change_is_audited_and_guarded(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    w = await world(app, database, client_for, make_user, sign_in, worker)
    pro, profile_id, _ = await listed_pro(database, client_for, make_user, sign_in)
    headers = key()
    body = {"category": "CONTRACTOR", "profile_id": profile_id, **CONTACT}
    first = await w.family.post(f"{w.base}/connections", json=body, headers=headers)
    replay = await w.family.post(f"{w.base}/connections", json=body, headers=headers)
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    changed = await w.family.post(
        f"{w.base}/connections", json={**body, "contact_name": "Someone"}, headers=headers
    )
    assert changed.status_code == 409
    async with database.transaction() as session:
        assert await session.scalar(select(func.count()).select_from(Connection)) == 1
    connection_id = category_of(first.json(), "CONTRACTOR")["connections"][0]["id"]
    accept_key = {**PRO_H, "Idempotency-Key": str(uuid.uuid4())}
    url = f"/api/v1/pro/connections/{connection_id}/accept"
    one = await pro.post(url, json={}, headers=accept_key)
    two = await pro.post(url, json={}, headers=accept_key)
    assert one.status_code == two.status_code == 200
    async with database.transaction() as session:
        assert await session.scalar(select(func.count()).select_from(ProjectEngagement)) == 1
        actions = set(await session.scalars(select(AuditEvent.action)))
        history = list(
            await session.execute(
                select(
                    EngagementEvent.subject, EngagementEvent.to_state, EngagementEvent.actor_role
                )
            )
        )
    assert {"connection.sent", "connection.accepted", "engagement.active"} <= actions
    assert ("CONNECTION", "ACCEPTED", "PROFESSIONAL") in [tuple(h) for h in history]
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(update(EngagementEvent).values(reason="changed"))
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(update(Connection).values(brief={}))
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("DELETE FROM project_engagements"))
    # Bad input is refused at the boundary.
    bad_phone = await w.family.post(
        f"{w.base}/connections", json={**body, "contact_phone": "call me"}, headers=key()
    )
    assert bad_phone.status_code == 422
    extra = await w.family.post(f"{w.base}/connections", json={**body, "budget": 1}, headers=key())
    assert extra.status_code == 422


async def test_a_cancelled_project_withdraws_its_open_requests(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
    app: FastAPI, worker: Run,
) -> None:  # fmt: skip
    """`project.cancelled` withdraws open requests (the handler, called as the relay would)."""
    from p2b.core.outbox import DeliveredEvent

    w = await world(app, database, client_for, make_user, sign_in, worker)
    _, profile_id, _ = await listed_pro(database, client_for, make_user, sign_in)
    connection_id = await sent(w, profile_id)
    registry = HandlerRegistry()
    engagements_handlers.register(registry, None)  # type: ignore[arg-type]
    event = DeliveredEvent(
        new_id(), "project.cancelled", "project", uuid.UUID(w.project_id),
        {"project_id": w.project_id}, None,
    )  # fmt: skip
    for _ in range(2):  # redelivery changes nothing
        async with database.transaction() as session:
            for handler in registry.handlers_for("project.cancelled"):
                await handler(session, event)
    assert await connection_state(database, connection_id) == ("WITHDRAWN", "PROJECT_CLOSED")
