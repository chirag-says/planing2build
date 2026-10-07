"""Checkpoint 2.1: topology families and their selection, slicing layouts, open areas, door-aware
fixture fit, the entry room's front wall, the new Scorer terms, and the regressions fixed on the
way (AI_DESIGN_ENGINE_CHECKPOINT_2_1_REPORT)."""

from typing import Any

import pytest

from p2b.core.vocabulary import RoomType, TopologyFamily, ValidationCode
from p2b.houseplans.engine import (
    GenerationResult,
    HousePlan,
    ZonedLocalSearchSolver,
    fixture_fit,
    score_plan,
    validate,
)
from p2b.houseplans.engine.build import BuildContext, build_plan
from p2b.houseplans.engine.compile import side_runs, window_gap
from p2b.houseplans.engine.derive import analyse
from p2b.houseplans.engine.footprint import exterior_runs, room_insets
from p2b.houseplans.engine.generate import compile_problem
from p2b.houseplans.engine.geom import Rect
from p2b.houseplans.engine.layout_tree import (
    Leaf,
    Part,
    boxes,
    compile_tree,
    initial_values,
    xs,
    ys,
)
from p2b.houseplans.engine.model import SCHEMA_VERSION, dump
from p2b.houseplans.engine.objective import LayoutFacts, score
from p2b.houseplans.engine.place import PlacementFailure
from p2b.houseplans.engine.repair import repair
from p2b.houseplans.engine.solver import LayoutProblem
from p2b.houseplans.engine.solver.zoned_ls import search
from p2b.houseplans.engine.zoning import select
from tests.houseplans_support import (
    SEED,
    benchmark_cases,
    generate_zoned_benchmark,
    intent_of,
    ruleset,
)

F = TopologyFamily
# A benchmark case on which each family builds a VALID plan (benchmark family matrix).
FAMILY_CASES = {
    F.SPINE: "2bhk_30x50_north_twowheeler_open",
    F.FRONT_EXTENSION: "3bhk_40x60_north_one_car",
    F.SIDE_WING: "4bhk_40x90_deep_car_utility",
    F.FRONT_LIVING_REAR_BEDROOM: "1bhk_25x40_south_small",
    F.FRONT_PUBLIC_REAR_PRIVATE: "2bhk_40x80_west_two_cars",
    F.L_CIRCULATION: "3bhk_40x65_east_puja",
    F.CENTRAL_LIVING_BEDROOM_WINGS: "4bhk_50x80_large_two_cars",
    F.LINEAR_REAR_CORRIDOR: "prop_very_wide_80x28",
}


def problem_of(name: str) -> LayoutProblem:
    rules = ruleset()
    problem = compile_problem(intent_of(benchmark_cases()[name], rules), rules)
    if not isinstance(problem, LayoutProblem):
        raise AssertionError(problem)
    return problem


def family_plan(name: str, family: TopologyFamily) -> HousePlan | None:
    """The best layout of one family for a case, built, repaired and validated, or None."""
    rules = ruleset()
    intent = intent_of(benchmark_cases()[name], rules)
    fit = fixture_fit(rules)
    found = search(problem_of(name), rules, fit, frozenset({family}))
    ctx = BuildContext(
        intent, rules, 1, "x", ZonedLocalSearchSolver(rules, fit), SEED, SCHEMA_VERSION
    )
    for layout in found.feasible[:5]:
        try:
            plan = build_plan(layout.zp.placed(layout.values), ctx)
        except PlacementFailure:
            continue
        fixed = repair(plan, rules, intent=intent)
        if fixed.report.valid:
            return fixed.plan
    return None


# ---------- topology selection ----------


def test_every_family_gets_a_verdict_with_a_reason() -> None:
    selection = select(problem_of("4bhk_50x80_large_two_cars"), ruleset(), fixture_fit(ruleset()))
    assert {v.family for v in selection.verdicts} == set(F)
    assert all(v.reason for v in selection.verdicts)
    for v in selection.verdicts:
        assert v.applicable == (v.candidates > 0)


def test_a_family_that_cannot_fit_is_rejected_with_the_arithmetic() -> None:
    selection = select(problem_of("1bhk_25x40_south_small"), ruleset(), fixture_fit(ruleset()))
    verdicts = {v.family: v for v in selection.verdicts}
    wings = verdicts[F.CENTRAL_LIVING_BEDROOM_WINGS]
    assert not wings.applicable
    assert " m" in wings.reason
    assert not any(t.family == F.CENTRAL_LIVING_BEDROOM_WINGS for t in selection.topologies)


