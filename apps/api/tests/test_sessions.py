"""Sessions and the authorisation chain for authenticated routes.
Sources: SECURITY_ARCHITECTURE sections 3.2 and 4.1; ADR-010; API_ARCHITECTURE section 2."""

import hashlib
from datetime import timedelta

from sqlalchemy import func, select, update

from p2b.audit.models import AuditEvent
from p2b.core.db import Database
from p2b.core.http import session_cookie_name
from p2b.core.outbox import OutboxEvent
from p2b.core.vocabulary import Audience, UserStatus
from p2b.identity.models import Session
from tests.conftest import ClientFactory, SignIn, UserFactory, csrf_headers


async def test_me_requires_a_session(client_for: ClientFactory) -> None:
    response = await client_for(Audience.IHB).get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_me_returns_the_actor_for_a_valid_session(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    user_id = await make_user()
    client = client_for(Audience.IHB)
    await sign_in(client, user_id, Audience.IHB)
    response = await client.get("/api/v1/me")
    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(user_id),
        "audience": "ihb",
        "status": "ACTIVE",
        "display_name": None,
        "locale": "en",
        "staff": None,  # staff details exist only on the operations host
    }


async def test_only_the_token_hash_is_stored(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    token = await sign_in(client_for(Audience.IHB), await make_user(), Audience.IHB)
    async with database.transaction() as session:
        stored = (await session.scalars(select(Session.token_hash))).one()
    assert stored == hashlib.sha256(token.encode()).digest()
    assert token.encode() not in stored


async def test_a_session_is_bound_to_its_audience(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    pro_user = await make_user(Audience.PRO)
    pro_client = client_for(Audience.PRO)
    token = await sign_in(pro_client, pro_user, Audience.PRO)
    assert (await pro_client.get("/api/v1/me")).status_code == 200

    # The same token presented on the homeowner host, even under that host's cookie name.
    ihb_client = client_for(Audience.IHB)
    ihb_client.cookies.set(session_cookie_name(Audience.IHB, secure=True), token)
    assert (await ihb_client.get("/api/v1/me")).status_code == 401


async def test_expired_sessions_are_rejected(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    client = client_for(Audience.IHB)
    await sign_in(client, await make_user(), Audience.IHB)

    async with database.transaction() as session:
        await session.execute(update(Session).values(expires_at=func.now() - timedelta(seconds=1)))
    assert (await client.get("/api/v1/me")).status_code == 401

    async with database.transaction() as session:
        await session.execute(
            update(Session).values(
                expires_at=func.now() + timedelta(days=1),
                absolute_expires_at=func.now() - timedelta(seconds=1),
            )
        )
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_session_lifetimes_follow_the_audience_policy(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    await sign_in(client_for(Audience.OPS), await make_user(Audience.OPS), Audience.OPS)
    async with database.transaction() as session:
        row = (await session.scalars(select(Session))).one()
    assert row.expires_at - row.created_at == timedelta(hours=12)
    assert row.absolute_expires_at - row.created_at == timedelta(hours=24)


async def test_activity_slides_the_idle_expiry_but_never_past_the_absolute_limit(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    client = client_for(Audience.IHB)
    await sign_in(client, await make_user(), Audience.IHB)
    async with database.transaction() as session:
        await session.execute(
            update(Session).values(
                last_seen_at=func.now() - timedelta(minutes=10),
                expires_at=func.now() + timedelta(hours=1),
                absolute_expires_at=func.now() + timedelta(days=2),
            )
        )
    assert (await client.get("/api/v1/me")).status_code == 200
    async with database.transaction() as session:
        row = (await session.scalars(select(Session))).one()
        now = (await session.execute(select(func.now()))).scalar_one()
    assert row.expires_at == row.absolute_expires_at  # capped: 14-day idle exceeds 2 days left
    assert now - row.last_seen_at < timedelta(minutes=1)


async def test_suspended_accounts_cannot_act_but_can_sign_out(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    client = client_for(Audience.IHB)
    await sign_in(client, await make_user(status=UserStatus.SUSPENDED), Audience.IHB)
    me = await client.get("/api/v1/me")
    assert me.status_code == 403
    assert me.json()["error"]["code"] == "FORBIDDEN"
    assert (
        await client.post("/api/v1/auth/logout", headers=csrf_headers(Audience.IHB))
    ).status_code == 204


async def test_logout_revokes_audits_publishes_and_clears_the_cookie(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    user_id = await make_user()
    client = client_for(Audience.IHB)
    token = await sign_in(client, user_id, Audience.IHB)

    response = await client.post("/api/v1/auth/logout", headers=csrf_headers(Audience.IHB))
    assert response.status_code == 204
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith("__Host-p2b_ihb_session=")
    for attribute in ("Max-Age=0", "HttpOnly", "Secure", "SameSite=lax", "Path=/"):
        assert attribute in set_cookie
    assert "Domain" not in set_cookie

    async with database.transaction() as session:
        revoked_at = (await session.scalars(select(Session.revoked_at))).one()
        actions = (await session.scalars(select(AuditEvent.action).order_by(AuditEvent.at))).all()
        events = (await session.scalars(select(OutboxEvent))).all()
    assert revoked_at is not None
    assert actions == ["session.created", "session.revoked"]
    assert [(e.event_type, e.payload["user_id"], e.payload["reason"]) for e in events] == [
        ("session.revoked", str(user_id), "logout")
    ]
    # The revoked session no longer authenticates, even if the client kept the token.
    client.cookies.set(session_cookie_name(Audience.IHB, secure=True), token)
    assert (await client.get("/api/v1/me")).status_code == 401
