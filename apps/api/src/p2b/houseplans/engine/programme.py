"""The owner's changes to the room programme (Checkpoint 3.1, decision "record as compromises").

Adding, removing or retyping a room departs from the requirement. The requirement is never
modified: each departure is a HousePlan compromise (I-P6) the owner accepted by making the edit,
at most one per room:

- ROOM_ADDED_BY_OWNER {room, room_type}
- ROOM_REMOVED_BY_OWNER {room, room_type}: room_type is the type the requirement gave it
- ROOM_TYPE_CHANGED_BY_OWNER {room, from_type, to_type}

The validator counts rooms against the requirement plus these records (`expected_counts`) and
drops the requirement's relations for rooms the owner removed; every other check is unchanged.
Rooms the solver added for circulation are not part of the requirement, so changing them records
nothing. Records are kept net: retyping a room back, or removing a room the owner added, deletes
the record, so an operation followed by its inverse leaves the document exactly as it was."""

from collections import Counter
from collections.abc import Iterable

from p2b.core.vocabulary import (
    ConstraintKind,
    ConstraintOutcome,
    ConstraintStrength,
    OriginKind,
    PlanOpRejection,
    ProgrammeChange,
    RoomType,
)
from p2b.houseplans.engine.model import Compromise, Constraint, HousePlan, Origin, Room

# Checkpoint 3.1, decision E-5: the owner may add, remove and retype rooms, but the plan keeps
# at least one room for each of these functions. Removing or retyping the last one is refused.
ESSENTIAL: dict[PlanOpRejection, frozenset[RoomType]] = {
    PlanOpRejection.LAST_KITCHEN_REQUIRED: frozenset({RoomType.KITCHEN}),
    PlanOpRejection.LAST_BATHROOM_REQUIRED: frozenset(
        {RoomType.BATH_ATTACHED, RoomType.BATH_COMMON, RoomType.WC}
    ),
}

_OWNER_CONSTRAINT = "owner_room_"  # id prefix of a ROOM_PRESENT added for an owner-added type
_RECORD = "owner_change_"


def owner_changes(compromises: Iterable[Compromise]) -> list[Compromise]:
    """The accepted programme changes, in document order."""
    keys = {c.value for c in ProgrammeChange}
    return [c for c in compromises if c.change_key in keys and c.accepted_by_user is True]


def expected_counts(
    requirement: Counter[RoomType], compromises: Iterable[Compromise]
) -> Counter[RoomType]:
    """Rooms of each type the plan should have: the requirement plus the owner's changes."""
    out: Counter[RoomType] = Counter(requirement)
    for c in owner_changes(compromises):
        if c.change_key == ProgrammeChange.ROOM_ADDED_BY_OWNER:
            out[RoomType(str(c.params["room_type"]))] += 1
        elif c.change_key == ProgrammeChange.ROOM_REMOVED_BY_OWNER:
            out[RoomType(str(c.params["room_type"]))] -= 1
        else:
            out[RoomType(str(c.params["from_type"]))] -= 1
            out[RoomType(str(c.params["to_type"]))] += 1
    return out


def removed_rooms(compromises: Iterable[Compromise]) -> set[str]:
    return {
        str(c.params["room"])
        for c in owner_changes(compromises)
        if c.change_key == ProgrammeChange.ROOM_REMOVED_BY_OWNER
    }


def essential_loss(
    plan: HousePlan, room: Room, new_type: RoomType | None
) -> PlanOpRejection | None:
    """The refusal for removing `room` (`new_type` None) or retyping it to `new_type` when it is
    the plan's last room of an essential function (ESSENTIAL); None when the change is allowed.
    """
    for code, types in ESSENTIAL.items():
        if room.type not in types or (new_type is not None and new_type in types):
            continue
        others = sum(1 for f in plan.floors for r in f.rooms if r.id != room.id and r.type in types)
        if others == 0:
            return code
    return None


def _counted(room: Room) -> bool:
    return room.origin.kind != OriginKind.SOLVER


def _record_of(plan: HousePlan, room: str) -> int | None:
    for i, c in enumerate(plan.compromises):
        if c.change_key in ProgrammeChange.__members__ and c.params.get("room") == room:
            return i
    return None


def _next_id(plan: HousePlan) -> str:
    used = [
        int(c.id[len(_RECORD) :])
        for c in plan.compromises
        if c.id.startswith(_RECORD) and c.id[len(_RECORD) :].isdigit()
    ]
    return f"{_RECORD}{max(used, default=0) + 1}"


