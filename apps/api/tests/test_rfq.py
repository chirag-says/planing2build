"""Slice 3.6 (SLICE3_6_READINESS section 0): the accepted Build Plan as the RFQ baseline and the
frozen pack, competing invitations within the limit, expiry and decline reasons, contractor
isolation with no internal rates and no competitor inference, quote completeness and server
amounts, immutable versions, withdrawal, validity and renewal, clarifications, review and
adjustment privacy, the neutral comparison and its deterministic PDF, one-time-code selection
with a versioned statement, engagement creation and reuse, the RFQ_SELECTION substantial-work
record (QD-02), N-02 under concurrency, package cancellation, baseline supersession, listing
loss, outside-contractor capture, document access, audit, invalid transitions and history."""

import asyncio
import json
import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError

from p2b.audit.models import AuditEvent
from p2b.billing.models import PackageServiceUsage
from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.errors import StateConflict
from p2b.core.vocabulary import Audience, InvitationState, QuoteVersionState, RfqState
from p2b.documents.models import DocumentAccessLog
from p2b.engagements.models import ProjectEngagement
from p2b.notifications.service import Kind, kinds_for
from p2b.rfq import comparison, pdf, quotes, rfqs
from p2b.rfq.common import INVITATION, QUOTE, REVIEW, RFQ
from p2b.rfq.models import QuoteLine, QuoteVersion, Rfq, RfqEvent, RfqInvitation
from tests.billing_support import key
from tests.buildplan_support import (
    Team,
    accepted,
    issued,
    ok,
    ops_key,
    pro_key,
    reason,
    sign_all_by_document,
    stored,
    submitted,
)
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.rfq_support import (
    accept,
    accepted_team,
    contractor,
    invitation_id,
    issue,
    keys_of,
    ops_view,
    publish,
    quote_body,
    request_rfq,
    requested,
    review,
    select_quote,
    submit,
    today_ist,
)
from tests.staff_support import OPS_HEADERS
from tests.test_billing import refund_request
from tests.test_engagements import Run, pro_post, sent

FORBIDDEN_FOR_CONTRACTORS = {
    "rate_card",
    "boq_total",
    "stage_totals",
    "adjustments",
    "review_state",
    "normalised_total",
    "comparison",
    "quotes_received",
    "invited",
    "basis_note",
    "rupee_impact",
}


Contractor = tuple[AsyncClient, str, uuid.UUID]


async def world(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn, run: Run,
) -> tuple[Team, str, Contractor, Contractor]:  # fmt: skip
    t, vid = await accepted_team(app, database, client_for, make_user, sign_in, run)
    a = await contractor(database, client_for, make_user, sign_in, "Alpha Builders")
    b = await contractor(database, client_for, make_user, sign_in, "Beta Constructions")
    return t, vid, a, b


async def rfq_db(database: Database, rfq_id: str) -> Rfq:
    async with database.transaction() as session:
        return await session.get_one(Rfq, uuid.UUID(rfq_id))


# --- the whole path ------------------------------------------------------------------------


