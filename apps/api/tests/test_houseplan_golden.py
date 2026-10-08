"""Golden plans and determinism (Checkpoint 1, section K): the same requirement gives a
byte-identical plan body and the same hash in this process, in a fresh process and in CI. A change
here is deliberate: rerun `scripts/update_houseplan_golden.py` and review the diff."""

import subprocess
import sys
from pathlib import Path

import pytest

from p2b.houseplans.engine.canonical import canonical_json
from p2b.houseplans.engine.model import dump
from tests.houseplans_support import (
    ZONED_GOLDEN,
    generate_case,
    generate_zoned_benchmark,
    golden_plan,
    valid_cases,
    zoned_golden,
)

API_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", valid_cases())
def test_generation_matches_the_golden_plan_byte_for_byte(name: str) -> None:
    golden = golden_plan(name)
    result = generate_case(name)
    assert result.outcome == "VALID"
    assert result.plan is not None
    assert result.topology == golden["topology"]
    assert result.plan.meta.body_sha256 == golden["body_sha256"]
    assert canonical_json(dump(result.plan)) == canonical_json(golden["plan"])


@pytest.mark.parametrize("name", valid_cases())
def test_repeated_generation_is_identical(name: str) -> None:
    first, second = generate_case(name), generate_case(name)
    assert first.plan is not None
    assert second.plan is not None
    assert canonical_json(dump(first.plan)) == canonical_json(dump(second.plan))


def test_a_fresh_process_produces_the_same_hashes() -> None:
    code = (
        "import sys; sys.path[:0] = ['.', 'src'];"
        "from tests.houseplans_support import generate_case, valid_cases;"
        "print(','.join(generate_case(n).plan.meta.body_sha256 for n in valid_cases()))"
    )
    out = subprocess.run(  # noqa: S603 (fixed interpreter and code)
        [sys.executable, "-c", code],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    ).stdout.strip()
    assert out.split(",") == [golden_plan(n)["body_sha256"] for n in valid_cases()]


def test_golden_plans_carry_no_authority_and_no_structural_claim() -> None:
    for name in valid_cases():
        plan = golden_plan(name)["plan"]
        assert {w["structural_role"] for w in plan["floors"][0]["walls"]} == {"UNASSESSED"}
        assert plan["meta"]["generator"]["solver"] == "DETERMINISTIC_MVP"


@pytest.mark.parametrize("name", ZONED_GOLDEN)
def test_zoned_generation_matches_its_golden_plan_byte_for_byte(name: str) -> None:
    golden = zoned_golden(name)
    result = generate_zoned_benchmark(name)
    assert result.outcome == "VALID"
    assert result.plan is not None
    assert result.topology == golden["topology"]
    assert result.plan.meta.body_sha256 == golden["body_sha256"]
    assert canonical_json(dump(result.plan)) == canonical_json(golden["plan"])


def test_a_fresh_process_produces_the_same_zoned_hashes() -> None:
    code = (
        "import sys; sys.path[:0] = ['.', 'src'];"
        "from tests.houseplans_support import ZONED_GOLDEN, generate_zoned_benchmark;"
        "print(','.join(generate_zoned_benchmark(n).plan.meta.body_sha256 for n in ZONED_GOLDEN))"
    )
    out = subprocess.run(  # noqa: S603 (fixed interpreter and code)
        [sys.executable, "-c", code],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    ).stdout.strip()
    assert out.split(",") == [zoned_golden(n)["body_sha256"] for n in ZONED_GOLDEN]
