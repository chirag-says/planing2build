"""Schema drift: the migrated database equals the ORM metadata, and CHECK constraints equal the
vocabulary (STATE_MODEL section 1, rule 1; ADR-019)."""

import re
from enum import StrEnum

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import Connection

from p2b.core.db import Base, Database
from p2b.core.vocabulary import (
    ActorType,
    Audience,
    ContactKind,
    OtpPurpose,
    OtpState,
    SecuritySeverity,
    UserStatus,
)


def _ignore_library_tables(_: object, name: str | None, type_: str, *__: object) -> bool:
    return not (
        type_ == "table"
        and name
        and (name.startswith("procrastinate_") or name == "spatial_ref_sys")
    )


async def test_migrations_produce_exactly_the_model_schema(database: Database) -> None:
    def diff(connection: Connection) -> list[object]:
        context = MigrationContext.configure(
            connection, opts={"include_object": _ignore_library_tables, "compare_type": True}
        )
        return list(compare_metadata(context, Base.metadata))

    async with database.engine.connect() as conn:
        differences = await conn.run_sync(diff)
    assert differences == []


@pytest.mark.parametrize(
    ("table", "constraint", "enum"),
    [
        ("users", "ck_users_status", UserStatus),
        ("users", "ck_users_audience", Audience),
        ("sessions", "ck_sessions_audience", Audience),
        ("audit_events", "ck_audit_events_actor_type", ActorType),
        ("security_events", "ck_security_events_severity", SecuritySeverity),
        ("user_contacts", "ck_user_contacts_audience", Audience),
        ("user_contacts", "ck_user_contacts_kind", ContactKind),
        ("otp_challenges", "ck_otp_challenges_audience", Audience),
        ("otp_challenges", "ck_otp_challenges_purpose", OtpPurpose),
        ("otp_challenges", "ck_otp_challenges_contact_kind", ContactKind),
        ("otp_challenges", "ck_otp_challenges_state", OtpState),
    ],
)
async def test_check_constraints_equal_the_vocabulary(
    database: Database, table: str, constraint: str, enum: type[StrEnum]
) -> None:
    async with database.engine.connect() as conn:
        definition = (
            await conn.execute(
                text(
                    "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
                    "JOIN pg_class t ON t.oid = c.conrelid WHERE t.relname = :t AND c.conname = :c"
                ),
                {"t": table, "c": constraint},
            )
        ).scalar_one()
    assert set(re.findall(r"'([^']+)'", definition)) == {member.value for member in enum}
