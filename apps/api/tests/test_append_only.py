"""Append-only records cannot be changed or removed (DATA_ARCHITECTURE section 1, principle 6;
SECURITY section 11). The trigger holds even for a superuser connection."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from p2b.audit.interface import record, record_security_event
from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.vocabulary import ActorType, SecuritySeverity


async def _seed(database: Database) -> None:
    async with database.transaction() as session:
        await record(
            session, action="test.done", entity_type="thing", entity_id=new_id(),
            actor_type=ActorType.SYSTEM,
        )  # fmt: skip
        await publish(
            session, event_type="thing.done", aggregate_type="thing", aggregate_id=new_id(),
            payload=EventPayload(), dedupe_suffix="1",
        )  # fmt: skip
    await record_security_event(database, kind="TEST", severity=SecuritySeverity.INFO)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_events SET reason = 'edited'",
        "DELETE FROM audit_events",
        "UPDATE security_events SET kind = 'EDITED'",
        "DELETE FROM security_events",
        "UPDATE outbox_events SET payload = '{}'::jsonb",
        "UPDATE outbox_events SET event_type = 'other.event'",
    ],
)
async def test_append_only_rows_refuse_changes(database: Database, statement: str) -> None:
    await _seed(database)
    with pytest.raises(DBAPIError, match=r"append-only|only processing columns"):
        async with database.transaction() as session:
            await session.execute(text(statement))


async def test_outbox_processing_columns_may_change(database: Database) -> None:
    await _seed(database)
    async with database.transaction() as session:
        await session.execute(
            text("UPDATE outbox_events SET processed_at = now(), attempts = 1, last_error = 'x'")
        )
