"""Typed HousePlan operations (CP1-11). The one way a plan changes after generation: deterministic
repair uses them now; the editor and natural-language edits will compile into them later. Each
apply returns the new plan and the inverse operation, so history and undo are exact. The applied
batches are logged in `house_plan_ops` (Checkpoint 3).

Checkpoint 1 applies the opening, fixture and room-label operations; Checkpoint 3 adds MOVE_WALL
(`_move_wall`); Checkpoint 3.1 adds the structural edits MOVE_EDGE, ADD_ROOM and DELETE_ROOM
(`graph_edit`), which rebuild the planar graph and so need the plan's ruleset. Their inverse is
REVERT_TO_REVISION of the revision they were applied to: the plan service rebuilds that revision
from version 1 and the operation log. REVERT_TO_REVISION and REVERT_TO_VERSION are applied by
the plan service alone, never here. Room additions, removals and type changes are recorded as
the owner's programme changes (`programme`)."""

from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter

from p2b.core.vocabulary import PlanOpKind, PlanOpRejection, RoomSide, RoomType, WallSide
from p2b.houseplans.engine import graph_edit, programme
from p2b.houseplans.engine.model import (
    DoorSpec,
    Fixture,
    Floor,
    Frozen,
    HousePlan,
    Id,
    Mm,
    Node,
    NonNegMm,
    Opening,
    PosMm,
    Room,
    SizeSpec,
    Text,
)
from p2b.houseplans.engine.ruleset import RulesetContent


class MoveOpening(Frozen):
    op: Literal[PlanOpKind.MOVE_OPENING] = PlanOpKind.MOVE_OPENING
    opening: Id
    offset_mm: NonNegMm


class SetOpening(Frozen):
    op: Literal[PlanOpKind.SET_OPENING] = PlanOpKind.SET_OPENING
    opening: Id
    width_mm: PosMm
    height_mm: PosMm
    sill_mm: NonNegMm
    door: DoorSpec | None = None


class AddOpening(Frozen):
    op: Literal[PlanOpKind.ADD_OPENING] = PlanOpKind.ADD_OPENING
    opening: Opening


class DeleteOpening(Frozen):
    op: Literal[PlanOpKind.DELETE_OPENING] = PlanOpKind.DELETE_OPENING
    opening: Id


class MoveFixture(Frozen):
    op: Literal[PlanOpKind.MOVE_FIXTURE] = PlanOpKind.MOVE_FIXTURE
    fixture: Id
    wall: Id
    offset_mm: NonNegMm
    side: WallSide


class AddFixture(Frozen):
    op: Literal[PlanOpKind.ADD_FIXTURE] = PlanOpKind.ADD_FIXTURE
    fixture: Fixture


class DeleteFixture(Frozen):
    op: Literal[PlanOpKind.DELETE_FIXTURE] = PlanOpKind.DELETE_FIXTURE
    fixture: Id


class RenameRoom(Frozen):
    op: Literal[PlanOpKind.RENAME_ROOM] = PlanOpKind.RENAME_ROOM
    room: Id
    name: Text


class SetRoomType(Frozen):
    op: Literal[PlanOpKind.SET_ROOM_TYPE] = PlanOpKind.SET_ROOM_TYPE
    room: Id
    type: RoomType


class MoveWall(Frozen):
    op: Literal[PlanOpKind.MOVE_WALL] = PlanOpKind.MOVE_WALL
    wall: Id
    delta_mm: Mm  # perpendicular to the wall, toward its LEFT side when positive


class MoveEdge(Frozen):
    """One side of a rectangular room, moved along +x (LEFT, RIGHT) or +y (FRONT, BACK); only
    the part of that line that must move with it moves (`graph_edit.move_edge`)."""

    op: Literal[PlanOpKind.MOVE_EDGE] = PlanOpKind.MOVE_EDGE
    room: Id
    side: RoomSide
    delta_mm: Mm


