"""Slice 3.7B (SLICE3_7_READINESS section 0, F, G, K, L, N, O, P.B, P.C): auditor appointments
(EX-09), the seeded and versioned checklists (EX-08), one inspection per gate stage instance
(EX-07), submission with a code and the frozen content, approval with the report (EX-14),
findings with severity that close only through a re-inspection (EX-11), the gate, staff capture,
the package (EX-18), the operations thresholds (EX-12, EX-23), isolation, notifications,
concurrency and audit."""

import asyncio
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from p2b.assurance import inspections
from p2b.assurance.common import sha256
from p2b.assurance.models import AssuranceEvent, Inspection
from p2b.assurance.pdf import render_report
from p2b.audit.models import AuditEvent
from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.vocabulary import StaffRole
from p2b.notifications.service import Kind, kinds_for
from tests.assurance_support import (
    Auditor,
    appoint,
    appoint_without_account,
    approve,
    detail,
    perform,
    restore_checklists,
    results,
    schedule,
    submit,
)
from tests.billing_support import key
from tests.buildplan_support import code_of
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.execution_support import (
    PRO_H,
    Site,
    ok,
    ops_key,
    photo,
    pro_key,
    reason,
    requested,
    site,
    stage,
)
from tests.rfq_support import keys_of
from tests.staff_support import verified_staff
from tests.test_billing import refund_request
from tests.test_engagements import Run

AUDITOR_FORBIDDEN = {"brand", "brand_category", "supplier", "product", "price", "rate", "amount",
                     "family_contact", "phone", "email", "contact_name", "owner"}  # fmt: skip


@pytest.fixture
def worker(rfq_worker: Run) -> Run:
    return rfq_worker


async def _ready(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn, worker: Run,
) -> tuple[Site, Auditor]:  # fmt: skip
    s = await site(app, database, client_for, make_user, sign_in, worker)
    a = await appoint(database, client_for, make_user, sign_in, s.world.admin)
    return s, a


def test_assurance_notices_map_to_their_notifications() -> None:
    assert kinds_for("assurance.auditor_notice", {"notice": "INSPECTION_ASSIGNED"}) == [
        Kind.AUDITOR_INSPECTION_ASSIGNED
    ]
    assert kinds_for("assurance.contractor_notice", {"notice": "FINDINGS"}) == [Kind.PRO_FINDINGS]
    assert kinds_for("assurance.family_notice", {"notice": "REPORT_APPROVED"}) == [
        Kind.FAMILY_INSPECTION_REPORT
    ]
    assert kinds_for("assurance.ops_notice", {"notice": "RECTIFICATION_SUBMITTED"}) == [
        Kind.OPS_RECTIFICATION_SUBMITTED
    ]


