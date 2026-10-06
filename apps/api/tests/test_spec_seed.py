"""The 67-line specification master seed (S04; rulings D-03, 2.3 to 2.5): the committed JSON equals
S04 when the source is present, keeps S04's fields, applies the structural rulings, and the
database holds exactly that seed."""

import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from p2b.catalog.models import SpecGroup, SpecLineMaster, SpecLineMasterVersion
from p2b.core.db import Database

REPO = Path(__file__).resolve().parents[3]
SEED = json.loads(
    (REPO / "apps" / "api" / "migrations" / "data" / "spec_lines_v1.json").read_text(
        encoding="utf-8"
    )
)
LINES = {line["code"]: line for line in SEED["lines"]}
STRUCTURAL = {"A01", "A02", "A04", "A05", "A09", "A12", "A13", "A19"}  # marked † in S04


def test_the_seed_equals_s04_when_the_source_is_available() -> None:
    script = REPO / "tools" / "extract_s04_spec_lines.py"
    if not (REPO / "SOURCE_OF_TRUTH" / "Plan2Build_Specification_Schema.docx").exists():
        pytest.skip("SOURCE_OF_TRUTH is not in this checkout")
    spec = importlib.util.spec_from_file_location("extract_s04", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build() == SEED


def test_sixty_seven_lines_in_three_packages() -> None:
    expected = (
        [f"A{n:02d}" for n in range(1, 22)]
        + [f"B{n:02d}" for n in range(1, 23)]
        + [f"C{n:02d}" for n in range(1, 25)]
    )
    assert list(LINES) == expected
    assert [(p["code"], p["name"]) for p in SEED["packages"]] == [
        ("A", "Structure"), ("B", "Concealed systems"), ("C", "Finishes"),
    ]  # fmt: skip
    assert all(line["package"] == code[0] for code, line in LINES.items())


def test_structural_lines_carry_no_brand_and_wait_for_engineer_sign_off() -> None:
    assert {code for code, line in LINES.items() if line["is_structural"]} == STRUCTURAL
    for code, line in LINES.items():
        if code in STRUCTURAL:
            assert line["brand_category"] is None
            assert line["engineer_signoff"] == "PENDING"
        else:
            assert line["engineer_signoff"] == "NOT_REQUIRED"
    a01 = LINES["A01"]
    assert (a01["item"], a01["s04_brand_category"], a01["brand_category"]) == (
        "Soil investigation", "Testing lab", None,
    )  # fmt: skip
    assert LINES["A04"]["s04_brand_category"] == "Cement / RMC"  # removed by D-03, kept as source


def test_s04_values_are_kept_as_written() -> None:
    assert LINES["A16"]["consuming_stages"] == [5, 6]
    assert all(1 <= stage <= 16 for line in LINES.values() for stage in line["consuming_stages"])
    assert LINES["C19"]["decide_by_weeks"] == 10
    assert LINES["B14"]["is_long_lead"] is True
    assert LINES["B18"]["is_long_lead"] is False  # 6 weeks, but not in S04's long-lead table
    assert LINES["A02"]["brand_category"] is None
    assert LINES["B03"]["brand_category"] == "Wires and cables"
    assert all(line["decide_by_weeks"] > 0 for line in LINES.values())


async def test_the_database_holds_exactly_the_seed(database: Database) -> None:
    async with database.transaction() as session:
        groups = [
            g.code for g in await session.scalars(select(SpecGroup).order_by(SpecGroup.sequence))
        ]
        rows = list(
            await session.execute(
                select(SpecLineMaster, SpecLineMasterVersion)
                .join(SpecLineMasterVersion, SpecLineMasterVersion.code == SpecLineMaster.code)
                .order_by(SpecLineMaster.sequence)
            )
        )
    assert groups == ["A", "B", "C"]  # S04 calls them packages; they are groups (PD-09)
    assert [master.code for master, _ in rows] == list(LINES)
    for master, version in rows:
        line = LINES[master.code]
        assert (master.item, master.brand_category, master.is_structural) == (
            line["item"], line["brand_category"], line["is_structural"],
        )  # fmt: skip
        assert list(master.consuming_stages) == line["consuming_stages"]
        assert (version.version, version.status) == (1, "ACTIVE")
        assert version.performance_specification == line["performance_specification"]
        assert version.engineer_signoff == line["engineer_signoff"]
