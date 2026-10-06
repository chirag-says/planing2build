"""Billing arithmetic without a database: pricing rules, tax and place of supply, splits that
add up exactly, instalment plans, the Indian financial year, and the gateway signatures."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from p2b.billing.configuration import parse_plan
from p2b.billing.invoices import due_split
from p2b.billing.money import financial_year, from_paise, split, to_paise
from p2b.billing.pricing import evaluate, parse_rule
from p2b.billing.tax import TaxConfig, compute, missing_fields, parse_lines
from p2b.core.errors import PriceUnavailable, ValidationFailed
from p2b.integrations.razorpay import checkout_message, event_from, hmac_hex, signature_matches

RULE = parse_rule(
    {
        "base": "1000",
        "adjustments": [
            {
                "kind": "BAND",
                "characteristic": "built_up_area_sqft",
                "bands": [
                    {"from": 0, "to": 2000, "amount": "0"},
                    {"from": 2000, "to": 4000, "amount": "500"},
                    {"from": 4000, "amount": "900"},
                ],
            },
            {"kind": "ADD_IF", "characteristic": "basement", "equals": True, "amount": "300"},
        ],
        "maximum": "1900",
    }
)


@pytest.mark.parametrize(
    ("area", "basement", "price"),
    [
        (1500, False, "1000.00"),
        (2000, False, "1500.00"),
        (3999, True, "1800.00"),
        (5000, True, "1900.00"),
    ],  # the last is held at the maximum
)
def test_rules_add_bands_and_conditions_within_bounds(
    area: int, basement: bool, price: str
) -> None:
    amount, inputs = evaluate(RULE, {"built_up_area_sqft": area, "basement": basement, "floors": 2})
    assert amount == Decimal(price)
    assert inputs == {"basement": basement, "built_up_area_sqft": area}  # only what it used


def test_a_missing_characteristic_makes_the_price_unavailable() -> None:
    with pytest.raises(PriceUnavailable) as raised:
        evaluate(RULE, {"built_up_area_sqft": None, "basement": False})  # "Not sure yet"
    assert raised.value.details["missing"] == ["built_up_area_sqft"]


@pytest.mark.parametrize(
    "rule",
    [
        {"base": "-1"},
        {
            "base": "1",
            "adjustments": [
                {
                    "kind": "BAND",
                    "characteristic": "built_up_area_sqft",
                    "bands": [{"from": 0, "to": 10, "amount": "1"}, {"from": 20, "amount": "1"}],
                }
            ],
        },
        {
            "base": "1",
            "adjustments": [
                {"kind": "ADD_IF", "characteristic": "owner_income", "equals": 1, "amount": "1"}
            ],
        },
        {"base": "1", "minimum": "5", "maximum": "2"},
        {"base": "1", "surprise": True},
    ],
)
def test_invalid_rules_are_refused(rule: dict[str, object]) -> None:
    with pytest.raises(ValidationFailed):
        parse_rule(rule)


LINES = parse_lines(
    {
        "PACKAGE": {
            "sac": "T",
            "components": [
                {"name": "CGST", "rate": "9", "applies": "SAME_STATE"},
                {"name": "SGST", "rate": "9", "applies": "SAME_STATE"},
                {"name": "IGST", "rate": "18", "applies": "OTHER_STATE"},
            ],
        },
        "AI_CREDIT": {"sac": "T", "components": [{"name": "X", "rate": "5"}]},
    }
)
CONFIG = TaxConfig("E", "A", "G", "22", "S", False, LINES)


def test_place_of_supply_chooses_the_components() -> None:
    same = compute(CONFIG, "PACKAGE", Decimal("1000"), "22")
    other = compute(CONFIG, "PACKAGE", Decimal("1000"), "27")
    assert [line["component"] for line in same.lines] == ["CGST", "SGST"]
    assert [line["component"] for line in other.lines] == ["IGST"]
    assert same.total == other.total == Decimal("1180.00")


def test_prices_that_include_tax_back_out_the_taxable_value_exactly() -> None:
    inclusive = TaxConfig("E", "A", "G", "22", "S", True, LINES)
    result = compute(inclusive, "PACKAGE", Decimal("999"), "22")
    assert result.total == Decimal("999.00")
    assert result.taxable + result.tax_total == result.total
    assert sum(Decimal(line["amount"]) for line in result.lines) == result.tax_total


def test_an_incomplete_configuration_names_what_is_missing() -> None:
    blank = TaxConfig("", "", "", "", "", False, parse_lines({}))
    assert missing_fields(blank) == [
        "legal_name",
        "address",
        "gstin",
        "state_code",
        "invoice_series",
        "lines.PACKAGE",
        "lines.AI_CREDIT",
    ]
    assert "state_code" in missing_fields(TaxConfig("E", "A", "G", "99", "S", False, LINES))


@pytest.mark.parametrize("total", ["2065.00", "1000.01", "0.03", "99999.99"])
def test_splits_and_instalments_always_add_back_to_the_whole(total: str) -> None:
    amount = Decimal(total)
    assert sum(split(amount, [3333, 3333, 3334])) == amount
    tax = [{"component": "CGST", "rate": "9", "amount": str(amount * 9 / 118)[:8]}]
    parts = due_split(amount, tax, split(amount, [5000, 5000]))
    assert sum(Decimal(t["amount"]) for _, lines in parts for t in lines) == Decimal(
        tax[0]["amount"]
    )


def test_instalment_plans_have_one_shape() -> None:
    assert (
        len(
            parse_plan(
                [
                    {"share_bp": 4000, "due": "ON_ORDER"},
                    {"share_bp": 6000, "due": "DAYS_AFTER_ACTIVATION", "days": 30},
                ]
            ).instalments
        )
        == 2
    )
    for bad in (
        [
            {"share_bp": 5000, "due": "ON_ORDER"},
            {"share_bp": 4000, "due": "DAYS_AFTER_ACTIVATION", "days": 30},
        ],
        [
            {"share_bp": 5000, "due": "DAYS_AFTER_ACTIVATION", "days": 1},
            {"share_bp": 5000, "due": "ON_ORDER"},
        ],
        [{"share_bp": 5000, "due": "ON_ORDER"}, {"share_bp": 5000, "due": "ON_STAGE", "days": 1}],
        [{"share_bp": 10000, "due": "ON_ORDER"}],
    ):
        with pytest.raises(ValidationFailed):
            parse_plan(bad)


def test_money_crosses_the_wire_in_paise_and_the_year_runs_april_to_march() -> None:
    assert to_paise(Decimal("2065.00")) == 206500
    assert from_paise(206501) == Decimal("2065.01")
    assert financial_year(datetime(2026, 3, 31, 18, 29, tzinfo=UTC)) == "2025-26"
    assert financial_year(datetime(2026, 3, 31, 18, 31, tzinfo=UTC)) == "2026-27"  # 00:01 IST


def test_signatures_are_hmac_sha256_compared_in_constant_time() -> None:
    signature = hmac_hex("secret", checkout_message("order_1", "pay_1"))
    assert signature_matches("secret", b"order_1|pay_1", signature)
    assert not signature_matches("secret", b"order_1|pay_2", signature)
    assert not signature_matches("other", b"order_1|pay_1", signature)
    event = event_from(
        b'{"event": "refund.processed", "payload": {"refund": {"entity": '
        b'{"id": "rfnd_1", "payment_id": "pay_1", "amount": 100, "status": "processed",'
        b' "notes": []}}}}'
    )
    assert event.refund is not None
    assert event.refund.notes == {}  # Razorpay sends empty notes as []
