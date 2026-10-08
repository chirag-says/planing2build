"""Checkpoint 3.1, engine side: structural edits on the planar graph (MOVE_EDGE, ADD_ROOM,
DELETE_ROOM), the owner's programme changes recorded as compromises, and the validator counting
against them (AI_DESIGN_ENGINE_CHECKPOINT_3_1_REPORT). Every test runs on real zoned plans."""

import json
from collections.abc import Iterator
from functools import cache

import pytest

from p2b.core.vocabulary import (
    OpeningKind,
    OriginKind,
    PlanOpRejection,
    ProgrammeChange,
    RoomSide,
    RoomType,
    ValidationCode,
    WallKind,
)
from p2b.houseplans.engine import HousePlan, sha256_of, validate
from p2b.houseplans.engine.derive import analyse
from p2b.houseplans.engine.edit import BatchRejected, EditResult, apply_batch, apply_edit, edit
from p2b.houseplans.engine.geom import Rect
from p2b.houseplans.engine.graph_edit import Change, _rebuild, room_rects
from p2b.houseplans.engine.model import Compromise, Opening, dump
from p2b.houseplans.engine.ops import (
    AddOpening,
    AddRoom,
    DeleteOpening,
    DeleteRoom,
    MoveEdge,
    MoveOpening,
    MoveWall,
    OperationRejected,
    PlanOp,
    RenameRoom,
    RevertToRevision,
    RevertToVersion,
    SetOpening,
    SetRoomType,
    apply,
    wall_run,
)
from tests.houseplans_support import GOLDEN, benchmark_cases, intent_of, ruleset

CASES = (
    "2bhk_30x50_north_twowheeler_open",
    "4bhk_50x80_large_two_cars",
    "2bhk_40x80_west_two_cars",
    "2bhk_22x60_narrow_deep",
    "prop_very_wide_80x28",
)
ALL = tuple(sorted(p.stem for p in (GOLDEN / "zoned").glob("*.json")))
SIDES = tuple(RoomSide)
ADDS = ((RoomType.WC, 1500), (RoomType.UTILITY, 1500), (RoomType.BEDROOM, 3000))


@cache
def golden(name: str) -> HousePlan:
    data = json.loads((GOLDEN / "zoned" / f"{name}.json").read_text("utf-8"))
    return HousePlan.model_validate(data["plan"])


def run(name: str, ops: list[PlanOp], plan: HousePlan | None = None) -> EditResult:
    rules = ruleset()
    return edit(
        plan or golden(name),
        ops,
        rules,
        intent=intent_of(benchmark_cases()[name], rules),
        ruleset_version=None,
        ruleset_sha256=None,
    )


def outcomes(name: str, ops: Iterator[PlanOp]) -> Iterator[tuple[PlanOp, EditResult | None, str]]:
    """Each operation with its edit result (None when rejected) and its code or validity."""
    for op in ops:
        try:
            result = run(name, [op])
        except BatchRejected as rejected:
            yield op, None, rejected.rejected.code.value
            continue
        yield op, result, "VALID" if result.report.valid else "INVALID"


def edge_moves(name: str) -> Iterator[PlanOp]:
    for room in golden(name).floors[0].rooms:
        for side in SIDES:
            for delta in (100, -100, 300, -300):
                yield MoveEdge(room=room.id, side=side, delta_mm=delta)


def first(name: str, ops: Iterator[PlanOp], want: str) -> tuple[PlanOp, EditResult | None]:
    for op, result, outcome in outcomes(name, ops):
        if outcome == want:
            return op, result
    raise AssertionError(f"no {want} operation in {name}")


def rects_of(plan: HousePlan) -> dict[str, Rect]:
    return room_rects(plan.floors[0])


def connections(plan: HousePlan) -> dict[str, frozenset[str]]:
    return {k: frozenset(v.connects) for k, v in analyse(plan).openings.items()}


