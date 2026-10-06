"""The independent validator, deterministic repair and typed operations (Checkpoint 1, sections
G, M; CP1-11). Every negative-corpus defect is caught with its own code, tied to the entities a
UI would highlight; every golden plan passes."""

import copy
from typing import Any

import pytest

from p2b.core.vocabulary import PlanOpKind, RoomType, ValidationCode
from p2b.houseplans.engine import HousePlan, apply, repair, sha256_of, validate
from p2b.houseplans.engine.ops import (
    PLAN_OP,
    MoveOpening,
    MoveWall,
    OperationRejected,
    RenameRoom,
    SetRoomType,
)
from tests.houseplans_support import (
    NEGATIVE_CASES,
    NegativeCase,
    golden_plan,
    intent_for,
    ruleset,
    valid_cases,
)

BASE = "3bhk_40x65_east"


def broken(case: NegativeCase) -> dict[str, Any]:
    plan: dict[str, Any] = copy.deepcopy(golden_plan(BASE)["plan"])
    case.mutate(plan)
    return plan


@pytest.mark.parametrize("name", valid_cases())
def test_every_golden_plan_passes(name: str) -> None:
    report = validate(golden_plan(name)["plan"], ruleset(), intent=intent_for(name))
    assert report.valid, [e.message for e in report.errors]
    assert report.errors == []
    assert ValidationCode.ROOM_OVERLAP in report.checks_run


@pytest.mark.parametrize("case", NEGATIVE_CASES, ids=lambda c: c.name)
def test_negative_corpus(case: NegativeCase) -> None:
    report = validate(broken(case), ruleset(), intent=intent_for(BASE))
    codes = {e.code for e in report.errors}
    assert not report.valid
    assert case.expected <= codes, f"{case.defect}: missing {case.expected - codes}"
    assert codes <= case.expected | case.allowed, (
        f"{case.defect}: unexpected {codes - case.expected - case.allowed}"
    )
    for error in report.errors:  # machine-readable and highlightable
        assert error.entities
        assert error.message_key.startswith("houseplans.validation.")
        assert error.message
        assert "{" not in error.message


def test_the_reported_image_generation_failures_name_their_entities() -> None:
    by_name = {c.name: c for c in NEGATIVE_CASES}
    wc = validate(broken(by_name["wc_in_living"]), ruleset())
    error = next(e for e in wc.errors if e.code == ValidationCode.FIXTURE_NOT_PERMITTED_IN_ROOM)
    assert {(e.kind.value, e.id) for e in error.entities} == {
        ("FIXTURE", "wc_western_living"),
        ("ROOM", "living"),
    }
    assert error.params == {"fixture_type": "WC_WESTERN", "room_type": "LIVING"}

    three = validate(broken(by_name["duplicate_wc"]), ruleset())
    error = next(e for e in three.errors if e.code == ValidationCode.FIXTURE_COUNT_EXCEEDS_SPEC)
    assert error.params["count"] == 3
    assert error.params["limit"] == 1
    assert {e.id for e in error.entities} == {"bath_common_1", "extra_wc_0", "extra_wc_1"}

    overlap = validate(broken(by_name["room_overlap"]), ruleset())
    error = next(e for e in overlap.errors if e.code == ValidationCode.ROOM_OVERLAP)
    assert {e.id for e in error.entities} == {"bedroom_1", "bath_attached_1"}
    assert isinstance(error.params["overlap_mm2"], int)
    assert error.params["overlap_mm2"] > 0


def test_bad_input_is_a_report_never_an_exception() -> None:
    report = validate({"meta": {}, "anything": 1}, ruleset())
    assert not report.valid
    assert {e.code for e in report.errors} == {ValidationCode.SCHEMA_INVALID}


def test_reports_are_deterministic() -> None:
    plan = broken(NEGATIVE_CASES[0])
    assert validate(plan, ruleset()) == validate(copy.deepcopy(plan), ruleset())


