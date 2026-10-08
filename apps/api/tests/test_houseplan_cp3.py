"""Checkpoint 3, engine side: MOVE_WALL on the planar graph, editing as a validated batch, and the
derived open areas of PlanGeometry 1.1.0 (AI_DESIGN_ENGINE_CHECKPOINT_3_REPORT)."""

import json
from functools import cache

import pytest

from p2b.core.vocabulary import (
    ConstraintStrength,
    OpeningKind,
    PlanOpRejection,
    PlanSource,
    RoomSide,
    RoomType,
    WallKind,
)
from p2b.houseplans.engine import HousePlan, plan_geometry, sha256_of
from p2b.houseplans.engine.derive import analyse, open_areas
from p2b.houseplans.engine.edit import MAX_BATCH, BatchRejected, EditResult, apply_batch, edit
from p2b.houseplans.engine.geom import Rect
from p2b.houseplans.engine.model import Floor
from p2b.houseplans.engine.ops import (
    AddRoom,
    DeleteRoom,
    MoveOpening,
    MoveWall,
    OperationRejected,
    PlanOp,
    apply,
    wall_run,
)
from tests.houseplans_support import GOLDEN, benchmark_cases, intent_of, ruleset

CASES = (
    "2bhk_30x50_north_twowheeler_open",
    "4bhk_50x80_large_two_cars",
    "2bhk_40x80_west_two_cars",
)


@cache
def golden(name: str) -> HousePlan:
    data = json.loads((GOLDEN / "zoned" / f"{name}.json").read_text("utf-8"))
    return HousePlan.model_validate(data["plan"])


def run_edit(name: str, ops: list[PlanOp]) -> EditResult:
    rules = ruleset()
    return edit(
        golden(name),
        ops,
        rules,
        intent=intent_of(benchmark_cases()[name], rules),
        ruleset_version=None,
        ruleset_sha256=None,
    )


def first_valid_move(name: str) -> tuple[MoveWall, EditResult]:
    """The first interior wall move (in document order, 100 mm either way) the validator accepts."""
    for wall in golden(name).floors[0].walls:
        if wall.kind != WallKind.INTERIOR:
            continue
        for delta in (100, -100):
            op = MoveWall(wall=wall.id, delta_mm=delta)
            try:
                result = run_edit(name, [op])
            except BatchRejected:
                continue
            if result.report.valid:
                return op, result
    raise AssertionError(f"no valid move in {name}")


def floor0(plan: HousePlan) -> Floor:
    return plan.floors[0]


# ---------- MOVE_WALL ----------


@pytest.mark.parametrize("name", CASES)
def test_a_wall_run_is_the_straight_line_through_collinear_walls(name: str) -> None:
    floor = floor0(golden(name))
    nodes = {n.id: n for n in floor.nodes}
    for wall in floor.walls:
        axis, walls, run_nodes = wall_run(floor, wall.id)
        assert axis in ("x", "y")
        line = {(nodes[n].y if axis == "x" else nodes[n].x) for n in run_nodes}
        assert len(line) == 1, wall.id
        assert wall.id in walls


@pytest.mark.parametrize("name", CASES)
def test_moving_a_wall_moves_its_run_and_stretches_what_meets_it(name: str) -> None:
    op, result = first_valid_move(name)
    before, after = floor0(golden(name)), floor0(result.plan)
    axis, _, run_nodes = wall_run(before, op.wall)
    old = {n.id: n for n in before.nodes}
    new = {n.id: n for n in after.nodes}
    for node_id, node in old.items():
        moved = (new[node_id].x - node.x, new[node_id].y - node.y)
        if node_id in run_nodes:  # perpendicular to the run, by the delta
            assert moved == ((0, moved[1]) if axis == "x" else (moved[0], 0))
            assert abs(moved[0]) + abs(moved[1]) == abs(op.delta_mm)
        else:
            assert moved == (0, 0), node_id
    # walls, rooms and openings keep their ids and references: only coordinates changed
    assert [w.model_dump() for w in before.walls] == [w.model_dump() for w in after.walls]
    assert [r.boundary for r in before.rooms] == [r.boundary for r in after.rooms]


