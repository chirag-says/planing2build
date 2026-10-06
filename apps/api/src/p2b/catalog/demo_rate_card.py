"""Load the DEMO rate card for Raipur: `python -m p2b.catalog.demo_rate_card`.

The values are the S14 prototype calculator's (IHB_FLOW 8.3, read from the prototype's script).
Chirag, 2026-10-04: these are not real Raipur rates. The card is stored with `is_demo = true`, is
never served in production, and this command refuses to run there. It exists so the estimator can
be built and tested before Plan2Build publishes an approved rate card.
"""

import asyncio
import sys
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from p2b.catalog.estimator import DurationRule, RateRange, RatesV1
from p2b.catalog.models import RateCard
from p2b.core.config import Settings, get_settings
from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.vocabulary import FinishLevel

DEMO_CITY = "Raipur"
DEMO_VERSION = 1
DEMO_LABEL = "DEMO: prototype values from the S14 calculator. Not approved Raipur rates."

# S14: Raipur multiplier 1.00; finish rates per sq ft; floor factor 1 + (floors - 1) x 0.012;
# months = round(12 + area / 700 + (floors - 1) x 1.6); the sixteen stage shares in stage order.
S14_STAGE_SHARES = [3, 2, 8, 4, 9, 11, 8, 4, 5, 3, 7, 8, 10, 7, 7, 4]

DEMO_RATES = RatesV1(
    city_multiplier=Decimal("1.00"),
    finish_rates_per_sqft={
        FinishLevel.STANDARD: RateRange(low=Decimal(1520), high=Decimal(1800)),
        FinishLevel.PREMIUM: RateRange(low=Decimal(1950), high=Decimal(2400)),
        FinishLevel.LUXURY: RateRange(low=Decimal(2650), high=Decimal(3600)),
    },
    floor_factor_per_additional_floor=Decimal("0.012"),
    duration=DurationRule(
        base_months=Decimal(12),
        sqft_per_month=Decimal(700),
        months_per_additional_floor=Decimal("1.6"),
    ),
    stage_shares_pct={
        stage: Decimal(share) for stage, share in enumerate(S14_STAGE_SHARES, start=1)
    },
)


async def load(database: Database, settings: Settings) -> bool:
    """Insert the demo card once. Returns True if it was inserted by this call."""
    if settings.env == "production":
        raise SystemExit("Refusing to load a demo rate card in production.")
    async with database.transaction() as session:
        result = await session.execute(
            insert(RateCard)
            .values(
                id=new_id(),
                city=DEMO_CITY,
                version=DEMO_VERSION,
                schema_version=1,
                rates=DEMO_RATES.model_dump(mode="json"),
                is_demo=True,
                label=DEMO_LABEL,
                valid_from=func.now(),
                published_by=None,
            )
            .on_conflict_do_nothing(index_elements=["city", "version"])
        )
    return bool(result.rowcount)  # type: ignore[attr-defined]


async def _main() -> None:
    settings = get_settings()
    database = Database(settings)
    try:
        inserted = await load(database, settings)
    finally:
        await database.dispose()
    sys.stdout.write("demo rate card loaded\n" if inserted else "demo rate card already present\n")


if __name__ == "__main__":
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(_main(), loop_factory=loop_factory)