def _new(plan: HousePlan, key: ProgrammeChange, params: dict[str, str]) -> Compromise:
    # `constraint` is filled in by _settle
    return Compromise(
        id=_next_id(plan),
        constraint="pending",
        change_key=key.value,
        params=dict(params),
        accepted_by_user=True,
    )


def _with(plan: HousePlan, compromises: list[Compromise]) -> HousePlan:
    return _settle(plan.model_copy(update={"compromises": compromises}))


def room_added(plan: HousePlan, room: Room) -> HousePlan:
    record = _new(
        plan, ProgrammeChange.ROOM_ADDED_BY_OWNER, {"room": room.id, "room_type": room.type.value}
    )
    return _with(plan, [*plan.compromises, record])


def room_removed(plan: HousePlan, room: Room) -> HousePlan:
    """Call with the plan as it was before the room went."""
    if not _counted(room):
        return plan
    items = list(plan.compromises)
    i = _record_of(plan, room.id)
    if i is None:
        params = {"room": room.id, "room_type": room.type.value}
        items.append(_new(plan, ProgrammeChange.ROOM_REMOVED_BY_OWNER, params))
    elif items[i].change_key == ProgrammeChange.ROOM_ADDED_BY_OWNER:
        items.pop(i)
    else:  # retyped, then removed: the requirement lost a room of the original type
        params = {"room": room.id, "room_type": str(items[i].params["from_type"])}
        items[i] = items[i].model_copy(
            update={"change_key": ProgrammeChange.ROOM_REMOVED_BY_OWNER.value, "params": params}
        )
    return _with(plan, items)


def room_retyped(plan: HousePlan, room: Room, new_type: RoomType) -> HousePlan:
    """Call with the plan as it was before the change; `room` carries the old type."""
    if not _counted(room) or room.type == new_type:
        return plan
    items = list(plan.compromises)
    i = _record_of(plan, room.id)
    if i is None:
        params = {"room": room.id, "from_type": room.type.value, "to_type": new_type.value}
        items.append(_new(plan, ProgrammeChange.ROOM_TYPE_CHANGED_BY_OWNER, params))
    elif items[i].change_key == ProgrammeChange.ROOM_ADDED_BY_OWNER:
        params = {"room": room.id, "room_type": new_type.value}
        items[i] = items[i].model_copy(update={"params": params})
    elif str(items[i].params["from_type"]) == new_type.value:
        items.pop(i)  # back to what the requirement asked for
    else:
        changed = {**items[i].params, "to_type": new_type.value}
        items[i] = items[i].model_copy(update={"params": changed})
    return _with(plan, items)


def _settle(plan: HousePlan) -> HousePlan:
    """Points every programme record at the ROOM_PRESENT constraint of the type it changes,
    adding a USER_EDIT ROOM_PRESENT {"count": 0} for a type the requirement did not ask for
    (after the last hard constraint), and dropping such constraints once nothing points at them.
    """
    constraints = list(plan.constraints)

    def present(room_type: str) -> str | None:
        return next(
            (
                c.id
                for c in constraints
                if c.kind == ConstraintKind.ROOM_PRESENT
                and c.strength == ConstraintStrength.HARD
                and c.subjects == [room_type]
            ),
            None,
        )

    compromises = []
    for c in plan.compromises:
        if c.change_key not in ProgrammeChange.__members__:
            compromises.append(c)
            continue
        target = str(c.params.get("room_type") or c.params["from_type"])
        ident = present(target)
        if ident is None:
            ident = f"{_OWNER_CONSTRAINT}{target.lower()}"
            last_hard = max(
                (i for i, x in enumerate(constraints) if x.strength == ConstraintStrength.HARD),
                default=-1,
            )
            constraints.insert(
                last_hard + 1,
                Constraint(
                    id=ident,
                    kind=ConstraintKind.ROOM_PRESENT,
                    strength=ConstraintStrength.HARD,
                    weight=0,
                    subjects=[target],
                    params={"count": 0},
                    origin=Origin(kind=OriginKind.USER_EDIT, ref="editor:add_room"),
                    outcome=ConstraintOutcome.MET,
                ),
            )
        compromises.append(c.model_copy(update={"constraint": ident}))
    used = {c.constraint for c in compromises}
    constraints = [c for c in constraints if not c.id.startswith(_OWNER_CONSTRAINT) or c.id in used]
    return plan.model_copy(update={"constraints": constraints, "compromises": compromises})
