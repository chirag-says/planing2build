"""Replay protection for creating and transition requests (API_ARCHITECTURE section 1;
DATA_ARCHITECTURE 4.15). The key row is written in the request's own transaction, so it commits
with the business change or not at all. A replay returns the stored response; the same key with a
different body is 409 IDEMPOTENCY_MISMATCH; a key whose first request is still running is 409."""

import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy import Integer, String, func, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base
from p2b.core.errors import AppError, ValidationFailed

HEADER = "Idempotency-Key"


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    session_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class IdempotencyMismatch(AppError):
    code, status = "IDEMPOTENCY_MISMATCH", 409
    default_message = "This request key was already used for a different request."


class IdempotencyInProgress(AppError):
    code, status = "IDEMPOTENCY_IN_PROGRESS", 409
    default_message = "The same request is still being processed."


def _idempotency_key(
    key: Annotated[
        str,
        Header(
            alias=HEADER,
            description="A new UUID for each action; reuse it only to retry the same request.",
        ),
    ],
) -> str:
    try:
        return str(uuid.UUID(key))
    except ValueError:
        raise ValidationFailed(
            details={"fields": {HEADER: ["A UUID Idempotency-Key header is required."]}}
        ) from None


# Declared as a header so it appears in the API contract and the typed client must send it.
IdempotencyKeyHeader = Annotated[str, Depends(_idempotency_key)]


async def run_once(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    key: str,
    request_body: Any,
    action: Callable[[], Awaitable[tuple[int, dict[str, Any]]]],
) -> JSONResponse:
    request_hash = hashlib.sha256(
        json.dumps(request_body, sort_keys=True, default=str).encode()
    ).hexdigest()
    inserted = await db.execute(
        insert(IdempotencyKey)
        .values(session_id=session_id, key=key, request_hash=request_hash)
        .on_conflict_do_nothing()
        .returning(IdempotencyKey.key)
    )
    if inserted.scalar_one_or_none() is None:
        stored = (
            await db.scalars(
                select(IdempotencyKey).where(
                    IdempotencyKey.session_id == session_id, IdempotencyKey.key == key
                )
            )
        ).one()
        if stored.request_hash != request_hash:
            raise IdempotencyMismatch
        if stored.response_status is None or stored.response_body is None:
            raise IdempotencyInProgress
        return JSONResponse(stored.response_body, status_code=stored.response_status)

    status, body = await action()
    stored = await db.get_one(IdempotencyKey, (session_id, key))
    stored.response_status = status
    stored.response_body = body
    return JSONResponse(body, status_code=status)
