"""Cost estimator engine (J02; S05 F2). Pure: no database, no clock, Decimal arithmetic.

Rate card schema version 1 encodes the calculation of the S14 prototype: a per-sq-ft range for the
finish level, times a city multiplier, times a floor factor, times the built-up area; a duration
formula; and a stage split that always sums to the total (S05 F2 acceptance). The values live in
the rate card, never here. Whether production rate cards keep this shape or move to S05's material
and labour rates is part of the production rate card decision (baseline, later blockers); a new
shape is a new `schema_version` handled here beside version 1.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from p2b.core.vocabulary import FinishLevel

PAISE = Decimal("0.01")
STAGE_NUMBERS = tuple(range(1, 17))


class RateRange(BaseModel):
    low: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> "RateRange":
        if self.high < self.low:
            raise ValueError("high must not be below low")
        return self


class DurationRule(BaseModel):
    base_months: Decimal = Field(ge=0)
    sqft_per_month: Decimal = Field(gt=0)
    months_per_additional_floor: Decimal = Field(ge=0)


class RatesV1(BaseModel):
    city_multiplier: Decimal = Field(gt=0)
    finish_rates_per_sqft: dict[FinishLevel, RateRange]
    floor_factor_per_additional_floor: Decimal = Field(ge=0)
    duration: DurationRule
    stage_shares_pct: dict[int, Decimal]

    @field_validator("finish_rates_per_sqft")
    @classmethod
    def _every_finish_level(
        cls, value: dict[FinishLevel, RateRange]
    ) -> dict[FinishLevel, RateRange]:
        if set(value) != set(FinishLevel):
            raise ValueError("a rate is required for every finish level")
        return value

    @field_validator("stage_shares_pct")
    @classmethod
    def _sixteen_stages_summing_to_100(cls, value: dict[int, Decimal]) -> dict[int, Decimal]:
        if tuple(sorted(value)) != STAGE_NUMBERS:
            raise ValueError("shares are required for stages 1 to 16")
        if sum(value.values()) != Decimal(100):
            raise ValueError("stage shares must sum to 100")
        return value


@dataclass(frozen=True)
class EstimateInputs:
    built_up_area_sqft: int
    floors: int  # 1 = ground only, 4 = ground + 3
    finish_level: FinishLevel


@dataclass(frozen=True)
class StageAmount:
    stage_number: int
    share_pct: Decimal
    amount: Decimal


@dataclass(frozen=True)
class Estimate:
    total_low: Decimal
    total_high: Decimal
    total_mid: Decimal
    per_sqft_low: Decimal
    per_sqft_high: Decimal
    duration_months: int
    stages: tuple[StageAmount, ...]


def _money(value: Decimal) -> Decimal:
    return value.quantize(PAISE, rounding=ROUND_HALF_UP)


def compute_estimate(inputs: EstimateInputs, rates: RatesV1) -> Estimate:
    area = Decimal(inputs.built_up_area_sqft)
    extra_floors = Decimal(inputs.floors - 1)
    floor_factor = 1 + extra_floors * rates.floor_factor_per_additional_floor
    finish = rates.finish_rates_per_sqft[inputs.finish_level]
    per_sqft_low = finish.low * rates.city_multiplier * floor_factor
    per_sqft_high = finish.high * rates.city_multiplier * floor_factor

    total_low = _money(per_sqft_low * area)
    total_high = _money(per_sqft_high * area)
    total_mid = _money((total_low + total_high) / 2)

    months = (
        rates.duration.base_months
        + area / rates.duration.sqft_per_month
        + extra_floors * rates.duration.months_per_additional_floor
    )
    duration_months = int(months.quantize(Decimal(1), rounding=ROUND_HALF_UP))

    return Estimate(
        total_low=total_low,
        total_high=total_high,
        total_mid=total_mid,
        per_sqft_low=_money(per_sqft_low),
        per_sqft_high=_money(per_sqft_high),
        duration_months=duration_months,
        stages=_split(total_mid, rates.stage_shares_pct),
    )


def _split(total: Decimal, shares: dict[int, Decimal]) -> tuple[StageAmount, ...]:
    """Stage amounts of the midpoint. Rounding leaves at most a few paise over or under; that
    remainder goes to the largest share (lowest stage number on a tie), so the parts always add up
    to the total exactly."""
    amounts = {stage: _money(total * share / 100) for stage, share in shares.items()}
    remainder = total - sum(amounts.values())
    largest = min(shares, key=lambda stage: (-shares[stage], stage))
    amounts[largest] += remainder
    return tuple(StageAmount(stage, shares[stage], amounts[stage]) for stage in STAGE_NUMBERS)