@pytest.mark.parametrize("name", CASES)
def test_the_inverse_restores_the_plan_exactly(name: str) -> None:
    _, result = first_valid_move(name)
    restored, _ = apply_batch(result.plan, result.inverse)
    original = golden(name)
    assert restored.floors == original.floors
    # undone as an edit, the body (soft terms re-measured) hashes as the generated one did
    rules = ruleset()
    undone = edit(
        result.plan,
        list(result.inverse),
        rules,
        intent=intent_of(benchmark_cases()[name], rules),
        ruleset_version=None,
        ruleset_sha256=None,
    )
    assert undone.plan.meta.body_sha256 == original.meta.body_sha256
    assert undone.plan.meta.revision_no == original.meta.revision_no + 2


def test_a_zero_move_an_unknown_wall_and_unsupported_operations_are_rejected() -> None:
    plan = golden(CASES[0])
    wall = floor0(plan).walls[0].id
    cases: list[tuple[PlanOp, PlanOpRejection]] = [
        (MoveWall(wall=wall, delta_mm=0), PlanOpRejection.NO_MOVEMENT),
        (MoveWall(wall="w_missing", delta_mm=100), PlanOpRejection.UNKNOWN_ENTITY),
        (
            # Checkpoint 3.1: the structural edits need the plan's ruleset to apply
            AddRoom(host_room="living", type=RoomType.STORE, side=RoomSide.BACK, depth_mm=1000),
            PlanOpRejection.NOT_SUPPORTED,
        ),
        (DeleteRoom(room="dining", merge_into="living"), PlanOpRejection.NOT_SUPPORTED),
    ]
    for op, code in cases:
        with pytest.raises(OperationRejected) as caught:
            apply(plan, op)
        assert caught.value.code == code, op


def test_a_move_that_would_collapse_a_wall_is_rejected() -> None:
    plan = golden(CASES[0])
    floor = floor0(plan)
    nodes = {n.id: n for n in floor.nodes}
    wall = next(w for w in floor.walls if w.kind == WallKind.INTERIOR)
    a, b = nodes[wall.a], nodes[wall.b]
    span = max(abs(a.x - b.x), abs(a.y - b.y))
    with pytest.raises(OperationRejected) as caught:
        apply(plan, MoveWall(wall=wall.id, delta_mm=100 * span))  # far past its neighbours
    assert caught.value.code in (
        PlanOpRejection.WALL_WOULD_COLLAPSE,
        PlanOpRejection.HOSTED_ITEM_LEAVES_WALL,
    )


def test_openings_off_the_moved_run_keep_their_place_on_the_ground() -> None:
    name = CASES[1]
    op, result = first_valid_move(name)
    _, run, _ = wall_run(floor0(golden(name)), op.wall)

    def jambs(plan: HousePlan) -> dict[str, tuple[int, int]]:
        out = {}
        for info in analyse(plan).openings.values():
            dx, dy = info.wall.direction
            out[info.opening.id] = (
                info.wall.a[0] + dx * info.start,
                info.wall.a[1] + dy * info.start,
            )
        return out

    before, after = jambs(golden(name)), jambs(result.plan)
    hosts = {o.id: o.wall for o in floor0(golden(name)).openings}
    for oid, at in before.items():
        if hosts[oid] not in run:
            assert after[oid] == at, oid


# ---------- edit: a validated batch ----------


@pytest.mark.parametrize("name", CASES)
def test_an_accepted_edit_is_a_new_revision_with_fresh_soft_terms(name: str) -> None:
    _, result = first_valid_move(name)
    plan = result.plan
    assert result.report.valid
    assert plan.meta.revision_no == golden(name).meta.revision_no + 1
    assert plan.meta.source == PlanSource.EDITED
    assert plan.meta.body_sha256 == sha256_of(plan.body())
    soft = [c for c in plan.constraints if c.strength == ConstraintStrength.SOFT]
    assert soft
    assert [c.id for c in plan.constraints] == [c.id for c in golden(name).constraints]


@pytest.mark.parametrize("name", CASES)
def test_edits_are_deterministic(name: str) -> None:
    op, first = first_valid_move(name)
    second = run_edit(name, [op])
    assert first.plan.model_dump() == second.plan.model_dump()
    assert first.inverse == second.inverse


def test_an_edit_that_breaks_a_rule_is_reported_by_the_validator() -> None:
    name = CASES[0]
    floor = floor0(golden(name))
    found = None
    for wall in floor.walls:
        if wall.kind != WallKind.INTERIOR:
            continue
        try:
            result = run_edit(name, [MoveWall(wall=wall.id, delta_mm=1500)])
        except BatchRejected:
            continue
        if not result.report.valid:
            found = result
            break
    assert found is not None
    assert found.report.errors
    assert all(e.entities for e in found.report.errors)