@pytest.mark.parametrize("family", list(FAMILY_CASES))
def test_each_family_builds_a_valid_plan(family: TopologyFamily) -> None:
    name = FAMILY_CASES[family]
    plan = family_plan(name, family)
    assert plan is not None, (family, name)
    report = validate(plan, ruleset(), intent=intent_of(benchmark_cases()[name], ruleset()))
    assert report.valid


def test_the_winning_family_follows_the_plot() -> None:
    """Different plots get genuinely different topologies, chosen by the Scorer."""
    won = {
        name: generate_zoned_benchmark(name).family
        for name in (
            "1bhk_25x40_south_small",
            "2bhk_40x80_west_two_cars",
            "4bhk_45x75_two_cars_puja",
            "4bhk_50x80_large_two_cars",
            "2bhk_30x50_north_twowheeler_open",
            "prop_very_wide_80x28",
        )
    }
    assert None not in won.values()
    assert len(set(won.values())) >= 5, won


# ---------- plot shapes ----------


def valid(name: str) -> GenerationResult:
    result = generate_zoned_benchmark(name)
    assert result.outcome == "VALID", (name, result.feasibility)
    assert result.plan is not None
    return result


def test_the_small_25x40_plot_is_valid_without_a_corridor() -> None:
    """Regression: Checkpoint 2 returned NO_SUPPORTED_LAYOUT for an expected-feasible case."""
    result = valid("1bhk_25x40_south_small")
    assert result.family == F.FRONT_LIVING_REAR_BEDROOM
    assert result.plan is not None
    assert not any(r.type == RoomType.PASSAGE for r in result.plan.floors[0].rooms)


def test_a_narrow_deep_plot_is_valid() -> None:
    valid("2bhk_22x60_narrow_deep")


def test_wide_shallow_plots_use_a_family_made_for_them() -> None:
    assert valid("prop_wide_60x35").family == F.FRONT_LIVING_REAR_BEDROOM
    assert valid("prop_very_wide_80x28").family == F.LINEAR_REAR_CORRIDOR


def test_a_large_plot_is_not_stretched_to_fill_the_envelope() -> None:
    result = valid("4bhk_50x80_large_two_cars")
    q = result.quality
    assert q is not None
    assert q.aspect_violations <= 3
    oversize = next(t for t in q.terms if t.kind.value == "OVERSIZE")
    assert (oversize.score_milli or 0) < 1000


@pytest.mark.parametrize("name", ["2bhk_40x80_west_two_cars", "3bhk_50x60_wide_two_cars"])
def test_two_car_parking_keeps_the_entrance_and_a_convenient_parking(name: str) -> None:
    result = valid(name)
    q = result.quality
    assert q is not None
    convenience = next(t for t in q.terms if t.kind.value == "PARKING_CONVENIENCE")
    assert convenience.score_milli == 0  # the parking shares a wall with the entry room


def test_kitchen_opens_to_dining_in_every_family() -> None:
    for family, name in FAMILY_CASES.items():
        plan = family_plan(name, family)
        assert plan is not None
        an = analyse(plan)
        pairs = {frozenset(i.connects) for i in an.openings.values()}
        if any(r.id == "dining" for r in plan.floors[0].rooms):
            assert frozenset({"kitchen", "dining"}) in pairs, family


# ---------- the new Scorer terms ----------


def facts(rects: dict[str, Rect], types: dict[str, RoomType], **extra: Any) -> LayoutFacts:
    region = Rect(0, 0, 12000, 12000)
    return LayoutFacts(
        rects=rects, types=types, region=region, entry="living", parking=None, **extra
    )


def term(f: LayoutFacts, kind: str) -> int | None:
    return next(t.score_milli for t in score(f, ruleset()).terms if t.kind.value == kind)


