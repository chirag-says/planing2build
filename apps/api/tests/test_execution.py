"""Slice 3.7A (SLICE3_7_READINESS section 0, D, E, M, N, P.A): progress updates in the standard
format (EX-02), completion request, owner confirm and return, operations with a reason (EX-03),
gate stages wait for clearance, no dates or percentages (EX-04), informational payment marks
(EX-05), contractor transition with history (EX-19), household read-only (EX-21), the operations
exception threshold (EX-12), notifications, idempotency, concurrency and audit."""

import asyncio
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from p2b.audit.models import AuditEvent
from p2b.construction.models import ConstructionEvent, StageUpdate
from p2b.core.db import Database
from p2b.money.models import PaymentMark
from p2b.notifications.service import Kind, kinds_for
from tests.billing_support import key
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.execution_support import (
    GATES,
    MILESTONES,
    PRO_H,
    Site,
    household,
    ok,
    ops_key,
    photo,
    post,
    pro_key,
    reason,
    requested,
    set_gate,
    site,
    stage,
    stages,
    update_body,
)
from tests.rfq_support import keys_of
from tests.test_engagements import Run, listed_pro, world

FORBIDDEN_KEYS = {
    "percent", "percentage", "progress_percent", "planned_start", "planned_end", "delay",
    "behind_plan", "amount", "contract_value", "balance", "settled",
}  # fmt: skip


@pytest.fixture
def worker(rfq_worker: Run) -> Run:
    """The 3.6 worker (billing, engagements, rfq and notification subscribers)."""
    return rfq_worker


def no_forbidden_keys(body: Any) -> None:
    assert not keys_of(body) & FORBIDDEN_KEYS, keys_of(body) & FORBIDDEN_KEYS


async def _site(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn, worker: Run, **kwargs: Any,
) -> Site:  # fmt: skip
    return await site(app, database, client_for, make_user, sign_in, worker, **kwargs)


def test_execution_notices_map_to_their_notifications() -> None:
    def kinds(event: str, notice: str) -> list[Kind]:
        return kinds_for(event, {"notice": notice})

    assert kinds("construction.family_notice", "COMPLETION_REQUESTED") == [
        Kind.FAMILY_STAGE_COMPLETION_REQUESTED
    ]
    assert kinds("construction.family_notice", "PAYMENT_DUE") == [Kind.FAMILY_PAYMENT_MILESTONE_DUE]
    assert kinds("construction.contractor_notice", "STAGE_RETURNED") == [Kind.PRO_STAGE_RETURNED]
    assert kinds("construction.contractor_notice", "MARKED_PAID") == [Kind.PRO_PAYMENT_MARKED_PAID]
    assert kinds("construction.ops_notice", "GATE_COMPLETION_REQUESTED") == [
        Kind.OPS_GATE_COMPLETION_REQUESTED
    ]
    assert kinds("construction.family_notice", "UNKNOWN") == []


