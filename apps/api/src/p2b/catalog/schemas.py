from decimal import Decimal

from pydantic import BaseModel, Field, field_serializer

from p2b.core.vocabulary import FinishLevel


class EstimateRequest(BaseModel):
    """API_ARCHITECTURE section 3. Bounds are the architecture defaults (OQ-043 open)."""

    city: str = Field(min_length=1, max_length=80)
    built_up_area_sqft: int = Field(ge=300, le=12000)
    floors: int = Field(ge=1, le=4, description="1 = ground only, 4 = ground + 3")
    finish_level: FinishLevel


class RateCardRef(BaseModel):
    city: str
    version: int
    is_demo: bool = Field(description="True: prototype values, not approved rates")
    label: str


class StageAmountOut(BaseModel):
    stage_number: int
    stage_name: str | None = Field(description="From the active stage configuration (S04)")
    share_pct: Decimal
    amount: Decimal

    @field_serializer("share_pct", "amount")
    def _as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"


class EstimateResponse(BaseModel):
    """Money as strings with two decimals plus a currency (API_ARCHITECTURE section 1)."""

    currency: str = "INR"
    total_low: Decimal
    total_high: Decimal
    total_mid: Decimal = Field(description="Midpoint; the stage amounts add up to it exactly")
    per_sqft_low: Decimal
    per_sqft_high: Decimal
    duration_months: int
    stages: list[StageAmountOut]
    rate_card: RateCardRef

    @field_serializer("total_low", "total_high", "total_mid", "per_sqft_low", "per_sqft_high")
    def _as_string(self, value: Decimal) -> str:
        return f"{value:.2f}"