class AddRoom(Frozen):
    """A new room split off one side of the host across its full width, `depth_mm` deep, with a
    door from the host (`graph_edit.add_room`). Checkpoint 3.1 replaced the never-applied
    free-rectangle form (x0, y0, x1, y1): the browser sends no coordinates."""

    op: Literal[PlanOpKind.ADD_ROOM] = PlanOpKind.ADD_ROOM
    host_room: Id
    type: RoomType
    side: RoomSide
    depth_mm: PosMm


class AddRoomOutside(Frozen):
    """A new room in open space against an outside wall of the host (Checkpoint 3.2): `depth_mm`
    beyond the host's `side`, `length_mm` long from `offset_mm` along that side, measured from
    its left (LEFT, RIGHT sides: front) end. Positions are along a known side, never free
    coordinates (`graph_edit.add_room_outside`)."""

    op: Literal[PlanOpKind.ADD_ROOM_OUTSIDE] = PlanOpKind.ADD_ROOM_OUTSIDE
    host_room: Id
    type: RoomType
    side: RoomSide
    offset_mm: NonNegMm
    length_mm: PosMm
    depth_mm: PosMm


class DeleteRoom(Frozen):
    op: Literal[PlanOpKind.DELETE_ROOM] = PlanOpKind.DELETE_ROOM
    room: Id
    merge_into: Id


class RevertToRevision(Frozen):
    """Make the plan what it was at `revision`, as a new revision (Checkpoint 3.1). The undo of
    a structural edit; applied by the plan service, alone in its batch."""

    op: Literal[PlanOpKind.REVERT_TO_REVISION] = PlanOpKind.REVERT_TO_REVISION
    revision: Annotated[int, Field(ge=0)]


class RevertToVersion(Frozen):
    """Make the plan what named version `version` holds, as a new revision (Checkpoint 3.1).
    Applied by the plan service, alone in its batch."""

    op: Literal[PlanOpKind.REVERT_TO_VERSION] = PlanOpKind.REVERT_TO_VERSION
    version: Annotated[int, Field(ge=1)]


PlanOp = Annotated[
    MoveOpening
    | SetOpening
    | AddOpening
    | DeleteOpening
    | MoveFixture
    | AddFixture
    | DeleteFixture
    | RenameRoom
    | SetRoomType
    | MoveWall
    | MoveEdge
    | AddRoom
    | AddRoomOutside
    | DeleteRoom
    | RevertToRevision
    | RevertToVersion,
    Field(discriminator="op"),
]
PLAN_OP: TypeAdapter[PlanOp] = TypeAdapter(PlanOp)
STRUCTURAL = (MoveEdge, AddRoom, AddRoomOutside, DeleteRoom)
REVERTS = (RevertToRevision, RevertToVersion)


class OperationRejected(Exception):
    """The operation cannot apply to this plan. `code` says why, for the editor; `reason` is the
    detail for logs and tests."""

    def __init__(
        self,
        op: PlanOpKind,
        reason: str,
        code: PlanOpRejection = PlanOpRejection.NOT_SUPPORTED,
        entities: tuple[str, ...] = (),
    ):
        super().__init__(f"{op.value}: {reason}")
        self.op, self.reason, self.code = op, reason, code
        self.entities = entities  # the ids the editor names in its message (Checkpoint 3.1)


def _floor_index(plan: HousePlan, attr: str, ident: str) -> tuple[int, int]:
    for fi, floor in enumerate(plan.floors):
        for i, item in enumerate(getattr(floor, attr)):
            if item.id == ident:
                return fi, i
    raise LookupError(ident)


def _replace(plan: HousePlan, fi: int, attr: str, items: list[Any]) -> HousePlan:
    floors = list(plan.floors)
    floors[fi] = floors[fi].model_copy(update={attr: items})
    return plan.model_copy(update={"floors": floors})


