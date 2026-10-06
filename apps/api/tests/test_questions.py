"""The requirement question engine and the seeded set (REQUIREMENT_QUESTIONS_V1, section L)."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from p2b.catalog.questions import QuestionSetDefinition, review_flags, validate_answers
from p2b.core.vocabulary import Audience
from tests.conftest import ClientFactory

REPO = Path(__file__).resolve().parents[3]
SEED = REPO / "apps" / "api" / "migrations" / "data" / "requirement_questions_v1.json"
LOCKED_DOC = REPO / "SYSTEM_BLUEPRINT" / "02_IMPLEMENTATION" / "REQUIREMENT_QUESTIONS_V1.md"

DEFINITION = QuestionSetDefinition.model_validate(json.loads(SEED.read_text(encoding="utf-8")))

COMPLETE: dict[str, Any] = {
    "location": {"lat": 21.2514, "lng": 81.6296},
    "locality": "Shankar Nagar",
    "property_type": "INDEPENDENT_HOUSE",
    "plot_is_rectangular": True,
    "plot_width_ft": 40,
    "plot_depth_ft": 60,
    "facing": "E",
    "setbacks": {"FRONT": 10, "BACK": 5, "LEFT": "NOT_SURE", "RIGHT": 3.5},
    "built_up_area_sqft": 2650,
    "floors": "G_PLUS_1",
    "basement": False,
    "quality_tier": "PREMIUM",
    "bedrooms": "3",
    "bathrooms": "3",
    "pooja_room": True,
    "car_parking": True,
    "vastu": "WHERE_POSSIBLE",
    "budget_band": "60L_80L",
    "start_timeline": "3_6M",
    "construction_started": False,
    "has_contractor": False,
    "has_quote": False,
    "priorities": ["QUALITY", "ON_TIME", "WITHIN_BUDGET", "SIMILAR_HOMES"],
}


def _locked_table_rows() -> dict[str, str]:
    """Key to options cell from section L.2 of the locked document."""
    text = LOCKED_DOC.read_text(encoding="utf-8")
    section = text.split("### L.2", 1)[1].split("### L.3", 1)[0]
    rows: dict[str, str] = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and cells[0].startswith("`"):
            rows[cells[0].strip("`")] = cells[3]
    return rows


def test_the_seeded_set_has_exactly_the_locked_questions_and_options() -> None:
    rows = _locked_table_rows()
    assert set(rows) == {q.key for q in DEFINITION.questions}
    for question in DEFINITION.questions:
        documented = set(re.findall(r"`([A-Z0-9_]+)`", rows[question.key]))
        assert documented == {o.value for o in question.options}, question.key


def test_funding_is_not_asked_in_version_1() -> None:
    assert not any("fund" in q.key for q in DEFINITION.questions)  # R-7


def test_a_complete_answer_set_passes() -> None:
    cleaned, errors = validate_answers(DEFINITION, COMPLETE, complete=True)
    assert errors == {}
    assert cleaned["locality"] == "Shankar Nagar"


def test_drafts_may_be_partial_but_submission_may_not() -> None:
    partial = {"budget_band": "40L_60L"}
    assert validate_answers(DEFINITION, partial, complete=False)[1] == {}
    errors = validate_answers(DEFINITION, partial, complete=True)[1]
    assert "location" in errors
    assert "notes" not in errors  # optional
    assert "style" not in errors  # optional (default D-3)
    assert "uploads" not in errors  # files are attached separately


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("property_type", "APARTMENT_PURCHASE"),
        ("floors", "G_PLUS_4"),
        ("budget_band", "UNDER_25L"),
        ("location", {"lat": 95, "lng": 81}),
        ("plot_width_ft", 0),
        ("built_up_area_sqft", 299),
        ("built_up_area_sqft", "about 2000"),
        ("setbacks", {"FRONT": 10}),
        ("setbacks", {"FRONT": 10, "BACK": 5, "LEFT": -1, "RIGHT": 3}),
        ("priorities", ["QUALITY", "ON_TIME"]),
        ("priorities", ["QUALITY", "QUALITY", "ON_TIME", "SIMILAR_HOMES"]),
        ("services_needed", ["MATERIAL_SUPPLY"]),
        ("notes", "x" * 501),
        ("basement", "yes"),
        ("uploads", ["file"]),
        ("funding_source", "SAVINGS"),
    ],
)
def test_malformed_or_unknown_answers_are_rejected(key: str, value: Any) -> None:
    # A rectangular plot makes the plot-side questions visible.
    answers = {"plot_is_rectangular": True, key: value}
    errors = validate_answers(DEFINITION, answers, complete=False)[1]
    assert key in errors


def test_built_up_area_accepts_not_sure() -> None:
    assert validate_answers(DEFINITION, {"built_up_area_sqft": "NOT_SURE"}, complete=False)[1] == {}


def test_hidden_answers_are_dropped() -> None:
    answers = {**COMPLETE, "property_type_other": "a temple", "plot_area_sqft": 2400}
    cleaned, errors = validate_answers(DEFINITION, answers, complete=True)
    assert errors == {}
    assert "property_type_other" not in cleaned  # only shown for Other
    assert "plot_area_sqft" not in cleaned  # only shown for a non-rectangular plot


def test_other_property_type_requires_its_description() -> None:
    errors = validate_answers(DEFINITION, {**COMPLETE, "property_type": "OTHER"}, complete=True)[1]
    assert "property_type_other" in errors


def test_an_irregular_plot_requires_its_area_instead_of_sides() -> None:
    answers = {**COMPLETE, "plot_is_rectangular": False}
    del answers["plot_width_ft"], answers["plot_depth_ft"]
    errors = validate_answers(DEFINITION, answers, complete=True)[1]
    assert list(errors) == ["plot_area_sqft"]


@pytest.mark.parametrize(
    ("changes", "flags"),
    [
        ({}, []),
        ({"property_type": "OTHER", "property_type_other": "a hostel"}, ["PROPERTY_TYPE_OTHER"]),
        ({"construction_started": True}, ["CONSTRUCTION_STARTED"]),
        ({"start_timeline": "ALREADY_STARTED"}, ["CONSTRUCTION_STARTED"]),
        ({"budget_band": "UNDER_40L"}, []),  # budget never flags or rejects (R-5)
    ],
)
def test_review_flags(changes: dict[str, Any], flags: list[str]) -> None:
    cleaned, errors = validate_answers(DEFINITION, {**COMPLETE, **changes}, complete=True)
    assert errors == {}
    assert review_flags(DEFINITION, cleaned) == flags


async def test_the_active_set_is_served_publicly(client_for: ClientFactory) -> None:
    response = await client_for(Audience.IHB).get("/api/v1/public/requirement-questions")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert [q["key"] for q in body["questions"]] == [q.key for q in DEFINITION.questions]
