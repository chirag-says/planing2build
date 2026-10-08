"""Slice 3.7C (SLICE3_7_READINESS section 0, H, I, K, L, N, P.D, P.E): the handover opens only with
Gate 6 cleared and no open finding (EX-15); documents and warranties; the owner's acknowledgement
with a code against the active statement; an operations issue that is never an acknowledgement;
the Build Record assembled from the records, issued with its hash, a deterministic PDF and JSON,
versioned and immutable (EX-16, EX-17); the package (EX-18); access (EX-21); concurrency."""

import asyncio
import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.records.models import BuildRecord, Handover
from p2b.records.pdf import render_record
from tests.assurance_support import restore_checklists
from tests.billing_support import key
from tests.buildplan_support import code_of
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.execution_support import household, ok, ops_key, reason
from tests.records_support import cleared, document, opened, ready
from tests.rfq_support import keys_of
from tests.test_billing import refund_request
from tests.test_engagements import Run, world

COMMERCIAL = {"price", "rate", "amount", "total", "contract_value", "quote_version_id"}


@pytest.fixture
def worker(rfq_worker: Run) -> Run:
    return rfq_worker


@pytest.fixture(autouse=True)
async def _checklists(database: Database) -> AsyncIterator[None]:
    """Every test here publishes a Gate 6 checklist version; the seeded one comes back after."""
    yield
    await restore_checklists(database)


async def _acknowledge(s: Any, database: Database) -> dict[str, Any]:
    challenge = ok(await s.family.post(f"{s.base}/handover/acknowledgement-code", headers=key()))
    code = await code_of(database, challenge["challenge_id"])
    body: dict[str, Any] = ok(
        await s.family.post(
            f"{s.base}/handover/acknowledge",
            json={"challenge_id": challenge["challenge_id"], "code": code,
                  "statement_id": challenge["statement_id"]},
            headers=key(),
        )
    )  # fmt: skip
    return body


