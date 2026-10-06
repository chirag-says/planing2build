"""Derived geometry (Checkpoint 1, section E.4): PlanGeometry is computed from the HousePlan with
hand-checkable results, and is the only geometry a renderer receives."""

from p2b.core.vocabulary import OpeningKind, WallKind, WallSide
from p2b.houseplans.engine import HousePlan, plan_geometry
from p2b.houseplans.engine.derive import WallInfo, analyse, opening_info
from p2b.houseplans.engine.geom import Rect
from p2b.houseplans.engine.graph import build_graph
from p2b.houseplans.engine.model import DoorSpec, Opening
from tests.houseplans_support import generate_case, golden_plan, ruleset


def test_one_room_by_hand() -> None:
    """A 4,000 x 3,000 mm room on wall centrelines with 200 mm exterior walls."""
    graph = build_graph(
        {"r": Rect(0, 0, 4000, 3000)}, {"r": True}, exterior_mm=200, interior_mm=100
    )
    assert len(graph.walls) == 4
    assert all(w.kind == WallKind.EXTERIOR for w in graph.walls)
    assert len(graph.boundaries["r"]) == 4


def test_t_junctions_split_walls_and_each_side_knows_its_room() -> None:
    rects = {
        "a": Rect(0, 0, 4000, 3000),
        "b": Rect(4000, 0, 8000, 1500),
        "c": Rect(4000, 1500, 8000, 3000),
    }
    graph = build_graph(rects, {k: True for k in rects}, exterior_mm=200, interior_mm=100)
    interior = [w for w in graph.walls if w.kind == WallKind.INTERIOR]
    # a|b, a|c (the shared line split at the T-junction) and b|c
    assert len(interior) == 3
    assert len(graph.boundaries["a"]) == 5  # the T-junction node sits on a's right edge
    shared = {(w.left_room, w.right_room) for w in interior}
    assert shared == {("a", "b"), ("a", "c"), ("c", "b")}  # left of a→b is +90° from its direction


def test_golden_room_geometry_matches_hand_arithmetic() -> None:
    plan = HousePlan.model_validate(golden_plan("2bhk_30x50_north")["plan"])
    geometry = plan_geometry(plan, ruleset())
    an = analyse(plan)
    for room in geometry.floors[0].rooms:
        rect = an.room_rects[room.id]
        clear = an.clear_rects[room.id]
        assert rect is not None
        assert clear is not None
        assert room.clear_w_mm == clear.w
        assert room.clear_d_mm == clear.h
        assert room.carpet_area_mm2 == clear.w * clear.h
        # half of each bounding wall (100 or 200 mm), or nothing on an open side
        assert rect.w - clear.w in (0, 50, 100, 150, 200)
        assert rect.h - clear.h in (0, 50, 100, 150, 200)
    dims = {d.id: d.value_mm for d in geometry.floors[0].dimensions}
    assert dims["plot_width"] == 9144
    assert dims["plot_depth"] == 15240
    assert dims["envelope_width"] == 9144 - 2 * 610
    assert dims["envelope_depth"] == 15240 - 1524 - 914


def test_wall_pieces_cover_the_wall_except_the_openings() -> None:
    plan = HousePlan.model_validate(golden_plan("3bhk_40x65_east")["plan"])
    geometry = plan_geometry(plan, ruleset())
    floor = geometry.floors[0]
    openings = {o.id: o for o in plan.floors[0].openings}
    for wall in floor.walls:
        full = [
            p for p in wall.pieces if p.z0_mm == 0 and p.z1_mm == plan.floors[0].floor_to_floor_mm
        ]
        hosted = [o for o in openings.values() if o.wall == wall.id]
        solid = sum(p.s1_mm - p.s0_mm for p in full)
        extensions = full[0].s0_mm * -1 + (full[-1].s1_mm - wall.length_mm) if full else 0
        assert solid == wall.length_mm + extensions - sum(o.width_mm for o in hosted)
        for o in hosted:
            above = [
                p
                for p in wall.pieces
                if (p.s0_mm, p.s1_mm) == (o.offset_mm, o.offset_mm + o.width_mm)
            ]
            if o.kind == OpeningKind.WINDOW:
                assert {(p.z0_mm, p.z1_mm) for p in above} == {
                    (0, o.sill_mm),
                    (o.sill_mm + o.height_mm, plan.floors[0].floor_to_floor_mm),
                }
            else:
                assert {(p.z0_mm, p.z1_mm) for p in above} == {
                    (o.height_mm, plan.floors[0].floor_to_floor_mm)
                }


def test_door_swing_follows_hinge_and_side() -> None:
    wall = WallInfo(
        id="w",
        a=(0, 0),
        b=(3000, 0),
        kind=WallKind.INTERIOR,
        thickness=100,
        length=3000,
        direction=(1, 0),
        left_rooms=("up",),
        right_rooms=("down",),
    )
    door = Opening(
        id="d",
        kind=OpeningKind.DOOR,
        wall="w",
        offset_mm=100,
        width_mm=900,
        height_mm=2100,
        sill_mm=0,
        door=DoorSpec(leaf="SINGLE", hinge="A_SIDE", opens_to=WallSide.LEFT),
    )
    info = opening_info(door, wall)
    assert info is not None
    assert info.connects == ("up", "down")
    assert info.zones == (Rect(100, 50, 1000, 950),)  # 900 deep from the wall face, on the left
    from p2b.houseplans.engine.derive import _swing

    swing = _swing(info)
    assert swing is not None
    assert (swing.hinge.x, swing.hinge.y, swing.start_deg, swing.end_deg) == (100, 0, 0, 90)


def test_every_fixture_has_a_footprint_inside_its_room() -> None:
    result = generate_case("3bhk_40x65_east")
    assert result.plan is not None
    geometry = plan_geometry(result.plan, ruleset())
    rooms = {r.id: r for r in geometry.floors[0].rooms}
    for fixture in geometry.floors[0].fixtures:
        assert fixture.footprint is not None
        clear = rooms[fixture.room].clear_polygon
        assert clear is not None
        xs, ys = [p.x for p in clear], [p.y for p in clear]
        assert all(
            min(xs) <= p.x <= max(xs) and min(ys) <= p.y <= max(ys) for p in fixture.footprint
        )
