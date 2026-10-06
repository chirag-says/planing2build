"""Health endpoints (API_ARCHITECTURE section 1).

`/healthz`: the process is up. `/readyz`: the database is reachable and migrations are at head.
Unauthenticated, outside `/api/v1`, used by Compose and Caddy.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from p2b.core.authz import public_route
from p2b.core.db import Database

router = APIRouter(tags=["health"])

# apps/api/alembic.ini, relative to apps/api/src/p2b/core/health.py
ALEMBIC_INI = Path(__file__).resolve().parents[3] / "alembic.ini"


def expected_migration_head() -> str | None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "migrations"))
    return ScriptDirectory.from_config(config).get_current_head()


@router.get("/healthz", dependencies=[public_route], include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", dependencies=[public_route], include_in_schema=False)
async def readyz(request: Request) -> JSONResponse:
    database: Database = request.app.state.database
    expected: str | None = request.app.state.migration_head
    try:
        async with database.engine.connect() as conn:
            current = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one_or_none()
    except Exception:  # noqa: BLE001 (any database failure means not ready)
        return JSONResponse({"status": "unavailable", "database": "unreachable"}, status_code=503)
    if current != expected:
        return JSONResponse({"status": "unavailable", "migrations": "behind"}, status_code=503)
    return JSONResponse({"status": "ok"})