async def test_version_1_holds_gates_1_to_5_from_the_s04_mapping(
    app: FastAPI, database: Database, client_for: ClientFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    versions = ok(await ops.client.get("/api/v1/ops/checklists"))
    v1 = next(v for v in versions if v["version"] == 1)
    assert v1["status"] == "PUBLISHED"
    counts: dict[int, int] = {}
    for c in v1["checkpoints"]:
        counts[c["gate"]] = counts.get(c["gate"], 0) + 1
    assert counts == {1: 6, 2: 3, 3: 3, 4: 13, 5: 2}  # no Gate 6 until drafted (EX-08)
    by_code = {c["spec_line_code"]: c for c in v1["checkpoints"]}
    assert by_code["A04"]["expected_evidence"] == "cube test"
    assert by_code["B15"]["expected_evidence"] == "ponding test"
    assert by_code["A02"]["expected_evidence"] is None
    assert "C24" in v1["note"]  # S04 maps External works to Gate 6: an input for the draft


async def test_admin_appoints_and_ends_auditors(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s, a = await _ready(app, database, client_for, make_user, sign_in, worker)
    refused = await s.ops.client.post(
        "/api/v1/admin/auditor-appointments", json={"name": "X", "qualification": "Y"},
        headers=ops_key(),
    )  # fmt: skip
    assert refused.status_code == 403
    second = await appoint_without_account(s.world.admin)
    listing = ok(await s.ops.client.get("/api/v1/ops/auditor-appointments"))
    codes = [r["auditor_code"] for r in listing]
    assert len(set(codes)) == len(codes) == 2
    assert all(c.startswith("AUD-") for c in codes)
    assert {r["has_account"] for r in listing} == {True, False}
    # One active appointment per account.
    email = f"auditor-{a.user_id.hex}@example.in"
    again = await s.world.admin.client.post(
        "/api/v1/admin/auditor-appointments",
        json={"name": "Again", "qualification": "Y", "account_email": email}, headers=ops_key(),
    )  # fmt: skip
    assert (again.status_code, reason(again)) == (409, "ACCOUNT_APPOINTED")
    ok(await s.world.admin.client.post(f"/api/v1/admin/auditor-appointments/{second}/end",
                                       json={"reason": "Contract over."},
                                       headers=ops_key()))  # fmt: skip
    gate = await stage(s, 3)
    ended = await s.ops.client.post(
        f"/api/v1/ops/stages/{gate['id']}/inspections", json={"appointment_id": second},
        headers=ops_key(),
    )  # fmt: skip
    assert (ended.status_code, reason(ended)) == (409, "APPOINTMENT_ENDED")
    # Someone without an appointment has no inspections.
    assert (await s.pro.get("/api/v1/pro/inspections")).status_code == 404  # type: ignore[union-attr]


async def test_an_inspection_opens_findings_and_only_a_reinspection_closes_them(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s, a = await _ready(app, database, client_for, make_user, sign_in, worker)
    assert s.pro is not None
    assert s.pro_user is not None
    gate = await requested(s, database, (await stage(s, 3))["id"])
    assert gate["gate_status"] == "NOT_INSPECTED"
    queue = ok(await s.ops.client.get("/api/v1/ops/assurance"))
    assert [q["stage_instance_id"] for q in queue["to_schedule"]] == [gate["id"]]
    inspection = await schedule(s, gate["id"], a.appointment_id, visit_note="Tuesday 10:00")
    iid = inspection["id"]
    assert (await stage(s, 3))["gate_status"] == "SCHEDULED"
    # The auditor sees the assignment: checklist, criteria, drawings; nothing commercial.
    listing = ok(await a.client.get("/api/v1/pro/inspections"))
    assert [i["id"] for i in listing["items"]] == [iid]
    view = await detail(a, iid)
    assert view["gate"] == 1
    assert len(view["checkpoints"]) == 6
    assert all(c["criteria"] for c in view["checkpoints"])
    assert not keys_of(view) & AUDITOR_FORBIDDEN, keys_of(view) & AUDITOR_FORBIDDEN
    # The homeowner and the contractor see that it is scheduled, no content.
    family = ok(await s.family.get(f"{s.base}/assurance"))
    assert (family["inspections"][0]["state"], family["inspections"][0]["outcome"]) == (
        "SCHEDULED", None,
    )  # fmt: skip
    # Results only while in progress; a finding needs severity and the rest.
    url = f"/api/v1/pro/inspections/{iid}"
    items = await results(a, database, s.project_id, iid, findings={"G1-A06": "CRITICAL"})
    early = await a.client.put(f"{url}/results", json={"results": items}, headers=PRO_H)
    assert (early.status_code, reason(early)) == (409, "NOT_IN_PROGRESS")
    ok(await a.client.post(f"{url}/readiness", headers=pro_key()))
    bad = [dict(items[0], result="NON_CONFORMANCE")]
    assert (await a.client.put(f"{url}/results", json={"results": bad},
                               headers=PRO_H)).status_code == 422  # fmt: skip
    ok(await a.client.put(f"{url}/results", json={"results": items[:3]}, headers=PRO_H))
    challenge = ok(await a.client.post(f"{url}/submission-code", headers=PRO_H))
    code = await code_of(database, challenge["challenge_id"])
    incomplete = await a.client.post(
        f"{url}/submit", json={"challenge_id": challenge["challenge_id"], "code": code},
        headers=pro_key(),
    )  # fmt: skip
    assert (incomplete.status_code, reason(incomplete)) == (409, "INCOMPLETE")
    ok(await a.client.put(f"{url}/results", json={"results": items}, headers=PRO_H))
    submitted = await submit(a, database, iid)
    assert submitted["state"] == "SUBMITTED"
    # Frozen: no more results, by the service and by the database.
    frozen = await a.client.put(f"{url}/results", json={"results": items}, headers=PRO_H)
    assert frozen.status_code == 409
    for statement in ("UPDATE inspection_results SET note = 'x' WHERE inspection_id = :id",
                      "UPDATE inspections SET summary = 'x' WHERE id = :id"):  # fmt: skip
        with pytest.raises(DBAPIError):
            async with database.transaction() as session:
                await session.execute(text(statement), {"id": uuid.UUID(iid)})
    # The homeowner never approves; operations do, and the report is rendered once.
    view = await approve(s, iid)
    approved = next(i for i in view["inspections"] if i["id"] == iid)
    assert approved["state"] == "APPROVED"
    assert [r["version"] for r in approved["reports"]] == [1]
    assert approved["outcome"].startswith("1 item(s) need correction")
    stage3 = await stage(s, 3)
    assert stage3["gate_status"] == "OPEN_NC"
    finding = view["findings"][0]
    assert (finding["severity"], finding["state"]) == ("CRITICAL", "OPEN")
    # The stage cannot complete while a finding is open.
    refused = await s.family.post(f"{s.base}/stages/{gate['id']}/confirm",
                                  json={"version": stage3["version"]}, headers=key())  # fmt: skip
    assert (refused.status_code, reason(refused)) == (409, "GATE_NOT_CLEARED")
    # The homeowner reads the outcome and the report; the contractor sees its finding.
    family = ok(await s.family.get(f"{s.base}/assurance"))
    assert family["inspections"][0]["auditor_code"] == a.code
    assert ok(await s.family.get(f"{s.base}/inspections/{iid}/reports/1/url"))["url"]
    contractor = ok(await s.pro.get(f"{s.pro_base}/assurance"))
    assert [f["id"] for f in contractor["findings"]] == [finding["id"]]
    # The finding's text never changes (set once); nobody closes it by hand.
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(
                text("UPDATE non_conformances SET description = 'x' WHERE id = :id"),
                {"id": uuid.UUID(finding["id"])},
            )
    # The contractor rectifies with its own photos; a re-inspection is scheduled.
    file_id = await photo(database, s.pro_user, s.project_id)
    rectify = f"{s.pro_base}/non-conformances/{finding['id']}/rectification"
    ok(await s.pro.post(rectify, json={"note": "Cover blocks placed.", "file_ids": [file_id]},
                        headers=pro_key()))  # fmt: skip
    again = await s.pro.post(rectify, json={"note": "Again.", "file_ids": [file_id]},
                             headers=pro_key())  # fmt: skip
    assert (again.status_code, reason(again)) == (409, "NOT_OPEN")
    body = ok(
        await s.ops.client.post("/api/v1/ops/reinspections",
                                json={"nc_ids": [finding["id"]],
                                      "appointment_id": a.appointment_id},
                                headers=ops_key()),
        201,
    )  # fmt: skip
    re_id = next(i["id"] for i in body["inspections"] if i["kind"] == "REINSPECTION")
    assert len((await detail(a, re_id))["checkpoints"]) == 1
    # A failed re-inspection keeps it open; another cycle passes and closes it.
    await perform(a, database, s.project_id, re_id, result="NON_CONFORMANCE")
    view = await approve(s, re_id)
    assert view["findings"][0]["state"] == "OPEN"
    assert (await stage(s, 3))["gate_status"] == "OPEN_NC"
    ok(await s.pro.post(rectify, json={"note": "Fixed again.", "file_ids": [file_id]},
                        headers=pro_key()))  # fmt: skip
    body = ok(
        await s.ops.client.post("/api/v1/ops/reinspections",
                                json={"nc_ids": [finding["id"]],
                                      "appointment_id": a.appointment_id},
                                headers=ops_key()),
        201,
    )  # fmt: skip
    second = next(i["id"] for i in body["inspections"]
                  if i["kind"] == "REINSPECTION" and i["state"] == "SCHEDULED")  # fmt: skip
    await perform(a, database, s.project_id, second)
    view = await approve(s, second)
    assert view["findings"][0]["state"] == "CLOSED"
    stage3 = await stage(s, 3)
    assert stage3["gate_status"] == "CLEARED"
    # Now the owner confirms the stage.
    ok(await s.family.post(f"{s.base}/stages/{gate['id']}/confirm",
                           json={"version": stage3["version"]}, headers=key()))  # fmt: skip
    # The original inspection is unchanged throughout.
    async with database.transaction() as session:
        original = await session.get_one(Inspection, uuid.UUID(iid))
        assert original.content_sha256 == sha256(await inspections.content(session, original))
        events = await session.scalar(select(func.count()).select_from(AssuranceEvent))
        audits = await session.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.entity_type.in_(("inspection", "non_conformance", "appointment"))
            )
        )  # fmt: skip
    assert events == audits
    mailbox = await worker()
    subjects = {m.subject for m in mailbox.sent}
    assert {"An inspection is assigned to you", "Your inspection report is ready",
            "Inspection findings to correct", "Corrections confirmed",
            "Inspection gate cleared"} <= subjects  # fmt: skip
    assert not any("Cover blocks" in m.text for m in mailbox.sent)  # no finding text by email


async def test_one_inspection_per_gate_stage_instance(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s, a = await _ready(app, database, client_for, make_user, sign_in, worker)
    gate = await stage(s, 3)
    await schedule(s, gate["id"], a.appointment_id)
    twice = await s.ops.client.post(
        f"/api/v1/ops/stages/{gate['id']}/inspections",
        json={"appointment_id": a.appointment_id}, headers=ops_key(),
    )  # fmt: skip
    assert (twice.status_code, reason(twice)) == (409, "ALREADY_SCHEDULED")
    plain = await s.ops.client.post(
        f"/api/v1/ops/stages/{(await stage(s, 2))['id']}/inspections",
        json={"appointment_id": a.appointment_id}, headers=ops_key(),
    )  # fmt: skip
    assert (plain.status_code, reason(plain)) == (409, "NOT_A_GATE")
    # Gate 3 is per slab: each floor's stage 6 instance has its own inspection (EX-07).
    rows = ok(await s.family.get(f"{s.base}/execution"))["stages"]
    slabs = [r for r in rows if r["stage_number"] == 6]
    assert len(slabs) >= 2
    for slab in slabs:
        inspection = await schedule(s, slab["id"], a.appointment_id)
        assert inspection["gate"] == 3
    # Gate 6 has no checkpoint in version 1.
    snag = await s.ops.client.post(
        f"/api/v1/ops/stages/{(await stage(s, 16))['id']}/inspections",
        json={"appointment_id": a.appointment_id}, headers=ops_key(),
    )  # fmt: skip
    assert (snag.status_code, reason(snag)) == (409, "NO_CHECKLIST")


async def test_return_amendment_cancel_and_isolation(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s, a = await _ready(app, database, client_for, make_user, sign_in, worker)
    other = await appoint(database, client_for, make_user, sign_in, s.world.admin, "Other")
    gate = await stage(s, 4)
    iid = (await schedule(s, gate["id"], a.appointment_id))["id"]
    # Another auditor, the contractor and a family see nothing of it.
    assert (await other.client.get(f"/api/v1/pro/inspections/{iid}")).status_code == 404
    assert s.pro is not None
    assert (await s.pro.get(f"/api/v1/pro/inspections/{iid}")).status_code == 404
    await perform(a, database, s.project_id, iid)
    # Returned for amendment: the record stays; a replacement names it.
    missing = await s.ops.client.post(f"/api/v1/ops/inspections/{iid}/return", json={},
                                      headers=ops_key())  # fmt: skip
    assert missing.status_code == 422
    ok(await s.ops.client.post(f"/api/v1/ops/inspections/{iid}/return",
                               json={"reason": "Photos of the plinth are missing."},
                               headers=ops_key()))  # fmt: skip
    assert (await stage(s, 4))["gate_status"] == "NOT_INSPECTED"
    replacement = await schedule(s, gate["id"], a.appointment_id, amends_id=iid)
    async with database.transaction() as session:
        returned = await session.get_one(Inspection, uuid.UUID(iid))
        assert (returned.state, returned.return_reason) == (
            "RETURNED", "Photos of the plinth are missing.",
        )  # fmt: skip
    # Cancelled with a reason before it starts.
    ok(await s.ops.client.post(f"/api/v1/ops/inspections/{replacement['id']}/cancel",
                               json={"reason": "Site not ready."}, headers=ops_key()))  # fmt: skip
    assert (await stage(s, 4))["gate_status"] == "NOT_INSPECTED"
    again = await s.ops.client.post(f"/api/v1/ops/inspections/{replacement['id']}/cancel",
                                    json={"reason": "x"}, headers=ops_key())  # fmt: skip
    assert (again.status_code, reason(again)) == (409, "NOT_OPEN")
    # A household member reads; the homeowner host cannot reach operations routes.
    assert ok(await s.family.get(f"{s.base}/assurance"))["inspections"]
    assert (await s.family.get("/api/v1/ops/assurance")).status_code in (401, 403, 404)


async def test_operations_capture_a_signed_report_for_an_auditor_without_an_account(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s = await site(app, database, client_for, make_user, sign_in, worker)
    appointment = await appoint_without_account(s.world.admin)
    gate = await stage(s, 10)
    iid = (await schedule(s, gate["id"], appointment))["id"]
    view = ok(await s.ops.client.get(f"/api/v1/ops/projects/{s.project_id}/assurance"))
    points = next(i for i in view["inspections"] if i["id"] == iid)["checkpoints"]
    assert len(points) == 2  # Gate 5: the two ponding tests
    signed = await photo(database, s.ops.user_id, s.project_id, purpose="INSPECTION_EVIDENCE")
    items = [{"checkpoint_id": c["id"], "result": "OBSERVATION", "note": "Minor seepage stain."}
             for c in points]  # fmt: skip
    missing = await s.ops.client.post(
        f"/api/v1/ops/inspections/{iid}/capture",
        json={"results": items, "evidence_file_id": str(uuid.uuid4())}, headers=ops_key(),
    )  # fmt: skip
    assert missing.status_code == 422
    captured = ok(
        await s.ops.client.post(
            f"/api/v1/ops/inspections/{iid}/capture",
            json={"results": items, "summary": "From the signed sheet.",
                  "evidence_file_id": signed}, headers=ops_key(),
        )
    )  # fmt: skip
    row = next(i for i in captured["inspections"] if i["id"] == iid)
    assert (row["state"], row["staff_capture"]) == ("SUBMITTED", True)
    view = await approve(s, iid)
    # Observations never block: the gate clears.
    assert (await stage(s, 10))["gate_status"] == "CLEARED"
    assert next(i for i in view["inspections"] if i["id"] == iid)["outcome"].startswith(
        "Passed, with 2 observation"
    )


async def test_the_package_gates_scheduling_and_approval_and_its_end_cancels(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    # No package: an outside contractor's project.
    free = await site(app, database, client_for, make_user, sign_in, None, outside=True)
    a = await appoint(database, client_for, make_user, sign_in, free.world.admin)
    refused = await free.ops.client.post(
        f"/api/v1/ops/stages/{(await stage(free, 3))['id']}/inspections",
        json={"appointment_id": a.appointment_id}, headers=ops_key(),
    )  # fmt: skip
    assert reason(refused) == "PACKAGE_REQUIRED"
    # With the package; then it is refunded.
    s = await site(app, database, client_for, make_user, sign_in, worker)
    scheduled = (await schedule(s, (await stage(s, 3))["id"], a.appointment_id))["id"]
    started = (await schedule(s, (await stage(s, 4))["id"], a.appointment_id))["id"]
    submitted = (await schedule(s, (await stage(s, 9, 0))["id"], a.appointment_id))["id"]
    ok(await a.client.post(f"/api/v1/pro/inspections/{started}/readiness", headers=pro_key()))
    await perform(a, database, s.project_id, submitted)
    request_id = await refund_request(s.family, s.world.order["order_id"])
    ok(await s.ops.client.post(
        f"/api/v1/ops/billing/refund-requests/{request_id}/approve",
        json={"amount": s.world.order["total"], "ends_package": True, "reason": "Refund agreed."},
        headers=ops_key(),
    ))  # fmt: skip
    await worker()
    states = {
        i["id"]: i["state"] for i in ok(await s.family.get(f"{s.base}/assurance"))["inspections"]
    }
    assert states == {scheduled: "CANCELLED", started: "IN_PROGRESS", submitted: "SUBMITTED"}
    blocked = await s.ops.client.post(f"/api/v1/ops/inspections/{submitted}/approve",
                                      headers=ops_key())  # fmt: skip
    assert reason(blocked) == "PACKAGE_REQUIRED"
    again = await s.ops.client.post(
        f"/api/v1/ops/stages/{(await stage(s, 3))['id']}/inspections",
        json={"appointment_id": a.appointment_id}, headers=ops_key(),
    )  # fmt: skip
    assert reason(again) == "PACKAGE_REQUIRED"
    async with database.transaction() as session:
        cancel = await session.scalar(
            select(Inspection.cancel_reason).where(Inspection.id == uuid.UUID(scheduled))
        )
    assert cancel == "PACKAGE_ENDED"


async def test_reports_are_deterministic_and_corrections_are_new_versions(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s, a = await _ready(app, database, client_for, make_user, sign_in, worker)
    iid = (await schedule(s, (await stage(s, 3))["id"], a.appointment_id))["id"]
    await perform(a, database, s.project_id, iid, findings={"G1-A03": "MINOR"})
    await approve(s, iid)
    async with database.transaction() as session:
        row = await session.get_one(Inspection, uuid.UUID(iid))
        snapshot = await inspections.report_snapshot(session, row)
    settings = get_settings()
    first = render_report(settings, snapshot, version=1, correction_reason=None)
    assert first == render_report(settings, snapshot, version=1, correction_reason=None)
    assert first.startswith(b"%PDF")
    assert not keys_of(snapshot) & {"brand", "price", "amount", "phone", "email"}
    view = ok(await s.ops.client.post(f"/api/v1/ops/inspections/{iid}/report-corrections",
                                      json={"reason": "Auditor name spelt wrongly."},
                                      headers=ops_key()))  # fmt: skip
    reports = next(i for i in view["inspections"] if i["id"] == iid)["reports"]
    assert [(r["version"], r["correction_reason"]) for r in reports] == [
        (1, None), (2, "Auditor name spelt wrongly."),
    ]  # fmt: skip
    for version in (1, 2):
        assert ok(await s.family.get(f"{s.base}/inspections/{iid}/reports/{version}/url"))["url"]
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("UPDATE inspection_reports SET sha256 = 'x'"))
    # A later cube test result is a new record on the checkpoint.
    result_id = next(
        r["id"] for i in view["inspections"] if i["id"] == iid for r in i["results"]
        if r["severity"] is None
    )  # fmt: skip
    ok(await s.ops.client.post(f"/api/v1/ops/results/{result_id}/test-results",
                               json={"test_kind": "Cube test, 28 days", "value": "31.5 N/mm2"},
                               headers=ops_key()), 201)  # fmt: skip
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("DELETE FROM test_results"))


async def test_thresholds_make_operations_exceptions_only(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s, a = await _ready(app, database, client_for, make_user, sign_in, worker)
    old = (await schedule(s, (await stage(s, 3))["id"], a.appointment_id))["id"]
    fresh = (await schedule(s, (await stage(s, 4))["id"], a.appointment_id))["id"]
    async with database.transaction() as session:
        await session.execute(
            text("ALTER TABLE inspections DISABLE TRIGGER inspections_lifecycle_only")
        )
        await session.execute(
            text("UPDATE inspections SET scheduled_at = now() - interval '7 days' WHERE id = :id"),
            {"id": uuid.UUID(old)},
        )
        await session.execute(
            text("ALTER TABLE inspections ENABLE TRIGGER inspections_lifecycle_only")
        )
    queue = ok(await s.ops.client.get("/api/v1/ops/assurance"))
    assert queue["inspection_open_days"] == 7
    flags = {q["inspection_id"]: q["exception"] for q in queue["open_inspections"]}
    assert (flags[old], flags[fresh]) == (True, False)
    # A finding past its due date is listed; nothing blocks and nothing is sent.
    gate = (await stage(s, 9, 0))["id"]
    iid = (await schedule(s, gate, a.appointment_id))["id"]
    await perform(a, database, s.project_id, iid, findings={"G4-B04": "MAJOR"})
    view = await approve(s, iid)
    nc_id = view["findings"][0]["id"]
    past = await s.ops.client.post(f"/api/v1/ops/non-conformances/{nc_id}/due-date",
                                   json={"due_date": "2000-01-01", "reason": "x"},
                                   headers=ops_key())  # fmt: skip
    assert past.status_code == 422
    async with database.transaction() as session:
        await session.execute(
            text("UPDATE non_conformances SET due_date = DATE '2000-01-01' WHERE id = :id"),
            {"id": uuid.UUID(nc_id)},
        )
    queue = ok(await s.ops.client.get("/api/v1/ops/assurance"))
    assert [q["nc_id"] for q in queue["overdue"]] == [nc_id]
    family = ok(await s.family.get(f"{s.base}/assurance"))
    assert family["findings"][0]["overdue"] is True
    ok(await s.ops.client.post(f"/api/v1/ops/non-conformances/{nc_id}/due-date",
                               json={"due_date": "2099-06-30",
                                     "reason": "Rains delayed the work."},
                               headers=ops_key()))  # fmt: skip
    mailbox = await worker()
    assert not [m for m in mailbox.sent if "overdue" in m.subject.lower()
                or "remind" in m.subject.lower()]  # fmt: skip


async def test_checklists_are_versioned_and_published_by_admin(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s, a = await _ready(app, database, client_for, make_user, sign_in, worker)
    try:
        before = (await schedule(s, (await stage(s, 3))["id"], a.appointment_id))["id"]
        v1 = next(v for v in ok(await s.ops.client.get("/api/v1/ops/checklists"))
                  if v["version"] == 1)  # fmt: skip
        draft = ok(await s.ops.client.post("/api/v1/ops/checklists",
                                           json={"from_version_id": v1["id"],
                                                 "note": "Gate 6 drafted with the auditor."},
                                           headers=ops_key()), 201)  # fmt: skip
        points: list[dict[str, Any]] = [
            {k: c[k] for k in ("gate", "sequence", "code", "text", "expected_evidence",
                               "is_critical", "spec_line_code")}
            for c in draft["checkpoints"]
        ]  # fmt: skip
        points.append({"gate": 6, "sequence": 1, "code": "G6-C24", "text": "External works",
                       "spec_line_code": "C24"})  # fmt: skip
        ok(await s.ops.client.put(f"/api/v1/ops/checklists/{draft['id']}/checkpoints",
                                  json={"checkpoints": points}, headers=ops_key()))  # fmt: skip
        denied = await s.ops.client.post(f"/api/v1/admin/checklists/{draft['id']}/publish",
                                         headers=ops_key())  # fmt: skip
        assert denied.status_code == 403
        ok(await s.world.admin.client.post(f"/api/v1/admin/checklists/{draft['id']}/publish",
                                           headers=ops_key()))  # fmt: skip
        versions = {v["version"]: v["status"]
                    for v in ok(await s.ops.client.get("/api/v1/ops/checklists"))}  # fmt: skip
        assert versions == {1: "RETIRED", 2: "PUBLISHED"}
        locked = await s.ops.client.put(f"/api/v1/ops/checklists/{draft['id']}/checkpoints",
                                        json={"checkpoints": []}, headers=ops_key())  # fmt: skip
        assert (locked.status_code, reason(locked)) == (409, "NOT_DRAFT")
        with pytest.raises(DBAPIError):
            async with database.transaction() as session:
                await session.execute(
                    text("UPDATE checkpoints SET text = 'x' WHERE checklist_version_id = :id"),
                    {"id": uuid.UUID(v1["id"])},
                )
        # The scheduled inspection keeps version 1; Gate 6 can now be scheduled.
        assert (await detail(a, before))["checklist_version"] == 1
        snag = await schedule(s, (await stage(s, 16))["id"], a.appointment_id)
        assert (await detail(a, snag["id"]))["checklist_version"] == 2
    finally:
        await restore_checklists(database)


async def test_concurrent_approvals_have_one_winner(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s, a = await _ready(app, database, client_for, make_user, sign_in, worker)
    iid = (await schedule(s, (await stage(s, 3))["id"], a.appointment_id))["id"]
    await perform(a, database, s.project_id, iid)
    results_ = await asyncio.gather(
        *(s.ops.client.post(f"/api/v1/ops/inspections/{iid}/approve", headers=ops_key())
          for _ in range(2))
    )  # fmt: skip
    assert sorted(r.status_code for r in results_) == [200, 409]
    async with database.transaction() as session:
        reports = await session.scalar(
            text("SELECT count(*) FROM inspection_reports WHERE inspection_id = :id"),
            {"id": uuid.UUID(iid)},
        )
    assert reports == 1