async def test_accepted_build_plan_to_selection_with_competing_quotes(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    t, vid, (ca, pa, _), (cb, pb, _) = await world(
        app, database, client_for, make_user, sign_in, rfq_worker
    )
    w = t.world
    rfq_id = await requested(t, [pa, pb])
    draft = await ops_view(t, rfq_id)
    assert draft["state"] == "DRAFT"
    assert draft["manifest_sha256"] is None
    assert {i["state"] for i in draft["invitations"]} == {"PROPOSED"}
    # Nothing reaches a contractor before issue.
    assert ok(await ca.get("/api/v1/pro/rfq-invitations"))["items"] == []

    issued_rfq = await issue(t, rfq_id)
    assert issued_rfq["state"] == "ISSUED"
    manifest = (await rfq_db(database, rfq_id)).manifest
    assert manifest is not None
    assert manifest["build_plan_version_id"] == vid
    assert issued_rfq["manifest_sha256"] == rfqs.sha256(manifest)

    # A sees the brief only until accepting; then the frozen pack, never internal rates.
    ia = await invitation_id(ca)
    before = ok(await ca.get(f"/api/v1/pro/rfq-invitations/{ia}"))
    assert before["pack"] is None
    assert before["brief"]["build_plan_accepted"] is True
    assert "contact" not in json.dumps(before["brief"])
    after = await accept(ca, ia)
    pack = after["pack"]
    assert [q["line_no"] for q in pack["quantities"]] == [1, 2]
    raw = json.dumps(after)
    for forbidden in ('"rate"', '"amount"', "100.00", "10.50", "1670.00"):
        assert forbidden not in raw, forbidden
    assert not keys_of(after) & FORBIDDEN_FOR_CONTRACTORS
    ib = await invitation_id(cb)
    await accept(cb, ib)

    # Completeness: every line priced or excluded with a reason (422 names the line).
    incomplete = await submit(
        ca,
        ia,
        quote_body(("200.00", None))
        | {"lines": [{"line_no": 1, "rate": "200.00"}, {"line_no": 2}]},
    )
    assert incomplete.status_code == 422
    assert "lines.2" in incomplete.json()["error"]["details"]["fields"]
    # Server amounts: 12.5 x 200.00 + 40 x 15.00; an excluded line has no amount.
    out = ok(await submit(ca, ia, quote_body(("200.00", "15.00"))), 201)
    v1 = out["versions"][0]["quote"]
    assert v1["comparable_total"] == "3100.00"
    assert [x["amount"] for x in v1["lines"]] == ["2500.00", "600.00"]
    # A revision is a new version; the first is SUPERSEDED, never changed.
    out = ok(await submit(ca, ia, quote_body(("190.00", "15.00"))), 201)
    assert [v["state"] for v in out["versions"]] == ["SUPERSEDED", "SUBMITTED"]
    assert out["versions"][0]["quote"]["comparable_total"] == "3100.00"
    ok(await submit(cb, ib, quote_body(("150.00", None))), 201)

    # Before publication the homeowner sees status, never prices (QD-07).
    family = ok(await w.family.get(f"{w.base}/rfqs"))
    assert "comparable_total" not in json.dumps(family)
    assert "2975.00" not in json.dumps(family)
    statuses = {i["contractor_name"]: i["latest_quote"] for i in family["rfqs"][0]["invitations"]}
    assert statuses["Alpha Builders"]["version_no"] == 2

    view = await ops_view(t, rfq_id)
    qa = next(
        v
        for v in view["quote_versions"]
        if v["state"] == "SUBMITTED" and v["quote"]["comparable_total"] == "2975.00"
    )["quote"]["id"]
    qb = next(v for v in view["quote_versions"] if v["quote"]["lines"][1]["excluded"])["quote"][
        "id"
    ]
    nothing = await t.advisor.client.post(
        f"/api/v1/ops/rfqs/{rfq_id}/comparisons", headers=ops_key()
    )
    assert reason(nothing) == "NO_REVIEWED_QUOTES"
    await review(t, qa)
    await review(
        t,
        qb,
        [
            {
                "line_no": 2,
                "deviation_type": "EXCLUDED",
                "description": "Masonry excluded",
                "rupee_impact": "420.00",
                "basis_note": "Build Plan rate",
            }
        ],
    )
    published = await publish(t, rfq_id)
    cmp_ = published["comparisons"][0]
    assert cmp_["state"] == "PUBLISHED"
    assert cmp_["counts"] == {
        "invited": 2,
        "quotes_received": 2,
        "included": 2,
    }
    by_id = {q["quote_version_id"]: q for q in cmp_["quotes"]}
    assert by_id[qb]["normalised_total"] == "2295.00"  # 1875.00 as submitted + 420.00
    assert by_id[qb]["quote"]["comparable_total"] == "1875.00"
    assert not keys_of(cmp_) & {"rank", "score", "recommended", "best", "lowest"}

    # The homeowner now sees prices, in the comparison only; the PDF is logged.
    family = ok(await w.family.get(f"{w.base}/rfqs"))
    assert family["rfqs"][0]["comparison"]["quotes"]
    assert family["rfqs"][0]["can_select"] is True
    doc = await w.family.get(f"{w.base}/rfqs/{rfq_id}/comparisons/{cmp_['id']}/document")
    assert doc.status_code == 200, doc.text

    # The contractors never see the comparison or each other.
    for client, iid in ((ca, ia), (cb, ib)):
        mine = ok(await client.get(f"/api/v1/pro/rfq-invitations/{iid}"))
        assert not keys_of(mine) & FORBIDDEN_FOR_CONTRACTORS
    assert (await ca.get(f"/api/v1/pro/rfq-invitations/{ib}")).status_code == 404

    selected = await select_quote(database, t, rfq_id, qa)
    assert selected.status_code == 200, selected.text
    rfq = selected.json()["rfqs"][0]
    assert rfq["state"] == "CLOSED"
    assert rfq["comparison"]["state"] == "DECIDED"
    assert rfq["selection"]["contractor_name"] == "Alpha Builders"
    async with database.transaction() as session:
        states = dict(
            (await session.execute(select(QuoteVersion.id, QuoteVersion.state))).tuples().all()
        )
        engagement = (
            await session.scalars(
                select(ProjectEngagement).where(
                    ProjectEngagement.state == "ACTIVE",
                    ProjectEngagement.category_code == "CONTRACTOR",
                )
            )
        ).one()
        usage = set(await session.scalars(select(PackageServiceUsage.service)))
    assert states[uuid.UUID(qa)] == "SELECTED"
    assert states[uuid.UUID(qb)] == "NOT_SELECTED"
    assert engagement.origin == "RFQ_SELECTION"
    assert str(engagement.profile_id) == pa
    assert engagement.family_contact
    assert engagement.family_contact["name"] == "Meera Iyer"
    assert usage == {"RFQ_SELECTION"}  # QD-02; nothing else from this slice

    # The winner sees the family's contact through its engagement; the loser sees its outcome.
    won = ok(await ca.get(f"/api/v1/pro/rfq-invitations/{ia}"))
    assert won["outcome"] == "SELECTED"
    assert won["engagement_id"] == str(engagement.id)
    eng = ok(await ca.get(f"/api/v1/pro/engagements/{engagement.id}"))
    assert eng["family_contact"]["phone"] == "+91 98765 43210"
    assert eng["origin"] == "RFQ_SELECTION"
    lost = ok(await cb.get(f"/api/v1/pro/rfq-invitations/{ib}"))
    assert lost["outcome"] == "NOT_SELECTED"
    assert lost["engagement_id"] is None
    assert (await cb.get(f"/api/v1/pro/engagements/{engagement.id}")).status_code == 404
    # The homeowner sees the contractor's contact on the engagement.
    services = ok(await w.family.get(f"{w.base}/services"))
    row = next(c for c in services["categories"] if c["code"] == "CONTRACTOR")
    assert row["engagement"]["professional_contact"]["phone"] == "+91 90000 00001"

    mailbox = await rfq_worker()
    subjects = [m.subject for m in mailbox.sent]
    assert "Your quote was selected" in subjects
    not_selected = next(m for m in mailbox.sent if m.subject == "Your quote was not selected")
    assert "Alpha" not in not_selected.text
    assert "2975" not in not_selected.text
    assert "Your contractor quote comparison is ready" in subjects
    # Selection is immutable: a second attempt is refused.
    again = await w.family.post(
        f"{w.base}/rfqs/{rfq_id}/selection-code", json={"quote_version_id": qb}, headers=key()
    )
    assert again.status_code == 409


async def test_an_rfq_needs_the_accepted_build_plan_and_names_it(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    from tests.buildplan_support import full_version, team

    t = await team(app, database, client_for, make_user, sign_in, rfq_worker)
    _, pa, _ = await contractor(database, client_for, make_user, sign_in, "Alpha")
    assert reason(await request_rfq(t, [pa])) == "NO_ACCEPTED_VERSION"
    vid, _, _ = await full_version(database, t)
    await issued(t, vid)
    assert reason(await request_rfq(t, [pa])) == "NO_ACCEPTED_VERSION"  # issued is not enough
    await accepted(database, t, vid)
    rfq_id = await requested(t, [pa])
    assert reason(await request_rfq(t, [pa])) == "OPEN_RFQ"
    assert str((await rfq_db(database, rfq_id)).build_plan_version_id) == vid
    # Issue needs a deadline in the future.
    refused = await t.advisor.client.post(f"/api/v1/ops/rfqs/{rfq_id}/issue", headers=ops_key())
    assert reason(refused) == "NO_DEADLINE"


async def test_recipients_limit_eligibility_and_the_engaged_category(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    t, _, (_, pa, _), (_, pb, _) = await world(
        app, database, client_for, make_user, sign_in, rfq_worker
    )
    pc = (await contractor(database, client_for, make_user, sign_in, "Gamma"))[1]
    pd = (await contractor(database, client_for, make_user, sign_in, "Delta"))[1]
    far = (await contractor(database, client_for, make_user, sign_in, "Far", at=(19.0, 73.0)))[1]
    hidden = (await contractor(database, client_for, make_user, sign_in, "Hid", hidden=True))[1]
    assert get_settings().rfq_max_recipients == 3
    assert reason(await request_rfq(t, [pa, pb, pc, pd])) == "LIMIT"
    assert reason(await request_rfq(t, [far])) == "OUTSIDE_AREA"
    assert reason(await request_rfq(t, [hidden])) == "NOT_LISTED"
    rfq_id = await requested(t, [pa, pb, pc])
    introduce = await t.advisor.client.post(
        f"/api/v1/ops/rfqs/{rfq_id}/invitations",
        json={"profile_id": pd, "reason": "Capacity"},
        headers=ops_key(),
    )
    assert reason(introduce) == "LIMIT"
    no_reason = await t.advisor.client.post(
        f"/api/v1/ops/rfqs/{rfq_id}/invitations", json={"profile_id": pd}, headers=ops_key()
    )
    assert no_reason.status_code == 422
    # Removing one frees a slot; the introduction is recorded with its reason.
    view = await ops_view(t, rfq_id)
    remove = next(i["id"] for i in view["invitations"] if i["profile_id"] == pc)
    ok(
        await t.advisor.client.post(
            f"/api/v1/ops/rfq-invitations/{remove}/withdraw",
            json={"reason": "Owner changed mind"},
            headers=ops_key(),
        )
    )
    view = ok(
        await t.advisor.client.post(
            f"/api/v1/ops/rfqs/{rfq_id}/invitations",
            json={"profile_id": pd, "reason": "Capacity"},
            headers=ops_key(),
        )
    )
    introduced = next(i for i in view["invitations"] if i["profile_id"] == pd)
    assert introduced["source"] == "INTRODUCED"
    assert introduced["introduced_reason"] == "Capacity"
    removed = next(i for i in view["invitations"] if i["profile_id"] == pc)
    assert removed["withdraw_reason"] == "REMOVED"
    ok(await t.world.family.post(f"{t.world.base}/rfqs/{rfq_id}/cancel", json={}, headers=key()))

    # QD-13: with an ACTIVE contractor engagement, only that contractor may quote.
    ce, pe, _ = await contractor(database, client_for, make_user, sign_in, "Engaged Co")
    connection = await sent(t.world, pe, "CONTRACTOR")
    assert (await pro_post(ce, connection, "accept")).status_code == 200
    assert reason(await request_rfq(t, [pa])) == "ENGAGED"
    rfq_id = await requested(t, [])
    view = await ops_view(t, rfq_id)
    assert [(i["profile_id"], i["source"]) for i in view["invitations"]] == [(pe, "ENGAGED")]
    blocked = await t.advisor.client.post(
        f"/api/v1/ops/rfqs/{rfq_id}/invitations",
        json={"profile_id": pa, "reason": "x"},
        headers=ops_key(),
    )
    assert reason(blocked) == "ENGAGED"


async def test_invitations_expire_and_declines_need_a_reason(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    t, _, (ca, pa, _), (cb, pb, _) = await world(
        app, database, client_for, make_user, sign_in, rfq_worker
    )
    rfq_id = await requested(t, [pa, pb])
    await issue(t, rfq_id)
    ia, ib = await invitation_id(ca), await invitation_id(cb)
    other = await ca.post(
        f"/api/v1/pro/rfq-invitations/{ia}/decline", json={"reason": "OTHER"}, headers=pro_key()
    )
    assert other.status_code == 422
    declined = ok(
        await ca.post(
            f"/api/v1/pro/rfq-invitations/{ia}/decline",
            json={"reason": "SCHEDULE_MISMATCH"},
            headers=pro_key(),
        )
    )
    assert declined["state"] == "DECLINED"
    async with database.transaction() as session:
        await session.execute(
            text("ALTER TABLE rfq_invitations DISABLE TRIGGER rfq_invitations_lifecycle_only")
        )
        await session.execute(
            update(RfqInvitation)
            .where(RfqInvitation.id == uuid.UUID(ib))
            .values(respond_by=func.now() - text("interval '1 minute'"))
        )
        await session.execute(
            text("ALTER TABLE rfq_invitations ENABLE TRIGGER rfq_invitations_lifecycle_only")
        )
    async with database.transaction() as session:
        assert await rfqs.expire_due(session) == 1
    late = await cb.post(f"/api/v1/pro/rfq-invitations/{ib}/accept", json={}, headers=pro_key())
    assert late.status_code == 409
    view = await ops_view(t, rfq_id)
    assert {i["state"] for i in view["invitations"]} == {"DECLINED", "EXPIRED"}
    assert (
        next(i for i in view["invitations"] if i["state"] == "DECLINED")["decline_reason"]
        == "SCHEDULE_MISMATCH"
    )


async def test_quote_versions_are_immutable_withdrawable_and_expire_into_renewal(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    t, _, (ca, pa, _), _ = await world(app, database, client_for, make_user, sign_in, rfq_worker)
    rfq_id = await requested(t, [pa])
    await issue(t, rfq_id)
    ia = await invitation_id(ca)
    await accept(ca, ia)
    ok(await submit(ca, ia, quote_body()), 201)
    async with database.transaction() as session:
        qv = (await session.scalars(select(QuoteVersion))).one()
        line_id = (await session.scalars(select(QuoteLine.id))).first()
    for statement in (
        update(QuoteVersion).where(QuoteVersion.id == qv.id).values(comparable_total=1),
        update(QuoteLine).where(QuoteLine.id == line_id).values(rate=1),
    ):
        with pytest.raises(DBAPIError):
            async with database.transaction() as session:
                await session.execute(statement)
    # Withdraw with a reason, then submit again before the deadline.
    out = ok(
        await ca.post(
            f"/api/v1/pro/rfq-invitations/{ia}/quote/withdraw",
            json={"reason": "Pricing error"},
            headers=pro_key(),
        )
    )
    assert out["versions"][-1]["state"] == "WITHDRAWN"
    ok(await submit(ca, ia, quote_body()), 201)
    # A validity that ended: the job expires it; selection is impossible; a renewal keeps
    # the content and changes only the dates.
    async with database.transaction() as session:
        await session.execute(
            text("ALTER TABLE quote_versions DISABLE TRIGGER quote_versions_lifecycle_only")
        )
        await session.execute(
            update(QuoteVersion)
            .where(QuoteVersion.state == "SUBMITTED")
            .values(
                valid_from=today_ist() - timedelta(days=40),
                valid_to=today_ist() - timedelta(days=1),
            )
        )
        await session.execute(
            text("ALTER TABLE quote_versions ENABLE TRIGGER quote_versions_lifecycle_only")
        )
    async with database.transaction() as session:
        assert await quotes.expire_due(session) == 1
    state = ok(await ca.get(f"/api/v1/pro/rfq-invitations/{ia}"))
    assert state["versions"][-1]["state"] == "EXPIRED"
    assert state["can_renew"]
    today = today_ist()
    renewed = ok(
        await ca.post(
            f"/api/v1/pro/rfq-invitations/{ia}/quote/renew",
            json={
                "valid_from": today.isoformat(),
                "valid_to": (today + timedelta(days=20)).isoformat(),
            },
            headers=pro_key(),
        )
    )
    last = renewed["versions"][-1]
    assert last["state"] == "SUBMITTED"
    assert last["quote"]["kind"] == "RENEWAL"
    assert last["quote"]["comparable_total"] == renewed["versions"][-2]["quote"]["comparable_total"]
    # Late submissions are refused once the deadline passed; a renewal is not a submission.
    async with database.transaction() as session:
        await session.execute(text("ALTER TABLE rfqs DISABLE TRIGGER rfqs_lifecycle_only"))
        await session.execute(
            update(Rfq).values(quotes_due_at=func.now() - text("interval '1 hour'"))
        )
        await session.execute(text("ALTER TABLE rfqs ENABLE TRIGGER rfqs_lifecycle_only"))
    assert reason(await submit(ca, ia, quote_body())) == "DEADLINE_PASSED"
    # The deadline notice goes to operations once.
    async with database.transaction() as session:
        assert await rfqs.notice_deadlines(session) == 1
    async with database.transaction() as session:
        assert await rfqs.notice_deadlines(session) == 0


async def test_clarifications_review_states_and_adjustment_privacy(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    t, _, (ca, pa, _), (cb, pb, _) = await world(
        app, database, client_for, make_user, sign_in, rfq_worker
    )
    rfq_id = await requested(t, [pa, pb])
    await issue(t, rfq_id)
    ia, ib = await invitation_id(ca), await invitation_id(cb)
    await accept(ca, ia)
    await accept(cb, ib)
    ok(await submit(ca, ia, quote_body()), 201)
    view = await ops_view(t, rfq_id)
    qa = view["quote_versions"][0]["quote"]["id"]
    inv_a = view["quote_versions"][0]["invitation_id"]
    # Operations ask A about its quote: NEEDS_CLARIFICATION until answered.
    view = ok(
        await t.advisor.client.post(
            f"/api/v1/ops/rfqs/{rfq_id}/clarifications",
            json={"invitation_id": inv_a, "quote_version_id": qa, "question": "Is plaster 15 mm?"},
            headers=ops_key(),
        )
    )
    assert view["quote_versions"][0]["review_state"] == "NEEDS_CLARIFICATION"
    question = view["clarifications"][0]["id"]
    seen_by_b = ok(await cb.get(f"/api/v1/pro/rfq-invitations/{ib}"))
    assert seen_by_b["clarifications"] == []
    ok(
        await ca.post(
            f"/api/v1/pro/rfq-invitations/{ia}/clarifications/{question}/answer",
            json={"answer": "Yes, 15 mm."},
            headers=pro_key(),
        )
    )
    assert (await ops_view(t, rfq_id))["quote_versions"][0]["review_state"] == "PENDING"
    # B asks; the answer is shared with everyone without B's identity.
    ok(
        await cb.post(
            f"/api/v1/pro/rfq-invitations/{ib}/clarifications",
            json={"question": "Is the soil report available?"},
            headers=pro_key(),
        )
    )
    asked = next(
        c
        for c in (await ops_view(t, rfq_id))["clarifications"]
        if c["direction"] == "CONTRACTOR_ASKS"
    )
    ok(
        await t.advisor.client.post(
            f"/api/v1/ops/rfq-clarifications/{asked['id']}/answer",
            json={"answer": "Yes, in the pack assumptions.", "shared_with_all": True},
            headers=ops_key(),
        )
    )
    for_a = ok(await ca.get(f"/api/v1/pro/rfq-invitations/{ia}"))["clarifications"]
    shared = [c for c in for_a if not c["yours"]]
    assert len(shared) == 1
    assert shared[0]["answer"] == "Yes, in the pack assumptions."
    assert "invitation_id" not in shared[0]
    # Adjustments stay internal and freeze once REVIEWED (service and database).
    await quotes_reviewed(t, qa)
    frozen = await t.advisor.client.put(
        f"/api/v1/ops/quote-versions/{qa}/adjustments",
        json={"adjustments": []},
        headers=OPS_HEADERS,
    )
    assert frozen.status_code == 409
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("DELETE FROM quote_adjustments"))
    mine = ok(await ca.get(f"/api/v1/pro/rfq-invitations/{ia}"))
    assert "Plaster" not in json.dumps(mine)
    assert not keys_of(mine) & FORBIDDEN_FOR_CONTRACTORS


async def quotes_reviewed(t: Any, qa: str) -> None:
    await review(
        t,
        qa,
        [
            {
                "spec_line_code": "C01",
                "deviation_type": "GRADE",
                "description": "Plaster thickness",
                "rupee_impact": "-50.00",
            }
        ],
    )


async def test_the_comparison_is_neutral_versioned_and_its_pdf_deterministic(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    ids = [uuid.uuid4() for _ in range(5)]
    orders = {tuple(comparison.neutral_order(f"seed{i}", ids)) for i in range(20)}
    assert len(orders) > 1  # the seed decides
    assert comparison.neutral_order("x", ids) == comparison.neutral_order("x", list(reversed(ids)))
    t, _, (ca, pa, _), _ = await world(app, database, client_for, make_user, sign_in, rfq_worker)
    rfq_id = await requested(t, [pa])
    await issue(t, rfq_id)
    ia = await invitation_id(ca)
    await accept(ca, ia)
    ok(await submit(ca, ia, quote_body()), 201)
    qa = (await ops_view(t, rfq_id))["quote_versions"][0]["quote"]["id"]
    await review(t, qa)
    first = (await publish(t, rfq_id))["comparisons"][0]
    assert first["counts"]["included"] == 1  # one quote is enough (QD-24)
    # A new version after publication: the published one is never edited.
    ok(await submit(ca, ia, quote_body(("210.00", "15.00"))), 201)
    w = t.world
    stale = await w.family.post(
        f"{w.base}/rfqs/{rfq_id}/selection-code", json={"quote_version_id": qa}, headers=key()
    )
    assert reason(stale) == "STALE"
    qa2 = (await ops_view(t, rfq_id))["quote_versions"][-1]["quote"]["id"]
    await review(t, qa2)
    view = await publish(t, rfq_id)
    assert [c["state"] for c in view["comparisons"]] == ["SUPERSEDED", "PUBLISHED"]
    assert view["comparisons"][0]["snapshot_sha256"] == first["snapshot_sha256"]
    async with database.transaction() as session:
        from p2b.rfq.models import Comparison

        row = (await session.scalars(select(Comparison).where(Comparison.version_no == 2))).one()
    one = pdf.render(get_settings(), row.snapshot, version_no=2, published_at=row.published_at)
    two = pdf.render(get_settings(), row.snapshot, version_no=2, published_at=row.published_at)
    assert one == two
    assert one.startswith(b"%PDF")


async def test_selection_needs_the_code_and_the_current_statement(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    try:
        t, _, (ca, pa, _), _ = await world(
            app, database, client_for, make_user, sign_in, rfq_worker
        )
        w = t.world
        rfq_id = await requested(t, [pa])
        await issue(t, rfq_id)
        ia = await invitation_id(ca)
        await accept(ca, ia)
        ok(await submit(ca, ia, quote_body()), 201)
        qa = (await ops_view(t, rfq_id))["quote_versions"][0]["quote"]["id"]
        await review(t, qa)
        await publish(t, rfq_id)
        challenge = ok(
            await w.family.post(
                f"{w.base}/rfqs/{rfq_id}/selection-code",
                json={"quote_version_id": qa},
                headers=key(),
            )
        )
        assert "not a party to the construction contract" in challenge["statement_text"]
        assert "Alpha Builders & Co" in challenge["statement_text"]
        wrong = await w.family.post(
            f"{w.base}/rfqs/{rfq_id}/select",
            json={
                "quote_version_id": qa,
                "challenge_id": challenge["challenge_id"],
                "code": "000000",
                "statement_id": challenge["statement_id"],
                "contact_name": "M",
                "contact_phone": "+91 98765 43210",
            },
            headers=key(),
        )
        assert wrong.status_code in (400, 409)
        # A new statement version: a code confirmed against the old one is refused.
        admin = t.admin.client
        bad = await admin.post(
            "/api/v1/admin/selection-statements",
            json={"text": "I pick $who.", "note": "x"},
            headers=ops_key(),
        )
        assert bad.status_code == 422
        draft = ok(
            await admin.post(
                "/api/v1/admin/selection-statements",
                json={
                    "text": "Version $version_no from $contractor for $project_code. "
                    "Plan2Build is not a party.",
                    "note": "TEST wording",
                },
                headers=ops_key(),
            ),
            201,
        )
        statements = ok(
            await admin.post(
                f"/api/v1/admin/selection-statements/{draft['id']}/activate", headers=OPS_HEADERS
            )
        )
        active = [x for x in statements if x["status"] == "ACTIVE"]
        assert [x["id"] for x in active] == [draft["id"]]
        assert next(x for x in statements if x["version"] == 1)["status"] == "RETIRED"
        from tests.buildplan_support import code_of

        code = await code_of(database, challenge["challenge_id"])
        changed = await w.family.post(
            f"{w.base}/rfqs/{rfq_id}/select",
            json={
                "quote_version_id": qa,
                "challenge_id": challenge["challenge_id"],
                "code": code,
                "statement_id": challenge["statement_id"],
                "contact_name": "M",
                "contact_phone": "+91 98765 43210",
            },
            headers=key(),
        )
        assert reason(changed) == "STATEMENT_CHANGED"
        done = await select_quote(database, t, rfq_id, qa)
        assert done.status_code == 200, done.text
        assert done.json()["rfqs"][0]["selection"]["statement_text"].startswith("Version 1 from")
        # The household reads but never selects; another family sees nothing.
        assert (await w.family.get(f"{w.base}/rfqs/{rfq_id}")).status_code == 200
    finally:
        async with database.transaction() as session:  # reference data: restore version 1
            await session.execute(
                text("UPDATE selection_statements SET status = 'RETIRED' WHERE status = 'ACTIVE'")
            )
            await session.execute(
                text("UPDATE selection_statements SET status = 'ACTIVE' WHERE version = 1")
            )


async def test_n02_holds_when_a_selection_races_a_connection_acceptance(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    t, _, (ca, pa, _), _ = await world(app, database, client_for, make_user, sign_in, rfq_worker)
    rfq_id = await requested(t, [pa])
    await issue(t, rfq_id)
    ia = await invitation_id(ca)
    await accept(ca, ia)
    ok(await submit(ca, ia, quote_body()), 201)
    qa = (await ops_view(t, rfq_id))["quote_versions"][0]["quote"]["id"]
    await review(t, qa)
    await publish(t, rfq_id)
    cc, pc, _ = await contractor(database, client_for, make_user, sign_in, "Racer")
    connection = await sent(t.world, pc, "CONTRACTOR")
    selection, acceptance = await asyncio.gather(
        select_quote(database, t, rfq_id, qa), pro_post(cc, connection, "accept")
    )
    assert sorted([selection.status_code, acceptance.status_code]) == [200, 409], (
        selection.text,
        acceptance.text,
    )
    async with database.transaction() as session:
        active = await session.scalar(
            select(func.count())
            .select_from(ProjectEngagement)
            .where(
                ProjectEngagement.category_code == "CONTRACTOR", ProjectEngagement.state == "ACTIVE"
            )
        )
    assert active == 1


async def test_a_refund_cancels_the_open_rfq_and_keeps_its_history(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    t, _, (ca, pa, _), _ = await world(app, database, client_for, make_user, sign_in, rfq_worker)
    w = t.world
    rfq_id = await requested(t, [pa])
    await issue(t, rfq_id)
    ia = await invitation_id(ca)
    await accept(ca, ia)
    ok(await submit(ca, ia, quote_body()), 201)
    request_id = await refund_request(w.family, w.order["order_id"])
    refunded = await t.issuer.client.post(
        f"/api/v1/ops/billing/refund-requests/{request_id}/approve",
        json={"amount": w.order["total"], "ends_package": True, "reason": "Refund agreed."},
        headers=ops_key(),
    )
    assert refunded.status_code == 200, refunded.text
    await rfq_worker()
    rfq = await rfq_db(database, rfq_id)
    assert (rfq.state, rfq.cancel_reason) == ("CANCELLED", "PACKAGE_ENDED")
    assert reason(await submit(ca, ia, quote_body())) == "RFQ_CLOSED"
    history = ok(await ca.get(f"/api/v1/pro/rfq-invitations/{ia}"))
    assert history["versions"][0]["state"] == "SUBMITTED"
    assert history["pack"] is None
    assert reason(await request_rfq(t, [pa])) == "PACKAGE_REQUIRED"
    async with database.transaction() as session:
        usage = list(await session.scalars(select(PackageServiceUsage.service)))
    assert usage == []  # no substantial work before a selection


async def test_a_newer_accepted_build_plan_cancels_the_open_rfq(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    t, vid, (_ca, pa, _), _ = await world(app, database, client_for, make_user, sign_in, rfq_worker)
    rfq_id = await requested(t, [pa])
    await issue(t, rfq_id)
    frozen = (await rfq_db(database, rfq_id)).manifest_sha256
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
    await rfq_worker()
    assert (await rfq_db(database, rfq_id)).state == "ISSUED"  # issue alone changes nothing
    await accepted(database, t, v2id)
    await rfq_worker()
    rfq = await rfq_db(database, rfq_id)
    assert (rfq.state, rfq.cancel_reason, rfq.manifest_sha256) == (
        "CANCELLED",
        "BASELINE_SUPERSEDED",
        frozen,
    )
    assert str(rfq.build_plan_version_id) == vid
    new_id = await requested(t, [pa])
    assert str((await rfq_db(database, new_id)).build_plan_version_id) == v2id


async def test_a_contractor_leaving_listed_loses_invitations_and_cannot_be_selected(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    t, _, (ca, pa, _), (cb, pb, _) = await world(
        app, database, client_for, make_user, sign_in, rfq_worker
    )
    rfq_id = await requested(t, [pa, pb])
    await issue(t, rfq_id)
    ia = await invitation_id(ca)
    assert ok(await cb.get("/api/v1/pro/rfq-invitations"))["items"][0]["state"] == "SENT"
    await accept(ca, ia)
    ok(await submit(ca, ia, quote_body()), 201)
    qa = (await ops_view(t, rfq_id))["quote_versions"][0]["quote"]["id"]
    await review(t, qa)
    await publish(t, rfq_id)
    async with database.transaction() as session:
        for profile in (pa, pb):
            await session.execute(
                text(
                    "UPDATE professional_categories SET listing_state = 'SUSPENDED' "
                    "WHERE profile_id = :p"
                ),
                {"p": uuid.UUID(profile)},
            )
        await rfqs.withdraw_for_profile(session, uuid.UUID(pb))
    view = await ops_view(t, rfq_id)
    states = {i["profile_id"]: (i["state"], i["withdraw_reason"]) for i in view["invitations"]}
    assert states[pb] == ("WITHDRAWN", "NOT_LISTED")
    assert states[pa] == ("ACCEPTED", None)
    w = t.world
    refused = await w.family.post(
        f"{w.base}/rfqs/{rfq_id}/selection-code", json={"quote_version_id": qa}, headers=key()
    )
    assert reason(refused) == "NOT_LISTED"


async def test_the_familys_outside_contractor_quotes_through_staff_capture(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    t, _ = await accepted_team(app, database, client_for, make_user, sign_in, rfq_worker)
    w = t.world
    ok(
        await w.family.post(
            f"{w.base}/engagements",
            json={"category": "CONTRACTOR", "name": "Own Builder"},
            headers=key(),
        ),
        201,
    )
    rfq_id = await requested(t, [])
    view = await issue(t, rfq_id)
    outside = view["invitations"][0]
    assert (outside["party"], outside["state"], outside["source"]) == (
        "OUTSIDE",
        "ACCEPTED",
        "ENGAGED",
    )
    evidence = await stored(database, t.advisor.user_id, t.project_id, "QUOTE_ATTACHMENT", "q.pdf")
    no_evidence = await t.advisor.client.post(
        f"/api/v1/ops/rfq-invitations/{outside['id']}/capture",
        json=quote_body() | {"evidence_file_id": str(uuid.uuid4())},
        headers=ops_key(),
    )
    assert no_evidence.status_code == 422
    view = ok(
        await t.advisor.client.post(
            f"/api/v1/ops/rfq-invitations/{outside['id']}/capture",
            json=quote_body() | {"evidence_file_id": evidence},
            headers=ops_key(),
        )
    )
    qv = view["quote_versions"][0]
    assert qv["quote"]["captured_by_staff"]
    assert qv["evidence_file_id"] == evidence
    await review(t, qv["quote"]["id"])
    await publish(t, rfq_id)
    selected = await select_quote(database, t, rfq_id, qv["quote"]["id"])
    assert selected.status_code == 200, selected.text
    async with database.transaction() as session:
        engagements = list(
            await session.scalars(
                select(ProjectEngagement).where(ProjectEngagement.category_code == "CONTRACTOR")
            )
        )
        usage = set(await session.scalars(select(PackageServiceUsage.service)))
    assert len(engagements) == 1
    assert engagements[0].origin == "OUTSIDE"
    assert usage == {"RFQ_SELECTION"}
    assert selected.json()["rfqs"][0]["selection"]["contractor_name"] == "Own Builder"


async def test_isolation_document_access_audit_and_transition_tables(
    app: FastAPI,
    database: Database,
    rfq_worker: Run,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    t, _, (ca, pa, _), (cb, pb, _) = await world(
        app, database, client_for, make_user, sign_in, rfq_worker
    )
    rfq_id = await requested(t, [pa, pb])
    await issue(t, rfq_id)
    ia, ib = await invitation_id(ca), await invitation_id(cb)
    await accept(ca, ia)
    pack = ok(await ca.get(f"/api/v1/pro/rfq-invitations/{ia}"))["pack"]
    drawing = pack["drawings"][0]["file_id"]
    # A drawing link only for an accepted invitation, logged; B has not accepted.
    assert (
        await ca.get(f"/api/v1/pro/rfq-invitations/{ia}/drawings/{drawing}/url")
    ).status_code == 200
    assert (
        await cb.get(f"/api/v1/pro/rfq-invitations/{ib}/drawings/{drawing}/url")
    ).status_code == 404
    assert (
        await cb.get(f"/api/v1/pro/rfq-invitations/{ia}/drawings/{drawing}/url")
    ).status_code == 404
    async with database.transaction() as session:
        logged = await session.scalar(
            select(func.count())
            .select_from(DocumentAccessLog)
            .where(DocumentAccessLog.file_id == uuid.UUID(drawing))
        )
    assert logged == 1
    # Foreign resources: another family, an unknown invitation, the ops routes for a contractor.
    other_family = client_for(Audience.IHB)
    stranger = await make_user(Audience.IHB)
    await sign_in(other_family, stranger, Audience.IHB)
    assert (await other_family.get(f"/api/v1/projects/{t.project_id}/rfqs")).status_code == 404
    assert (await ca.get(f"/api/v1/pro/rfq-invitations/{uuid.uuid4()}")).status_code == 404
    assert (await ca.get(f"/api/v1/ops/rfqs/{rfq_id}")).status_code in (401, 403, 404)
    # Every transition is audited and in the history.
    async with database.transaction() as session:
        audited = await session.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.action.like("rfq_%"))
        )
        events = await session.scalar(select(func.count()).select_from(RfqEvent))
    assert audited
    assert audited == events
    # Disallowed transitions are refused by the tables.
    for table, current, trigger in (
        (RFQ, RfqState.CLOSED, "cancel"),
        (RFQ, RfqState.DRAFT, "select"),
        (INVITATION, InvitationState.DECLINED, "accept"),
        (INVITATION, InvitationState.EXPIRED, "withdraw"),
        (QUOTE, QuoteVersionState.SELECTED, "withdraw"),
        (QUOTE, QuoteVersionState.WITHDRAWN, "select"),
        (REVIEW, None, "review"),
    ):
        with pytest.raises(StateConflict):
            table.target(current, trigger)  # type: ignore[arg-type]
    # History rows are append-only.
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("DELETE FROM rfq_events"))


def test_rfq_notices_map_to_their_emails() -> None:
    assert kinds_for("rfq.contractor_notice", {"notice": "NOT_SELECTED"}) == [
        Kind.PRO_QUOTE_NOT_SELECTED
    ]
    assert kinds_for("rfq.family_notice", {"notice": "COMPARISON_PUBLISHED"}) == [
        Kind.FAMILY_COMPARISON_PUBLISHED
    ]
    assert kinds_for("rfq.ops_notice", {"notice": "UNKNOWN"}) == []
