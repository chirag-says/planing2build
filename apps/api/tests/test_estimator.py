"""Cost estimator (J02; S05 F2; API_ARCHITECTURE section 3) and the demo rate card guard
(Chirag, 2026-10-04: prototype values are not real Raipur rates)."""

from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, func

from p2b.catalog.demo_rate_card import DEMO_RATES, load
from p2b.catalog.estimator import EstimateInputs, RatesV1, compute_estimate
from p2b.catalog.models import RateCard
from p2b.catalog.service import active_rate_card
from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.vocabulary import Audience, FinishLevel
from tests.conftest import ClientFactory, csrf_headers


def test_the_engine_reproduces_the_s14_prototype_default() -> None:
    # IHB_FLOW 8.3: Raipur, 2,650 sq ft, G+1, Premium shows "52.3 L to 64.4 L",
    # "1,973 to 2,429 per sq ft", "about 17 months".
    result = compute_estimate(EstimateInputs(2650, 2, FinishLevel.PREMIUM), DEMO_RATES)
    assert result.total_low == Decimal("5229510.00")
    assert result.total_high == Decimal("6436320.00")
    assert result.per_sqft_low == Decimal("1973.40")
    assert result.per_sqft_high == Decimal("2428.80")
    assert result.duration_months == 17


@pytest.mark.parametrize("finish", list(FinishLevel))
@pytest.mark.parametrize("floors", [1, 2, 3, 4])
@pytest.mark.parametrize("area", [300, 1234, 2650, 7777, 12000])
def test_the_stage_breakdown_always_sums_to_the_total(
    finish: FinishLevel, floors: int, area: int
) -> None:
    result = compute_estimate(EstimateInputs(area, floors, finish), DEMO_RATES)
    assert sum(stage.amount for stage in result.stages) == result.total_mid
    assert [stage.stage_number for stage in result.stages] == list(range(1, 17))
    assert result.total_low <= result.total_mid <= result.total_high


def test_more_floors_cost_more_per_sq_ft_and_take_longer() -> None:
    ground = compute_estimate(EstimateInputs(2000, 1, FinishLevel.STANDARD), DEMO_RATES)
    upper = compute_estimate(EstimateInputs(2000, 4, FinishLevel.STANDARD), DEMO_RATES)
    assert upper.per_sqft_low > ground.per_sqft_low
    assert upper.duration_months > ground.duration_months


def test_the_same_inputs_and_card_give_the_same_estimate() -> None:
    inputs = EstimateInputs(1800, 3, FinishLevel.LUXURY)
    assert compute_estimate(inputs, DEMO_RATES) == compute_estimate(inputs, DEMO_RATES)


def _rates(**changes: object) -> dict[str, object]:
    data = DEMO_RATES.model_dump(mode="json")
    data.update(changes)
    return data


@pytest.mark.parametrize(
    "bad",
    [
        _rates(stage_shares_pct={str(n): "6.25" for n in range(1, 16)}),  # 15 stages
        _rates(stage_shares_pct={**{str(n): "6" for n in range(1, 16)}, "16": "11"}),  # sums to 101
        _rates(finish_rates_per_sqft={"STANDARD": {"low": "1", "high": "2"}}),  # levels missing
        _rates(city_multiplier="0"),
    ],
)
def test_invalid_rate_cards_are_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        RatesV1.model_validate(bad)


async def estimate(client_for: ClientFactory, **overrides: object):  # type: ignore[no-untyped-def]
    body = {"city": "Raipur", "built_up_area_sqft": 2650, "floors": 2, "finish_level": "PREMIUM"}
    body.update(overrides)
    return await client_for(Audience.IHB).post(
        "/api/v1/public/estimate", json=body, headers=csrf_headers(Audience.IHB)
    )


async def test_without_a_rate_card_there_is_no_estimate(client_for: ClientFactory) -> None:
    response = await estimate(client_for)
    assert response.status_code == 422
    assert "city" in response.json()["error"]["details"]["fields"]


async def test_an_estimate_from_the_demo_card_says_so(
    client_for: ClientFactory, database: Database
) -> None:
    assert await load(database, get_settings()) is True
    assert await load(database, get_settings()) is False  # idempotent
    response = await estimate(client_for, city="raipur")
    assert response.status_code == 200
    body = response.json()
    assert body["rate_card"]["is_demo"] is True
    assert body["rate_card"]["label"].startswith("DEMO:")
    assert body["total_low"] == "5229510.00"
    assert body["currency"] == "INR"
    assert sum(Decimal(s["amount"]) for s in body["stages"]) == Decimal(body["total_mid"])


async def test_an_approved_card_takes_over_and_demo_cards_are_hidden_in_production(
    database: Database,
) -> None:
    await load(database, get_settings())
    async with database.transaction() as session:
        session.add(
            RateCard(
                id=new_id(), city="Raipur", version=2, schema_version=1,
                rates=DEMO_RATES.model_dump(mode="json"), is_demo=False,
                label="Approved test card", valid_from=func.now(), published_by=new_id(),
            )
        )  # fmt: skip
    async with database.transaction() as session:
        newest = await active_rate_card(session, city="Raipur", allow_demo=True)
        assert newest is not None
        assert newest.version == 2
    async with database.transaction() as session:
        await session.execute(delete(RateCard).where(RateCard.version == 2))
        assert await active_rate_card(session, city="Raipur", allow_demo=False) is None


async def test_the_demo_loader_refuses_production(database: Database) -> None:
    production = get_settings().model_copy(update={"env": "production"})
    with pytest.raises(SystemExit):
        await load(database, production)


async def test_an_approved_card_must_name_its_publisher(database: Database) -> None:
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        async with database.transaction() as session:
            session.add(
                RateCard(
                    id=new_id(), city="Raipur", version=3, schema_version=1,
                    rates=DEMO_RATES.model_dump(mode="json"), is_demo=False, label="x",
                    valid_from=func.now(), published_by=None,
                )
            )  # fmt: skip


@pytest.mark.parametrize(
    "overrides",
    [{"built_up_area_sqft": 299}, {"built_up_area_sqft": 12001}, {"floors": 0}, {"floors": 5},
     {"finish_level": "BASIC"}],
)  # fmt: skip
async def test_inputs_outside_the_bounds_are_rejected(
    client_for: ClientFactory, overrides: dict[str, object]
) -> None:
    response = await estimate(client_for, **overrides)
    assert response.status_code == 422
