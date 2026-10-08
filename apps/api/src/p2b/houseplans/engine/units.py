"""Real-world units. Every stored length is an integer number of millimetres; feet exist only at
the requirement boundary (RQ v1 asks in feet) and in messages."""

from decimal import ROUND_HALF_EVEN, Decimal

MM_PER_FOOT = Decimal("304.8")


def ft_to_mm(value: int | float | Decimal | str) -> int:
    """Feet to whole millimetres, half-even, through Decimal so 30.1 ft is exact every time."""
    return int((Decimal(str(value)) * MM_PER_FOOT).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def mm_text(value: int) -> str:
    return f"{value:,} mm"


def area_text(mm2: int) -> str:
    return f"{mm2 / 1_000_000:.2f} m²"
