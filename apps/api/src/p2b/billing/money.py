"""Money arithmetic for billing: Decimal rupees to two places, integer paise on the wire, and
splits that always add back to the whole (the last part takes the remainder)."""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

PAISA = Decimal("0.01")
RUPEE = Decimal("1")
IST = timezone(timedelta(hours=5, minutes=30), "IST")  # no daylight saving in India


def rupees(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(PAISA, rounding=ROUND_HALF_UP)


def whole_rupees(value: Decimal) -> Decimal:
    return value.quantize(RUPEE, rounding=ROUND_HALF_UP).quantize(PAISA)


def to_paise(amount: Decimal) -> int:
    return int((rupees(amount) * 100).to_integral_value())


def from_paise(paise: int) -> Decimal:
    return rupees(Decimal(paise) / 100)


def split(total: Decimal, weights: Sequence[Decimal | int]) -> list[Decimal]:
    """`total` in parts proportional to `weights`, each rounded to the paisa, the last taking
    the remainder so the parts add up exactly."""
    whole = sum(Decimal(w) for w in weights)
    if whole <= 0:
        raise ValueError("weights must add up to more than zero")
    parts = [rupees(total * Decimal(w) / whole) for w in weights[:-1]]
    return [*parts, rupees(total) - sum(parts, Decimal("0"))]


def financial_year(moment: datetime) -> str:
    """The Indian financial year (April to March) of a moment, in IST: "2026-27"."""
    local = moment.astimezone(IST)
    start = local.year if local.month >= 4 else local.year - 1
    return f"{start}-{(start + 1) % 100:02d}"