def test_a_rejected_operation_names_its_place_in_the_batch_and_nothing_applies() -> None:
    plan = golden(CASES[0])
    op, _ = first_valid_move(CASES[0])
    with pytest.raises(BatchRejected) as caught:
        apply_batch(plan, [op, MoveWall(wall="w_missing", delta_mm=100)])
    assert caught.value.index == 1
    assert caught.value.rejected.code == PlanOpRejection.UNKNOWN_ENTITY


def test_a_batch_has_one_to_fifty_operations() -> None:
    door = next(o for o in floor0(golden(CASES[0])).openings if o.kind == OpeningKind.DOOR)
    same = MoveOpening(opening=door.id, offset_mm=door.offset_mm)
    with pytest.raises(ValueError, match="1 to"):
        run_edit(CASES[0], [])
    with pytest.raises(ValueError, match="1 to"):
        run_edit(CASES[0], [same] * (MAX_BATCH + 1))


def test_a_door_moves_only_along_its_host_wall() -> None:
    plan = golden(CASES[1])
    door = next(o for o in floor0(plan).openings if o.kind == OpeningKind.DOOR)
    moved, inverse = apply(plan, MoveOpening(opening=door.id, offset_mm=door.offset_mm + 50))
    after = next(o for o in floor0(moved).openings if o.id == door.id)
    assert after.wall == door.wall
    assert after.offset_mm == door.offset_mm + 50
    assert inverse == MoveOpening(opening=door.id, offset_mm=door.offset_mm)


# ---------- open areas (PlanGeometry 1.1.0) ----------


def rect_poly(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def test_open_areas_are_classified_by_where_they_lie() -> None:
    region = Rect(0, 0, 10000, 20000)
    # a house in the middle: forecourt in front, rear yard behind, side yards either side
    house = rect_poly(2000, 5000, 8000, 15000)
    kinds = {a.kind for a in open_areas(region, [house])}
    assert kinds == {"SIDE_YARD"}  # one ring around the house: it touches front and back
    # front band of rooms across the plot and a back band: the gap between them is a court
    # only if it touches no side; here it spans the width, so it is a side yard
    rooms = [
        rect_poly(0, 0, 10000, 5000),
        rect_poly(0, 12000, 10000, 20000),
        rect_poly(0, 5000, 4000, 12000),
        rect_poly(7000, 5000, 10000, 12000),
    ]
    (court,) = open_areas(region, rooms)
    assert court.kind == "COURT"
    assert court.area_mm2 == 3000 * 7000
    # a strip at the front only
    (front,) = open_areas(region, [rect_poly(0, 3000, 10000, 20000)])
    assert front.kind == "FORECOURT"
    (back,) = open_areas(region, [rect_poly(0, 0, 10000, 17000)])
    assert back.kind == "REAR_YARD"
    assert open_areas(region, [rect_poly(0, 0, 10000, 20000)]) == []


@pytest.mark.parametrize("name", CASES)
def test_open_areas_fill_exactly_what_no_room_covers(name: str) -> None:
    plan = golden(name)
    geometry = plan_geometry(plan, ruleset())
    floor = geometry.floors[0]
    assert geometry.geometry_version == "1.1.0"
    envelope = geometry.envelope
    assert envelope is not None
    t = (ruleset().walls.exterior_mm + 1) // 2
    xs, ys = [p.x for p in envelope], [p.y for p in envelope]
    region_area = (max(xs) - min(xs) - 2 * t) * (max(ys) - min(ys) - 2 * t)
    rooms_area = 0
    for room in floor.rooms:
        rx, ry = [p.x for p in room.polygon], [p.y for p in room.polygon]
        rooms_area += (max(rx) - min(rx)) * (max(ry) - min(ry))
    assert rooms_area + sum(a.area_mm2 for a in floor.open_areas) == region_area
    for area in floor.open_areas:
        for cell in area.cells:
            cx = sorted({p.x for p in cell})
            cy = sorted({p.y for p in cell})
            for room in floor.rooms:
                rx = sorted({p.x for p in room.polygon})
                ry = sorted({p.y for p in room.polygon})
                overlap_x = min(cx[-1], rx[-1]) - max(cx[0], rx[0])
                overlap_y = min(cy[-1], ry[-1]) - max(cy[0], ry[0])
                assert overlap_x <= 0 or overlap_y <= 0, (area.id, room.id)