def assert_canonical_graph(plan: HousePlan) -> None:
    """The floor is exactly what the generator's builder makes of its own room rectangles: one
    planar graph, T-junctions split, no stray node or wall."""
    floor = plan.floors[0]
    rects = room_rects(floor)
    rebuilt = _rebuild(floor, rects, Change(rects=rects, rooms=list(floor.rooms)), ruleset())
    assert dump(rebuilt) == dump(floor)


# ---------- the rebuild ----------


@pytest.mark.parametrize("name", ALL)
def test_rebuilding_an_unchanged_plan_changes_nothing(name: str) -> None:
    assert_canonical_graph(golden(name))


def test_a_room_that_is_not_a_rectangle_cannot_take_a_structural_edit() -> None:
    plan = golden(CASES[0])
    floor = plan.floors[0]
    room = next(r for r in floor.rooms if r.enclosed)
    corner = room.boundary[0]
    nodes = [n.model_copy(update={"x": n.x + 50}) if n.id == corner else n for n in floor.nodes]
    bent = plan.model_copy(update={"floors": [floor.model_copy(update={"nodes": nodes})]})
    with pytest.raises(OperationRejected) as caught:
        apply(bent, MoveEdge(room=room.id, side=RoomSide.BACK, delta_mm=100), ruleset())
    assert caught.value.code == PlanOpRejection.NOT_RECTANGULAR


# ---------- MOVE_EDGE ----------


@pytest.mark.parametrize("name", CASES)
def test_a_valid_edge_move_is_local_keeps_topology_and_keeps_openings_on_the_ground(
    name: str,
) -> None:
    plan = golden(name)
    op, result = first(name, edge_moves(name), "VALID")
    assert isinstance(op, MoveEdge)
    assert result is not None
    before, after = rects_of(plan), rects_of(result.plan)
    changed = {k for k in before if before[k] != after[k]}
    assert op.room in changed
    # only rooms with a side on the moved line change, and only that side
    field = {"LEFT": "x0", "RIGHT": "x1", "FRONT": "y0", "BACK": "y1"}[op.side]
    line = getattr(before[op.room], field)
    for key in changed:
        b, a = before[key], after[key]
        moved = [f for f in ("x0", "y0", "x1", "y1") if getattr(b, f) != getattr(a, f)]
        assert len(moved) == 1
        assert getattr(b, moved[0]) == line
        assert getattr(a, moved[0]) == line + op.delta_mm
    assert_canonical_graph(result.plan)
    # every door, window and open connection still joins the same rooms
    assert connections(result.plan) == connections(plan)
    assert result.inverse == (RevertToRevision(revision=plan.meta.revision_no),)
    # walls away from the move keep their ids
    untouched = {w.id for w in plan.floors[0].walls} & {w.id for w in result.plan.floors[0].walls}
    assert len(untouched) >= len(plan.floors[0].walls) // 2


def test_moving_an_edge_moves_less_than_moving_the_whole_line() -> None:
    """MOVE_WALL (Checkpoint 3) moves a wall's whole straight run; MOVE_EDGE moves only the part
    of the line that must move. On real plans the edge move changes fewer rooms."""
    smaller = 0
    for name in CASES:
        plan = golden(name)
        floor = plan.floors[0]
        nodes = {n.id: (n.x, n.y) for n in floor.nodes}
        rects = rects_of(plan)
        for op, result, outcome in outcomes(name, edge_moves(name)):
            if outcome != "VALID" or result is None or not isinstance(op, MoveEdge):
                continue
            after = rects_of(result.plan)
            changed = {k for k in rects if rects[k] != after[k]}
            r = rects[op.room]
            vertical = op.side in (RoomSide.LEFT, RoomSide.RIGHT)
            line = {"LEFT": r.x0, "RIGHT": r.x1, "FRONT": r.y0, "BACK": r.y1}[op.side]
            wall = next(
                (
                    w
                    for w in floor.walls
                    if all(
                        (nodes[n][0] if vertical else nodes[n][1]) == line
                        and (
                            r.y0 <= nodes[n][1] <= r.y1 if vertical else r.x0 <= nodes[n][0] <= r.x1
                        )
                        for n in (w.a, w.b)
                    )
                ),
                None,
            )
            if wall is None:  # an open room's outside edge has no wall
                continue
            _, _, run_nodes = wall_run(floor, wall.id)
            along = sorted(nodes[n][1] if vertical else nodes[n][0] for n in run_nodes)
            on_run = {
                k
                for k, q in rects.items()
                if line in ((q.x0, q.x1) if vertical else (q.y0, q.y1))
                and ((q.y0, q.y1) if vertical else (q.x0, q.x1))[0] < along[-1]
                and ((q.y0, q.y1) if vertical else (q.x0, q.x1))[1] > along[0]
            }
            assert changed <= on_run
            smaller += len(changed) < len(on_run)
    assert smaller > 0


