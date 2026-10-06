"""Helpers for the Slice 3.6 tests: a project with an ACCEPTED Build Plan and the package, listed
contractors, the worker with the rfq subscribers, and the steps of the RFQ path through the API
(request, deadline, issue, accept, quote, review, publish, select)."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from httpx import AsyncClient, Response

from p2b.core.db import Database
from tests.billing_support import key
from tests.buildplan_support import (
    Team,
    accepted,
    code_of,
    full_version,
    issued,
    ok,
    ops_key,
    pro_key,
    team,
)
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.staff_support import OPS_HEADERS
from tests.test_engagements import Run, give_email, listed_pro


def today_ist() -> date:
    """Quote validity is read as a calendar date in Raipur."""
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


CONTACT = {"contact_name": "Meera Iyer", "contact_phone": "+91 98765 43210"}


async def accepted_team(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn, run: Run,
) -> tuple[Team, str]:  # fmt: skip
    """An eligible project with the package and an ACCEPTED Build Plan version (two quantity
    lines: 12.5 cum and 40 sqm)."""
    t = await team(app, database, client_for, make_user, sign_in, run)
    vid, _, _ = await full_version(database, t)
    await issued(t, vid)
    await accepted(database, t, vid)
    return t, vid


async def contractor(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
    name: str, **kwargs: Any,
) -> tuple[AsyncClient, str, uuid.UUID]:  # fmt: skip
    client, profile_id, user_id = await listed_pro(
        database, client_for, make_user, sign_in, ("CONTRACTOR",), name=name, **kwargs
    )
    await give_email(database, user_id, f"c-{user_id.hex}@example.in", "pro")
    return client, profile_id, user_id


async def request_rfq(t: Team, profile_ids: list[str]) -> Response:
    w = t.world
    return await w.family.post(f"{w.base}/rfqs", json={"profile_ids": profile_ids}, headers=key())


async def requested(t: Team, profile_ids: list[str]) -> str:
    body = ok(await request_rfq(t, profile_ids), 201)
    return str(body["rfqs"][0]["id"])


def due(days: int = 7) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


async def issue(t: Team, rfq_id: str) -> dict[str, Any]:
    c = t.advisor.client
    ok(await c.put(f"/api/v1/ops/rfqs/{rfq_id}/deadline", json={"quotes_due_at": due()},
                   headers=OPS_HEADERS))  # fmt: skip
    out: dict[str, Any] = ok(await c.post(f"/api/v1/ops/rfqs/{rfq_id}/issue", headers=ops_key()))
    return out


async def invitation_id(client: AsyncClient) -> str:
    items = ok(await client.get("/api/v1/pro/rfq-invitations"))["items"]
    return str(items[0]["id"])


async def accept(client: AsyncClient, iid: str) -> dict[str, Any]:
    out: dict[str, Any] = ok(
        await client.post(
            f"/api/v1/pro/rfq-invitations/{iid}/accept", json={"phone": "+91 90000 00001"},
            headers=pro_key(),
        )
    )  # fmt: skip
    return out


def quote_body(
    rates: tuple[str | None, str | None] = ("200.00", "15.00"), **extra: Any
) -> dict[str, Any]:
    lines = []
    for n, rate in enumerate(rates, 1):
        if rate is None:
            lines.append({"line_no": n, "excluded": True, "exclusion_reason": "Not in our scope"})
        else:
            lines.append({"line_no": n, "rate": rate})
    today = today_ist()
    body = {
        "lines": lines, "valid_from": today.isoformat(),
        "valid_to": (today + timedelta(days=30)).isoformat(), "tax_treatment": "EXCLUSIVE",
        "duration_days": 240, "payment_terms": "Stage-wise, agreed with the homeowner.",
        "warranty": "One year on workmanship.", "exclusions": ["Electricity connection"],
    }  # fmt: skip
    body.update(extra)
    return body


async def submit(client: AsyncClient, iid: str, body: dict[str, Any]) -> Response:
    return await client.post(
        f"/api/v1/pro/rfq-invitations/{iid}/quotes", json=body, headers=pro_key()
    )


async def ops_view(t: Team, rfq_id: str) -> dict[str, Any]:
    out: dict[str, Any] = ok(await t.advisor.client.get(f"/api/v1/ops/rfqs/{rfq_id}"))
    return out


async def current_version(t: Team, rfq_id: str, profile_id: str) -> str:
    view = await ops_view(t, rfq_id)
    inv = next(i["id"] for i in view["invitations"] if i["profile_id"] == profile_id)
    versions = [v for v in view["quote_versions"] if v["invitation_id"] == inv]
    return str(versions[-1]["quote"]["id"])


async def review(t: Team, qv_id: str, adjustments: list[dict[str, Any]] | None = None) -> None:
    c = t.advisor.client
    ok(await c.put(f"/api/v1/ops/quote-versions/{qv_id}/adjustments",
                   json={"adjustments": adjustments or []}, headers=OPS_HEADERS))  # fmt: skip
    ok(await c.post(f"/api/v1/ops/quote-versions/{qv_id}/reviewed", headers=ops_key()))


async def publish(t: Team, rfq_id: str) -> dict[str, Any]:
    out: dict[str, Any] = ok(
        await t.advisor.client.post(f"/api/v1/ops/rfqs/{rfq_id}/comparisons", headers=ops_key())
    )
    return out


async def select_quote(database: Database, t: Team, rfq_id: str, qv_id: str) -> Response:
    w = t.world
    challenge = ok(
        await w.family.post(f"{w.base}/rfqs/{rfq_id}/selection-code",
                            json={"quote_version_id": qv_id}, headers=key())
    )  # fmt: skip
    code = await code_of(database, challenge["challenge_id"])
    return await w.family.post(
        f"{w.base}/rfqs/{rfq_id}/select",
        json={"quote_version_id": qv_id, "challenge_id": challenge["challenge_id"], "code": code,
              "statement_id": challenge["statement_id"], **CONTACT},
        headers=key(),
    )  # fmt: skip


def keys_of(value: Any) -> set[str]:
    """Every key anywhere in a JSON document."""
    found: set[str] = set()
    if isinstance(value, dict):
        for k, v in value.items():
            found.add(str(k))
            found |= keys_of(v)
    elif isinstance(value, list):
        for v in value:
            found |= keys_of(v)
    return found
