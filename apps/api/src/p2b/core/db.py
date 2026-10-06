"""Database engine, ORM base and the per-request unit of work.

One business action is one transaction (DATA_ARCHITECTURE section 2): the request's session commits
after the route returns and before the response is sent, or rolls back on any error. Audit rows and
outbox events written through the same session commit or vanish with the business change.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import MetaData, func, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import DateTime

from p2b.core.config import Settings

# Deterministic constraint names so migrations and drift checks are stable.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: DateTime(timezone=True)}  # noqa: RUF012 (SQLAlchemy API)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


def _engine_args(settings: Settings) -> dict[str, Any]:
    connect_args: dict[str, Any] = {
        "server_settings": {"statement_timeout": str(settings.statement_timeout_ms)}
    }
    if settings.database_pooler_mode == "transaction":
        # Supavisor transaction mode cannot keep prepared statements across transactions.
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0
    return {
        "pool_size": settings.database_pool_size,
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }


class Database:
    def __init__(self, settings: Settings):
        self.engine: AsyncEngine = create_async_engine(
            str(settings.database_url), **_engine_args(settings)
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """A unit of work outside a request (worker, relay, independent security logging)."""
        async with self.sessions() as session, session.begin():
            yield session

    async def ping(self) -> None:
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()


async def _request_session(request: Request) -> AsyncIterator[AsyncSession]:
    database: Database = request.app.state.database
    async with database.sessions() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


# scope="function": commit before the response is sent, so a failed commit is a 500, never a
# 2xx for a change that did not persist.
DbSession = Annotated[AsyncSession, Depends(_request_session, scope="function")]
