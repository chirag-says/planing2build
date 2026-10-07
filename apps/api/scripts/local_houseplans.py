"""Local development helpers for concept floor plans (Checkpoint 3.1). LOCAL ONLY.

    uv run python scripts/local_houseplans.py seed-ruleset        # load the synthetic test ruleset
    uv run python scripts/local_houseplans.py reset-rate-limits   # clear the counters e2e trips

Both act only on the local Compose database (127.0.0.1:55432, database p2b or p2b_test) and refuse
anything else, whatever P2B_DATABASE_URL says. `seed-ruleset` stores the synthetic test ruleset as
a DRAFT marked synthetic: the API uses it only when the houseplans settings allow draft and
synthetic rulesets, which the configuration permits in `local` and `test` and refuses in
production (infra/local/compose.houseplans.yml sets them for the local stack). Its values are
synthetic test values, never rules (AD-05). `reset-rate-limits` deletes only the fixed-window
counters of the limits a repeated end-to-end run trips (per-IP sign-in and the floor plan
routes); every other counter, and every counter of any other database, is left alone.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT / "src"))

from p2b.houseplans.engine import sha256_of  # noqa: E402

RULESET = API_ROOT / "tests" / "fixtures" / "houseplans" / "ruleset_synthetic_test_only.json"
DEFAULT_URL = "postgresql+asyncpg://p2b:p2b_local@127.0.0.1:55432/p2b"
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
LOCAL_PORT = 55432
LOCAL_DATABASES = {"p2b", "p2b_test"}
# the limits a repeated local e2e run trips; nothing else is reset
E2E_LIMITS = (
    "otp_start_ip",
    "otp_verify_ip",
    "otp_send_contact",
    "houseplan_request_session",
    "houseplan_edit_session",
    "houseplan_version_session",
)


def local_url() -> str:
    url = os.environ.get("P2B_LOCAL_DATABASE_URL", DEFAULT_URL)
    parts = urlsplit(url)
    if os.environ.get("P2B_ENV") == "production":
        raise SystemExit("Refusing: P2B_ENV is production.")
    if (
        parts.hostname not in LOCAL_HOSTS
        or parts.port != LOCAL_PORT
        or parts.path.lstrip("/") not in LOCAL_DATABASES
    ):
        raise SystemExit(
            f"Refusing: {parts.hostname}:{parts.port}{parts.path} is not the local stack."
        )
    return url


async def seed_ruleset(url: str) -> None:
    content = json.loads(RULESET.read_text("utf-8"))
    if content.get("synthetic") is not True:
        raise SystemExit("Refusing: the ruleset file is not marked synthetic.")
    sha = sha256_of(content)
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            existing = await conn.scalar(
                text("SELECT version FROM layout_rulesets WHERE content_sha256 = :sha"),
                {"sha": sha},
            )
            if existing is not None:
                print(f"The synthetic ruleset is already loaded (version {existing}).")
                return
            version = await conn.scalar(
                text("SELECT coalesce(max(version), 0) + 1 FROM layout_rulesets")
            )
            await conn.execute(
                text(
                    "INSERT INTO layout_rulesets (id, version, status, is_synthetic,"
                    " schema_version, content, content_sha256, note)"
                    " VALUES (gen_random_uuid(), :version, 'DRAFT',"
                    " true, '1.0.0', CAST(:content AS jsonb), :sha,"
                    " 'synthetic test values, local development only (AD-05)')"
                ),
                {"version": version, "content": json.dumps(content), "sha": sha},
            )
            print(f"Loaded the synthetic test ruleset as DRAFT version {version}.")
    finally:
        await engine.dispose()


async def reset_rate_limits(url: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            total = 0
            for name in E2E_LIMITS:
                result = await conn.execute(
                    text("DELETE FROM rate_counters WHERE bucket_key LIKE :prefix"),
                    {"prefix": f"{name}:%"},
                )
                total += result.rowcount or 0
            print(f"Cleared {total} rate counters ({', '.join(E2E_LIMITS)}).")
    finally:
        await engine.dispose()


def main() -> None:
    commands = {"seed-ruleset": seed_ruleset, "reset-rate-limits": reset_rate_limits}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        raise SystemExit(f"usage: local_houseplans.py {{{'|'.join(commands)}}}")
    asyncio.run(commands[sys.argv[1]](local_url()))


if __name__ == "__main__":
    main()
