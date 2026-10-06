"""Rate limits (API_ARCHITECTURE section 1, tiers; ADR-007).

Fixed-window counters in Postgres (`rate_counters`, DATA_ARCHITECTURE 4.15). ADR-007 makes Redis the
fast path with Postgres as the fallback; until Upstash is provisioned, Postgres is the only store,
which is the fail-closed behaviour SECURITY asks for on OTP limits. A Redis adapter implements the
same `hit` contract when it arrives.

Each hit commits in its own transaction, so a request that later fails still counts.
"""

import math
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func, literal
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base, Database
from p2b.core.errors import RateLimited


class RateCounter(Base):
    __tablename__ = "rate_counters"

    bucket_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)


@dataclass(frozen=True)
class Limit:
    name: str
    limit: int
    window_seconds: int


@dataclass(frozen=True)
class Decision:
    allowed: bool
    count: int
    retry_after_seconds: int


async def hit(database: Database, rule: Limit, subject: str) -> Decision:
    """Count one event for `subject` (a keyed hash, never a raw contact or IP)."""
    window = literal(rule.window_seconds, BigInteger)
    window_start = func.to_timestamp(
        func.floor(func.extract("epoch", func.now()) / window) * window
    )
    async with database.transaction() as session:
        row = (
            await session.execute(
                insert(RateCounter)
                .values(bucket_key=f"{rule.name}:{subject}", window_start=window_start, count=1)
                .on_conflict_do_update(
                    index_elements=["bucket_key", "window_start"],
                    set_={"count": RateCounter.count + 1},
                )
                .returning(RateCounter.count, RateCounter.window_start, func.now())
            )
        ).one()
    count, started, now = int(row[0]), row[1], row[2]
    seconds_left = rule.window_seconds - (now - started).total_seconds()
    return Decision(count <= rule.limit, count, max(1, math.ceil(seconds_left)))


async def enforce(database: Database, rule: Limit, subject: str) -> None:
    decision = await hit(database, rule, subject)
    if not decision.allowed:
        raise RateLimited(retry_after_seconds=decision.retry_after_seconds)