async def test_the_contractor_reports_and_the_owner_confirms(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s = await _site(app, database, client_for, make_user, sign_in, worker)
    assert s.pro is not None
    assert s.pro_user is not None
    first = await stage(s, 1)
    assert (first["state"], first["update_count"], first["actual_start"]) == (
        "NOT_STARTED", 0, None,
    )  # fmt: skip
    # Any stage may start: no ordering guard until BP-07A (EX-04).
    later = await stage(s, 8)
    ok(await post(s, database, later["id"]), 201)
    # The standard update, with the optional fields; the first update starts the stage.
    file_id = await photo(database, s.pro_user, s.project_id)
    body = ok(
        await s.pro.post(
            f"{s.pro_base}/stages/{first['id']}/updates",
            json=update_body([file_id], materials="40 bags OPC 53", open_problems="Water supply"),
            headers=pro_key(),
        ),
        201,
    )  # fmt: skip
    no_forbidden_keys(body)
    assert body["stage"]["state"] == "IN_PROGRESS"
    assert body["stage"]["actual_start"] is not None
    update = body["updates"][0]
    assert (update["materials"], update["open_problems"]) == ("40 bags OPC 53", "Water supply")
    assert update["photos"][0]["captured_at"] == "2026-10-06T09:00:00+05:30"
    assert update["entered_by_operations"] is False
    # Completion is requested with evidence; a second request waits for the decision.
    body = ok(await post(s, database, first["id"], "COMPLETION_REQUEST"), 201)
    assert body["stage"]["state"] == "COMPLETION_REQUESTED"
    again = await post(s, database, first["id"], "COMPLETION_REQUEST")
    assert (again.status_code, reason(again)) == (409, "ALREADY_REQUESTED")
    # Progress may still be reported while waiting.
    ok(await post(s, database, first["id"]), 201)
    # The owner reads the updates (newest first) and the photo.
    updates = ok(await s.family.get(f"{s.base}/stages/{first['id']}/updates"))
    no_forbidden_keys(updates)
    assert [u["kind"] for u in updates["updates"]] == [
        "PROGRESS", "COMPLETION_REQUEST", "PROGRESS",
    ]  # fmt: skip
    assert updates["updates"][0]["contractor_name"] == "Ravi Builders"
    url = f"{s.base}/stages/{first['id']}/files/{file_id}/url"
    assert ok(await s.family.get(url))["url"]
    other_stage_photo = f"{s.base}/stages/{later['id']}/files/{file_id}/url"
    assert (await s.family.get(other_stage_photo)).status_code == 404
    # A stale version is refused; the current one confirms. No automatic completion.
    current = await stage(s, 1)
    stale = await s.family.post(
        f"{s.base}/stages/{first['id']}/confirm", json={"version": current["version"] - 1},
        headers=key(),
    )  # fmt: skip
    assert (stale.status_code, reason(stale)) == (409, "STALE")
    done = ok(
        await s.family.post(
            f"{s.base}/stages/{first['id']}/confirm", json={"version": current["version"]},
            headers=key(),
        )
    )  # fmt: skip
    confirmed = next(x for x in done["stages"] if x["id"] == first["id"])
    assert confirmed["state"] == "COMPLETED"
    assert confirmed["actual_end"] is not None
    # A completed stage takes no more updates.
    closed = await post(s, database, first["id"])
    assert (closed.status_code, reason(closed)) == (409, "STAGE_COMPLETED")
    # Notifications: the owner is asked, the contractor told, the milestone due (stage 1).
    mailbox = await worker()
    subjects = {(m.to.split("@")[0][:6], m.subject) for m in mailbox.sent}
    assert ("owner-", "Your contractor asks you to confirm a stage") in subjects
    assert ("owner-", "A payment milestone is reached") in subjects
    assert any(m.subject == "Stage completion confirmed" for m in mailbox.sent)
    due = next(m for m in mailbox.sent if m.subject == "A payment milestone is reached")
    assert "Rs" not in due.text
    assert "₹" not in due.text
    # History and audit: one audit row for every history row.
    async with database.transaction() as session:
        events = list(
            await session.scalars(
                select(ConstructionEvent.to_state).where(
                    ConstructionEvent.stage_instance_id == uuid.UUID(first["id"])
                ).order_by(ConstructionEvent.at)
            )
        )  # fmt: skip
        audits = await session.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.entity_type == "stage_instance",
                AuditEvent.action != "stage_instance.created",
            )
        )  # fmt: skip
        history = await session.scalar(select(func.count()).select_from(ConstructionEvent))
    assert events == ["IN_PROGRESS", "COMPLETION_REQUESTED", "COMPLETED"]
    assert audits == history


