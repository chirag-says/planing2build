"""Edge middleware for every API request (pure ASGI; one pass per request).

In order: request id (accepted from Caddy or minted), host validation and audience, CSRF check on
every state-changing request except provider webhooks (API_ARCHITECTURE 1, version 0.2),
`Cache-Control: no-store` and `nosniff` on responses, and one access log line. Health endpoints
skip the host check so container health checks work on any host.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from p2b.core.config import Settings
from p2b.core.errors import CsrfRejected, InvalidHost, envelope
from p2b.core.request_context import accept_or_mint_request_id, set_request_id
from p2b.core.vocabulary import Audience

log = structlog.get_logger("p2b.access")

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
WEBHOOK_PREFIX = "/api/v1/webhooks/"
HEALTH_PATHS = frozenset({"/healthz", "/readyz"})
CSRF_HEADER_VALUE = "plan2build"

SecurityEventSink = Callable[[str, Audience | None, dict[str, Any]], Awaitable[None]]


def session_cookie_name(audience: Audience, *, secure: bool) -> str:
    """`__Host-p2b_ihb_session` (ADR-010). The prefix requires Secure, so LOCAL without TLS
    drops both together (baseline N-04)."""
    base = f"p2b_{audience.value}_session"
    return f"__Host-{base}" if secure else base


def _bare_host(raw: str) -> str:
    return raw.split(":", 1)[0].strip().lower()


def client_ip(headers: Headers, peer: str | None) -> str:
    """The caller's IP. Caddy writes X-Forwarded-For and replaces any value a client sends (the
    same rule verified for X-Forwarded-Host), so its first entry is the client."""
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return peer or "unknown"


def effective_host(headers: Headers) -> str:
    """The host the user addressed. Behind Caddy, and for server-side calls from Next.js (whose
    fetch cannot set Host), it arrives as X-Forwarded-Host. Only Caddy and the web container can
    reach the API, and Caddy replaces any client-supplied value (verified in the local stack), so
    the header is trustworthy here. The session's own audience binding is a second check."""
    forwarded = headers.get("x-forwarded-host")
    raw = forwarded.split(",", 1)[0] if forwarded else headers.get("host", "")
    return _bare_host(raw)


class EdgeMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings, on_security_event: SecurityEventSink):
        self.app = app
        self.settings = settings
        self.on_security_event = on_security_event

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = accept_or_mint_request_id(headers.get("x-request-id"))
        set_request_id(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                raw = list(message.get("headers", []))
                raw.append((b"x-request-id", request_id.encode()))
                raw.append((b"x-content-type-options", b"nosniff"))
                if not any(name.lower() == b"cache-control" for name, _ in raw):
                    raw.append((b"cache-control", b"no-store"))
                message["headers"] = raw
            await send(message)

        try:
            await self._guard_and_call(scope, receive, send_wrapper, headers)
        finally:
            log.info(
                "http.request",
                method=scope["method"],
                path=scope["path"],
                status=status_holder["status"],
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
                audience=scope.get("state", {}).get("audience"),
            )
            structlog.contextvars.unbind_contextvars("request_id")
            set_request_id(None)

    async def _guard_and_call(
        self, scope: Scope, receive: Receive, send: Send, headers: Headers
    ) -> None:
        path: str = scope["path"]
        if path in HEALTH_PATHS:
            await self.app(scope, receive, send)
            return

        host = effective_host(headers)
        audience = self.settings.audience_by_host.get(host)
        if audience is None:
            await envelope(InvalidHost.status, InvalidHost.code, InvalidHost.default_message, {})(
                scope, receive, send
            )
            return
        scope.setdefault("state", {})["audience"] = audience

        if scope["method"] not in SAFE_METHODS and not path.startswith(WEBHOOK_PREFIX):
            reason = self._csrf_failure(headers, host)
            if reason is not None:
                await self.on_security_event("CSRF_REJECTED", audience, {"reason": reason})
                await envelope(
                    CsrfRejected.status, CsrfRejected.code, CsrfRejected.default_message, {}
                )(scope, receive, send)
                return

        await self.app(scope, receive, send)

    def _csrf_failure(self, headers: Headers, host: str) -> str | None:
        """API_ARCHITECTURE section 1: X-Requested-With and an Origin matching the host."""
        if headers.get("x-requested-with") != CSRF_HEADER_VALUE:
            return "missing_header"
        origin = headers.get("origin")
        if origin is None:
            return "missing_origin"
        scheme, _, rest = origin.partition("://")
        if scheme not in {"https", "http"} or _bare_host(rest) != host:
            return "origin_mismatch"
        if scheme == "http" and self.settings.cookie_secure:
            return "origin_not_https"
        return None