def apply(
    plan: HousePlan, op: PlanOp, ruleset: RulesetContent | None = None
) -> tuple[HousePlan, PlanOp]:
    """The plan with `op` applied, and the operation that undoes it. The result is not validated
    here: callers validate after every batch. The structural edits need `ruleset` (wall
    thicknesses, door and window sizes); with it, a room type change is checked against it and
    takes the type's zone and sizes."""
    try:
        if isinstance(op, STRUCTURAL):
            if ruleset is None:
                raise OperationRejected(op.op, "needs the plan's ruleset")
            return _structural(plan, op, ruleset), RevertToRevision(revision=plan.meta.revision_no)
        if isinstance(op, REVERTS):
            raise OperationRejected(op.op, "applied by the plan service, alone in its batch")
        if isinstance(op, MoveOpening | SetOpening | DeleteOpening):
            fi, i = _floor_index(plan, "openings", op.opening)
            items = list(plan.floors[fi].openings)
            old = items[i]
            if isinstance(op, MoveOpening):
                items[i] = old.model_copy(update={"offset_mm": op.offset_mm})
                inverse: PlanOp = MoveOpening(opening=old.id, offset_mm=old.offset_mm)
            elif isinstance(op, SetOpening):
                items[i] = Opening.model_validate(
                    {
                        **old.model_dump(),
                        "width_mm": op.width_mm,
                        "height_mm": op.height_mm,
                        "sill_mm": op.sill_mm,
                        "door": op.door.model_dump() if op.door else None,
                    }
                )
                inverse = SetOpening(
                    opening=old.id,
                    width_mm=old.width_mm,
                    height_mm=old.height_mm,
                    sill_mm=old.sill_mm,
                    door=old.door,
                )
            else:
                items.pop(i)
                inverse = AddOpening(opening=old)
            return _replace(plan, fi, "openings", items), inverse
        if isinstance(op, AddOpening):
            if any(o.id == op.opening.id for f in plan.floors for o in f.openings):
                raise OperationRejected(
                    op.op, "opening id exists", PlanOpRejection.ENTITY_EXISTS, (op.opening.id,)
                )
            fi = 0
            return (
                _replace(plan, fi, "openings", [*plan.floors[fi].openings, op.opening]),
                DeleteOpening(opening=op.opening.id),
            )
        if isinstance(op, MoveFixture | DeleteFixture):
            fi, i = _floor_index(plan, "fixtures", op.fixture)
            fixtures = list(plan.floors[fi].fixtures)
            old_f = fixtures[i]
            if isinstance(op, MoveFixture):
                fixtures[i] = old_f.model_copy(
                    update={"wall": op.wall, "offset_mm": op.offset_mm, "side": op.side}
                )
                inverse = MoveFixture(
                    fixture=old_f.id, wall=old_f.wall, offset_mm=old_f.offset_mm, side=old_f.side
                )
            else:
                fixtures.pop(i)
                inverse = AddFixture(fixture=old_f)
            return _replace(plan, fi, "fixtures", fixtures), inverse
        if isinstance(op, AddFixture):
            if any(x.id == op.fixture.id for f in plan.floors for x in f.fixtures):
                raise OperationRejected(
                    op.op, "fixture id exists", PlanOpRejection.ENTITY_EXISTS, (op.fixture.id,)
                )
            return (
                _replace(plan, 0, "fixtures", [*plan.floors[0].fixtures, op.fixture]),
                DeleteFixture(fixture=op.fixture.id),
            )
        if isinstance(op, RenameRoom | SetRoomType):
            fi, i = _floor_index(plan, "rooms", op.room)
            rooms = list(plan.floors[fi].rooms)
            old_r = rooms[i]
            if isinstance(op, RenameRoom):
                rooms[i] = old_r.model_copy(update={"name": op.name})
                inverse = RenameRoom(room=old_r.id, name=old_r.name)
            else:
                lost = programme.essential_loss(plan, old_r, op.type)
                if lost is not None:
                    raise OperationRejected(
                        op.op, f"{old_r.id} is the last room of its kind", lost, (old_r.id,)
                    )
                rooms[i] = _retyped(old_r, op, ruleset)
                inverse = SetRoomType(room=old_r.id, type=old_r.type)
                changed = _replace(plan, fi, "rooms", rooms)
                return programme.room_retyped(changed, old_r, op.type), inverse
            return _replace(plan, fi, "rooms", rooms), inverse
        if isinstance(op, MoveWall):
            return _move_wall(plan, op)
    except LookupError as missing:
        ident = str(missing.args[0]) if missing.args else ""
        raise OperationRejected(
            op.op, f"unknown entity {ident}", PlanOpRejection.UNKNOWN_ENTITY, (ident,)
        ) from None
    raise OperationRejected(op.op, "not supported")


