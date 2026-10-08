"""Requirement normalisation (Checkpoint 1, section F): RQ v1 answers plus provisional design
inputs become an ArchitecturalIntent, deterministically, and never by guessing."""

from typing import Any

import pytest

from p2b.core.vocabulary import (
    DesignInputKey,
    Facing,
    MissingInputReason,
    OrientationMode,
    OriginKind,
    RelationKind,
    RoomType,
    SetbackSide,
    UnsupportedReason,
)
from p2b.houseplans.engine import (
    DesignInputs,
    InputConflict,
    NeedsInput,
    Normalised,
    Unsupported,
    normalise,
)
from p2b.houseplans.engine.intent import north_angle
from tests.houseplans_support import cases, ruleset, ruleset_sha


def run(answers: dict[str, Any], inputs: dict[str, Any] | None, qsv: int = 1) -> object:
    return normalise(
        answers,
        DesignInputs.model_validate(inputs) if inputs is not None else None,
        ruleset(),
        question_set_version=qsv,
        requirement_version=3,
        ruleset_version=1,
        ruleset_sha256=ruleset_sha(),
    )


def base() -> tuple[dict[str, Any], dict[str, Any]]:
    case = cases()["3bhk_40x65_east"]
    return dict(case["answers"]), dict(case["design_inputs"])


def test_the_prototype_requirement_becomes_its_exact_programme() -> None:
    answers, inputs = base()
    out = run(answers, inputs)
    assert isinstance(out, Normalised)
    intent = out.intent
    assert [(p.key, p.room_type) for p in intent.programme] == [
        ("living", RoomType.LIVING),
        ("kitchen", RoomType.KITCHEN),
        ("dining", RoomType.DINING),
        ("puja", RoomType.PUJA),
        ("parking", RoomType.PARKING),
        ("bedroom_1", RoomType.BEDROOM),
        ("bedroom_2", RoomType.BEDROOM),
        ("bedroom_3", RoomType.BEDROOM),
        ("bath_attached_1", RoomType.BATH_ATTACHED),
        ("bath_common_1", RoomType.BATH_COMMON),
    ]
    # Living and kitchen come from ruleset data (CP1-09), the rest from answers and inputs.
    assert intent.programme[0].origin.kind == OriginKind.RULESET
    assert intent.programme[5].origin.kind == OriginKind.REQUIREMENT
    assert [(r.room, r.host, r.kind) for r in intent.relations] == [
        ("kitchen", "dining", RelationKind.ADJACENT_WITH_DOOR),
        ("bath_attached_1", "bedroom_1", RelationKind.ADJACENT_WITH_DOOR),
    ]
    assert intent.site.frontage_mm == 12192
    assert intent.site.depth_mm == 19812
    assert intent.site.setbacks_mm == {
        SetbackSide.FRONT: 1829,
        SetbackSide.BACK: 1219,
        SetbackSide.LEFT: 914,
        SetbackSide.RIGHT: 914,
    }
    assert intent.orientation == OrientationMode.SOFT
    assert intent.parking is not None
    assert intent.parking.spaces == 1
    assert intent.sources.design_inputs_sha256 is not None


@pytest.mark.parametrize(
    ("facing", "angle"),
    [
        (Facing.S, 0),
        (Facing.SW, 315),
        (Facing.W, 270),
        (Facing.NW, 225),
        (Facing.N, 180),
        (Facing.NE, 135),
        (Facing.E, 90),
        (Facing.SE, 45),
    ],
)
def test_north_angle_from_the_road_side(facing: Facing, angle: int) -> None:
    assert north_angle(facing) == angle


def test_the_inputs_may_correct_the_facing_and_say_so() -> None:
    answers, inputs = base()
    out = run(answers, {**inputs, "facing_override": "N"})
    assert isinstance(out, Normalised)
    assert out.intent.site.facing == Facing.N
    assert out.intent.site.facing_origin.kind == OriginKind.DESIGN_INPUT


