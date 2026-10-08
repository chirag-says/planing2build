"""Checkpoint 2 engine: zoning, the constraint compiler, the zoned local search, the Scorer, the
feasibility classes, candidate fallback and repair (AI_DESIGN_ENGINE_CHECKPOINT_2)."""

import importlib
import random
from collections.abc import Callable
from typing import Any

import pytest

from p2b.core.vocabulary import (
    ConstraintOutcome,
    ConstraintStrength,
    FeasibilityClass,
    InfeasibleReason,
    OriginKind,
    RepairReason,
    SolverKind,
    TopologyFamily,
    ValidationCode,
)
from p2b.houseplans.engine import (
    DeterministicMVPLayoutSolver,
    HousePlan,
    ZonedLocalSearchSolver,
    fixture_fit,
    generate,
    repair,
    score_plan,
    sha256_of,
    validate,
)
from p2b.houseplans.engine.compile import ZonedProblem
from p2b.houseplans.engine.derive import analyse
from p2b.houseplans.engine.feasibility import MESSAGE_NO_SUPPORTED_LAYOUT, precheck
from p2b.houseplans.engine.footprint import clear_rect, room_insets
from p2b.houseplans.engine.generate import compile_problem
from p2b.houseplans.engine.model import dump
from p2b.houseplans.engine.objective import plan_facts, score
from p2b.houseplans.engine.place import PlacementFailure
from p2b.houseplans.engine.solver import InfeasibleDetail, LayoutProblem
from p2b.houseplans.engine.solver.zoned_ls import search
from p2b.houseplans.engine.zoning import Context, _splits, select, zoning_inputs
from p2b.houseplans.service import solver_for
from tests.houseplans_support import (
    SEED,
    generate_zoned,
    golden_plan,
    intent_for,
    ruleset,
    ruleset_cp1,
    ruleset_cp1_sha,
    ruleset_sha,
    valid_cases,
)

# The package re-exports the function `generate`, which shadows the module of the same name.
generate_module = importlib.import_module("p2b.houseplans.engine.generate")
FEASIBLE = ("3bhk_40x65_east", "2bhk_30x50_north", "2bhk_40x80_west_two_cars")


def problem_for(name: str) -> LayoutProblem:
    problem = compile_problem(intent_for(name, ruleset()), ruleset())
    if not isinstance(problem, LayoutProblem):
        raise AssertionError(problem)
    return problem


# ---------- the Checkpoint 1 contract is untouched ----------


def test_the_frozen_cp1_ruleset_still_hashes_as_in_checkpoint_1() -> None:
    for name in valid_cases():
        recorded = golden_plan(name)["plan"]["meta"]["generator"]["ruleset_sha256"]
        assert ruleset_cp1_sha() == recorded


def test_the_mvp_solver_still_emits_schema_1_0_without_soft_terms() -> None:
    result = generate(
        intent_for("3bhk_40x65_east"),
        ruleset_cp1(),
        ruleset_version=1,
        ruleset_sha256=ruleset_cp1_sha(),
        solver=DeterministicMVPLayoutSolver(),
        seed=SEED,
    )
    assert result.plan is not None
    assert result.plan.meta.schema_version == "1.0.0"
    assert {c.strength for c in result.plan.constraints} == {ConstraintStrength.HARD}
    assert "score_milli" not in str(dump(result.plan))


# ---------- zoning ----------


def test_topology_selection_is_bounded_deterministic_and_unique() -> None:
    problem, rules = problem_for("3bhk_40x65_east"), ruleset()
    fit = fixture_fit(rules)
    first, second = select(problem, rules, fit), select(problem, rules, fit)
    assert [t.name for t in first.topologies] == [t.name for t in second.topologies]
    assert len({t.name for t in first.topologies}) == len(first.topologies)
    assert len({(t.tree, t.access, t.opens) for t in first.topologies}) == len(first.topologies)
    assert {t.family for t in first.topologies} >= {
        TopologyFamily.SPINE,
        TopologyFamily.FRONT_EXTENSION,
    }
    assert len(first.topologies) <= 400


