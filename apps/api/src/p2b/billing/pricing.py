"""Pricing rules (SLICE3_3_READINESS B.1): one small engine driven by data. A rule version holds
a base amount and ordered adjustments; the server evaluates it against the project's submitted
characteristics and stamps the result, the inputs and the version on the order. No amount is in
code; every value is a published version (O-01, O-07).

Characteristics are an allow-list read from the project (`projects.billing_facts`). Adding one
is a reviewed code change; changing amounts is a new version.
"""

from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from p2b.billing.money import rupees, whole_rupees
from p2b.core.errors import PriceUnavailable, ValidationFailed

NumericCharacteristic = Literal["built_up_area_sqft", "floors"]
Characteristic = Literal[
    "built_up_area_sqft", "floors", "basement", "quality_tier", "property_type"
]
Amount = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class Band(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_value: Decimal = Field(ge=0, alias="from")
    to_value: Decimal | None = Field(default=None, alias="to")  # exclusive; None is open-ended
    amount: Amount


class BandAdjustment(BaseModel):
    """Add the amount of the band the characteristic falls in (from inclusive, to exclusive)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["BAND"]
    characteristic: NumericCharacteristic
    bands: list[Band] = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered(self) -> "BandAdjustment":
        previous_end: Decimal | None = Decimal(0)
        for band in self.bands:
            if previous_end is None or band.from_value != previous_end:
                raise ValueError("bands must follow each other without gaps or overlaps")
            if band.to_value is not None and band.to_value <= band.from_value:
                raise ValueError("a band must end after it starts")
            previous_end = band.to_value
        return self


class AddIfAdjustment(BaseModel):
    """Add the amount when the characteristic equals the value."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["ADD_IF"]
    characteristic: Characteristic
    equals: str | bool | int
    amount: Amount


class PricingRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base: Amount
    adjustments: list[Annotated[BandAdjustment | AddIfAdjustment, Field(discriminator="kind")]] = []
    minimum: Amount | None = None
    maximum: Amount | None = None

    @model_validator(mode="after")
    def _bounds(self) -> "PricingRule":
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("the minimum is above the maximum")
        return self

    @property
    def characteristics(self) -> list[str]:
        return sorted({a.characteristic for a in self.adjustments})


def parse_rule(raw: dict[str, Any]) -> PricingRule:
    try:
        return PricingRule.model_validate(raw)
    except ValidationError as exc:
        raise ValidationFailed(
            message="The pricing rule is not valid.",
            details={"fields": {"rule": [e["msg"] for e in exc.errors()][:10]}},
        ) from None


def evaluate(rule: PricingRule, characteristics: dict[str, Any]) -> tuple[Decimal, dict[str, Any]]:
    """The price, in whole rupees, and the inputs it used. Raises PriceUnavailable naming the
    characteristics the rule needs but the project does not have."""
    missing = [c for c in rule.characteristics if characteristics.get(c) is None]
    if missing:
        raise PriceUnavailable(details={"missing": missing})
    price = Decimal(rule.base)
    for adjustment in rule.adjustments:
        value = characteristics[adjustment.characteristic]
        if isinstance(adjustment, BandAdjustment):
            number = Decimal(value)
            for band in adjustment.bands:
                if number >= band.from_value and (band.to_value is None or number < band.to_value):
                    price += band.amount
                    break
        elif value == adjustment.equals:
            price += adjustment.amount
    if rule.minimum is not None:
        price = max(price, Decimal(rule.minimum))
    if rule.maximum is not None:
        price = min(price, Decimal(rule.maximum))
    price = whole_rupees(price)
    if price <= 0:
        raise PriceUnavailable(details={"missing": [], "reason": "price is not positive"})
    inputs = {c: characteristics[c] for c in rule.characteristics}
    return rupees(price), inputs
