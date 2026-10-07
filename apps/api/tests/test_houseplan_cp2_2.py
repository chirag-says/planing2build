"""Checkpoint 2.2: architectural quality. Same-axis splits flattened and sibling cuts across
corridors, slab moves, the ROOM_SIZE_OUTLIER term, stepped carport courts, the courtyard wings
layout, the linear yard, door-position-complete fixture fit, the evaluation memo, and the
regressions fixed on the way (AI_DESIGN_ENGINE_CHECKPOINT_2_2_REPORT)."""

from types import SimpleNamespace

import pytest

from p2b.core.vocabulary import ConstraintKind, RoomType
from p2b.houseplans.engine import fixture_fit, score_plan
from p2b.houseplans.engine.compile import shared_coords
from p2b.houseplans.engine.geom import Rect
from p2b.houseplans.engine.layout_tree import Coords, Leaf, Part, Split, compile_tree, xs, ys
from p2b.houseplans.engine.objective import (
    LayoutFacts,
    SizingAccumulator,
    room_terms,
    score,
    size_rule,
)
from p2b.houseplans.engine.solver.zoned_ls import CandidateLayout, _apply, search
from p2b.houseplans.engine.zoning import OPEN_CENTRE, OPEN_REAR, OPEN_SERVICE, OPEN_SIDE
from tests.houseplans_support import (
    benchmark_cases,
    generate_zoned_benchmark,
    intent_of,
    ruleset,
)
from tests.test_houseplan_cp2_1 import problem_of


def best_layout(name: str) -> tuple[CandidateLayout, dict[str, Coords]]:
    best = search(problem_of(name), ruleset(), fixture_fit(ruleset())).feasible[0]
    co = best.zp.coords(best.values)
    assert co is not None
    return best, co


def width(c: Coords) -> int:
    return c[2] - c[0]


def depth(c: Coords) -> int:
    return c[3] - c[1]


# ---------- the slicing tree ----------


def test_a_flexible_split_along_the_same_axis_is_spliced_in() -> None:
    """Regression: `with_open` wrapped a layout in a second y split, so the yard's cut and the
    layout's cuts were never siblings and could not move together."""
    a, b, c = Leaf("a"), Leaf("b"), Leaf("c")
    assert ys(ys(a, b), c) == Split("y", (Part(a), Part(b), Part(c)))
    # across the axis, or with a fixed size, it stays a part of its own
    assert ys(xs(a, b), c) == Split("y", (Part(Split("x", (Part(a), Part(b)))), Part(c)))
    fixed = Part(ys(a, b), 1200)
    assert ys(fixed, c) == Split("y", (fixed, Part(c)))


def test_sibling_cuts_span_a_fixed_corridor() -> None:
    """Regression: a fixed part (a corridor) reset the sibling chain, so the rooms either side of
    a corridor could not shift together."""
    prog = compile_tree(xs(Leaf("a"), Part(Leaf("corridor"), 1200), Leaf("b"), Leaf("c")))
    assert len(prog.var_names) == 2  # a's and b's cuts; c takes the rest
    assert prog.siblings == ((0, 1),)


def test_a_slab_move_shifts_every_cut_beyond_the_line() -> None:
    zp = SimpleNamespace(prog=SimpleNamespace(var_axis=("y", "y", "x", "y")))
    v = (3000, 6000, 4000, 9000)
    # the slab at the cut 6000 along y: 6000 and 9000 move, 3000 and the x cut do not
    assert _apply(zp, v, (True, ((1, 600),))) == (3000, 6600, 4000, 9600)  # type: ignore[arg-type]
    assert _apply(zp, v, (False, ((1, 600),))) == (3000, 6600, 4000, 9000)  # type: ignore[arg-type]


# ---------- ROOM_SIZE_OUTLIER ----------


