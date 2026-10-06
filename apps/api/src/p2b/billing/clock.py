"""The database's clock, read once per use, so timestamps set on a row are real values (an SQL
`now()` expression would leave the attribute unloaded after the flush)."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def db_now(session: AsyncSession) -> datetime:
    """Without autoflush: callers read it between setting a row's state and its timestamp, and
    the row's CHECK ties the two together."""
    with session.sync_session.no_autoflush:
        now: datetime = (await session.execute(select(func.now()))).scalar_one()
    return now
