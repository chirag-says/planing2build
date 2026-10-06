"""Edge middleware: hosts, request ids, response headers, CSRF, error envelope.
Sources: API_ARCHITECTURE section 1 (errors, CSRF, request id); SECURITY_ARCHITECTURE 4 to 6."""

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from p2b.audit.models import SecurityEvent
from p2b.core.db import Database
from p2b.core.vocabulary import Audience
from tests.conftest import ClientFactory, SignIn, UserFactory, csrf_headers


async def test_health_endpoints_answer_on_any_host(app: object) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as c:  # type: ignore[arg-type]
        assert (await c.get("/healthz")).json() == {"status": "ok"}
        ready = await c.get("/readyz")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ok"}


async def test_unknown_host_is_rejected_with_the_envelope(app: object) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://evil.test") as c:  # type: ignore[arg-type]
        response = await c.get("/api/v1/me")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "INVALID_HOST"
    assert error["request_id"] == response.headers["x-request-id"]


async def test_forwarded_host_decides_the_audience(app: object) -> None:
    # Server-side rendering reaches the API on an internal address and names the user's host in
    # X-Forwarded-Host, as Caddy does for browser traffic.
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://api.internal:8000") as c:
        known = await c.get("/api/v1/me", headers={"X-Forwarded-Host": "pro.test"})
        unknown = await c.get("/api/v1/me", headers={"X-Forwarded-Host": "evil.test, pro.test"})
    assert known.json()["error"]["code"] == "UNAUTHENTICATED"
    assert unknown.json()["error"]["code"] == "INVALID_HOST"


async def test_request_id_is_accepted_when_well_formed_and_minted_otherwise(
    client_for: ClientFactory,
) -> None:
    client = client_for(Audience.IHB)
    good = await client.get("/api/v1/me", headers={"X-Request-Id": "caddy-1234-abcd"})
    assert good.headers["x-request-id"] == "caddy-1234-abcd"
    bad = await client.get("/api/v1/me", headers={"X-Request-Id": "<script>"})
    assert bad.headers["x-request-id"] != "<script>"
    assert len(bad.headers["x-request-id"]) == 36


async def test_api_responses_are_never_cached_and_never_sniffed(client_for: ClientFactory) -> None:
    response = await client_for(Audience.IHB).get("/api/v1/me")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_unknown_route_returns_not_found_envelope(client_for: ClientFactory) -> None:
    response = await client_for(Audience.IHB).get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_state_change_with_session_cookie_requires_csrf_header_and_origin(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, database: Database
) -> None:
    client = client_for(Audience.IHB)
    await sign_in(client, await make_user(), Audience.IHB)

    no_header = await client.post("/api/v1/auth/logout", headers={"Origin": "https://ihb.test"})
    wrong_origin = await client.post(
        "/api/v1/auth/logout",
        headers={"X-Requested-With": "plan2build", "Origin": "https://pro.test"},
    )
    plain_http_origin = await client.post(
        "/api/v1/auth/logout",
        headers={"X-Requested-With": "plan2build", "Origin": "http://ihb.test"},
    )
    for response in (no_header, wrong_origin, plain_http_origin):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "CSRF_REJECTED"

    async with database.transaction() as session:
        reasons = (
            await session.scalars(
                select(SecurityEvent.details["reason"].astext).where(
                    SecurityEvent.kind == "CSRF_REJECTED"
                )
            )
        ).all()
    assert sorted(reasons) == ["missing_header", "origin_mismatch", "origin_not_https"]

    accepted = await client.post("/api/v1/auth/logout", headers=csrf_headers(Audience.IHB))
    assert accepted.status_code == 204


async def test_state_change_without_a_cookie_is_csrf_checked_too(
    client_for: ClientFactory,
) -> None:
    # API_ARCHITECTURE 0.2: public writes are checked as well, because otp/verify sets a session
    # (a hostile page could otherwise sign a visitor into the attacker's account).
    client = client_for(Audience.IHB)
    rejected = await client.post("/api/v1/auth/logout")
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "CSRF_REJECTED"
    passed = await client.post("/api/v1/auth/logout", headers=csrf_headers(Audience.IHB))
    assert passed.status_code == 401


async def test_webhook_paths_are_exempt_from_the_csrf_check(client_for: ClientFactory) -> None:
    # No CSRF header or Origin: the edge lets it through to the route, which refuses it for its
    # own reason (no event id or signature), never as CSRF.
    response = await client_for(Audience.IHB).post("/api/v1/webhooks/razorpay")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