def test_not_sure_setbacks_need_input_and_inputs_fill_only_those() -> None:
    answers, inputs = base()
    answers["setbacks"] = {"FRONT": 6, "BACK": "NOT_SURE", "LEFT": 3, "RIGHT": 3}
    out = run(answers, inputs)
    assert isinstance(out, NeedsInput)
    assert [(m.key, m.reason) for m in out.missing] == [
        (DesignInputKey.SETBACK_BACK, MissingInputReason.NOT_SURE)
    ]
    filled = run(answers, {**inputs, "setbacks_ft": {"BACK": 4}})
    assert isinstance(filled, Normalised)
    conflict = run(answers, {**inputs, "setbacks_ft": {"BACK": 4, "FRONT": 9}})
    assert isinstance(conflict, InputConflict)  # a provisional input never replaces an answer
    assert conflict.keys == (DesignInputKey.SETBACK_FRONT,)


def test_missing_inputs_are_listed_not_guessed() -> None:
    answers, _ = base()
    out = run(
        answers, {"parking_spaces": 1, "parking_kind": "CAR", "stair": "NONE", "utility": False}
    )
    assert isinstance(out, NeedsInput)
    assert {m.key for m in out.missing} == {
        DesignInputKey.ATTACHED_BATHROOMS,
        DesignInputKey.DINING,
        DesignInputKey.KITCHEN,
    }
    assert isinstance(run({**answers, "facing": "NOT_SURE"}, base()[1]), NeedsInput)


def test_out_of_range_attached_bathrooms() -> None:
    answers, inputs = base()
    out = run(answers, {**inputs, "attached_bathrooms": 3})
    assert isinstance(out, NeedsInput)
    assert out.missing[0].reason == MissingInputReason.OUT_OF_RANGE


@pytest.mark.parametrize(
    ("change", "inputs_change", "reason"),
    [
        ({"plot_is_rectangular": False}, {}, UnsupportedReason.PLOT_NOT_RECTANGULAR),
        ({"floors": "G_PLUS_1"}, {}, UnsupportedReason.FLOORS_NOT_SUPPORTED),
        ({"basement": True}, {}, UnsupportedReason.BASEMENT_NOT_SUPPORTED),
        ({}, {"stair": "INTERNAL"}, UnsupportedReason.STAIR_NOT_YET_SUPPORTED),
        ({"bedrooms": "seven"}, {}, UnsupportedReason.ANSWER_INVALID),
    ],
)
def test_unsupported_cases_are_refused(
    change: dict[str, Any], inputs_change: dict[str, Any], reason: UnsupportedReason
) -> None:
    answers, inputs = base()
    out = run({**answers, **change}, {**inputs, **inputs_change})
    assert isinstance(out, Unsupported)
    assert reason in out.reasons


def test_an_unknown_question_set_is_refused() -> None:
    answers, inputs = base()
    out = run(answers, inputs, qsv=2)
    assert isinstance(out, Unsupported)
    assert out.reasons == (UnsupportedReason.QUESTION_SET_NOT_SUPPORTED,)


def test_five_plus_needs_the_exact_number_and_the_exact_number_is_only_for_five_plus() -> None:
    answers, inputs = base()
    out = run({**answers, "bedrooms": "5_PLUS"}, inputs)
    assert isinstance(out, NeedsInput)
    assert out.missing[0].key == DesignInputKey.BEDROOMS_EXACT
    assert isinstance(run(answers, {**inputs, "bedrooms_exact": 6}), InputConflict)


def test_parking_inputs_without_parking_conflict() -> None:
    answers, inputs = base()
    out = run({**answers, "car_parking": False}, inputs)
    assert isinstance(out, InputConflict)


def test_normalisation_is_deterministic() -> None:
    answers, inputs = base()
    first, second = run(answers, inputs), run(answers, inputs)
    assert isinstance(first, Normalised)
    assert isinstance(second, Normalised)
    assert first.intent == second.intent


def test_provisional_inputs_are_marked_and_versioned() -> None:
    inputs = DesignInputs()
    assert inputs.kind == "PROVISIONAL_DESIGN_INPUTS"
    assert inputs.version == 1
    with pytest.raises(ValueError, match="extra"):
        DesignInputs.model_validate({"bedrooms": "3"})  # not a second requirement form