async def test_the_owner_returns_with_a_reason_and_the_household_only_reads(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s = await _site(app, database, client_for, make_user, sign_in, worker)
    home = await household(database, client_for, make_user, sign_in, s.project_id)
    target = await requested(s, database, (await stage(s, 2))["id"])
    # The household reads everything and acts on nothing (EX-21).
    assert ok(await home.get(f"{s.base}/execution"))["is_owner"] is False
    ok(await home.get(f"{s.base}/stages/{target['id']}/updates"))
    for action, body in (("confirm", {"version": target["version"]}),
                         ("return", {"version": target["version"], "reason": "No."})):  # fmt: skip
        refused = await home.post(f"{s.base}/stages/{target['id']}/{action}", json=body,
                                  headers=key())  # fmt: skip
        assert refused.status_code == 403
    # A return needs a reason.
    blank = await s.family.post(
        f"{s.base}/stages/{target['id']}/return", json={"version": target["version"],
                                                        "reason": "  "}, headers=key(),
    )  # fmt: skip
    assert blank.status_code == 422
    returned = ok(
        await s.family.post(
            f"{s.base}/stages/{target['id']}/return",
            json={"version": target["version"], "reason": "Plaster is cracked near the door."},
            headers=key(),
        )
    )  # fmt: skip
    assert next(x for x in returned["stages"] if x["id"] == target["id"])["state"] == "IN_PROGRESS"
    # Nothing to decide now.
    again = await s.family.post(
        f"{s.base}/stages/{target['id']}/confirm", json={"version": target["version"] + 1},
        headers=key(),
    )  # fmt: skip
    assert (again.status_code, again.json()["error"]["code"]) == (409, "STATE_CONFLICT")
    # The contractor is told; the reason is recorded in the history.
    mailbox = await worker()
    assert any(m.subject == "Stage completion returned" for m in mailbox.sent)
    async with database.transaction() as session:
        reasons = list(
            await session.scalars(
                select(ConstructionEvent.reason).where(ConstructionEvent.to_state == "IN_PROGRESS",
                                                       ConstructionEvent.reason.is_not(None))
            )
        )  # fmt: skip
    assert reasons == ["Plaster is cracked near the door."]


async def test_operations_confirm_with_a_reason_and_a_gate_waits_for_clearance(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s = await _site(app, database, client_for, make_user, sign_in, worker)
    gate = await stage(s, 3)
    assert gate["is_gate"]
    assert gate["gate_status"] == "NOT_INSPECTED"
    gate = await requested(s, database, gate["id"])
    for client, url, body in (
        (s.family, f"{s.base}/stages/{gate['id']}/confirm", {"version": gate["version"]}),
        (s.ops.client, f"/api/v1/ops/stages/{gate['id']}/confirm",
         {"version": gate["version"], "reason": "Owner asked by phone."}),
    ):  # fmt: skip
        refused = await client.post(url, json=body, headers=key() if client is s.family
                                    else ops_key())  # fmt: skip
        assert (refused.status_code, reason(refused)) == (409, "GATE_NOT_CLEARED")
    # Operations need a reason.
    missing = await s.ops.client.post(
        f"/api/v1/ops/stages/{gate['id']}/confirm", json={"version": gate["version"]},
        headers=ops_key(),
    )  # fmt: skip
    assert missing.status_code == 422
    await set_gate(database, gate["id"], "CLEARED")
    done = ok(
        await s.ops.client.post(
            f"/api/v1/ops/stages/{gate['id']}/confirm",
            json={"version": gate["version"], "reason": "Owner confirmed by phone."},
            headers=ops_key(),
        )
    )  # fmt: skip
    assert next(x for x in done["stages"] if x["id"] == gate["id"])["state"] == "COMPLETED"
    # Operations may also return, with a reason.
    plain = await requested(s, database, (await stage(s, 5, 0))["id"])
    back = ok(
        await s.ops.client.post(
            f"/api/v1/ops/stages/{plain['id']}/return",
            json={"version": plain["version"], "reason": "Photos do not show the slab."},
            headers=ops_key(),
        )
    )  # fmt: skip
    assert next(x for x in back["stages"] if x["id"] == plain["id"])["state"] == "IN_PROGRESS"
    # Operations are told about the gate stage's request (schedule an inspection); the test
    # settings have no operations mailbox, so the notice is checked in the outbox.
    from p2b.core.outbox import OutboxEvent

    async with database.transaction() as session:
        notices = list(
            await session.scalars(
                select(OutboxEvent.payload["notice"].astext).where(
                    OutboxEvent.event_type == "construction.ops_notice"
                )
            )
        )
    assert notices == ["GATE_COMPLETION_REQUESTED"]
    async with database.transaction() as session:
        row = (
            await session.execute(
                select(ConstructionEvent.actor_role, ConstructionEvent.reason).where(
                    ConstructionEvent.stage_instance_id == uuid.UUID(gate["id"]),
                    ConstructionEvent.to_state == "COMPLETED",
                )
            )
        ).one()
    assert tuple(row) == ("OPS", "Owner confirmed by phone.")


async def test_no_dates_no_percentages_and_the_record_is_append_only(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s = await _site(app, database, client_for, make_user, sign_in, worker)
    assert s.pro is not None
    rows = await stages(s)
    assert {r["stage_number"] for r in rows if r["is_gate"]} == GATES
    assert {r["stage_number"] for r in rows if r["is_payment_milestone"]} == MILESTONES
    body = ok(await s.family.get(f"{s.base}/execution"))
    no_forbidden_keys(body)
    no_forbidden_keys(ok(await s.pro.get(f"{s.pro_base}/execution")))
    no_forbidden_keys(ok(await s.ops.client.get(f"/api/v1/ops/projects/{s.project_id}/execution")))
    # A percentage cannot be sent.
    first = rows[0]
    sneaky = await s.pro.post(
        f"{s.pro_base}/stages/{first['id']}/updates",
        json={**update_body([await photo(database, s.pro_user or uuid.uuid4(), s.project_id)]),
              "percent_complete": 40},
        headers=pro_key(),
    )  # fmt: skip
    assert sneaky.status_code == 422
    ok(await post(s, database, first["id"]), 201)
    # BP-07A: no planned date can be written; identity columns never change; updates and
    # history refuse change.
    statements = [
        "UPDATE stage_instances SET planned_start = current_date WHERE id = :id",
        "UPDATE stage_instances SET stage_number = 2 WHERE id = :id",
        "DELETE FROM stage_instances WHERE id = :id",
        "UPDATE stage_updates SET note = 'edited' WHERE stage_instance_id = :id",
        "DELETE FROM stage_updates WHERE stage_instance_id = :id",
        "UPDATE construction_events SET reason = 'x' WHERE stage_instance_id = :id",
    ]
    for statement in statements:
        with pytest.raises(DBAPIError):
            async with database.transaction() as session:
                await session.execute(text(statement), {"id": uuid.UUID(first["id"])})


async def test_an_update_needs_its_own_scanned_photos_on_the_project(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s = await _site(app, database, client_for, make_user, sign_in, worker)
    assert s.pro is not None
    assert s.pro_user is not None
    target = (await stage(s, 2))["id"]
    url = f"{s.pro_base}/stages/{target}/updates"
    other = await world(app, database, client_for, make_user, sign_in, None)
    bad = [
        await photo(database, s.pro_user, s.project_id, state="UPLOADED"),
        await photo(database, s.pro_user, s.project_id, purpose="DRAWING"),
        await photo(database, s.owner, s.project_id),
        await photo(database, s.pro_user, other.project_id),
        str(uuid.uuid4()),
    ]
    for file_id in bad:
        refused = await s.pro.post(url, json=update_body([file_id]), headers=pro_key())
        assert refused.status_code == 422, file_id
    empty = await s.pro.post(url, json=update_body([]), headers=pro_key())
    assert empty.status_code == 422
    many = [await photo(database, s.pro_user, s.project_id) for _ in range(11)]
    too_many = await s.pro.post(url, json=update_body(many), headers=pro_key())
    assert too_many.status_code == 422
    blank = await s.pro.post(url, json={**update_body(many[:1]), "note": "  "}, headers=pro_key())
    assert blank.status_code == 422
    # A correction names an update of the same stage.
    first = ok(await s.pro.post(url, json=update_body(many[:1]), headers=pro_key()), 201)
    wrong = await s.pro.post(
        f"{s.pro_base}/stages/{(await stage(s, 1))['id']}/updates",
        json=update_body(many[1:2], corrects_update_id=first["updates"][0]["id"]),
        headers=pro_key(),
    )  # fmt: skip
    assert wrong.status_code == 422
    fixed = ok(
        await s.pro.post(
            url, json=update_body(many[2:3], corrects_update_id=first["updates"][0]["id"]),
            headers=pro_key(),
        ),
        201,
    )  # fmt: skip
    assert fixed["updates"][0]["corrects_update_id"] == first["updates"][0]["id"]
    # The evidence upload: images only, with the device's claims kept apart.
    ticket = await s.pro.post(
        f"{s.pro_base}/evidence",
        json={"file_name": "slab.jpg", "content_type": "image/jpeg", "size_bytes": 2000,
              "captured_at": "2026-10-06T10:00:00+05:30", "latitude": 21.25,
              "longitude": 81.63},
        headers=PRO_H,
    )  # fmt: skip
    assert ticket.status_code == 201, ticket.text
    async with database.transaction() as session:
        claim = await session.scalar(
            text("SELECT capture_claim FROM file_objects WHERE id = :id"),
            {"id": uuid.UUID(ticket.json()["file"]["file_id"])},
        )
    assert claim == {"captured_at": "2026-10-06T10:00:00+05:30", "latitude": 21.25,
                     "longitude": 81.63}  # fmt: skip
    pdf = await s.pro.post(
        f"{s.pro_base}/evidence",
        json={"file_name": "a.pdf", "content_type": "application/pdf", "size_bytes": 2000},
        headers=PRO_H,
    )  # fmt: skip
    assert pdf.status_code == 422
    half = await s.pro.post(
        f"{s.pro_base}/evidence",
        json={"file_name": "b.jpg", "content_type": "image/jpeg", "size_bytes": 10,
              "latitude": 21.25},
        headers=PRO_H,
    )  # fmt: skip
    assert half.status_code == 422


async def test_only_the_engaged_contractor_reaches_the_project(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s = await _site(app, database, client_for, make_user, sign_in, worker)
    assert s.pro is not None
    target = (await stage(s, 2))["id"]
    ok(await post(s, database, target), 201)
    stranger, _, stranger_user = await listed_pro(
        database, client_for, make_user, sign_in, name="Stranger"
    )
    file_id = await photo(database, stranger_user, s.project_id)
    for path in (f"{s.pro_base}/execution", f"{s.pro_base}/stages/{target}/updates",
                 f"{s.pro_base}/payment-marks"):  # fmt: skip
        assert (await stranger.get(path)).status_code == 404
    foreign = await stranger.post(
        f"{s.pro_base}/stages/{target}/updates", json=update_body([file_id]), headers=pro_key()
    )
    assert foreign.status_code == 404
    # Another family sees nothing of this project.
    other = await world(app, database, client_for, make_user, sign_in, None)
    for path in ("execution", f"stages/{target}/updates", "payment-marks"):
        assert (await other.family.get(f"{s.base}/{path}")).status_code == 404
    refused = await other.family.post(
        f"{s.base}/stages/{target}/confirm", json={"version": 1}, headers=key()
    )
    assert refused.status_code == 404
    # A stage of another project is 404 through this engagement.
    other_stage = (await stages(Site(other, s.owner, s.ops, None, None, None, "")))[0]["id"]
    assert (await s.pro.get(f"{s.pro_base}/stages/{other_stage}/updates")).status_code == 404
    # The homeowner host cannot reach the operations routes.
    assert (await s.family.get("/api/v1/ops/execution")).status_code in (401, 403, 404)


async def test_a_new_contractor_continues_and_history_stays_with_the_old(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s = await _site(app, database, client_for, make_user, sign_in, worker)
    assert s.pro is not None
    target = (await stage(s, 2))["id"]
    ok(await post(s, database, target), 201)
    old_base = s.pro_base
    ended = await s.family.post(
        f"{s.base}/engagements/{s.engagement_id}/end", json={"reason": "Contract ended."},
        headers=key(),
    )  # fmt: skip
    assert ended.status_code == 200, ended.text
    # Access ends with the engagement.
    assert (await s.pro.get(f"{old_base}/execution")).status_code == 404
    gone = await post(s, database, target)
    assert gone.status_code == 404
    # Without a contractor, operations cannot post.
    file_id = await photo(database, s.ops.user_id, s.project_id)
    body = {**update_body([file_id]), "reason": "Received on WhatsApp."}
    none = await s.ops.client.post(f"/api/v1/ops/stages/{target}/updates", json=body,
                                   headers=ops_key())  # fmt: skip
    assert (none.status_code, reason(none)) == (409, "NOT_CONTRACTOR")
    # The family records its own contractor; operations enter its updates with a reason.
    outside = await s.family.post(
        f"{s.base}/engagements", json={"category": "CONTRACTOR", "name": "Sharma Constructions"},
        headers=key(),
    )  # fmt: skip
    assert outside.status_code == 201, outside.text
    missing = await s.ops.client.post(
        f"/api/v1/ops/stages/{target}/updates", json=update_body([file_id]), headers=ops_key()
    )
    assert missing.status_code == 422
    entered = ok(
        await s.ops.client.post(f"/api/v1/ops/stages/{target}/updates", json=body,
                                headers=ops_key()),
        201,
    )  # fmt: skip
    names = [(u["contractor_name"], u["entered_by_operations"]) for u in entered["updates"]]
    assert names == [("Sharma Constructions", True), ("Ravi Builders", False)]
    # The same stage continues; the change is recorded on it.
    async with database.transaction() as session:
        change = (
            await session.execute(
                select(ConstructionEvent.subject, ConstructionEvent.from_state,
                       ConstructionEvent.to_state)
                .where(ConstructionEvent.subject == "CONTRACTOR")
            )
        ).one()  # fmt: skip
        engagements = set(await session.scalars(select(StageUpdate.engagement_id)))
    assert change[1] == s.engagement_id
    assert len(engagements) == 2
    assert (await stage(s, 2))["state"] == "IN_PROGRESS"


async def test_operations_enter_only_for_an_outside_contractor_and_need_no_package(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    listed = await _site(app, database, client_for, make_user, sign_in, worker)
    target = (await stage(listed, 2))["id"]
    file_id = await photo(database, listed.ops.user_id, listed.project_id)
    refused = await listed.ops.client.post(
        f"/api/v1/ops/stages/{target}/updates",
        json={**update_body([file_id]), "reason": "By email."}, headers=ops_key(),
    )  # fmt: skip
    assert (refused.status_code, reason(refused)) == (409, "LISTED_CONTRACTOR")
    # An outside contractor, no package at all (EX-18: execution is free).
    s = await site(app, database, client_for, make_user, sign_in, None, outside=True)
    first = (await stage(s, 1))["id"]
    ops_photo = await photo(database, s.ops.user_id, s.project_id)
    for kind in ("PROGRESS", "COMPLETION_REQUEST"):
        ok(
            await s.ops.client.post(
                f"/api/v1/ops/stages/{first}/updates",
                json={**update_body([ops_photo], kind), "reason": "Photos by WhatsApp."},
                headers=ops_key(),
            ),
            201,
        )  # fmt: skip
    pending = await stage(s, 1)
    ok(await s.family.post(f"{s.base}/stages/{first}/confirm",
                           json={"version": pending["version"]}, headers=key()))  # fmt: skip
    ok(await s.family.post(f"{s.base}/stages/{first}/payment-mark", json={"value": "YES"},
                           headers=key()))  # fmt: skip
    marks = ok(
        await s.ops.client.post(
            f"/api/v1/ops/stages/{first}/payment-mark",
            json={"value": "YES", "reason": "Contractor confirmed by phone."}, headers=ops_key(),
        )
    )  # fmt: skip
    milestone = next(m for m in marks["milestones"] if m["stage_instance_id"] == first)
    assert milestone["due"] is True
    assert milestone["paid"]["value"] == "YES"
    assert milestone["received"]["by_operations"] is True
    # The ops evidence route stores a scanned photo for the update.
    upload = await s.ops.client.post(
        f"/api/v1/ops/projects/{s.project_id}/stage-evidence",
        params={"file_name": "site.png"}, content=b"\x89PNG\r\n\x1a\n" + b"0" * 64,
        headers={**ops_key(), "content-type": "image/png"},
    )  # fmt: skip
    assert upload.status_code == 201, upload.text
    assert upload.json()["state"] == "UPLOADED"


async def test_payment_marks_inform_and_never_block(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s = await _site(app, database, client_for, make_user, sign_in, worker)
    assert s.pro is not None
    home = await household(database, client_for, make_user, sign_in, s.project_id)
    first = (await stage(s, 1))["id"]
    plain = (await stage(s, 2))["id"]
    url = f"{s.base}/stages/{first}/payment-mark"
    not_milestone = await s.family.post(
        f"{s.base}/stages/{plain}/payment-mark", json={"value": "YES"}, headers=key()
    )
    assert (not_milestone.status_code, reason(not_milestone)) == (409, "NOT_A_MILESTONE")
    amount = await s.family.post(url, json={"value": "YES", "amount": "50000"}, headers=key())
    assert amount.status_code == 422
    assert (await home.post(url, json={"value": "YES"}, headers=key())).status_code == 403
    # Marked before completion, freely: information only.
    marks = ok(await s.family.post(url, json={"value": "YES"}, headers=key()))
    no_forbidden_keys(marks)
    milestone = next(m for m in marks["milestones"] if m["stage_instance_id"] == first)
    assert (milestone["due"], milestone["paid"]["value"], milestone["received"]) == (
        False, "YES", None,
    )  # fmt: skip
    same = await s.family.post(url, json={"value": "YES"}, headers=key())
    assert (same.status_code, reason(same)) == (409, "UNCHANGED")
    # The contractor says it was not received: no mismatch flag, nothing blocked.
    received = ok(
        await s.pro.post(f"{s.pro_base}/stages/{first}/payment-mark", json={"value": "NO"},
                         headers=pro_key())
    )  # fmt: skip
    no_forbidden_keys(received)
    pending = await requested(s, database, first)
    ok(await s.family.post(f"{s.base}/stages/{first}/confirm",
                           json={"version": pending["version"]}, headers=key()))  # fmt: skip
    # The owner may change the mark; the history keeps both.
    ok(await s.family.post(url, json={"value": "NO"}, headers=key()))
    view = ok(await home.get(f"{s.base}/payment-marks"))
    milestone = next(m for m in view["milestones"] if m["stage_instance_id"] == first)
    assert (milestone["due"], milestone["paid"]["value"], milestone["received"]["value"]) == (
        True, "NO", "NO",
    )  # fmt: skip
    async with database.transaction() as session:
        values = list(
            await session.scalars(
                select(PaymentMark.value).where(PaymentMark.side == "PAID")
                .order_by(PaymentMark.marked_at)
            )
        )  # fmt: skip
        columns = set(
            await session.scalars(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_name IN ('payment_marks', 'stage_instances', 'stage_updates')")
            )
        )  # fmt: skip
    assert values == ["YES", "NO"]
    assert not [c for c in columns if "amount" in c or "percent" in c]
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("UPDATE payment_marks SET value = 'YES'"))
    # The contractor was told of the "paid" mark.
    mailbox = await worker()
    assert any(m.subject == "A payment was marked as paid" for m in mailbox.sent)


async def test_concurrent_decisions_and_marks_have_one_winner(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s = await _site(app, database, client_for, make_user, sign_in, worker)
    target = await requested(s, database, (await stage(s, 2))["id"])
    url = f"{s.base}/stages/{target['id']}"
    results = await asyncio.gather(
        s.family.post(f"{url}/confirm", json={"version": target["version"]}, headers=key()),
        s.family.post(f"{url}/return", json={"version": target["version"], "reason": "No"},
                      headers=key()),
    )  # fmt: skip
    assert sorted(r.status_code for r in results) == [200, 409]
    first = (await stage(s, 1))["id"]
    marks = await asyncio.gather(
        *(s.family.post(f"{s.base}/stages/{first}/payment-mark", json={"value": "YES"},
                        headers=key()) for _ in range(3))
    )  # fmt: skip
    assert sorted(r.status_code for r in marks) == [200, 409, 409]
    # The same idempotency key replays the first answer.
    second = await requested(s, database, (await stage(s, 8))["id"])
    headers = key()
    body = {"version": second["version"]}
    one = await s.family.post(f"{s.base}/stages/{second['id']}/confirm", json=body, headers=headers)
    two = await s.family.post(f"{s.base}/stages/{second['id']}/confirm", json=body, headers=headers)
    assert one.status_code == two.status_code == 200
    assert one.json() == two.json()


async def test_an_unanswered_request_becomes_an_operations_exception(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s = await _site(app, database, client_for, make_user, sign_in, worker)
    fresh = await requested(s, database, (await stage(s, 2))["id"])
    old = await requested(s, database, (await stage(s, 8))["id"])
    async with database.transaction() as session:
        await session.execute(
            text("UPDATE stage_instances SET completion_requested_at = now() - interval '3 days' "
                 "WHERE id = :id"),
            {"id": uuid.UUID(old["id"])},
        )  # fmt: skip
    queue = ok(await s.ops.client.get("/api/v1/ops/execution"))
    assert queue["exception_days"] == 3
    flags = {w["stage"]["id"]: w["exception"] for w in queue["waiting"]}
    assert flags[old["id"]] is True
    assert flags[fresh["id"]] is False
    assert [w["stage"]["id"] for w in queue["waiting"]][:1] == [old["id"]]  # oldest first
    # No reminder is sent: only the request's own notices.
    mailbox = await worker()
    assert not [m for m in mailbox.sent if "remind" in m.subject.lower()]
    # The operations view of the project and of a stage.
    view = ok(await s.ops.client.get(f"/api/v1/ops/projects/{s.project_id}/execution"))
    assert view["contractor"]["party"] == "LISTED"
    updates = ok(await s.ops.client.get(f"/api/v1/ops/stages/{old['id']}/updates"))
    file_id = updates["updates"][0]["photos"][0]["file_id"]
    assert ok(await s.ops.client.get(f"/api/v1/ops/stage-files/{file_id}/url"))["url"]


async def test_the_contractor_sees_the_accepted_drawings_and_its_own_updates_only(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    from tests.buildplan_support import stored
    from tests.execution_support import pro_key as pk
    from tests.rfq_support import accepted_team
    from tests.test_engagements import category_of, pro_post, sent, services

    t, _ = await accepted_team(app, database, client_for, make_user, sign_in, worker)
    pro, profile_id, user_id = await listed_pro(database, client_for, make_user, sign_in)
    ok(await pro_post(pro, await sent(t.world, profile_id), "accept", phone="+91 90000 11111"))
    engagement_id = category_of(await services(t.world), "CONTRACTOR")["engagement"]["id"]
    base = f"/api/v1/pro/engagements/{engagement_id}"
    view = ok(await pro.get(f"{base}/execution"))
    no_forbidden_keys(view)
    assert view["build_plan_version_no"] == 1
    assert view["drawings"]
    drawing = view["drawings"][0]["file_id"]
    assert ok(await pro.get(f"{base}/execution/files/{drawing}/url"))["url"]
    other_file = await stored(database, t.owner, t.project_id, "REQUIREMENT_UPLOAD")
    assert (await pro.get(f"{base}/execution/files/{other_file}/url")).status_code == 404
    first = view["stages"][0]["id"]
    file_id = await photo(database, user_id, t.project_id)
    ok(await pro.post(f"{base}/stages/{first}/updates", json=update_body([file_id]),
                      headers=pk()), 201)  # fmt: skip
    assert ok(await pro.get(f"{base}/execution/files/{file_id}/url"))["url"]
    assert ok(await pro.get(f"{base}/execution"))["stages"][0]["update_count"] == 1


async def test_writes_stop_when_the_project_is_cancelled(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s = await _site(app, database, client_for, make_user, sign_in, worker)
    first = (await stage(s, 1))["id"]
    async with database.transaction() as session:
        await session.execute(text("ALTER TABLE projects DISABLE TRIGGER USER"))
        await session.execute(text("UPDATE projects SET status = 'CANCELLED' WHERE id = :id"),
                              {"id": uuid.UUID(s.project_id)})  # fmt: skip
        await session.execute(text("ALTER TABLE projects ENABLE TRIGGER USER"))
    closed = await post(s, database, first)
    assert closed.status_code in (404, 409)
    if closed.status_code == 409:
        assert reason(closed) == "PROJECT_CLOSED"
    mark = await s.family.post(f"{s.base}/stages/{first}/payment-mark", json={"value": "YES"},
                               headers=key())  # fmt: skip
    assert (mark.status_code, reason(mark)) == (409, "PROJECT_CLOSED")
    assert ok(await s.family.get(f"{s.base}/execution"))["stages"]


async def test_outbox_payloads_carry_ids_only(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    from p2b.core.outbox import OutboxEvent

    s = await _site(app, database, client_for, make_user, sign_in, worker)
    await requested(s, database, (await stage(s, 2))["id"])
    async with database.transaction() as session:
        payloads = list(
            await session.scalars(
                select(OutboxEvent.payload).where(OutboxEvent.event_type.like("construction.%"))
            )
        )
    assert payloads
    for payload in payloads:
        assert set(payload) <= {"notice", "stage_instance_id", "project_id", "schema_version"}