def test_impossible_edge_moves_are_rejected_with_their_reason() -> None:
    plan = golden(CASES[0])
    room = next(r for r in plan.floors[0].rooms if r.enclosed)
    r = rects_of(plan)[room.id]
    rules = ruleset()
    cases: list[tuple[PlanOp, PlanOpRejection]] = [
        (MoveEdge(room=room.id, side=RoomSide.RIGHT, delta_mm=0), PlanOpRejection.NO_MOVEMENT),
        (
            MoveEdge(room="nowhere", side=RoomSide.RIGHT, delta_mm=100),
            PlanOpRejection.UNKNOWN_ENTITY,
        ),
        (
            MoveEdge(room=room.id, side=RoomSide.RIGHT, delta_mm=-r.w),
            PlanOpRejection.WALL_WOULD_COLLAPSE,
        ),
    ]
    for op, code in cases:
        with pytest.raises(OperationRejected) as caught:
            apply(plan, op, rules)
        assert caught.value.code == code, op
    assert caught.value.entities == (room.id,)  # the collapse names the room


def test_every_rejection_code_of_an_edge_move_occurs_on_real_plans() -> None:
    seen = {outcome for name in CASES for _, _, outcome in outcomes(name, edge_moves(name))}
    assert {"VALID", "INVALID", PlanOpRejection.HOSTED_ITEM_LEAVES_WALL.value} <= seen


# ---------- ADD_ROOM ----------


def add_attempts(name: str) -> Iterator[PlanOp]:
    for room in golden(name).floors[0].rooms:
        for side in SIDES:
            for t, depth in (
                (RoomType.WC, 1500),
                (RoomType.UTILITY, 1500),
                (RoomType.BEDROOM, 3000),
            ):
                yield AddRoom(host_room=room.id, type=t, side=side, depth_mm=depth)


def test_adding_a_room_splits_the_host_with_a_door_and_records_the_owner_change() -> None:
    name = "2bhk_22x60_narrow_deep"
    plan = golden(name)
    op, result = first(name, add_attempts(name), "VALID")
    assert isinstance(op, AddRoom)
    assert result is not None
    edited = result.plan
    new = next(r for r in edited.floors[0].rooms if r.id not in rects_of(plan))
    assert new.type == op.type
    assert new.origin.kind == OriginKind.USER_EDIT
    assert new.required is False
    rects = rects_of(edited)
    host_before = rects_of(plan)[op.host_room]
    assert rects[op.host_room].area + rects[new.id].area == host_before.area
    doors = [k for k, c in connections(edited).items() if c == {op.host_room, new.id}]
    assert len(doors) == 1
    door = next(o for o in edited.floors[0].openings if o.id == doors[0])
    assert door.kind == OpeningKind.DOOR
    assert door.width_mm == ruleset().openings.door_width_mm
    if ruleset().rooms[op.type].needs_window:
        assert any(
            c == {new.id, "EXTERIOR"} or (new.id in c and len(c) == 1)
            for k, c in connections(edited).items()
            if next(o for o in edited.floors[0].openings if o.id == k).kind == OpeningKind.WINDOW
        )
    (record,) = edited.compromises
    assert record.change_key == ProgrammeChange.ROOM_ADDED_BY_OWNER
    assert record.params == {"room": new.id, "room_type": op.type.value}
    assert record.accepted_by_user is True
    assert any(c.id == record.constraint for c in edited.constraints)
    assert_canonical_graph(edited)
    assert result.inverse == (RevertToRevision(revision=0),)
    # the other rooms' connections are untouched
    before = connections(plan)
    assert {k: v for k, v in connections(edited).items() if k in before} == before