def _structural(
    plan: HousePlan, op: MoveEdge | AddRoom | AddRoomOutside | DeleteRoom, ruleset: RulesetContent
) -> HousePlan:
    try:
        if isinstance(op, MoveEdge):
            return graph_edit.move_edge(plan, op.room, op.side, op.delta_mm, ruleset)
        if isinstance(op, AddRoom):
            return graph_edit.add_room(plan, op.host_room, op.type, op.side, op.depth_mm, ruleset)
        if isinstance(op, AddRoomOutside):
            return graph_edit.add_room_outside(
                plan,
                op.host_room,
                op.type,
                op.side,
                op.offset_mm,
                op.length_mm,
                op.depth_mm,
                ruleset,
            )
        return graph_edit.delete_room(plan, op.room, op.merge_into, ruleset)
    except graph_edit.GraphEditRejected as rejected:
        raise OperationRejected(op.op, rejected.reason, rejected.code, rejected.entities) from None


def _retyped(room: Room, op: SetRoomType, ruleset: RulesetContent | None) -> Room:
    """The room with its new type. With a ruleset, the type must exist there and keep the room
    enclosed or open as it is (that decides which walls exist), and the room takes the type's
    zone and sizes."""
    if ruleset is None:
        return room.model_copy(update={"type": op.type})
    rule = ruleset.rooms.get(op.type)
    if rule is None or rule.enclosed != room.enclosed:
        raise OperationRejected(
            op.op,
            f"{room.id} cannot become {op.type.value}",
            PlanOpRejection.ROOM_TYPE_NOT_ALLOWED,
            (room.id,),
        )
    return room.model_copy(
        update={
            "type": op.type,
            "zone": rule.zone,
            "size_spec": SizeSpec(
                min_short_mm=rule.min_short_mm,
                min_area_mm2=rule.min_area_mm2,
                pref_area_mm2=rule.pref_area_mm2,
                max_area_mm2=rule.max_area_mm2,
            ),
        }
    )


# ---------- MOVE_WALL ----------


def _axis(a: Node, b: Node) -> str | None:
    """'x' for a wall along x, 'y' for a wall along y, None when slanted or of no length."""
    if a.y == b.y and a.x != b.x:
        return "x"
    if a.x == b.x and a.y != b.y:
        return "y"
    return None


def wall_run(floor: Floor, wall_id: str) -> tuple[str, set[str], set[str]]:
    """The straight run a wall belongs to: (axis, wall ids, node ids). The run is the wall and
    every wall collinear with it and joined to it through nodes on the same line, the straight
    line a slicing layout was cut along. LookupError for an unknown wall; axis '' when the wall
    is slanted."""
    nodes = {n.id: n for n in floor.nodes}
    wall = next((w for w in floor.walls if w.id == wall_id), None)
    if wall is None:
        raise LookupError(wall_id)
    axis = _axis(nodes[wall.a], nodes[wall.b])
    if axis is None:
        return "", {wall.id}, {wall.a, wall.b}
    line = nodes[wall.a].y if axis == "x" else nodes[wall.a].x

    def on_line(n: Node) -> bool:
        return (n.y if axis == "x" else n.x) == line

    walls, run_nodes, frontier = {wall.id}, {wall.a, wall.b}, [wall.a, wall.b]
    while frontier:
        node = frontier.pop()
        for w in floor.walls:
            if w.id in walls or node not in (w.a, w.b):
                continue
            a, b = nodes[w.a], nodes[w.b]
            if _axis(a, b) == axis and on_line(a) and on_line(b):
                walls.add(w.id)
                for end in (w.a, w.b):
                    if end not in run_nodes:
                        run_nodes.add(end)
                        frontier.append(end)
    return axis, walls, run_nodes


