"""Authorisation chain branches not reached by the foundation's own routes: audience-restricted
routes, MFA freshness, account states (SECURITY_ARCHITECTURE sections 3.3 and 4.1)."""

from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Annotated

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, update

from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.vocabulary import Audience, UserStatus
from p2b.identity.interface import Actor, require_actor
from p2b.identity.models import Session
from p2b.main import create_app
from tests.conftest import HOSTS, SignIn, UserFactory


@pytest.fixture(scope="module")
def probe_app() -> FastAPI:
    app = create_app(get_settings())

    @app.get("/api/v1/probe/homeowners")
    async def homeowners(actor: Annotated[Actor, require_actor(Audience.IHB)]) -> dict[str, str]:
        return {"user_id": str(actor.user_id)}

    @app.get("/api/v1/probe/ops-mfa")
    async def ops_mfa(
        actor: Annotated[Actor, require_actor(Audience.OPS, mfa=True)],
    ) -> dict[str, str]:
        return {"user_id": str(actor.user_id)}

    return app


@pytest.fixture
async def probe(probe_app: FastAPI) -> AsyncIterator[dict[Audience, AsyncClient]]:
    clients = {
        audience: AsyncClient(transport=ASGITransport(app=probe_app), base_url=f"https://{host}")
        for audience, host in HOSTS.items()
    }
    yield clients
    for client in clients.values():
        await client.aclose()


async def test_a_route_for_one_audience_does_not_exist_on_another_host(
    probe: dict[Audience, AsyncClient], make_user: UserFactory, sign_in: SignIn
) -> None:
    pro = probe[Audience.PRO]
    await sign_in(pro, await make_user(Audience.PRO), Audience.PRO)
    response = await pro.get("/api/v1/probe/homeowners")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_mfa_routes_need_a_recent_verification(
    probe: dict[Audience, AsyncClient], make_user: UserFactory, sign_in: SignIn,
    database: Database,
) -> None:  # fmt: skip
    ops = probe[Audience.OPS]
    await sign_in(ops, await make_user(Audience.OPS), Audience.OPS)

    never = await ops.get("/api/v1/probe/ops-mfa")
    assert never.status_code == 403
    assert never.json()["error"]["code"] == "MFA_REQUIRED"

    async with database.transaction() as session:
        await session.execute(update(Session).values(mfa_verified_at=func.now()))
    assert (await ops.get("/api/v1/probe/ops-mfa")).status_code == 200

    async with database.transaction() as session:
        await session.execute(
            update(Session).values(mfa_verified_at=func.now() - timedelta(hours=8, minutes=1))
        )
    assert (await ops.get("/api/v1/probe/ops-mfa")).status_code == 403


@pytest.mark.parametrize("status", [UserStatus.PENDING_VERIFICATION, UserStatus.CLOSED])
async def test_accounts_that_are_not_active_or_suspended_are_not_authenticated(
    probe: dict[Audience, AsyncClient], make_user: UserFactory, sign_in: SignIn,
    status: UserStatus,
) -> None:  # fmt: skip
    ihb = probe[Audience.IHB]
    await sign_in(ihb, await make_user(Audience.IHB, status), Audience.IHB)
    assert (await ihb.get("/api/v1/probe/homeowners")).status_code == 401