async def test_the_handover_waits_for_gate_6_and_closed_findings(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    from tests.assurance_support import approve, perform, schedule
    from tests.execution_support import site, stage

    early = await site(app, database, client_for, make_user, sign_in, worker)
    refused = await early.ops.client.post(f"/api/v1/ops/projects/{early.project_id}/handover",
                                          headers=ops_key())  # fmt: skip
    assert (refused.status_code, reason(refused)) == (409, "GATE6_NOT_CLEARED")
    s, a = await cleared(app, database, client_for, make_user, sign_in, worker)
    # An open finding anywhere on the project blocks the handover.
    iid = (await schedule(s, (await stage(s, 3))["id"], a.appointment_id))["id"]
    await perform(a, database, s.project_id, iid, findings={"G1-A06": "MINOR"})
    await approve(s, iid)
    blocked = await s.ops.client.post(f"/api/v1/ops/projects/{s.project_id}/handover",
                                      headers=ops_key())  # fmt: skip
    assert (blocked.status_code, reason(blocked)) == (409, "OPEN_FINDINGS")
    other, _ = await cleared(app, database, client_for, make_user, sign_in, worker)
    body = await opened(other)
    assert body["handover"]["state"] == "OPEN"
    again = await other.ops.client.post(f"/api/v1/ops/projects/{other.project_id}/handover",
                                        headers=ops_key())  # fmt: skip
    assert (again.status_code, reason(again)) == (409, "ALREADY_OPEN")
    mailbox = await worker()
    assert any(m.subject == "Your handover has started" for m in mailbox.sent)


async def test_documents_warranties_and_the_owners_acknowledgement(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s, _ = await cleared(app, database, client_for, make_user, sign_in, worker)
    assert s.pro is not None
    await opened(s)
    # The contractor adds a document while the handover is open.
    from tests.execution_support import photo, pro_key

    assert s.pro_user is not None
    file_id = await photo(database, s.pro_user, s.project_id, purpose="HANDOVER_DOCUMENT")
    ok(await s.pro.post(f"{s.pro_base}/handover/documents",
                        json={"kind": "CERTIFICATE", "title": "Electrical test certificate",
                              "file_id": file_id}, headers=pro_key()), 201)  # fmt: skip
    # A warranty document needs its warranty entry before READY.
    await document(s, database, "WARRANTY", "Pump warranty")
    missing = await s.ops.client.post(f"/api/v1/ops/projects/{s.project_id}/handover/ready",
                                      headers=ops_key())  # fmt: skip
    assert (missing.status_code, reason(missing)) == (409, "WARRANTY_MISSING")
    view = ok(await s.ops.client.get(f"/api/v1/ops/projects/{s.project_id}/handover"))
    doc = next(d for d in view["handover"]["documents"] if d["kind"] == "WARRANTY")
    ok(await s.ops.client.post(
        f"/api/v1/ops/projects/{s.project_id}/handover/warranties",
        json={"item": "Pressure pump", "term": "2 years", "expiry_date": "2028-10-01",
              "installer": "Aqua Fit (TEST)", "document_id": doc["id"]}, headers=ops_key(),
    ))  # fmt: skip
    ok(await s.ops.client.post(f"/api/v1/ops/projects/{s.project_id}/handover/ready",
                               headers=ops_key()))  # fmt: skip
    # The household reads, never acknowledges (EX-21).
    home = await household(database, client_for, make_user, sign_in, s.project_id)
    assert ok(await home.get(f"{s.base}/handover"))["handover"]["state"] == "READY"
    assert (await home.post(f"{s.base}/handover/acknowledgement-code",
                            headers=key())).status_code == 403  # fmt: skip
    # The owner reads the statement, and a stale statement id is refused.
    challenge = ok(await s.family.post(f"{s.base}/handover/acknowledgement-code", headers=key()))
    assert "not a completion certificate" in challenge["statement_text"]
    code = await code_of(database, challenge["challenge_id"])
    stale = await s.family.post(
        f"{s.base}/handover/acknowledge",
        json={"challenge_id": challenge["challenge_id"], "code": code,
              "statement_id": str(uuid.uuid4())},
        headers=key(),
    )  # fmt: skip
    assert (stale.status_code, reason(stale)) == (409, "STATEMENT_CHANGED")
    done = ok(
        await s.family.post(
            f"{s.base}/handover/acknowledge",
            json={"challenge_id": challenge["challenge_id"], "code": code,
                  "statement_id": challenge["statement_id"]},
            headers=key(),
        )
    )  # fmt: skip
    handover = done["handover"]
    assert handover["state"] == "ACKNOWLEDGED"
    assert handover["acknowledged_at"] is not None
    assert handover["issued_without_acknowledgement"] is False
    # Frozen: no more documents, by the service and by the database.
    late = await s.ops.client.post(
        f"/api/v1/ops/projects/{s.project_id}/handover/documents",
        json={"kind": "OTHER", "title": "Late", "file_id": file_id}, headers=ops_key(),
    )  # fmt: skip
    assert (late.status_code, reason(late)) == (409, "NOT_OPEN")
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("UPDATE handovers SET statement_text = 'x' WHERE id = :id"),
                                  {"id": uuid.UUID(handover["id"])})  # fmt: skip
    # A DRAFT Build Record is assembled for operations; the family sees issued versions only.
    ops_view = ok(await s.ops.client.get(f"/api/v1/ops/projects/{s.project_id}/handover"))
    versions = ops_view["build_records"]["versions"]
    assert [(v["version_no"], v["state"], v["basis"]) for v in versions] == [
        (1, "DRAFT", "ACKNOWLEDGED"),
    ]  # fmt: skip
    assert ok(await s.family.get(f"{s.base}/build-record"))["versions"] == []
    mailbox = await worker()
    subjects = {m.subject for m in mailbox.sent}
    assert {"Your handover is ready to acknowledge", "Handover acknowledged"} <= subjects


async def test_an_operations_issue_is_never_an_acknowledgement(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s, _ = await cleared(app, database, client_for, make_user, sign_in, worker)
    await ready(s, database)
    url = f"/api/v1/ops/projects/{s.project_id}/handover/issue-without-acknowledgement"
    assert (await s.ops.client.post(url, json={}, headers=ops_key())).status_code == 422
    body = ok(await s.ops.client.post(
        url, json={"reason": "The owner did not respond in three weeks; called twice."},
        headers=ops_key()))  # fmt: skip
    handover = body["handover"]
    assert handover["state"] == "ISSUED_BY_OPERATIONS"
    assert handover["acknowledged_at"] is None
    assert handover["statement_text"] is None
    assert handover["issued_without_acknowledgement"] is True
    assert body["build_records"]["versions"][0]["basis"] == "ISSUED_BY_OPERATIONS"
    family = ok(await s.family.get(f"{s.base}/handover"))["handover"]
    assert (family["acknowledged_at"], family["issued_without_acknowledgement"]) == (None, True)
    # The owner can no longer acknowledge; the database refuses to dress it up as one.
    late = await s.family.post(f"{s.base}/handover/acknowledgement-code", headers=key())
    assert (late.status_code, reason(late)) == (409, "NOT_READY")
    async with database.transaction() as session:
        await session.execute(text("ALTER TABLE handovers DISABLE TRIGGER handovers_frozen"))
    try:
        with pytest.raises(DBAPIError):
            async with database.transaction() as session:
                await session.execute(
                    text("UPDATE handovers SET acknowledged_by = forced_by WHERE id = :id"),
                    {"id": uuid.UUID(handover["id"])},
                )
    finally:
        async with database.transaction() as session:
            await session.execute(text("ALTER TABLE handovers ENABLE TRIGGER handovers_frozen"))
    async with database.transaction() as session:
        row = await session.get_one(Handover, uuid.UUID(handover["id"]))
        assert row.acknowledged_by is None
        record = (await session.execute(
            text("SELECT snapshot FROM build_records WHERE project_id = :p"),
            {"p": uuid.UUID(s.project_id)})).scalar_one()  # fmt: skip
    assert record["handover"]["acknowledgement"] is None
    assert record["handover"]["issued_without_acknowledgement"]["reason"].startswith("The owner")


async def test_the_build_record_is_issued_versioned_and_immutable(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s, _ = await cleared(app, database, client_for, make_user, sign_in, worker)
    await ready(s, database)
    await _acknowledge(s, database)
    view = ok(await s.ops.client.get(f"/api/v1/ops/projects/{s.project_id}/handover"))
    draft_id = view["build_records"]["versions"][0]["id"]
    issued = ok(await s.ops.client.post(f"/api/v1/ops/build-records/{draft_id}/issue",
                                        headers=ops_key()))  # fmt: skip
    v1 = issued["build_records"]["versions"][0]
    assert v1["state"] == "ISSUED"
    assert all(v1[k] for k in ("snapshot_sha256", "pdf_sha256", "json_sha256"))
    # The family reads the versions, the snapshot, the PDF and the JSON (logged).
    listing = ok(await s.family.get(f"{s.base}/build-record"))
    assert [v["version_no"] for v in listing["versions"]] == [1]
    snapshot = ok(await s.family.get(f"{s.base}/build-record/versions/1"))
    canonical = json.dumps(snapshot["snapshot"], sort_keys=True, separators=(",", ":"), default=str)
    assert hashlib.sha256(canonical.encode()).hexdigest() == v1["snapshot_sha256"]
    for form in ("pdf", "json"):
        assert ok(await s.family.get(f"{s.base}/build-record/versions/1/{form}/url"))["url"]
    assert (await s.family.get(f"{s.base}/build-record/versions/1/zip/url")).status_code == 404
    # Content: no commercial data; product, purchase and installation not recorded (EX-16).
    content = snapshot["snapshot"]
    assert not keys_of(content) & COMMERCIAL, keys_of(content) & COMMERCIAL
    assert len(content["specification"]) == 67
    assert {line["product"] for line in content["specification"]} == {"NOT RECORDED"}
    c24 = next(line for line in content["specification"] if line["code"] == "C24")
    assert c24["verification"][0]["gate"] == 6
    assert content["contractors"][0]["name"] == "Ravi Builders"
    assert content["handover"]["acknowledgement"]["statement_text"]
    # The JSON export carries the same snapshot and hash as the PDF.
    async with database.transaction() as session:
        row = await session.get_one(BuildRecord, uuid.UUID(draft_id))
        stored = await app.state.storage.read(
            (
                await session.execute(
                    text("SELECT object_key FROM file_objects WHERE id = :id"),
                    {"id": row.json_file_id},
                )
            ).scalar_one()
        )
    export = json.loads(stored)
    assert export["snapshot_sha256"] == v1["snapshot_sha256"]
    assert export["snapshot"] == content
    assert hashlib.sha256(stored).hexdigest() == v1["json_sha256"]
    # Deterministic PDF: the same snapshot gives the same bytes.
    settings = get_settings()
    assert row.issued_at is not None
    args = {"version_no": 1, "issued_at": row.issued_at, "digest": v1["snapshot_sha256"],
            "basis": "ACKNOWLEDGED", "correction_reason": None}  # fmt: skip
    first = render_record(settings, content, **args)
    assert first == render_record(settings, content, **args)
    assert hashlib.sha256(first).hexdigest() == v1["pdf_sha256"]
    # Issued is frozen.
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("UPDATE build_records SET snapshot = '{}' WHERE id = :id"),
                                  {"id": uuid.UUID(draft_id)})  # fmt: skip
    # A correction is a new version with a reason; the earlier one stays readable.
    url = f"/api/v1/ops/projects/{s.project_id}/build-record/assemble"
    no_reason = await s.ops.client.post(url, json={}, headers=ops_key())
    assert (no_reason.status_code, reason(no_reason)) == (409, "REASON_REQUIRED")
    body = ok(await s.ops.client.post(url, json={"reason": "Warranty expiry corrected."},
                                      headers=ops_key()))  # fmt: skip
    v2 = next(v for v in body["build_records"]["versions"] if v["version_no"] == 2)
    ok(await s.ops.client.post(f"/api/v1/ops/build-records/{v2['id']}/issue", headers=ops_key()))
    states = {v["version_no"]: v["state"]
              for v in ok(await s.family.get(f"{s.base}/build-record"))["versions"]}  # fmt: skip
    assert states == {1: "SUPERSEDED", 2: "ISSUED"}
    assert ok(await s.family.get(f"{s.base}/build-record/versions/1"))["snapshot"] == content
    # Sent before another project is set up (its setup relays the outbox on its own).
    mailbox = await worker()
    assert any(m.subject == "Your Build Record is issued" for m in mailbox.sent)
    # OWNER and HOUSEHOLD only: another family and the contractor see nothing.
    home = await household(database, client_for, make_user, sign_in, s.project_id)
    assert ok(await home.get(f"{s.base}/build-record"))["versions"]
    stranger = await world(app, database, client_for, make_user, sign_in, None)
    assert (await stranger.family.get(f"{s.base}/build-record")).status_code == 404
    assert s.pro is not None
    assert (await s.pro.get(f"{s.base}/build-record")).status_code in (401, 403, 404)


async def test_issuing_needs_the_package_and_acknowledging_does_not(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s, _ = await cleared(app, database, client_for, make_user, sign_in, worker)
    await ready(s, database)
    request_id = await refund_request(s.family, s.world.order["order_id"])
    ok(await s.ops.client.post(
        f"/api/v1/ops/billing/refund-requests/{request_id}/approve",
        json={"amount": s.world.order["total"], "ends_package": True, "reason": "Refund agreed."},
        headers=ops_key(),
    ))  # fmt: skip
    await worker()
    body = await _acknowledge(s, database)
    assert body["handover"]["state"] == "ACKNOWLEDGED"
    view = ok(await s.ops.client.get(f"/api/v1/ops/projects/{s.project_id}/handover"))
    draft_id = view["build_records"]["versions"][0]["id"]
    blocked = await s.ops.client.post(f"/api/v1/ops/build-records/{draft_id}/issue",
                                      headers=ops_key())  # fmt: skip
    assert reason(blocked) == "PACKAGE_REQUIRED"


async def test_concurrent_issues_have_one_winner(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    s, _ = await cleared(app, database, client_for, make_user, sign_in, worker)
    await ready(s, database)
    await _acknowledge(s, database)
    view = ok(await s.ops.client.get(f"/api/v1/ops/projects/{s.project_id}/handover"))
    draft_id = view["build_records"]["versions"][0]["id"]
    results = await asyncio.gather(
        *(s.ops.client.post(f"/api/v1/ops/build-records/{draft_id}/issue", headers=ops_key())
          for _ in range(2))
    )  # fmt: skip
    assert sorted(r.status_code for r in results) == [200, 409]
    async with database.transaction() as session:
        files = await session.scalar(
            text("SELECT count(*) FROM file_objects WHERE purpose = 'BUILD_RECORD_DOCUMENT'")
        )
    assert files == 1
