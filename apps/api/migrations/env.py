"""Alembic environment. Runs migrations with the async engine as the app_migrate role.

Every module's models are imported here so autogenerate and the drift test see all tables.
"""

import asyncio
import os

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import p2b.assurance.models
import p2b.audit.models
import p2b.billing.models
import p2b.buildplan.models
import p2b.catalog.models
import p2b.construction.models
import p2b.core.idempotency
import p2b.core.outbox
import p2b.core.ratelimit
import p2b.designs.models
import p2b.documents.models
import p2b.engagements.models
import p2b.identity.models
import p2b.integrations.fake_gateway
import p2b.money.models
import p2b.operations.models
import p2b.professionals.models
import p2b.projects.models
import p2b.rfq.models
import p2b.specification.models  # noqa: F401  (registers tables on the metadata)
from p2b.core.db import Base

target_metadata = Base.metadata


def _database_url() -> str:
    url = os.environ.get("P2B_MIGRATE_DATABASE_URL") or os.environ.get("P2B_DATABASE_URL")
    if not url:
        raise RuntimeError("Set P2B_MIGRATE_DATABASE_URL or P2B_DATABASE_URL")
    return url


def _include_object(obj: object, name: str | None, type_: str, *_: object) -> bool:
    # Procrastinate owns its tables; PostGIS owns spatial_ref_sys.
    return not (type_ == "table" and name is not None and (
        name.startswith("procrastinate_") or name == "spatial_ref_sys"
    ))  # fmt: skip


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_include_object,
        compare_type=True,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.execute("SET lock_timeout = '5s'")
        context.run_migrations()


async def _run_online() -> None:
    engine = create_async_engine(_database_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline SQL generation is not used; run migrations against a database")
asyncio.run(_run_online())