def test_a_room_that_cannot_be_added_says_why() -> None:
    name = CASES[0]
    plan = golden(name)
    rules = ruleset()
    living = rects_of(plan)["living"]
    cases: list[tuple[PlanOp, PlanOpRejection]] = [
        (
            AddRoom(host_room="living", type=RoomType.WC, side=RoomSide.BACK, depth_mm=living.h),
            PlanOpRejection.NOT_A_SLICE,
        ),
        (
            AddRoom(host_room="living", type=RoomType.PARKING, side=RoomSide.BACK, depth_mm=1000),
            PlanOpRejection.ROOM_TYPE_NOT_ALLOWED,
        ),
        (
            AddRoom(host_room="living", type=RoomType.STORE, side=RoomSide.BACK, depth_mm=1000),
            PlanOpRejection.ROOM_TYPE_NOT_ALLOWED,  # not in this ruleset
        ),
    ]
    for op, code in cases:
        with pytest.raises(OperationRejected) as caught:
            apply(plan, op, rules)
        assert caught.value.code == code, op
    # a slice that would carry a door of the host to a different room is refused, never moved
    seen = {outcome for _, _, outcome in outcomes(name, add_attempts(name))}
    assert PlanOpRejection.HOSTED_ITEM_CHANGES_ROOMS.value in seen


# ---------- DELETE_ROOM ----------


def delete_attempts(name: str) -> Iterator[PlanOp]:
    rooms = golden(name).floors[0].rooms
    for a in rooms:
        for b in rooms:
            if a.id != b.id:
                yield DeleteRoom(room=a.id, merge_into=b.id)


@pytest.mark.parametrize("name", CASES[:3])
def test_deleting_a_room_merges_it_and_records_the_owner_change(name: str) -> None:
    plan = golden(name)
    op, result = first(name, delete_attempts(name), "VALID")
    assert isinstance(op, DeleteRoom)
    assert result is not None
    edited = result.plan
    before, after = rects_of(plan), rects_of(edited)
    assert op.room not in after
    a, b = before[op.room], before[op.merge_into]
    assert after[op.merge_into].area == a.area + b.area
    assert {k: v for k, v in after.items() if k != op.merge_into} == {
        k: v for k, v in before.items() if k not in (op.room, op.merge_into)
    }
    assert all(f.room != op.room for f in edited.floors[0].fixtures)
    assert all(op.room not in c for c in connections(edited).values())
    gone = next(r for r in plan.floors[0].rooms if r.id == op.room)
    if gone.origin.kind != OriginKind.SOLVER:
        (record,) = edited.compromises
        assert record.change_key == ProgrammeChange.ROOM_REMOVED_BY_OWNER
        assert record.params == {"room": op.room, "room_type": gone.type.value}
    assert_canonical_graph(edited)


def test_rooms_that_do_not_make_a_rectangle_are_not_merged() -> None:
    name = CASES[0]
    plan = golden(name)
    rules = ruleset()
    rects = rects_of(plan)
    keys = list(rects)
    apart = next(
        (a, b)
        for a in keys
        for b in keys
        if a != b
        and not (
            (rects[a].y0, rects[a].y1) == (rects[b].y0, rects[b].y1)
            and (rects[a].x1 == rects[b].x0 or rects[b].x1 == rects[a].x0)
        )
        and not (
            (rects[a].x0, rects[a].x1) == (rects[b].x0, rects[b].x1)
            and (rects[a].y1 == rects[b].y0 or rects[b].y1 == rects[a].y0)
        )
    )
    for op, code in [
        (DeleteRoom(room=apart[0], merge_into=apart[1]), PlanOpRejection.ROOMS_NOT_MERGEABLE),
        (DeleteRoom(room=apart[0], merge_into=apart[0]), PlanOpRejection.ROOMS_NOT_MERGEABLE),
        (DeleteRoom(room=apart[0], merge_into="nowhere"), PlanOpRejection.UNKNOWN_ENTITY),
    ]:
        with pytest.raises(OperationRejected) as caught:
            apply(plan, op, rules)
        assert caught.value.code == code, op