def test_a_room_below_the_ruleset_minimum_is_caught() -> None:
    rules = ruleset()
    stricter = rules.model_copy(
        update={
            "rooms": {
                **rules.rooms,
                RoomType.BEDROOM: rules.rooms[RoomType.BEDROOM].model_copy(
                    update={"min_area_mm2": 40_000_000}
                ),
            }
        }
    )
    report = validate(golden_plan(BASE)["plan"], stricter)
    assert {e.code for e in report.errors} == {ValidationCode.ROOM_BELOW_MIN_AREA}
    assert {e.entities[0].id for e in report.errors} == {"bedroom_1", "bedroom_2", "bedroom_3"}


@pytest.mark.parametrize("case", [c for c in NEGATIVE_CASES if c.repairable], ids=lambda c: c.name)
def test_deterministic_repair_fixes_what_it_may_with_typed_operations(case: NegativeCase) -> None:
    plan = HousePlan.model_validate(broken(case))
    result = repair(plan, ruleset(), intent=intent_for(BASE))
    assert result.report.valid, [e.message for e in result.report.errors]
    assert result.applied
    assert all(
        a.op.op in (PlanOpKind.MOVE_OPENING, PlanOpKind.MOVE_FIXTURE) for a in result.applied
    )


@pytest.mark.parametrize(
    "case",
    [c for c in NEGATIVE_CASES if c.name in {"wc_in_living", "room_unreachable"}],
    ids=lambda c: c.name,
)
def test_repair_never_changes_requirements(case: NegativeCase) -> None:
    plan = HousePlan.model_validate(broken(case))
    result = repair(plan, ruleset(), intent=intent_for(BASE))
    assert not result.report.valid  # left for the homeowner: no fixture removed, no door invented
    assert result.applied == []
    assert result.plan == plan


def test_operations_apply_and_invert_exactly() -> None:
    plan = HousePlan.model_validate(golden_plan(BASE)["plan"])
    before = sha256_of(plan.body())
    door = next(o for o in plan.floors[0].openings if o.kind.value == "DOOR")
    for op in (
        MoveOpening(opening=door.id, offset_mm=door.offset_mm + 50),
        RenameRoom(room="bedroom_1", name="Grandparents' room"),
        SetRoomType(room="puja", type="STORE"),
    ):
        changed, inverse = apply(plan, op)
        assert sha256_of(changed.body()) != before
        restored, _ = apply(changed, inverse)
        assert sha256_of(restored.body()) == before


def test_operations_are_a_closed_typed_contract() -> None:
    op = PLAN_OP.validate_python(
        {"op": "MOVE_OPENING", "opening": "door_bedroom_2", "offset_mm": 300}
    )
    assert isinstance(op, MoveOpening)
    with pytest.raises(ValueError, match="extra"):
        PLAN_OP.validate_python({"op": "MOVE_OPENING", "opening": "d", "offset_mm": 1, "x": 5})
    plan = HousePlan.model_validate(golden_plan(BASE)["plan"])
    with pytest.raises(OperationRejected, match="editing checkpoint"):
        apply(plan, MoveWall(wall="w1", delta_mm=100))
    with pytest.raises(OperationRejected, match="unknown entity"):
        apply(plan, RenameRoom(room="no_such_room", name="x"))


def test_the_synthetic_ruleset_has_no_citations_and_publication_would_need_them() -> None:
    from p2b.houseplans.engine import missing_citations
    from p2b.houseplans.engine.ruleset import Citation, value_pointers

    rules = ruleset()
    assert rules.synthetic is True
    assert missing_citations(rules) == value_pointers(rules)  # nothing here is a sourced value
    cited = rules.model_copy(
        update={"sources": {"/walls": Citation(document="example", clause="1")}}
    )
    assert not any(
        p.startswith("/walls/") for p in missing_citations(cited)
    )  # a parent covers its values
    assert any(p.startswith("/rooms/") for p in missing_citations(cited))