def _move_wall(plan: HousePlan, op: MoveWall) -> tuple[HousePlan, PlanOp]:
    """Moves the wall's straight run (`wall_run`) perpendicular to itself by `delta_mm`, towards
    the wall's left side looking from node a to node b when positive.

    All the run's nodes move; every other wall meeting the run must be perpendicular to it and
    stretches or shrinks; rooms follow because their boundaries reference nodes. Moving one
    segment of a straight line alone would bend its neighbours out of square, so the run moves
    as one, and the editor shows every room along it.

    Openings and fixtures on a stretched wall keep their place on the ground: when the wall's node
    a moved, their offsets change by the change in length. One that would then start before the
    wall's node a is rejected (HOSTED_ITEM_LEAVES_WALL); one that would run past node b is left
    for the validator to report. Nothing else is checked here: rooms too small, outside the
    envelope or overlapping are the validator's to report."""
    fi, wi = _floor_index(plan, "walls", op.wall)
    floor = plan.floors[fi]
    nodes = {n.id: n for n in floor.nodes}
    wall = floor.walls[wi]
    axis, run, moved = wall_run(floor, wall.id)
    if not axis:
        raise OperationRejected(
            op.op,
            f"wall {wall.id} is not axis-aligned",
            PlanOpRejection.NOT_AXIS_ALIGNED,
            (wall.id,),
        )
    if op.delta_mm == 0:
        raise OperationRejected(op.op, "zero movement", PlanOpRejection.NO_MOVEMENT)

    # the left normal of a → b: along +x it is +y; along +y it is -x
    a, b = nodes[wall.a], nodes[wall.b]
    sign = 1 if (b.x - a.x if axis == "x" else b.y - a.y) > 0 else -1
    dx, dy = (0, sign * op.delta_mm) if axis == "x" else (-sign * op.delta_mm, 0)
    new_nodes = {
        n.id: n.model_copy(update={"x": n.x + dx, "y": n.y + dy}) if n.id in moved else n
        for n in floor.nodes
    }

    length_change: dict[str, tuple[int, bool]] = {}  # wall → (new - old length, node a moved)
    for w in floor.walls:
        if w.id in run or (w.a not in moved and w.b not in moved):
            continue
        old_a, old_b, new_a, new_b = nodes[w.a], nodes[w.b], new_nodes[w.a], new_nodes[w.b]
        if _axis(old_a, old_b) in (axis, None):
            raise OperationRejected(
                op.op,
                f"wall {w.id} meets the moving line but is not perpendicular to it",
                PlanOpRejection.NOT_AXIS_ALIGNED,
                (w.id,),
            )
        before = (old_b.x - old_a.x) + (old_b.y - old_a.y)
        after = (new_b.x - new_a.x) + (new_b.y - new_a.y)
        if after == 0 or (after > 0) != (before > 0):
            raise OperationRejected(
                op.op,
                f"wall {w.id} would collapse",
                PlanOpRejection.WALL_WOULD_COLLAPSE,
                (w.id,),
            )
        length_change[w.id] = (abs(after) - abs(before), w.a in moved)

    def shifted(wall_id: str, offset: int, item: str) -> int:
        change, a_moved = length_change.get(wall_id, (0, False))
        if not a_moved:
            return offset
        if offset + change < 0:
            raise OperationRejected(
                op.op,
                f"{item} would leave wall {wall_id}",
                PlanOpRejection.HOSTED_ITEM_LEAVES_WALL,
                (item,),
            )
        return offset + change

    new_floor = floor.model_copy(
        update={
            "nodes": [new_nodes[n.id] for n in floor.nodes],
            "openings": [
                o.model_copy(update={"offset_mm": shifted(o.wall, o.offset_mm, o.id)})
                for o in floor.openings
            ],
            "fixtures": [
                f.model_copy(update={"offset_mm": shifted(f.wall, f.offset_mm, f.id)})
                for f in floor.fixtures
            ],
        }
    )
    floors = list(plan.floors)
    floors[fi] = new_floor
    return (
        plan.model_copy(update={"floors": floors}),
        MoveWall(wall=wall.id, delta_mm=-op.delta_mm),
    )
