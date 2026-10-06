"""Tax configuration and arithmetic (SLICE3_3_READINESS section F). Every value comes from a
published tax configuration version with the accountant's figures (O-05): entity, GSTIN, state
code, invoice series, and per offering kind the SAC and its tax components. Which components
apply to a buyer (place of supply) is configuration too: each component says whether it applies
when the buyer's state equals the seller's, differs from it, or always. Nothing here is a rate.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from p2b.billing.money import rupees, split
from p2b.core.errors import ValidationFailed

# GST state and union territory codes, for the buyer's billing state.
STATE_CODES: dict[str, str] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory",
}


class TaxComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=20)
    rate: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    applies: Literal["SAME_STATE", "OTHER_STATE", "ALWAYS"] = "ALWAYS"


class TaxLineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sac: str = Field(min_length=1, max_length=10)
    components: list[TaxComponent] = Field(min_length=1)


class TaxLines(BaseModel):
    model_config = ConfigDict(extra="forbid")

    PACKAGE: TaxLineConfig | None = None
    AI_CREDIT: TaxLineConfig | None = None


def parse_lines(raw: dict[str, Any]) -> TaxLines:
    try:
        return TaxLines.model_validate(raw)
    except ValidationError as exc:
        raise ValidationFailed(
            message="The tax lines are not valid.",
            details={"fields": {"lines": [e["msg"] for e in exc.errors()][:10]}},
        ) from None


@dataclass(frozen=True)
class TaxConfig:
    legal_name: str
    address: str
    gstin: str
    state_code: str
    invoice_series: str
    prices_include_tax: bool
    lines: TaxLines


def missing_fields(config: TaxConfig) -> list[str]:
    """What a configuration lacks before it can be published or used for an order."""
    missing = [
        name
        for name in ("legal_name", "address", "gstin", "state_code", "invoice_series")
        if not str(getattr(config, name)).strip()
    ]
    if config.state_code and config.state_code not in STATE_CODES:
        missing.append("state_code")
    missing += [
        f"lines.{kind}" for kind in ("PACKAGE", "AI_CREDIT") if getattr(config.lines, kind) is None
    ]
    return missing


@dataclass(frozen=True)
class TaxBreakdown:
    taxable: Decimal
    lines: list[dict[str, str]]  # component, rate, amount (strings, for JSON)
    tax_total: Decimal
    total: Decimal


def compute(config: TaxConfig, kind: str, price: Decimal, buyer_state: str) -> TaxBreakdown:
    """Tax on `price` for a buyer in `buyer_state`. With prices including tax, the taxable
    value is backed out of the price and the components take the difference exactly."""
    line: TaxLineConfig = getattr(config.lines, kind)
    same = buyer_state == config.state_code
    components = [
        c for c in line.components if c.applies == "ALWAYS" or (c.applies == "SAME_STATE") == same
    ]
    rate = sum((c.rate for c in components), Decimal("0"))
    if config.prices_include_tax:
        total = rupees(price)
        taxable = rupees(total * 100 / (100 + rate))
        tax_total = total - taxable
        amounts = (
            split(tax_total, [c.rate for c in components])
            if rate > 0
            else [Decimal("0.00") for _ in components]
        )
    else:
        taxable = rupees(price)
        amounts = [rupees(taxable * c.rate / 100) for c in components]
        tax_total = sum(amounts, Decimal("0.00"))
        total = taxable + tax_total
    return TaxBreakdown(
        taxable,
        [
            {"component": c.name, "rate": str(c.rate), "amount": str(a)}
            for c, a in zip(components, amounts, strict=True)
        ],
        tax_total,
        total,
    )


def scale(lines: list[dict[str, str]], part: Decimal, whole: Decimal) -> list[dict[str, str]]:
    """The tax lines of a share of an amount (an instalment, a partial refund): each component
    in proportion, rounded, the last taking the remainder of the share's tax."""
    if not lines:
        return []
    amounts = [Decimal(line["amount"]) for line in lines]
    share_total = rupees(sum(amounts, Decimal("0")) * part / whole)
    shares = split(share_total, amounts) if sum(amounts) > 0 else [Decimal("0.00")] * len(lines)
    return [{**line, "amount": str(share)} for line, share in zip(lines, shares, strict=True)]