def test_bedroom_grouping_counts_the_rooms_bedrooms_open_off() -> None:
    rects = {
        "living": Rect(0, 0, 6000, 4000),
        "passage": Rect(6000, 0, 7000, 12000),
        "bedroom_1": Rect(0, 4000, 6000, 8000),
        "bedroom_2": Rect(0, 8000, 6000, 12000),
        "bath_attached_1": Rect(7000, 4000, 12000, 8000),
        "store": Rect(7000, 8000, 12000, 12000),
    }
    types = {
        "living": RoomType.LIVING,
        "passage": RoomType.PASSAGE,
        "bedroom_1": RoomType.BEDROOM,
        "bedroom_2": RoomType.BEDROOM,
        "bath_attached_1": RoomType.BATH_ATTACHED,
        "store": RoomType.PUJA,
    }
    del rects["store"], types["store"]
    one_hall = facts(
        rects,
        types,
        links=(
            ("bedroom_1", "passage"),
            ("bedroom_2", "passage"),
            ("bath_attached_1", "bedroom_1"),
        ),
        attached=frozenset({("bath_attached_1", "bedroom_1")}),
    )
    scattered = facts(rects, types, links=(("bedroom_1", "living"), ("bedroom_2", "passage")))
    assert term(one_hall, "BEDROOM_GROUPING") == 0
    assert term(scattered, "BEDROOM_GROUPING") == 1000


def test_zone_order_flags_a_bedroom_in_front_of_the_living_room() -> None:
    types = {"living": RoomType.LIVING, "bedroom_1": RoomType.BEDROOM}
    behind = facts(
        {"living": Rect(0, 0, 6000, 4000), "bedroom_1": Rect(0, 4000, 6000, 8000)}, types
    )
    ahead = facts({"bedroom_1": Rect(0, 0, 6000, 4000), "living": Rect(0, 4000, 6000, 8000)}, types)
    assert term(behind, "ZONE_ORDER") == 0
    assert term(ahead, "ZONE_ORDER") == 1000


def test_an_attached_bathroom_behind_its_bedroom_is_not_a_zone_order_break() -> None:
    types = {"bedroom_1": RoomType.BEDROOM, "bath_attached_1": RoomType.BATH_ATTACHED}
    rects = {"bedroom_1": Rect(0, 0, 6000, 4000), "bath_attached_1": Rect(0, 4000, 6000, 6000)}
    with_relation = facts(rects, types, attached=frozenset({("bath_attached_1", "bedroom_1")}))
    without = facts(rects, types)
    assert term(with_relation, "ZONE_ORDER") is None  # no comparable pair left
    assert term(without, "ZONE_ORDER") == 1000


def test_wet_rooms_sharing_a_wall_cluster() -> None:
    types = {
        "living": RoomType.LIVING,
        "kitchen": RoomType.KITCHEN,
        "bath_common_1": RoomType.BATH_COMMON,
    }
    apart = facts(
        {
            "living": Rect(0, 0, 4000, 4000),
            "kitchen": Rect(4000, 0, 8000, 4000),
            "bath_common_1": Rect(0, 4000, 4000, 6000),
        },
        types,
    )
    together = facts(
        {
            "living": Rect(0, 0, 4000, 4000),
            "kitchen": Rect(4000, 0, 8000, 4000),
            "bath_common_1": Rect(4000, 4000, 8000, 6000),
        },
        types,
    )
    assert term(apart, "WET_CLUSTER") == 1000
    assert term(together, "WET_CLUSTER") == 0


def test_exterior_exposure_counts_walls_facing_an_open_area() -> None:
    region = Rect(0, 0, 10000, 10000)
    rects = {"a": Rect(0, 0, 10000, 4000), "b": Rect(3000, 4000, 7000, 8000)}
    # b is surrounded by unbuilt space on three sides: its longest outside stretch is 4 m
    assert exterior_runs("b", rects) == 4000
    del region


# ---------- regressions fixed in Checkpoint 2.1 ----------


def test_a_split_may_end_with_a_fixed_part() -> None:
    """Regression: a passage at the far edge (`xs(column, passage)`) raised an error."""
    tree = xs(Leaf("room"), Part(Leaf("passage"), 1200))
    prog = compile_tree(tree)
    box = boxes(prog, (0, 0, 5000, 3000), ())
    assert box is not None
    assert box[prog.leaf_slot["passage"]] == (3800, 0, 5000, 3000)


def test_the_start_gives_every_part_its_minimum_first() -> None:
    """Regression: proportional starts left a bathroom 0.9 m deep on a narrow plot."""
    tree = ys(Leaf("bedroom"), Leaf("bath"), Leaf("kitchen"))
    prog = compile_tree(tree)
    weights = {"bedroom": 10_000_000, "bath": 1_000_000, "kitchen": 7_000_000}
    least = {"bedroom": (0, 3000), "bath": (0, 1700), "kitchen": (0, 2200)}
    values = initial_values(tree, prog, (0, 0, 4000, 7200), weights, 50, least)
    box = boxes(prog, (0, 0, 4000, 7200), values)
    assert box is not None
    depths = {k: box[s][3] - box[s][1] for k, s in prog.leaf_slot.items()}
    assert depths["bath"] >= 1700
    assert depths["bedroom"] >= 3000


