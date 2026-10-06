"""Per-request context carried through logs, audit rows and outbox events (OBSERVABILITY 1)."""

import re
from contextvars import ContextVar

from p2b.core.ids import new_id

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

# Caddy generates the id; accept it only if it looks like one, otherwise mint our own.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def accept_or_mint_request_id(candidate: str | None) -> str:
    if candidate and _VALID_REQUEST_ID.fullmatch(candidate):
        return candidate
    return str(new_id())


def set_request_id(value: str | None) -> None:
    _request_id.set(value)


def current_request_id() -> str | None:
    return _request_id.get()
