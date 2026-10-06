"""Job queue schema (Procrastinate 3.10.0; ADR-009).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-04

The library's schema is frozen into migrations/sql at the version installed, so a fresh database and
an upgraded one end in the same state. A Procrastinate upgrade ships its delta migration SQL as a
new Alembic revision.
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op
from sqlalchemy.util import await_only

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "sql" / "procrastinate_3.10.0_schema.sql"


def _execute_script(sql: str) -> None:
    """asyncpg runs a multi-statement script only through the simple query protocol, so the
    script goes to the driver connection directly, inside Alembic's transaction."""
    driver_connection = op.get_bind().connection.driver_connection
    await_only(driver_connection.execute(sql))


def upgrade() -> None:
    _execute_script(SCHEMA_SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    _execute_script(
        """
        DROP TABLE IF EXISTS procrastinate_events, procrastinate_periodic_defers,
            procrastinate_jobs, procrastinate_workers CASCADE;
        DO $$
        DECLARE fn record;
        BEGIN
            FOR fn IN
                SELECT p.oid::regprocedure AS signature
                FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = current_schema() AND p.proname LIKE 'procrastinate\\_%'
            LOOP
                EXECUTE 'DROP FUNCTION ' || fn.signature || ' CASCADE';
            END LOOP;
        END $$;
        DROP TYPE IF EXISTS procrastinate_job_to_defer_v1, procrastinate_job_event_type,
            procrastinate_job_status CASCADE;
        """
    )
