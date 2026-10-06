"""Slice 3.5 (SLICE3_5_READINESS section 0): design intake and checking, Build Plan versions and
every transition, immutability (service and database), structural sign-off in both modes with
hash binding, four-eyes issue, the PDF, one-time-code acceptance and supersession, package
gating with the refund rule unchanged, DEMO cards never in production, the contractor manifest
without rates, access, logged downloads, AI concepts never authoritative, and the deferred
schedule (BP-07A: no dates)."""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError

from p2b.billing.models import PackageServiceUsage
from p2b.buildplan import pdf
from p2b.buildplan.models import (
    BoqLine,
    BuildPlanAcceptance,
    BuildPlanSpecValue,
    BuildPlanVersion,
    ScheduleEntry,
    StructuralSignoff,
)
from p2b.buildplan.plans import usable_card
from p2b.buildplan.views import snapshot
from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.errors import StateConflict
from p2b.core.vocabulary import Audience
from p2b.documents.models import DocumentAccessLog
from p2b.projects.interface import build_plan_facts
from p2b.specification.models import ProjectSpecLine
from tests.billing_support import key
from tests.buildplan_support import (
    CLASSES,
    PRO_H,
    STRUCTURAL,
    Team,
    accepted,
    approved_set,
    code_of,
    drafted,
    full_version,
    issued,
    ok,
    ops_key,
    pro_key,
    reason,
    sign_all_by_document,
    stored,
    submitted,
    team,
    verified_engineer,
)
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.staff_support import OPS_HEADERS
from tests.test_billing import refund_request
from tests.test_engagements import Run, listed_pro, sent, worker  # noqa: F401  (the fixture)


async def version_state(database: Database, vid: str) -> str:
    async with database.transaction() as session:
        return (await session.get_one(BuildPlanVersion, uuid.UUID(vid))).state


async def setup(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    run: Run,
) -> Team:
    return await team(app, database, client_for, make_user, sign_in, run)


# --- the whole path ------------------------------------------------------------------------


