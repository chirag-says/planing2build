"""Typed HousePlan operations (CP1-11). The one way a plan changes after generation: deterministic
repair uses them now; the editor and natural-language edits will compile into them later. Each
apply returns the new plan and the inverse operation, so history and undo are exact. Persistent
operation history is deferred (no table in Checkpoint 1).

Checkpoint 1 applies the opening, fixture and room-label operations. MOVE_WALL, ADD_ROOM and
DELETE_ROOM are defined so the contract is stable, and refuse to apply until the editing
checkpoint implements their graph edits (they must keep rooms and walls on one planar graph)."""

from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter

from p2b.core.vocabulary import PlanOpKind, RoomType, WallSide
from p2b.houseplans.engine.model import (
    DoorSpec,
    Fixture,
    Frozen,
    HousePlan,
    Id,
    Mm,
    NonNegMm,
    Opening,
    PosMm,
    Text,
)


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


class AddRoom(Frozen):
    op: Literal[PlanOpKind.ADD_ROOM] = PlanOpKind.ADD_ROOM
    host_room: Id
    type: RoomType
    x0: Mm
    y0: Mm
    x1: Mm
    y1: Mm


class DeleteRoom(Frozen):
    op: Literal[PlanOpKind.DELETE_ROOM] = PlanOpKind.DELETE_ROOM
    room: Id
    merge_into: Id


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
    | AddRoom
    | DeleteRoom,
    Field(discriminator="op"),
]
PLAN_OP: TypeAdapter[PlanOp] = TypeAdapter(PlanOp)


class OperationRejected(Exception):
    """The operation cannot apply to this plan (unknown entity, or not supported yet)."""

    def __init__(self, op: PlanOpKind, reason: str):
        super().__init__(f"{op.value}: {reason}")
        self.op, self.reason = op, reason


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


def apply(plan: HousePlan, op: PlanOp) -> tuple[HousePlan, PlanOp]:
    """The plan with `op` applied, and the operation that undoes it. The result is not validated
    here: callers validate after every batch."""
    try:
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
                raise OperationRejected(op.op, "opening id exists")
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
                raise OperationRejected(op.op, "fixture id exists")
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
                rooms[i] = old_r.model_copy(update={"type": op.type})
                inverse = SetRoomType(room=old_r.id, type=old_r.type)
            return _replace(plan, fi, "rooms", rooms), inverse
    except LookupError as missing:
        raise OperationRejected(op.op, f"unknown entity {missing}") from None
    raise OperationRejected(op.op, "not supported until the editing checkpoint")