def test_fixture_fit_depends_on_the_door_wall() -> None:
    """Regression: a bathroom entered through its short wall failed fixture placement after the
    solver had sized it for a door on the long wall."""
    bath = fixture_fit(ruleset())[RoomType.BATH_COMMON]
    door_on_short_wall = bath.shortfall(1500, 2250)  # along the door wall, across
    # 2750 in Checkpoint 2.1; 2800 since Checkpoint 2.2 tests every door position a plan can produce
    door_on_long_wall = bath.shortfall(2800, 1500)
    assert door_on_short_wall > 0
    assert door_on_long_wall == 0


def test_the_entry_room_needs_front_wall_for_entrance_and_window() -> None:
    """Regression: a centred living room with only its front wall outside could not take its
    window beside the main entrance."""
    need, entry = 1400, 3800
    assert window_gap((0, 3000, 0, 0), need, entry) == 800
    assert window_gap((0, 3800, 0, 0), need, entry) == 0
    assert window_gap((1500, 3000, 0, 0), need, entry) == 0  # a side wall takes the window
    assert side_runs((0, 0, 4000, 3000), (0, 0, 10000, 10000), []) == (3000, 4000, 0, 0)


def test_insets_treat_a_side_facing_an_open_area_as_exterior() -> None:
    rects = {"a": Rect(0, 0, 4000, 4000), "b": Rect(4000, 0, 8000, 2000)}
    insets = room_insets(
        rects, {"a": True, "b": True}, Rect(0, 0, 8000, 6000), exterior_mm=200, interior_mm=100
    )
    # a's right side is half beside b (interior) and half open (exterior): the thicker wall wins
    assert insets["a"][2] == 100


def test_topologies_are_unique_across_families() -> None:
    selection = select(
        problem_of("2bhk_30x50_north_twowheeler_open"), ruleset(), fixture_fit(ruleset())
    )
    keys = [(t.tree, t.access, t.opens) for t in selection.topologies]
    assert len(keys) == len(set(keys))


# ---------- validator independence and determinism ----------


def test_the_validator_judges_a_new_family_plan_on_its_own() -> None:
    plan = family_plan("4bhk_50x80_large_two_cars", F.CENTRAL_LIVING_BEDROOM_WINGS)
    assert plan is not None
    data = dump(plan)
    floor = data["floors"][0]
    # break the plan: the kitchen's door goes
    floor["openings"] = [o for o in floor["openings"] if o["id"] != "door_kitchen"]
    report = validate(
        data, ruleset(), intent=intent_of(benchmark_cases()["4bhk_50x80_large_two_cars"], ruleset())
    )
    codes = {i.code for i in report.errors}
    assert ValidationCode.RELATION_UNMET in codes or ValidationCode.ROOM_UNREACHABLE in codes


@pytest.mark.parametrize("family", [F.FRONT_LIVING_REAR_BEDROOM, F.CENTRAL_LIVING_BEDROOM_WINGS])
def test_family_plans_are_reproducible(family: TopologyFamily) -> None:
    name = FAMILY_CASES[family]
    first, second = family_plan(name, family), family_plan(name, family)
    assert first is not None
    assert second is not None
    assert first.meta.body_sha256 is None or first.meta.body_sha256 == second.meta.body_sha256
    assert dump(first) == dump(second)


def test_the_plan_score_is_the_solver_score_for_a_plan_with_an_open_area() -> None:
    result = valid("2bhk_40x80_west_two_cars")
    assert result.plan is not None
    assert result.topology is not None
    assert result.topology.endswith("_open")
    assert result.quality == score_plan(result.plan, ruleset())


def test_layouts_enter_bedrooms_only_from_shared_space() -> None:
    """No family routes circulation through a bedroom: only its attached bathroom opens off it."""
    for family, name in FAMILY_CASES.items():
        plan = family_plan(name, family)
        assert plan is not None
        types = {r.id: r.type for r in plan.floors[0].rooms}
        for info in analyse(plan).openings.values():
            a, b = info.connects
            for room, other in ((a, b), (b, a)):
                if types.get(room) == RoomType.BEDROOM and other in types:
                    assert types[other] != RoomType.BEDROOM, (family, room, other)