async def test_design_to_accepted_build_plan_and_a_later_version_supersedes_it(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    w = t.world
    vid, set_id, _ = await full_version(database, t)

    # The family never sees a version before it is issued.
    assert (await w.family.get(f"{w.base}/build-plan/versions/{vid}")).status_code == 404
    assert ok(await w.family.get(f"{w.base}/build-plan"))["versions"] == []

    # The last editor cannot issue (BP-13); someone else can.
    refused = await t.advisor.client.post(
        f"/api/v1/ops/build-plan-versions/{vid}/issue", headers=ops_key()
    )
    assert (refused.status_code, reason(refused)) == (409, "LAST_EDITOR")
    out = await issued(t, vid)
    assert out["snapshot"]["version"]["state"] == "ISSUED"
    document_id = out["issued_document_id"]
    assert document_id

    family_view = ok(await w.family.get(f"{w.base}/build-plan"))
    assert [v["state"] for v in family_view["versions"]] == ["ISSUED"]
    snap = ok(await w.family.get(f"{w.base}/build-plan/versions/{vid}"))
    assert snap["boq_total"] == "1670.00"  # 12.5 x 100.00 + 40 x 10.50
    assert {s["line_code"] for s in snap["signoffs"]} == set(STRUCTURAL)
    assert all(e["planned_start"] is None and e["planned_end"] is None for e in snap["schedule"])
    assert snap["dates_status"] == "NOT_CALCULATED_BP07A_DEFERRED"

    # Authenticated, logged download of the PDF.
    url = await w.family.get(f"{w.base}/build-plan/files/{document_id}/url")
    assert url.status_code == 200, url.text
    anonymous = client_for(Audience.IHB)
    assert (await anonymous.get(f"{w.base}/build-plan/files/{document_id}/url")).status_code == 401
    async with database.transaction() as session:
        logged = await session.scalar(
            select(func.count())
            .select_from(DocumentAccessLog)
            .where(DocumentAccessLog.file_id == uuid.UUID(document_id))
        )
    assert logged == 1

    # Acceptance by one-time code: the exact version, the RFQ baseline.
    after = await accepted(database, t, vid)
    assert after["version"]["state"] == "ACCEPTED"
    assert after["acceptance"]["content_hash"] == after["version"]["content_hash"]
    async with database.transaction() as session:
        acceptance = (await session.scalars(select(BuildPlanAcceptance))).one()
        assert acceptance.version_no == 1
        pointers = list(await session.scalars(select(ProjectSpecLine.accepted_value_id)))
        accepted_doc = (
            await session.get_one(BuildPlanVersion, uuid.UUID(vid))
        ).accepted_document_id
    assert all(pointers)
    assert len(pointers) == 67
    assert accepted_doc is not None
    assert str(accepted_doc) != document_id

    # Version 2: carried forward, changed, issued and accepted; version 1 becomes SUPERSEDED.
    v2 = ok(
        await t.advisor.client.post(
            f"/api/v1/ops/projects/{t.project_id}/build-plan/versions", headers=ops_key()
        ),
        201,
    )
    v2id = v2["snapshot"]["version"]["id"]
    assert v2["missing"] == []  # carried forward complete
    ok(
        await t.advisor.client.put(
            f"/api/v1/ops/build-plan-versions/{v2id}/values",
            json={"values": [{"code": "C01", "value_text": "TEST revised", "basis": "ADVISOR"}]},
            headers=OPS_HEADERS,
        )
    )
    await submitted(t.advisor.client, v2id)
    ok(await sign_all_by_document(database, t, v2id))
    await issued(t, v2id)
    assert await version_state(database, vid) == "ACCEPTED"  # still the baseline until v2 is
    await accepted(database, t, v2id)
    assert await version_state(database, vid) == "SUPERSEDED"
    assert await version_state(database, v2id) == "ACCEPTED"
    plan = ok(await w.family.get(f"{w.base}/build-plan"))
    assert plan["accepted_version_id"] == v2id
    # Old versions stay readable.
    assert (
        ok(await w.family.get(f"{w.base}/build-plan/versions/{vid}"))["version"]["state"]
        == "SUPERSEDED"
    )

    # Issuing never wrote a refund substantial-work record (BP-09; N-12 stays the rule).
    async with database.transaction() as session:
        services = list(await session.scalars(select(PackageServiceUsage.service)))
    assert "BUILD_PLAN_ISSUED" not in services
    assert set(services) <= {"CONNECTION_ACCEPTED"}
    assert set_id
    # The family was told the plan was issued.
    mailbox = await worker()
    subjects = [m.subject for m in mailbox.sent]
    assert "Your Plan2Build Build Plan is ready to review" in subjects


# --- transitions ---------------------------------------------------------------------------


async def test_review_returns_to_draft_voids_signoffs_and_new_content_needs_new_signatures(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    vid, _, _ = await full_version(database, t)
    c = t.advisor.client
    # In review, the content is frozen.
    frozen = await c.put(
        f"/api/v1/ops/build-plan-versions/{vid}/values",
        json={"values": [{"code": "C01", "value_text": "x", "basis": "ADVISOR"}]},
        headers=OPS_HEADERS,
    )
    assert frozen.status_code == 409
    back = ok(
        await c.post(
            f"/api/v1/ops/build-plan-versions/{vid}/return", json={"reason": "Fix C01"},
            headers=ops_key(),
        )
    )  # fmt: skip
    assert back["snapshot"]["version"]["state"] == "DRAFT"
    assert all(s["state"] == "VOID" for s in back["snapshot"]["signoffs"])
    ok(
        await c.put(
            f"/api/v1/ops/build-plan-versions/{vid}/values",
            json={"values": [{"code": "C01", "value_text": "TEST changed", "basis": "ADVISOR"}]},
            headers=OPS_HEADERS,
        )
    )
    again = await submitted(c, vid)
    assert sorted(again["snapshot"]["unsigned_structural_lines"]) == sorted(STRUCTURAL)
    refused = await t.issuer.client.post(
        f"/api/v1/ops/build-plan-versions/{vid}/issue", headers=ops_key()
    )
    assert (refused.status_code, reason(refused)) == (409, "UNSIGNED")
    # Partial sign-off is not issuable.
    ok(await sign_all_by_document(database, t, vid, STRUCTURAL[:4]))
    partial = await t.issuer.client.post(
        f"/api/v1/ops/build-plan-versions/{vid}/issue", headers=ops_key()
    )
    assert reason(partial) == "UNSIGNED"
    ok(await sign_all_by_document(database, t, vid, STRUCTURAL[4:]))
    await issued(t, vid)
    async with database.transaction() as session:
        rows = list(await session.scalars(select(StructuralSignoff)))
    signed = [r for r in rows if r.state == "SIGNED"]
    version = await database_version(database, vid)
    assert {r.content_hash for r in signed} == {version.content_hash}
    assert all(r.drawing_hashes and r.statement_text for r in signed)


async def database_version(database: Database, vid: str) -> BuildPlanVersion:
    async with database.transaction() as session:
        return await session.get_one(BuildPlanVersion, uuid.UUID(vid))


async def test_changes_requested_withdrawal_and_acceptance_rules(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    w = t.world
    vid, _, _ = await full_version(database, t)
    await issued(t, vid)
    changes = await w.family.post(
        f"{w.base}/build-plan/versions/{vid}/request-changes",
        json={"reason": "Please add a terrace."}, headers=key(),
    )  # fmt: skip
    assert changes.status_code == 200, changes.text
    assert await version_state(database, vid) == "CHANGES_REQUESTED"
    code = await w.family.post(f"{w.base}/build-plan/versions/{vid}/acceptance-code", headers=key())
    assert code.status_code == 409  # a version with changes requested can never be accepted
    # The next version is issued; the earlier one is superseded; it is then withdrawn and the
    # family cannot accept a withdrawn version.
    v2 = ok(
        await t.advisor.client.post(
            f"/api/v1/ops/projects/{t.project_id}/build-plan/versions", headers=ops_key()
        ),
        201,
    )
    v2id = v2["snapshot"]["version"]["id"]
    await submitted(t.advisor.client, v2id)
    ok(await sign_all_by_document(database, t, v2id))
    await issued(t, v2id)
    assert await version_state(database, vid) == "SUPERSEDED"
    withdrawn = await t.advisor.client.post(
        f"/api/v1/ops/build-plan-versions/{v2id}/withdraw", json={"reason": "Wrong BOQ"},
        headers=ops_key(),
    )  # fmt: skip
    assert withdrawn.status_code == 200, withdrawn.text
    assert await version_state(database, v2id) == "WITHDRAWN"
    late = await w.family.post(
        f"{w.base}/build-plan/versions/{v2id}/acceptance-code", headers=key()
    )
    assert late.status_code == 409
    # An accepted version can never be withdrawn.
    v3 = ok(
        await t.advisor.client.post(
            f"/api/v1/ops/projects/{t.project_id}/build-plan/versions", headers=ops_key()
        ),
        201,
    )
    v3id = v3["snapshot"]["version"]["id"]
    await submitted(t.advisor.client, v3id)
    ok(await sign_all_by_document(database, t, v3id))
    await issued(t, v3id)
    await accepted(database, t, v3id)
    refused = await t.advisor.client.post(
        f"/api/v1/ops/build-plan-versions/{v3id}/withdraw", json={"reason": "x"},
        headers=ops_key(),
    )  # fmt: skip
    assert refused.status_code == 409
    # A wrong one-time code is refused and counted.
    v4 = ok(
        await t.advisor.client.post(
            f"/api/v1/ops/projects/{t.project_id}/build-plan/versions", headers=ops_key()
        ),
        201,
    )
    v4id = v4["snapshot"]["version"]["id"]
    await submitted(t.advisor.client, v4id)
    ok(await sign_all_by_document(database, t, v4id))
    await issued(t, v4id)
    challenge = ok(
        await w.family.post(f"{w.base}/build-plan/versions/{v4id}/acceptance-code", headers=key())
    )
    wrong = await w.family.post(
        f"{w.base}/build-plan/versions/{v4id}/accept",
        json={"challenge_id": challenge["challenge_id"], "code": "000000"}, headers=key(),
    )  # fmt: skip
    if wrong.status_code != 400:  # the code could, in a million, be 000000
        assert wrong.status_code == 200
    else:
        assert wrong.json()["error"]["code"] == "OTP_INVALID"
        assert await version_state(database, v4id) == "ISSUED"


async def test_a_confirmation_code_never_signs_anyone_in(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    w = t.world
    vid, _, _ = await full_version(database, t)
    await issued(t, vid)
    challenge = ok(
        await w.family.post(f"{w.base}/build-plan/versions/{vid}/acceptance-code", headers=key())
    )
    code = await code_of(database, challenge["challenge_id"])
    anonymous = client_for(Audience.IHB)
    attempt = await anonymous.post(
        "/api/v1/auth/otp/verify",
        json={"challenge_id": challenge["challenge_id"], "code": code},
        headers={"X-Requested-With": "plan2build", "Origin": "https://plan2build.in"},
    )
    assert attempt.status_code in (400, 403, 422)
    # Another family member cannot use the owner's code either.
    stranger = client_for(Audience.IHB)
    await sign_in(stranger, await make_user(), Audience.IHB)
    other = await stranger.post(
        f"{w.base}/build-plan/versions/{vid}/accept",
        json={"challenge_id": challenge["challenge_id"], "code": code}, headers=key(),
    )  # fmt: skip
    assert other.status_code == 404


# --- immutability --------------------------------------------------------------------------


async def test_issued_accepted_and_signed_records_are_immutable_in_the_database(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    vid, set_id, _ = await full_version(database, t)
    await issued(t, vid)
    await accepted(database, t, vid)
    attacks: list[Any] = [
        update(BuildPlanVersion).where(BuildPlanVersion.id == uuid.UUID(vid))
        .values(explanation_note="changed"),
        update(BuildPlanVersion).where(BuildPlanVersion.id == uuid.UUID(vid))
        .values(content_hash="0" * 64),
        update(BuildPlanSpecValue).where(BuildPlanSpecValue.version_id == uuid.UUID(vid))
        .values(value_text="changed"),
        update(BoqLine).where(BoqLine.version_id == uuid.UUID(vid)).values(quantity=1),
        update(ScheduleEntry).where(ScheduleEntry.version_id == uuid.UUID(vid))
        .values(duration_days=99),
        update(StructuralSignoff).values(engineer_name="someone else"),
        update(BuildPlanAcceptance).values(content_hash="x"),
        text("DELETE FROM build_plan_versions"),
        text("DELETE FROM build_plan_events"),
        text("UPDATE drawing_sets SET content_hash = 'x' WHERE id = :id").bindparams(
            id=uuid.UUID(set_id)
        ),
        text("DELETE FROM drawing_files WHERE set_id = :id").bindparams(id=uuid.UUID(set_id)),
        text("UPDATE item_rate_card_lines SET rate = 1"),
        text("UPDATE signoff_statements SET text = 'changed'"),
    ]  # fmt: skip
    for statement in attacks:
        with pytest.raises(DBAPIError):
            async with database.transaction() as session:
                await session.execute(statement)
    # Schedule dates cannot be written while BP-07A is deferred.
    v2 = ok(
        await t.advisor.client.post(
            f"/api/v1/ops/projects/{t.project_id}/build-plan/versions", headers=ops_key()
        ),
        201,
    )
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(
                update(ScheduleEntry)
                .where(ScheduleEntry.version_id == uuid.UUID(v2["snapshot"]["version"]["id"]))
                .values(planned_start=datetime(2027, 1, 1, tzinfo=UTC).date())
            )
    # The four-eyes rule is also a database CHECK.
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(
                text(
                    "UPDATE build_plan_versions SET issued_by = last_edited_by WHERE id = :id"
                ).bindparams(id=uuid.UUID(v2["snapshot"]["version"]["id"]))
            )


# --- schedule (BP-07, BP-07A) --------------------------------------------------------------


async def test_schedule_holds_durations_and_explicit_dependencies_only(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    set_id, files = await approved_set(database, t)
    draft = await drafted(database, t, set_id, files)
    vid = draft["snapshot"]["version"]["id"]
    entries = draft["snapshot"]["schedule"]
    keys = [e["entry_key"] for e in entries]
    # G+1 with a basement in the COMPLETE requirement: repeated stages per floor, no inferred order.
    assert all(e["predecessors"] == [] for e in entries[2:])
    assert all(e["planned_start"] is None for e in entries)
    url = f"/api/v1/ops/build-plan-versions/{vid}/schedule"
    loop = await t.advisor.client.put(
        url,
        json={"entries": [{"entry_key": keys[0], "duration_days": 5, "predecessors": [keys[1]]}]},
        headers=OPS_HEADERS,
    )
    assert loop.status_code == 422  # keys[1] already follows keys[0]: a loop
    unknown = await t.advisor.client.put(
        url, json={"entries": [{"entry_key": "S99", "duration_days": 5}]}, headers=OPS_HEADERS
    )
    assert unknown.status_code == 422
    async with database.transaction() as session:
        dates = await session.scalar(
            select(func.count())
            .select_from(ScheduleEntry)
            .where(ScheduleEntry.planned_start.is_not(None))
        )
        spec_dates = await session.scalar(
            select(func.count())
            .select_from(ProjectSpecLine)
            .where(ProjectSpecLine.decide_by.is_not(None))
        )
    assert dates == 0
    assert spec_dates == 0


# --- sign-off ------------------------------------------------------------------------------


async def test_a_verified_engineer_signs_with_a_one_time_code(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    engineer, profile_id, _ = await verified_engineer(
        database, client_for, make_user, sign_in, t, worker
    )
    set_id, files = await approved_set(database, t)
    draft = await drafted(database, t, set_id, files)
    vid = draft["snapshot"]["version"]["id"]
    # Not yet in review: nothing to sign.
    assert ok(await engineer.get("/api/v1/pro/build-plan/signoffs"))["items"] == []
    await submitted(t.advisor.client, vid)
    view = ok(await engineer.get(f"/api/v1/pro/build-plan/signoffs/{vid}"))
    assert view["verified"] is True
    assert view["statement_version"] == 1
    assert "I confirm that I have reviewed" in view["statement_text"]
    assert sorted(line["code"] for line in view["lines"]) == sorted(STRUCTURAL)
    assert {d["drawing_class"] for d in view["drawings"]} == set(CLASSES)
    challenge = ok(
        await engineer.post(
            f"/api/v1/pro/build-plan/signoffs/{vid}/code", json={"line_codes": STRUCTURAL},
            headers=PRO_H,
        )
    )  # fmt: skip
    code = await code_of(database, challenge["challenge_id"])
    signed = ok(
        await engineer.post(
            f"/api/v1/pro/build-plan/signoffs/{vid}/sign",
            json={"line_codes": STRUCTURAL, "challenge_id": challenge["challenge_id"],
                  "code": code},
            headers=pro_key(),
        )
    )  # fmt: skip
    assert all(line["signed"] for line in signed["lines"])
    async with database.transaction() as session:
        rows = list(await session.scalars(select(StructuralSignoff)))
    assert {r.mode for r in rows} == {"ONE_TIME_CODE"}
    first = rows[0]
    assert first.profile_id == uuid.UUID(profile_id)
    assert first.category_code == "STRUCTURAL_ENGINEER"
    assert first.registration_number == "TEST-REG-9"
    assert first.credential_reference["verification_check_id"]
    assert first.challenge_id == uuid.UUID(challenge["challenge_id"])
    assert len(first.drawing_hashes) == 1  # the set's one structural drawing
    # The same code cannot be used twice.
    again = await engineer.post(
        f"/api/v1/pro/build-plan/signoffs/{vid}/sign",
        json={"line_codes": ["A01"], "challenge_id": challenge["challenge_id"], "code": code},
        headers=pro_key(),
    )  # fmt: skip
    assert again.status_code in (400, 409)
    # Revocation before issue voids; the version then needs a new signature for that line.
    revoke = await engineer.post(
        f"/api/v1/pro/build-plan/signoffs/{first.id}/revoke", json={"reason": "Recheck"},
        headers=pro_key(),
    )  # fmt: skip
    assert revoke.status_code == 200, revoke.text
    blocked = await t.issuer.client.post(
        f"/api/v1/ops/build-plan-versions/{vid}/issue", headers=ops_key()
    )
    assert reason(blocked) == "UNSIGNED"
    ok(await sign_all_by_document(database, t, vid, [first.line_code]))
    await issued(t, vid)
    # A revocation after issue is recorded and blocks acceptance (BP-20); the record stays.
    second = next(r for r in rows if r.line_code != first.line_code)
    late = await engineer.post(
        f"/api/v1/pro/build-plan/signoffs/{second.id}/revoke", json={"reason": "Error found"},
        headers=pro_key(),
    )  # fmt: skip
    assert late.status_code == 200, late.text
    async with database.transaction() as session:
        assert (await session.get_one(StructuralSignoff, second.id)).state == "SIGNED"
    w = t.world
    blocked_accept = await w.family.post(
        f"{w.base}/build-plan/versions/{vid}/acceptance-code", headers=key()
    )
    assert reason(blocked_accept) == "SIGNOFF_REVOKED"


async def test_only_a_verified_engaged_engineer_may_sign(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    unverified, profile_id, _ = await listed_pro(
        database, client_for, make_user, sign_in, ("STRUCTURAL_ENGINEER",), name="No Reg"
    )
    connection_id = await sent(t.world, profile_id, "STRUCTURAL_ENGINEER")
    ok(await unverified.post(f"/api/v1/pro/connections/{connection_id}/accept", json={},
                             headers=pro_key()))  # fmt: skip
    set_id, files = await approved_set(database, t)
    draft = await drafted(database, t, set_id, files)
    vid = draft["snapshot"]["version"]["id"]
    await submitted(t.advisor.client, vid)
    view = ok(await unverified.get(f"/api/v1/pro/build-plan/signoffs/{vid}"))
    assert view["verified"] is False
    refused = await unverified.post(
        f"/api/v1/pro/build-plan/signoffs/{vid}/code", json={"line_codes": ["A01"]}, headers=PRO_H
    )
    assert (refused.status_code, reason(refused)) == (409, "NOT_VERIFIED")
    stranger, _, _ = await listed_pro(
        database, client_for, make_user, sign_in, ("STRUCTURAL_ENGINEER",), name="Not Engaged"
    )
    assert (await stranger.get(f"/api/v1/pro/build-plan/signoffs/{vid}")).status_code == 404
    # Outside engineer: operations need the certificate and the signed document.
    missing = await t.advisor.client.post(
        f"/api/v1/ops/build-plan-versions/{vid}/signoffs",
        json={"line_codes": ["A01"], "engineer_name": "X", "registration_number": "R",
              "registration_issuer": "I", "credential_file_id": str(uuid.uuid4()),
              "evidence_file_id": str(uuid.uuid4()), "attestation": "Checked."},
        headers=ops_key(),
    )  # fmt: skip
    assert missing.status_code == 422
    not_structural = await sign_all_by_document(database, t, vid, ["C01"])
    assert not_structural.status_code == 422


# --- package, rate cards, manifest ---------------------------------------------------------


async def test_package_gating_and_refund_leave_history_readable_and_drafts_in_place(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    w = t.world
    vid, set_id, files = await full_version(database, t)
    await issued(t, vid)
    v2 = ok(
        await t.advisor.client.post(
            f"/api/v1/ops/projects/{t.project_id}/build-plan/versions", headers=ops_key()
        ),
        201,
    )
    v2id = v2["snapshot"]["version"]["id"]
    request_id = await refund_request(w.family, w.order["order_id"])
    refunded = await t.issuer.client.post(
        f"/api/v1/ops/billing/refund-requests/{request_id}/approve",
        json={"amount": w.order["total"], "ends_package": True, "reason": "Refund agreed."},
        headers=ops_key(),
    )  # fmt: skip
    assert refunded.status_code == 200, refunded.text
    await worker()
    # New package-gated work is blocked.
    for response in (
        await t.advisor.client.post(
            f"/api/v1/ops/projects/{t.project_id}/build-plan/versions", headers=ops_key()
        ),
        await t.advisor.client.put(
            f"/api/v1/ops/build-plan-versions/{v2id}/scope",
            json={"inclusions": ["a"], "exclusions": ["b"], "assumptions": ["c"]},
            headers=OPS_HEADERS,
        ),
        await w.family.post(f"{w.base}/build-plan/versions/{vid}/acceptance-code", headers=key()),
        await w.family.post(
            f"{w.base}/design-requests",
            json={"kind": "HOMEOWNER_PROVIDED", "scope_note": "x"}, headers=key(),
        ),
    ):  # fmt: skip
        assert (response.status_code, reason(response)) == (409, "PACKAGE_REQUIRED"), response.text
    # Issued history stays readable; the draft is not withdrawn automatically.
    assert (
        ok(await w.family.get(f"{w.base}/build-plan/versions/{vid}"))["version"]["state"]
        == "ISSUED"
    )
    assert await version_state(database, v2id) == "DRAFT"
    # Operations may still withdraw it.
    withdrawn = await t.advisor.client.post(
        f"/api/v1/ops/build-plan-versions/{v2id}/withdraw", json={"reason": "Package ended"},
        headers=ops_key(),
    )  # fmt: skip
    assert withdrawn.status_code == 200
    assert set_id
    assert files


async def test_demo_cards_never_price_production_and_publishing_needs_admin(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    production = get_settings().model_copy(update={"env": "production"})
    async with database.transaction() as session:
        with pytest.raises(StateConflict) as refused:
            await usable_card(session, production, uuid.UUID(t.card_id))
    assert refused.value.details["reason"] == "DEMO_CARD"
    draft = ok(
        await t.advisor.client.post(
            "/api/v1/ops/item-rate-cards",
            json={"geography": "Raipur", "effective_from": "2026-10-01",
                  "source_reference": "TEST", "is_demo": False},
            headers=ops_key(),
        ),
        201,
    )  # fmt: skip
    # OPS prepares; only ADMIN publishes.
    forbidden = await t.advisor.client.post(
        f"/api/v1/admin/item-rate-cards/{draft['id']}/publish", headers=ops_key()
    )
    assert forbidden.status_code == 403
    empty = await t.admin.client.post(
        f"/api/v1/admin/item-rate-cards/{draft['id']}/publish", headers=ops_key()
    )
    assert empty.status_code == 422  # no lines
    # A DRAFT card cannot price a BOQ.
    set_id, files = await approved_set(database, t)
    version = ok(
        await t.advisor.client.post(
            f"/api/v1/ops/projects/{t.project_id}/build-plan/versions", headers=ops_key()
        ),
        201,
    )
    vid = version["snapshot"]["version"]["id"]
    unpublished = await t.advisor.client.put(
        f"/api/v1/ops/build-plan-versions/{vid}/boq",
        json={"rate_card_id": draft["id"], "lines": [
            {"item_code": "TEST-RCC", "quantity": "1", "quantity_basis": "ADVISOR_ESTIMATE",
             "basis_note": "x"}]},
        headers=OPS_HEADERS,
    )  # fmt: skip
    assert reason(unpublished) == "CARD_NOT_PUBLISHED"
    unknown_item = await t.advisor.client.put(
        f"/api/v1/ops/build-plan-versions/{vid}/boq",
        json={"rate_card_id": t.card_id, "lines": [
            {"item_code": "NOT-ON-CARD", "quantity": "1", "quantity_basis": "ADVISOR_ESTIMATE",
             "basis_note": "x"}]},
        headers=OPS_HEADERS,
    )  # fmt: skip
    assert unknown_item.status_code == 422
    assert set_id
    assert files


async def test_the_contractor_manifest_has_scope_and_quantities_but_no_internal_rates(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    url = f"/api/v1/ops/projects/{t.project_id}/build-plan/rfq-manifest"
    none_yet = await t.advisor.client.get(url)
    assert reason(none_yet) == "NO_ACCEPTED_VERSION"
    vid, _, _ = await full_version(database, t)
    await issued(t, vid)
    assert reason(await t.advisor.client.get(url)) == "NO_ACCEPTED_VERSION"  # issued only
    await accepted(database, t, vid)
    manifest = ok(await t.advisor.client.get(url))
    assert manifest["build_plan_version_id"] == vid
    assert len(manifest["quantities"]) == 2
    assert len(manifest["specifications"]) == 67
    raw = json.dumps(manifest)
    for forbidden in ('"rate"', '"amount"', '"rate_card"', "100.00", "10.50", "1670.00"):
        assert forbidden not in raw
    assert manifest["dates_status"] == "NOT_CALCULATED_BP07A_DEFERRED"


# --- access, AI exclusion, PDF ------------------------------------------------------------


async def test_access_rules_and_ai_concepts_never_become_drawings(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    w = t.world
    stranger = client_for(Audience.IHB)
    await sign_in(stranger, await make_user(), Audience.IHB)
    assert (await stranger.get(f"{w.base}/build-plan")).status_code == 404
    anonymous = client_for(Audience.IHB)
    assert (await anonymous.get(f"{w.base}/build-plan")).status_code == 401
    # Only operations arrange a professional.
    arranged = await w.family.post(
        f"{w.base}/design-requests",
        json={"kind": "PLAN2BUILD_ARRANGED", "scope_note": "x", "provider_name": "A",
              "provider_qualification": "B"},
        headers=key(),
    )  # fmt: skip
    assert reason(arranged) == "OPS_ONLY"
    # An AI concept of another project cannot even be named; an AI image is never a drawing.
    unknown = await w.family.post(
        f"{w.base}/design-requests",
        json={"kind": "HOMEOWNER_PROVIDED", "scope_note": "x",
              "reference_design_ids": [str(uuid.uuid4())]},
        headers=key(),
    )  # fmt: skip
    assert unknown.status_code == 422
    view = ok(await w.family.post(
        f"{w.base}/design-requests", json={"kind": "HOMEOWNER_PROVIDED", "scope_note": "Mine"},
        headers=key()), 201)  # fmt: skip
    request_id = view["design_requests"][-1]["id"]
    view = ok(
        await w.family.post(f"{w.base}/design-requests/{request_id}/sets", headers=key()), 201
    )
    set_id = view["design_requests"][-1]["sets"][-1]["id"]
    concept = await stored(database, t.owner, w.project_id, "AI_CONCEPT", "concept.png")
    as_drawing = await w.family.post(
        f"{w.base}/drawing-sets/{set_id}/files",
        json={"file_id": concept, "drawing_class": "FLOOR_PLAN", "title": "AI"}, headers=key(),
    )  # fmt: skip
    assert as_drawing.status_code == 422
    # A version cannot use a set that is not approved.
    version = ok(
        await t.advisor.client.post(
            f"/api/v1/ops/projects/{t.project_id}/build-plan/versions", headers=ops_key()
        ),
        201,
    )
    vid = version["snapshot"]["version"]["id"]
    not_approved = await t.advisor.client.put(
        f"/api/v1/ops/build-plan-versions/{vid}/drawing-set", json={"set_id": set_id},
        headers=OPS_HEADERS,
    )  # fmt: skip
    assert reason(not_approved) == "SET_NOT_APPROVED"
    # The family never reads a draft; a professional never reads the family's plan.
    assert (await w.family.get(f"{w.base}/build-plan/versions/{vid}")).status_code == 404
    assert set(CLASSES) >= {"SITE_PLAN", "FLOOR_PLAN"}


async def test_the_pdf_is_deterministic_and_names_its_version(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    vid, _, _ = await full_version(database, t)
    await issued(t, vid)
    async with database.transaction() as session:
        version = await session.get_one(BuildPlanVersion, uuid.UUID(vid))
        facts = await build_plan_facts(session, version.project_id)
        assert facts is not None
        view: dict[str, Any] = await snapshot(session, facts, version)
    assert version.issued_at is not None
    settings = get_settings()
    first = pdf.render(settings, view, created_at=version.issued_at, accepted_copy=False)
    second = pdf.render(settings, view, created_at=version.issued_at, accepted_copy=False)
    assert first == second
    assert first.startswith(b"%PDF")
    assert b"TEST DOCUMENT" not in first or view["rate_card"]["is_demo"]


async def test_a_listed_architects_set_goes_through_the_family_and_an_account_holding_checker(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    w = t.world
    architect, profile_id, architect_user = await listed_pro(
        database, client_for, make_user, sign_in, ("ARCHITECT",), name="Listed Architect"
    )
    connection_id = await sent(w, profile_id, "ARCHITECT")
    ok(await architect.post(f"/api/v1/pro/connections/{connection_id}/accept", json={},
                            headers=pro_key()))  # fmt: skip
    services = ok(await w.family.get(f"{w.base}/services"))
    engagement_id = next(
        c["engagement"]["id"] for c in services["categories"] if c["code"] == "ARCHITECT"
    )
    view = ok(await w.family.post(
        f"{w.base}/design-requests",
        json={"kind": "LISTED_PROFESSIONAL", "engagement_id": engagement_id,
              "scope_note": "Full drawing set"},
        headers=key()), 201)  # fmt: skip
    request_id = view["design_requests"][-1]["id"]
    # The family does not add files to a professional's request; the architect does.
    assert view["design_requests"][-1]["can_provide"] is False
    listing = ok(await architect.get("/api/v1/pro/build-plan/design-requests"))
    assert [i["request"]["id"] for i in listing["items"]] == [request_id]
    created = ok(
        await architect.post(
            f"/api/v1/pro/build-plan/design-requests/{request_id}/sets", headers=pro_key()
        ),
        201,
    )
    set_id = created["items"][0]["request"]["sets"][-1]["id"]
    for drawing_class in CLASSES:
        file_id = await stored(database, architect_user, w.project_id, name=f"{drawing_class}.pdf")
        ok(await architect.post(
            f"/api/v1/pro/build-plan/drawing-sets/{set_id}/files",
            json={"file_id": file_id, "drawing_class": drawing_class, "title": drawing_class},
            headers=PRO_H))  # fmt: skip
    ok(
        await architect.post(
            f"/api/v1/pro/build-plan/drawing-sets/{set_id}/submit", headers=pro_key()
        )
    )
    # The family asks for changes; the set closes and a new one follows.
    changes = ok(await w.family.post(
        f"{w.base}/drawing-sets/{set_id}/decision",
        json={"approve": False, "note": "Bigger kitchen"}, headers=key()))  # fmt: skip
    assert changes["design_requests"][-1]["sets"][-1]["state"] == "CHANGES_REQUESTED"
    created = ok(
        await architect.post(
            f"/api/v1/pro/build-plan/design-requests/{request_id}/sets", headers=pro_key()
        ),
        201,
    )
    second = created["items"][0]["request"]["sets"][-1]["id"]
    file_id = await stored(database, architect_user, w.project_id, name="floor.pdf")
    ok(await architect.post(
        f"/api/v1/pro/build-plan/drawing-sets/{second}/files",
        json={"file_id": file_id, "drawing_class": "FLOOR_PLAN", "title": "Floor"},
        headers=PRO_H))  # fmt: skip
    ok(
        await architect.post(
            f"/api/v1/pro/build-plan/drawing-sets/{second}/submit", headers=pro_key()
        )
    )
    ok(await w.family.post(f"{w.base}/drawing-sets/{second}/decision", json={"approve": True},
                           headers=key()))  # fmt: skip
    # A checker holding an account records the check directly, without a separate note.
    checker = ok(await t.admin.client.post(
        "/api/v1/admin/drawing-checkers",
        json={"name": "Checker With Account", "qualification": "Civil engineer (TEST)",
              "user_id": str(t.issuer.user_id)},
        headers=ops_key()), 201)  # fmt: skip
    approved = ok(await t.issuer.client.post(
        f"/api/v1/ops/drawing-sets/{second}/check",
        json={"appointment_id": checker["id"], "approve": True, "note": "Checked."},
        headers=ops_key()))  # fmt: skip
    assert approved["design_requests"][-1]["sets"][-1]["state"] == "APPROVED"
    # Another listed professional sees none of it.
    stranger, _, _ = await listed_pro(
        database, client_for, make_user, sign_in, ("ARCHITECT",), name="Other Architect"
    )
    assert ok(await stranger.get("/api/v1/pro/build-plan/design-requests"))["items"] == []
    assert (await stranger.get(f"/api/v1/pro/build-plan/files/{file_id}/url")).status_code == 404
    assert (await architect.get(f"/api/v1/pro/build-plan/files/{file_id}/url")).status_code == 200


async def test_operations_upload_evidence_through_the_api_and_it_is_scanned_before_use(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    url = f"/api/v1/ops/projects/{t.project_id}/build-plan/files"
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    uploaded = await t.advisor.client.post(
        url, params={"purpose": "BUILD_PLAN_EVIDENCE", "file_name": "note.png"}, content=png,
        headers={**ops_key(), "Content-Type": "image/png"},
    )  # fmt: skip
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["state"] == "UPLOADED"  # AVAILABLE only after the worker's scan
    for purpose, mime in (("AI_CONCEPT", "image/png"), ("BUILD_PLAN_EVIDENCE", "text/plain")):
        refused = await t.advisor.client.post(
            url, params={"purpose": purpose, "file_name": "x"}, content=png,
            headers={**ops_key(), "Content-Type": mime},
        )  # fmt: skip
        assert refused.status_code == 422
    family = await t.world.family.post(
        url, params={"purpose": "BUILD_PLAN_EVIDENCE", "file_name": "x.png"}, content=png,
        headers={**key(), "Content-Type": "image/png"},
    )  # fmt: skip
    assert family.status_code in (401, 403, 404)


async def test_the_acceptance_statement_is_versioned_configuration(
    app: FastAPI, database: Database, worker: Run, client_for: ClientFactory,  # noqa: F811
    make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    t = await setup(app, database, client_for, make_user, sign_in, worker)
    listed = ok(await t.advisor.client.get("/api/v1/ops/acceptance-statements"))
    v1 = next(s for s in listed if s["version"] == 1)
    assert "PENDING FINAL CLIENT + LEGAL CONFIRMATION" in v1["note"]
    vid, _, _ = await full_version(database, t)
    await issued(t, vid)
    first = await accepted(database, t, vid)
    active = next(s for s in listed if s["status"] == "ACTIVE")
    assert first["acceptance"]["statement_version"] == active["version"]
    assert first["acceptance"]["statement"].startswith("I accept Build Plan version 1 for project")
    # Only ADMIN drafts; only the known placeholders are accepted.
    body = {"text": "Launch wording for $project_code version $version_no ($content_hash).",
            "note": "TEST launch wording"}  # fmt: skip
    forbidden = await t.advisor.client.post(
        "/api/v1/admin/acceptance-statements", json=body, headers=ops_key()
    )
    assert forbidden.status_code == 403
    bad = await t.admin.client.post(
        "/api/v1/admin/acceptance-statements",
        json={"text": "Accept $unknown", "note": "x"}, headers=ops_key(),
    )  # fmt: skip
    assert bad.status_code == 422
    draft = ok(
        await t.admin.client.post(
            "/api/v1/admin/acceptance-statements", json=body, headers=ops_key()
        ),
        201,
    )
    ok(
        await t.admin.client.post(
            f"/api/v1/admin/acceptance-statements/{draft['id']}/activate", headers=OPS_HEADERS
        )
    )
    try:
        v2 = ok(
            await t.advisor.client.post(
                f"/api/v1/ops/projects/{t.project_id}/build-plan/versions", headers=ops_key()
            ),
            201,
        )
        v2id = v2["snapshot"]["version"]["id"]
        await submitted(t.advisor.client, v2id)
        ok(await sign_all_by_document(database, t, v2id))
        await issued(t, v2id)
        second = await accepted(database, t, v2id)
        assert second["acceptance"]["statement_version"] == draft["version"]
        assert second["acceptance"]["statement"].startswith("Launch wording for ")
        # The earlier acceptance keeps the wording it confirmed.
        again = ok(await t.world.family.get(f"{t.world.base}/build-plan/versions/{vid}"))
        assert again["acceptance"]["statement"] == first["acceptance"]["statement"]
    finally:
        async with database.transaction() as session:  # reference data: restore version 1
            await session.execute(
                text("UPDATE acceptance_statements SET status = 'RETIRED' WHERE status = 'ACTIVE'")
            )
            await session.execute(
                text("UPDATE acceptance_statements SET status = 'ACTIVE' WHERE version = 1")
            )
