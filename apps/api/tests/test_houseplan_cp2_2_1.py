"""Checkpoint 2.2.1: the parking bay. The car space keeps its required size inside its layout
cell; leftover wide enough for an open strip stays open
(AI_DESIGN_ENGINE_CHECKPOINT_2_2_1_REPORT)."""

import copy
from types import SimpleNamespace

import pytest

from p2b.core.vocabulary import TopologyFamily
from p2b.houseplans.engine import fixture_fit
from p2b.houseplans.engine.compile import ZonedProblem, shared_coords
from p2b.houseplans.engine.generate import compile_problem
from p2b.houseplans.engine.layout_tree import Coords
from p2b.houseplans.engine.objective import plan_facts
from p2b.houseplans.engine.solver import LayoutProblem
from p2b.houseplans.engine.solver.zoned_ls import search
from tests.houseplans_support import benchmark_cases, generate_zoned_benchmark, intent_of, ruleset

F = TopologyFamily
OPEN_MIN = 1500
REGION: Coords = (0, 0, 20000, 30000)


def bay(
    cell: Coords, need: tuple[int, int] = (5100, 5100), open_min: int | None = OPEN_MIN
) -> Coords:
    fake = SimpleNamespace(_bay=None if open_min is None else (*need, open_min), _region=REGION)
    return ZonedProblem.bay(fake, cell)  # type: ignore[arg-type]


# ---------- the rule ----------


def test_a_cell_at_the_left_boundary_keeps_the_house_side() -> None:
    # 8 m wide, 6 m deep cell at the left boundary: 2.9 m of width and 0.9 m of depth spare
    assert bay((0, 0, 8000, 6000)) == (2900, 0, 8000, 6000)


def test_a_cell_at_the_right_boundary_keeps_the_house_side() -> None:
    assert bay((12000, 0, 20000, 6000)) == (12000, 0, 17100, 6000)


def test_an_inner_cell_moves_towards_the_centre_line() -> None:
    assert bay((1000, 0, 9000, 6000)) == (3900, 0, 9000, 6000)  # left of centre: keep right
    assert bay((11000, 0, 19000, 6000)) == (11000, 0, 16100, 6000)


def test_depth_beyond_an_open_strip_stays_open_behind_the_car() -> None:
    assert bay((0, 0, 5100, 9000)) == (0, 0, 5100, 5100)


def test_leftover_narrower_than_an_open_strip_stays_with_the_parking() -> None:
    """An apron: a strip too narrow to be a usable court is not left as a sliver."""
    assert bay((0, 0, 6550, 6550)) == (0, 0, 6550, 6550)
    assert bay((0, 0, 6600, 6600)) == (1500, 0, 6600, 5100)


def test_without_an_open_space_rule_the_cell_is_the_parking() -> None:
    assert bay((0, 0, 8000, 9000), open_min=None) == (0, 0, 8000, 9000)


# ---------- the regression ----------


def parking_rect(name: str) -> tuple[Coords, LayoutProblem]:
    result = generate_zoned_benchmark(name)
    assert result.outcome == "VALID"
    assert result.plan is not None
    facts = plan_facts(result.plan, ruleset())
    assert facts is not None
    r = facts.rects["parking"]
    problem = compile_problem(intent_of(benchmark_cases()[name], ruleset()), ruleset())
    assert isinstance(problem, LayoutProblem)
    return (r.x0, r.y0, r.x1, r.y1), problem


def test_the_50x60_two_car_parking_is_no_longer_a_spare_space_dump() -> None:
    """Regression (CP2.2 report L-1): the carport was 8.25 x 8.6 m for 5 x 5 m of cars."""
    (x0, y0, x1, y1), problem = parking_rect("3bhk_50x60_wide_two_cars")
    park = problem.parking
    assert park is not None
    assert x1 - x0 <= park.clear_w_mm + 100
    assert y1 - y0 <= park.clear_d_mm + 100


def test_a_two_wheeler_gets_a_bay_not_a_column() -> None:
    """Regression (CP2.2 report L-1): a 1 x 2 m two-wheeler took a 4.2 x 6.5 m cell."""
    (x0, y0, x1, y1), problem = parking_rect("2bhk_30x50_north_twowheeler_open")
    park = problem.parking
    assert park is not None
    assert (x1 - x0) * (y1 - y0) <= 2 * (park.clear_w_mm + 100) * (park.clear_d_mm + 100)


def test_the_bay_adds_no_room() -> None:
    rules = ruleset()
    result = generate_zoned_benchmark("3bhk_50x60_wide_two_cars")
    assert result.plan is not None
    circulation = rules.zoning.circulation_room
    planned = sorted(r.type.value for r in result.plan.floors[0].rooms if r.type != circulation)
    intent = intent_of(benchmark_cases()["3bhk_50x60_wide_two_cars"], rules)
    assert planned == sorted(p.room_type.value for p in intent.programme)


# ---------- every parking type, every family with parking ----------


def variant(name: str, spaces: int | None = None) -> LayoutProblem:
    case = copy.deepcopy(benchmark_cases()[name])
    if spaces is not None:
        case["design_inputs"]["parking_spaces"] = spaces
    problem = compile_problem(intent_of(case, ruleset()), ruleset())
    assert isinstance(problem, LayoutProblem)
    return problem


MATRIX = [
    ("2bhk_30x50_north_twowheeler_open", None, F.SPINE),  # one two-wheeler, stepped spine
    ("2bhk_30x50_north_twowheeler_open", 3, F.L_CIRCULATION),  # three two-wheelers
    ("q15_2bhk_50x30_wide_shallow_twowheeler", 2, F.FRONT_LIVING_REAR_BEDROOM),  # beside living
    ("3bhk_50x60_wide_two_cars", None, F.L_CIRCULATION),  # two cars, stepped court
    ("3bhk_50x60_wide_two_cars", None, F.FRONT_PUBLIC_REAR_PRIVATE),
    ("3bhk_40x65_east_puja", None, F.CENTRAL_LIVING_BEDROOM_WINGS),  # one car, wings
    ("c04_4bhk_55x90_two_cars", None, F.CENTRAL_LIVING_BEDROOM_WINGS),  # courtyard, service side
    ("4bhk_40x90_deep_car_utility", None, F.SIDE_WING),
    ("4bhk_40x90_deep_car_utility", None, F.SPINE),
    ("prop_very_wide_80x28", None, F.LINEAR_REAR_CORRIDOR),  # wide-shallow
]


@pytest.mark.parametrize(("name", "spaces", "family"), MATRIX)
def test_the_parking_is_bounded_on_the_road_and_beside_the_house(
    name: str, spaces: int | None, family: TopologyFamily
) -> None:
    rules = ruleset()
    problem = variant(name, spaces)
    park = problem.parking
    assert park is not None
    found = search(problem, rules, fixture_fit(rules), frozenset({family}))
    assert found.feasible, family
    best = found.feasible[0]
    zp = best.zp
    co = zp.coords(best.values)
    assert co is not None
    x0, y0, x1, y1 = co[park.key]
    open_min = rules.zoning.open_space_min_mm or 0
    # at least the cars (the search's hard constraint), at most cars + walls + less than a strip
    assert x1 - x0 < park.clear_w_mm + 100 + open_min
    assert y1 - y0 < park.clear_d_mm + 100 + open_min
    assert y0 == zp._region[1]  # on the road edge
    beside = [k for k in zp.types if k != park.key and shared_coords(co[k], (x0, y0, x1, y1)) > 0]
    assert beside, "the parking touches the house"
