"""The LayoutSolver interface and the DeterministicMVPLayoutSolver (Checkpoint 1, section J)."""

from itertools import combinations

import pytest

from p2b.core.vocabulary import InfeasibleReason
from p2b.houseplans.engine import DeterministicMVPLayoutSolver, LayoutSolver
from p2b.houseplans.engine.generate import compile_problem
from p2b.houseplans.engine.solver import Infeasible, LayoutProblem, Placed
from tests.houseplans_support import cases, generate_case, intent_for, ruleset, valid_cases


def problem_for(name: str) -> LayoutProblem:
    problem = compile_problem(intent_for(name), ruleset())
    assert isinstance(problem, LayoutProblem)
    return problem


def test_the_mvp_solver_satisfies_the_solver_interface() -> None:
    solver: LayoutSolver = DeterministicMVPLayoutSolver()
    assert solver.kind.value == "DETERMINISTIC_MVP"


@pytest.mark.parametrize("name", valid_cases())
def test_rooms_tile_the_region_exactly_with_no_overlap(name: str) -> None:
    problem = problem_for(name)
    placed = DeterministicMVPLayoutSolver().solve(problem, seed=1)
    assert isinstance(placed, Placed)
    assert placed.topology == cases()[name]["topology"]
    rects = list(placed.rects.values())
    assert all(problem.region.contains(r) for r in rects)
    assert all(a.overlap_area(b) == 0 for a, b in combinations(rects, 2))
    assert sum(r.area for r in rects) == problem.region.area
    # every room is entered from somewhere, and the passage from the entry room
    entered = {a.room for a in placed.access}
    assert entered | {placed.entry_room} | {k for k in placed.rects if k == "parking"} == set(
        placed.rects
    )


@pytest.mark.parametrize("name", valid_cases())
def test_the_solver_is_deterministic(name: str) -> None:
    problem = problem_for(name)
    assert DeterministicMVPLayoutSolver().solve(
        problem, seed=1
    ) == DeterministicMVPLayoutSolver().solve(problem, seed=99)


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("3bhk_20x30_too_small", InfeasibleReason.AREA_BUDGET),
        ("2bhk_30x60_two_cars_too_wide", InfeasibleReason.PARKING_TOO_WIDE),
    ],
)
def test_an_impossible_programme_is_infeasible_with_the_arithmetic(
    name: str, reason: InfeasibleReason
) -> None:
    outcome = DeterministicMVPLayoutSolver().solve(problem_for(name), seed=1)
    assert isinstance(outcome, Infeasible)
    detail = outcome.reasons[0]
    assert detail.code == reason
    numbers = {k: v for k, v in detail.params.items() if k.endswith(("_mm", "_mm2"))}
    assert numbers, "the reason states the shortfall in millimetres"
    result = generate_case(name)
    assert result.outcome == "INFEASIBLE"
    assert result.plan is None  # never a plan for an impossible programme


def test_infeasible_reasons_name_every_layout_tried() -> None:
    problem = problem_for("2bhk_30x50_north")
    squeezed = LayoutProblem(**{**problem.__dict__, "door_span_mm": 50_000})
    outcome = DeterministicMVPLayoutSolver().solve(squeezed, seed=1)
    assert isinstance(outcome, Infeasible)
    assert [r.params["topology"] for r in outcome.reasons] == [
        "two_columns_centre_spine",
        "one_column_spine_right",
        "one_column_spine_left",
    ]


def test_a_ruleset_without_the_needed_rules_is_infeasible_not_guessed() -> None:
    rules = ruleset()
    rooms = {k: v for k, v in rules.rooms.items() if k.value != "BEDROOM"}
    incomplete = rules.model_copy(update={"rooms": rooms})
    outcome = compile_problem(intent_for("2bhk_30x50_north"), incomplete)
    assert isinstance(outcome, Infeasible)
    assert outcome.reasons[0].code == InfeasibleReason.RULESET_INCOMPLETE