def test_removing_a_room_the_owner_added_leaves_no_trace_of_either_change() -> None:
    name = "2bhk_22x60_narrow_deep"
    plan = golden(name)
    op, added = first(name, add_attempts(name), "VALID")
    assert isinstance(op, AddRoom)
    assert added is not None
    new = next(r.id for r in added.plan.floors[0].rooms if r.id not in rects_of(plan))
    removed, _ = apply_edit(added.plan, [DeleteRoom(room=new, merge_into=op.host_room)], ruleset())
    assert removed.compromises == []
    assert removed.constraints == plan.constraints
    assert rects_of(removed) == rects_of(plan)


# ---------- room metadata ----------


def test_a_type_change_is_recorded_counted_and_undone_exactly() -> None:
    name = "4bhk_50x80_large_two_cars"
    plan = golden(name)
    bedroom = next(r for r in plan.floors[0].rooms if r.type == RoomType.BEDROOM)
    changed, inverse = apply(plan, SetRoomType(room=bedroom.id, type=RoomType.DINING), ruleset())
    room = next(r for r in changed.floors[0].rooms if r.id == bedroom.id)
    assert room.type == RoomType.DINING
    assert room.zone == ruleset().rooms[RoomType.DINING].zone
    (record,) = changed.compromises
    assert record.change_key == ProgrammeChange.ROOM_TYPE_CHANGED_BY_OWNER
    assert record.params == {"room": bedroom.id, "from_type": "BEDROOM", "to_type": "DINING"}
    restored, _ = apply(changed, inverse, ruleset())
    assert sha256_of(restored.body()) == sha256_of(plan.body())

    # the validator counts against the requirement plus the recorded change
    intent = intent_of(benchmark_cases()[name], ruleset())
    counted = validate(changed, ruleset(), intent=intent)
    assert ValidationCode.ROOM_COUNT_MISMATCH not in {e.code for e in counted.errors}


def test_the_validator_still_catches_a_programme_change_nobody_recorded() -> None:
    name = "4bhk_50x80_large_two_cars"
    plan = golden(name)
    intent = intent_of(benchmark_cases()[name], ruleset())
    bedroom = next(r for r in plan.floors[0].rooms if r.type == RoomType.BEDROOM)
    changed, _ = apply(plan, SetRoomType(room=bedroom.id, type=RoomType.DINING), ruleset())
    silent = changed.model_copy(update={"compromises": []})
    assert ValidationCode.ROOM_COUNT_MISMATCH in {
        e.code for e in validate(silent, ruleset(), intent=intent).errors
    }
    unaccepted = changed.model_copy(
        update={
            "compromises": [changed.compromises[0].model_copy(update={"accepted_by_user": None})]
        }
    )
    assert ValidationCode.ROOM_COUNT_MISMATCH in {
        e.code for e in validate(unaccepted, ruleset(), intent=intent).errors
    }
    forged = Compromise(
        id="other",
        constraint="c1",
        change_key="SOMETHING_ELSE",
        params={"room": bedroom.id},
        accepted_by_user=True,
    )
    assert ValidationCode.ROOM_COUNT_MISMATCH in {
        e.code
        for e in validate(
            silent.model_copy(update={"compromises": [forged]}), ruleset(), intent=intent
        ).errors
    }


def test_a_type_the_ruleset_cannot_give_this_room_is_refused() -> None:
    plan = golden("4bhk_50x80_large_two_cars")
    for room, to in (("bedroom_1", RoomType.PARKING), ("bedroom_1", RoomType.STORE)):
        with pytest.raises(OperationRejected) as caught:
            apply(plan, SetRoomType(room=room, type=to), ruleset())
        assert caught.value.code == PlanOpRejection.ROOM_TYPE_NOT_ALLOWED