def test_room_size_outlier_is_the_worst_room_area_deviation() -> None:
    rules = ruleset()
    rule = size_rule(rules, RoomType.BEDROOM)
    pref = rules.rooms[RoomType.BEDROOM].pref_area_mm2
    assert pref
    acc = SizingAccumulator()
    sizes = ((3000, pref // 3000), (3000, 2 * pref // 3000))  # at preference; twice the area
    for w, h in sizes:
        acc.add(rule, w, h, False)
    devs = [room_terms(rule, w, h).area_dev for w, h in sizes]
    assert acc.worst_area_dev == max(d for d in devs if d is not None)
    assert acc.worst_area_dev >= 990  # about +100 %
    # the mean (AREA_DEVIATION) is half that: the outlier term is what keeps one room honest
    mean = acc.values(None)[ConstraintKind.AREA_DEVIATION]
    assert mean is not None
    assert mean * 2 <= acc.worst_area_dev + 1


def test_room_size_outlier_names_the_room_furthest_from_its_preference() -> None:
    rules = ruleset()
    pref = rules.rooms[RoomType.BEDROOM].pref_area_mm2
    assert pref
    side = 3300
    near, far = pref // 3000 + 300, 3 * pref // 3000  # about the preference; about three times
    rects = {"bed": Rect(0, 0, side, near), "bed2": Rect(side, 0, 2 * side, far)}
    types = {"bed": RoomType.BEDROOM, "bed2": RoomType.BEDROOM}
    facts = LayoutFacts(rects, types, Rect(0, 0, 2 * side, far), "bed", None)
    term = next(t for t in score(facts, rules).terms if t.kind == ConstraintKind.ROOM_SIZE_OUTLIER)
    assert term.subjects == ("bed2",)
    assert term.score_milli is not None
    assert term.score_milli > 1000


def test_room_terms_cache_is_bounded() -> None:
    """The search asks for the same room sizes many times; the cache must not grow without
    limit in a long-running worker."""
    assert room_terms.cache_info().maxsize == 1 << 15


# ---------- topologies ----------


def test_a_wide_carport_leaves_an_open_court_beside_the_rooms_behind_it() -> None:
    """Regression (CP2.1 audit): behind a two-car carport the kitchen took the carport's whole
    width (6.6 m). The stepped court keeps it to the house side, the rest open."""
    best, co = best_layout("2bhk_40x80_west_two_cars")
    assert OPEN_SIDE in best.zp.opens
    park, side = co["parking"], co[OPEN_SIDE]
    assert side[1] == park[3]  # directly behind the carport
    assert width(side) >= (ruleset().zoning.open_space_min_mm or 0)
    behind = [k for k, c in co.items() if k in best.zp.types and c[1] == park[3]]
    assert behind
    assert all(width(co[k]) < width(park) for k in behind)


def test_the_courtyard_layout_puts_dining_on_the_court_and_kitchen_beside_it() -> None:
    best, co = best_layout("prop_square_45x45")
    assert "_court_" in best.name
    assert {OPEN_CENTRE, OPEN_SERVICE} <= set(best.zp.opens)
    assert shared_coords(co["dining"], co[OPEN_CENTRE]) > 0
    assert shared_coords(co["kitchen"], co["dining"]) > 0
    assert shared_coords(co["kitchen"], co[OPEN_SERVICE]) > 0


def test_the_linear_row_keeps_its_own_depth_with_a_yard_behind() -> None:
    """Regression (CP2.1 audit): on 80x28 every room in the row was as deep as the car beside it."""
    best, co = best_layout("prop_very_wide_80x28")
    assert best.name.endswith("_yard")
    assert OPEN_REAR in best.zp.opens
    assert co[OPEN_REAR][1] == co["passage"][3]
    assert depth(co["living"]) < depth(co["parking"])


def test_the_wet_aware_order_puts_attached_bathrooms_back_to_back() -> None:
    best, co = best_layout("c01_3bhk_40x70_car_attached2")
    assert "_o2" in best.name  # the wet-aware row order
    assert shared_coords(co["bath_attached_1"], co["bath_attached_2"]) > 0


def test_parking_starts_at_its_least_size() -> None:
    """Regression: the courtyard's parking took a share of the spare depth from the start and
    the search kept it, a 20 m long car space."""
    best, _ = best_layout("prop_square_45x45")
    zp = best.zp
    start = zp.coords(zp.initial())
    assert start is not None
    park = zp.p.parking
    assert park is not None
    walls = ruleset().walls.exterior_mm + ruleset().walls.interior_mm
    assert depth(start["parking"]) <= park.clear_d_mm + walls + zp.g


# ---------- fixture fit ----------


def test_fixture_fit_covers_the_door_beside_a_crossing_exterior_wall() -> None:
    """Regression: 3bhk_50x60_wide_two_cars turned INFEASIBLE. Its common bath (clear 1800 along
    the door wall x 2000) passed the bound, but in the plan its door sat half an exterior wall
    further in (a T-junction) and the fittings no longer fitted. The bound now tests every door
    position a plan can produce, with the hall on any side."""
    bath = fixture_fit(ruleset())[RoomType.BATH_COMMON]
    assert bath.shortfall(1800, 2000) > 0
    assert bath.shortfall(1900, 1800) == 0


def test_the_50x60_two_car_plot_is_valid() -> None:
    result = generate_zoned_benchmark("3bhk_50x60_wide_two_cars")
    assert result.outcome == "VALID"


# ---------- the search ----------


# ---------- the plans ----------


@pytest.mark.parametrize(
    "name",
    [
        "4bhk_50x80_large_two_cars",
        "c04_4bhk_55x90_two_cars",
        "q06_4bhk_60x90_large_two_cars_puja_utility",
    ],
)
def test_large_plots_get_no_invented_rooms_and_no_room_over_two_and_a_half_times_its_preference(
    name: str,
) -> None:
    """Unused space stays open: the room programme is exactly what was asked for."""
    rules = ruleset()
    result = generate_zoned_benchmark(name)
    assert result.plan is not None
    intent = intent_of(benchmark_cases()[name], rules)
    circulation = rules.zoning.circulation_room
    planned = sorted(r.type.value for r in result.plan.floors[0].rooms if r.type != circulation)
    assert planned == sorted(p.room_type.value for p in intent.programme)
    quality = score_plan(result.plan, rules)
    assert quality is not None
    for room in quality.rooms:
        pref = rules.rooms[room.room_type].pref_area_mm2
        if pref:
            assert room.clear_w_mm * room.clear_d_mm <= 5 * pref // 2, room.key