def test_splits_that_only_swap_rooms_of_the_same_type_are_dropped() -> None:
    problem, rules = problem_for("3bhk_40x65_east"), ruleset()
    ctx = Context(problem, rules, fixture_fit(rules))
    groups = list(ctx.inp.groups)
    splits = _splits(ctx, groups, 1, (ctx.w // 2, ctx.w // 2), 64)
    shapes = [
        tuple(
            tuple(tuple(ctx.inp.rooms[k].room_type for k in g.keys) for g in col) for col in split
        )
        for split in splits
    ]
    assert len(shapes) == len(set(shapes))


# ---------- the compiler and the Scorer agree ----------


@pytest.mark.parametrize("name", FEASIBLE)
def test_the_compiled_evaluator_equals_the_shortfalls_and_the_scorer(name: str) -> None:
    problem, rules = problem_for(name), ruleset()
    fit = fixture_fit(rules)
    inputs = zoning_inputs(problem)
    rng = random.Random(7)  # noqa: S311 (test data, not security)
    checked = 0
    topologies = select(problem, rules, fit).topologies
    # one topology of every family, so open areas, corridors and wings are all exercised
    sample = list({t.family: t for t in reversed(topologies)}.values())
    for topology in sample:
        zp = ZonedProblem(problem, rules, topology, fit, inputs)
        base = zp.initial()
        for _ in range(60):
            values = tuple(v + rng.randint(-8, 8) * rules.grid_mm for v in base)
            got = zp.evaluate(values)
            if zp.rects(values) is None:
                assert got is None
                continue
            expected = (
                sum(s.amount for s in zp.shortfalls(values)),
                score(zp.facts(values), rules, sizing_only=True).total,
            )
            assert got == expected, topology.name
            checked += 1
    assert checked > 100


@pytest.mark.parametrize("name", FEASIBLE)
def test_the_solver_score_is_the_built_plan_score(name: str) -> None:
    rules = ruleset()
    result = generate_zoned(name)
    assert result.outcome == "VALID"
    assert result.plan is not None
    found = search(problem_for(name), rules, fixture_fit(rules))
    chosen = next(c for c in found.feasible if c.name == result.topology)
    built = score_plan(result.plan, rules)
    assert chosen.quality is not None
    assert built is not None
    assert result.quality == built
    assert chosen.quality.total == built.total
    assert [t.score_milli for t in chosen.quality.terms] == [t.score_milli for t in built.terms]


@pytest.mark.parametrize("name", FEASIBLE)
def test_solver_clear_rectangles_equal_the_validators(name: str) -> None:
    rules = ruleset()
    plan = generate_zoned(name).plan
    assert plan is not None
    facts = plan_facts(plan, rules)
    assert facts is not None
    enclosed = {k: rules.rooms[t].enclosed for k, t in facts.types.items()}
    insets = room_insets(
        facts.rects,
        enclosed,
        facts.region,
        exterior_mm=rules.walls.exterior_mm,
        interior_mm=rules.walls.interior_mm,
    )
    derived = analyse(plan).clear_rects
    for key, rect in facts.rects.items():
        assert clear_rect(rect, insets[key]) == derived[key], key


# ---------- the zoned pipeline ----------


@pytest.mark.parametrize("name", FEASIBLE)
def test_zoned_generation_is_valid_scored_and_deterministic(name: str) -> None:
    first, second = generate_zoned(name), generate_zoned(name)
    assert first.outcome == "VALID"
    assert first.plan is not None
    assert second.plan is not None
    assert first.plan.meta.body_sha256 == second.plan.meta.body_sha256
    assert first.plan.meta.schema_version == "1.1.0"
    assert first.plan.meta.generator.solver == SolverKind.ZONED_LOCAL_SEARCH
    assert validate(first.plan, ruleset(), intent=intent_for(name, ruleset())).valid
    soft = [c for c in first.plan.constraints if c.strength == ConstraintStrength.SOFT]
    assert len(soft) == 14  # 13 in Checkpoint 2.1; Checkpoint 2.2 added ROOM_SIZE_OUTLIER
    assert all(c.origin.kind == OriginKind.RULESET for c in soft)
    assert all(c.origin.ref == f"ruleset:objective.weights.{c.kind.value}" for c in soft)
    orientation = next(c for c in soft if c.kind.value == "ORIENTATION")
    assert orientation.outcome == ConstraintOutcome.NOT_EVALUATED
    assert orientation.score_milli is None
    hard = [c for c in first.plan.constraints if c.strength == ConstraintStrength.HARD]
    assert {c.outcome for c in hard} == {ConstraintOutcome.MET}


def test_the_search_ranking_is_deterministic() -> None:
    rules = ruleset()
    fit = fixture_fit(rules)
    runs = [search(problem_for("3bhk_40x65_east"), rules, fit) for _ in range(2)]
    ranked = [[(c.name, c.values, c.quality) for c in r.feasible] for r in runs]
    assert ranked[0] == ranked[1]
    totals = [c.quality.total for c in runs[0].feasible if c.quality]
    assert totals == sorted(totals)


def test_a_layout_that_fails_to_build_falls_back_to_the_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rules = ruleset()
    best = search(problem_for("3bhk_40x65_east"), rules, fixture_fit(rules)).feasible
    real: Callable[..., HousePlan] = generate_module.build_plan
    refused = best[0].name

    def refuse_first(placed: Any, ctx: Any) -> HousePlan:
        if placed.topology == refused:
            raise PlacementFailure(InfeasibleDetail(InfeasibleReason.FIXTURE_FIT, {"room": "x"}))
        return real(placed, ctx)

    monkeypatch.setattr(generate_module, "build_plan", refuse_first)
    result = generate_zoned("3bhk_40x65_east")
    assert result.outcome == "VALID"
    assert result.topology == best[1].name
    assert [(a.topology, a.result) for a in result.attempts] == [
        (refused, "PLACEMENT"),
        (best[1].name, "VALID"),
    ]


# ---------- feasibility ----------


def test_an_impossible_programme_is_proven_with_an_explanation_in_metres() -> None:
    result = generate_zoned("3bhk_20x30_too_small")
    assert result.outcome == "INFEASIBLE"
    report = result.feasibility
    assert report is not None
    assert report.classification == FeasibilityClass.PROVEN
    assert report.code == InfeasibleReason.AREA_BUDGET
    assert " m by " in report.explanation
    assert "cannot fit in any arrangement" in report.explanation
    assert report.message_key == "houseplans.infeasible.proven"
    assert any(c.kind == "INSIDE_ENVELOPE" for c in report.constraints)


def test_no_supported_layout_never_claims_impossible() -> None:
    result = generate_zoned("2bhk_30x60_two_cars_too_wide")
    assert result.outcome == "INFEASIBLE"
    report = result.feasibility
    assert report is not None
    assert report.classification == FeasibilityClass.NO_SUPPORTED_LAYOUT
    assert report.message == MESSAGE_NO_SUPPORTED_LAYOUT  # CP2-U4, approved wording
    assert "does not mean the home is impossible" in report.explanation
    assert "cannot fit in any arrangement" not in report.explanation
    assert result.candidates_sized > 0


@pytest.mark.parametrize("name", valid_cases())
def test_the_precheck_never_rejects_a_programme_a_solver_can_build(name: str) -> None:
    for rules in (ruleset(), ruleset_cp1()):
        assert precheck(intent_for(name, rules), rules) is None


def test_the_service_falls_back_to_the_cp1_solver_without_an_objective() -> None:
    assert solver_for("ZONED_LOCAL_SEARCH", ruleset()).kind == SolverKind.ZONED_LOCAL_SEARCH
    assert solver_for("ZONED_LOCAL_SEARCH", ruleset_cp1()).kind == SolverKind.DETERMINISTIC_MVP
    assert solver_for("DETERMINISTIC_MVP", ruleset()).kind == SolverKind.DETERMINISTIC_MVP


def test_the_zoned_solver_face_returns_the_best_layout() -> None:
    rules = ruleset()
    solver = ZonedLocalSearchSolver(rules, fixture_fit(rules))
    placed = solver.solve(problem_for("2bhk_30x50_north"), seed=SEED)
    best = search(problem_for("2bhk_30x50_north"), rules, fixture_fit(rules)).feasible[0]
    assert getattr(placed, "topology", None) == best.name
    assert ruleset_sha() == sha256_of(rules)


# ---------- repair ----------


def broken(plan: HousePlan, edit: Any) -> HousePlan:
    data = dump(plan)
    edit(data["floors"][0], analyse(plan))
    return HousePlan.model_validate(data)


def test_overlapping_openings_are_separated_by_sliding_the_later_one() -> None:
    name = "3bhk_40x65_east"
    plan = generate_zoned(name).plan
    assert plan is not None

    def overlap(floor: dict[str, Any], an: Any) -> None:
        by_wall: dict[str, list[dict[str, Any]]] = {}
        for o in floor["openings"]:
            by_wall.setdefault(o["wall"], []).append(o)
        pair = sorted(next(v for v in by_wall.values() if len(v) > 1), key=lambda o: o["id"])
        pair[1]["offset_mm"] = pair[0]["offset_mm"]

    bad = broken(plan, overlap)
    intent = intent_for(name, ruleset())
    before = validate(bad, ruleset(), intent=intent)
    assert ValidationCode.OPENING_OVERLAP in {i.code for i in before.errors}
    fixed = repair(bad, ruleset(), intent=intent)
    assert fixed.report.valid
    assert ValidationCode.OPENING_OVERLAP in {a.code for a in fixed.applied}
    assert {a.reason for a in fixed.applied} == {RepairReason.VALIDATION_ERROR}


def test_a_fixture_blocking_a_door_moves_to_a_clear_slot() -> None:
    name = "3bhk_40x65_east"
    plan = generate_zoned(name).plan
    assert plan is not None

    def block(floor: dict[str, Any], an: Any) -> None:
        # a fitting moved onto the wall and position of a door into its own room
        for fixture in sorted(floor["fixtures"], key=lambda f: f["id"]):
            for door in sorted(floor["openings"], key=lambda o: o["id"]):
                wall = an.walls[door["wall"]]
                if door["kind"] != "DOOR" or not wall.orthogonal:
                    continue
                if fixture["room"] in wall.left_rooms:
                    side = "LEFT"
                elif fixture["room"] in wall.right_rooms:
                    side = "RIGHT"
                else:
                    continue
                fixture |= {"wall": door["wall"], "side": side, "offset_mm": door["offset_mm"]}
                return
        raise AssertionError("no fitting shares a room with a door")

    bad = broken(plan, block)
    intent = intent_for(name, ruleset())
    codes = {i.code for i in validate(bad, ruleset(), intent=intent).errors}
    assert codes & {ValidationCode.FIXTURE_BLOCKS_OPENING, ValidationCode.FIXTURE_OUTSIDE_ROOM}
    fixed = repair(bad, ruleset(), intent=intent)
    assert fixed.report.valid
    assert fixed.applied
    # Repair moved hosted elements only: rooms, walls and counts are unchanged.
    after, original = fixed.plan.floors[0], plan.floors[0]
    assert after.rooms == original.rooms
    assert after.walls == original.walls
    assert len(after.fixtures) == len(original.fixtures)