def test_renaming_and_retyping_back_and_forth_keeps_at_most_one_record() -> None:
    plan = golden("4bhk_50x80_large_two_cars")
    rules = ruleset()
    step, _ = apply(plan, SetRoomType(room="bedroom_1", type=RoomType.DINING), rules)
    step, _ = apply(step, SetRoomType(room="bedroom_1", type=RoomType.LIVING), rules)
    step, _ = apply(step, RenameRoom(room="bedroom_1", name="Family room"), rules)
    (record,) = step.compromises
    assert record.params == {"room": "bedroom_1", "from_type": "BEDROOM", "to_type": "LIVING"}
    step, _ = apply(step, SetRoomType(room="bedroom_1", type=RoomType.BEDROOM), rules)
    assert step.compromises == []


# ---------- openings ----------


def test_openings_are_added_resized_moved_and_deleted_with_exact_inverses() -> None:
    name = "2bhk_40x80_west_two_cars"
    plan = golden(name)
    floor = plan.floors[0]
    window = next(o for o in floor.openings if o.kind == OpeningKind.WINDOW)
    centre = window.offset_mm + window.width_mm // 2
    wider = window.width_mm + 200
    resize: list[PlanOp] = [
        SetOpening(
            opening=window.id, width_mm=wider, height_mm=window.height_mm, sill_mm=window.sill_mm
        ),
        MoveOpening(opening=window.id, offset_mm=centre - wider // 2),
    ]
    resized = run(name, resize)
    assert resized.report.valid, [e.message for e in resized.report.errors]
    restored, _ = apply_batch(resized.plan, resized.inverse)
    assert sha256_of(restored.body()) == sha256_of(plan.body())

    deleted = run(name, [DeleteOpening(opening=window.id)])
    assert deleted.inverse == (AddOpening(opening=window),)
    # the room loses its only window: the validator reports it, so it would not be stored
    assert ValidationCode.HABITABLE_ROOM_NO_WINDOW in {e.code for e in deleted.report.errors}

    exterior = next(
        w
        for w in floor.walls
        if w.kind == WallKind.EXTERIOR and not any(o.wall == w.id for o in floor.openings)
    )
    added = Opening(
        id="window_new",
        kind=OpeningKind.WINDOW,
        wall=exterior.id,
        offset_mm=1000,
        width_mm=600,
        height_mm=1200,
        sill_mm=900,
    )
    with_window = run(name, [AddOpening(opening=added)])
    assert with_window.inverse == (DeleteOpening(opening="window_new"),)
    on_interior = run(
        name,
        [
            AddOpening(
                opening=added.model_copy(
                    update={"wall": next(w.id for w in floor.walls if w.kind == WallKind.INTERIOR)}
                )
            )
        ],
    )
    assert ValidationCode.WINDOW_ON_INTERIOR_WALL in {e.code for e in on_interior.report.errors}


# ---------- batches and replay ----------


def test_a_batch_with_a_structural_edit_undoes_by_revision_and_a_revert_stands_alone() -> None:
    name = CASES[0]
    plan = golden(name)
    op, _ = first(name, edge_moves(name), "VALID")
    door = next(o for o in plan.floors[0].openings if o.kind == OpeningKind.DOOR)
    _, inverse = apply_batch(
        plan, [MoveOpening(opening=door.id, offset_mm=door.offset_mm), op], ruleset()
    )
    assert inverse == (RevertToRevision(revision=0),)
    for revert in (RevertToRevision(revision=0), RevertToVersion(version=1)):
        with pytest.raises(BatchRejected) as caught:
            apply_batch(plan, [op, revert], ruleset())
        assert caught.value.index == 1
        assert caught.value.rejected.code == PlanOpRejection.REVERT_NOT_ALONE


@pytest.mark.parametrize("name", CASES[:2])
def test_replaying_a_logged_batch_reproduces_it_byte_for_byte(name: str) -> None:
    op, result = first(name, edge_moves(name), "VALID")
    assert result is not None
    again, _ = apply_edit(golden(name), [op], ruleset())
    assert dump(again) == dump(result.plan)
    assert again.meta.body_sha256 == sha256_of(again.body())


def test_a_move_wall_still_moves_the_whole_run() -> None:
    """Checkpoint 3 behaviour is unchanged: MOVE_WALL is the 'move whole line' tool."""
    name = CASES[0]
    plan = golden(name)
    wall = next(w for w in plan.floors[0].walls if w.kind == WallKind.INTERIOR)
    _, run_walls, _ = wall_run(plan.floors[0], wall.id)
    _, inverse = apply(plan, MoveWall(wall=wall.id, delta_mm=100))
    assert inverse == MoveWall(wall=wall.id, delta_mm=-100)
    assert run_walls


# ---------- E-5: a home keeps a kitchen and a bathroom ----------


def _without_others(plan: HousePlan, keep: str, types: set[RoomType]) -> HousePlan:
    """The plan with every other room of `types` retyped away through recorded changes, so `keep`
    is the last one."""
    rules = ruleset()
    for room in plan.floors[0].rooms:
        if room.type in types and room.id != keep:
            plan, _ = apply(plan, SetRoomType(room=room.id, type=RoomType.UTILITY), rules)
    return plan


@pytest.mark.parametrize(
    ("kinds", "code"),
    [
        ({RoomType.KITCHEN}, PlanOpRejection.LAST_KITCHEN_REQUIRED),
        (
            {RoomType.BATH_ATTACHED, RoomType.BATH_COMMON, RoomType.WC},
            PlanOpRejection.LAST_BATHROOM_REQUIRED,
        ),
    ],
)
def test_the_last_kitchen_or_bathroom_cannot_be_removed_or_retyped(
    kinds: set[RoomType], code: PlanOpRejection
) -> None:
    rules = ruleset()
    plan = golden("4bhk_50x80_large_two_cars")
    last = next(r for r in plan.floors[0].rooms if r.type in kinds)
    plan = _without_others(plan, last.id, kinds)
    assert [r.id for r in plan.floors[0].rooms if r.type in kinds] == [last.id]
    with pytest.raises(OperationRejected) as retyped:
        apply(plan, SetRoomType(room=last.id, type=RoomType.STORE), rules)
    assert retyped.value.code == code
    assert retyped.value.entities == (last.id,)
    rects = rects_of(plan)
    neighbours = [
        k
        for k in rects
        if k != last.id
        and (
            (
                (rects[k].y0, rects[k].y1) == (rects[last.id].y0, rects[last.id].y1)
                and (rects[k].x1 == rects[last.id].x0 or rects[last.id].x1 == rects[k].x0)
            )
            or (
                (rects[k].x0, rects[k].x1) == (rects[last.id].x0, rects[last.id].x1)
                and (rects[k].y1 == rects[last.id].y0 or rects[last.id].y1 == rects[k].y0)
            )
        )
    ]
    for target in neighbours or ["living"]:
        with pytest.raises(OperationRejected) as removed:
            apply(plan, DeleteRoom(room=last.id, merge_into=target), rules)
        assert removed.value.code in (code, PlanOpRejection.ROOMS_NOT_MERGEABLE)
        if neighbours:
            assert removed.value.code == code


def test_other_kitchens_and_bathrooms_stay_removable_and_retypable_within_their_function() -> None:
    rules = ruleset()
    plan = golden("4bhk_50x80_large_two_cars")
    baths = [
        r for r in plan.floors[0].rooms if r.type in (RoomType.BATH_ATTACHED, RoomType.BATH_COMMON)
    ]
    assert len(baths) >= 2
    changed, _ = apply(plan, SetRoomType(room=baths[0].id, type=RoomType.UTILITY), rules)
    assert next(r for r in changed.floors[0].rooms if r.id == baths[0].id).type == RoomType.UTILITY
    # within the function, even the last one may change: a bathroom becoming a toilet keeps it
    last_plan = _without_others(
        plan, baths[0].id, {RoomType.BATH_ATTACHED, RoomType.BATH_COMMON, RoomType.WC}
    )
    toilet, _ = apply(last_plan, SetRoomType(room=baths[0].id, type=RoomType.WC), rules)
    assert next(r for r in toilet.floors[0].rooms if r.id == baths[0].id).type == RoomType.WC
