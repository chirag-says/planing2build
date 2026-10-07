"""Structured intent for AI-assisted design interpretation (Checkpoint 4). Pure: no I/O.

A language model never touches geometry. It answers in one of two closed schemas:

- RequirementIntent: what a homeowner's description of a home asks for (plot, rooms, parking,
  preferences, questions back, and what is outside this product). `requirement_answers` turns
  it into the requirement answers and provisional design inputs the existing `normalise` and the
  deterministic solver consume. Nothing here invents a missing fact: it is listed as missing.
- EditInterpretation: one edit intent from a closed vocabulary (resize a room, move it towards
  another, add, remove, retype or rename a room, move or resize a door or window), or an
  explicit UNSUPPORTED or CLARIFY. Rooms are named by the ids the plan already has.

`compile_edit` turns an edit intent into typed operations deterministically: it builds a fixed,
ordered list of candidate batches from the plan's own geometry and keeps the first that the
engine applies and the validator passes. The browser shows the result as a proposal; nothing is
stored until the owner confirms it and the server applies and validates it again."""

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints

from p2b.core.vocabulary import (
    DiningArrangement,
    Facing,
    KitchenArrangement,
    OpeningKind,
    ParkingKind,
    RoomSide,
    RoomType,
    SetbackSide,
)
from p2b.houseplans.engine.build import ROOM_NAMES, room_name
from p2b.houseplans.engine.derive import analyse, plan_geometry
from p2b.houseplans.engine.edit import BatchRejected, EditResult, edit
from p2b.houseplans.engine.graph_edit import room_rects
from p2b.houseplans.engine.insertion import insertion_slots
from p2b.houseplans.engine.intent import ArchitecturalIntent, DesignInputs
from p2b.houseplans.engine.model import Frozen, HousePlan, Id
from p2b.houseplans.engine.ops import (
    AddRoomOutside,
    DeleteRoom,
    MoveEdge,
    MoveOpening,
    PlanOp,
    RenameRoom,
    SetOpening,
    SetRoomType,
)
from p2b.houseplans.engine.ruleset import RulesetContent

ShortText = Annotated[str, StringConstraints(min_length=1, max_length=200)]
RoomName = Annotated[str, StringConstraints(min_length=1, max_length=60)]

# ---------- what is outside this product (said, never improvised) ----------

UnsupportedTopic = Literal[
    "ADD_FLOOR",
    "FREE_SHAPE",
    "STRUCTURAL_ENGINEERING",
    "PERMIT_COMPLIANCE",
    "VASTU_CERTIFICATION",
    "PRIVACY_REDESIGN",
    "UNSUPPORTED_ROOM_TYPE",
    "IMAGES_OR_3D",
    "OTHER",
]

# ---------- requirement intent ----------

RoomKind = Literal[
    "LIVING",
    "DINING",
    "KITCHEN",
    "BEDROOM",
    "MASTER_BEDROOM",
    "BATHROOM",
    "PUJA",
    "UTILITY",
    "STUDY",
    "STORE",
    "PARKING",
]


class PlotIntent(Frozen):
    width_ft: Annotated[Decimal, Field(gt=0, le=500, max_digits=6, decimal_places=2)] | None = None
    depth_ft: Annotated[Decimal, Field(gt=0, le=500, max_digits=6, decimal_places=2)] | None = None
    facing: Facing | None = None
    setbacks_ft: dict[SetbackSide, Annotated[Decimal, Field(ge=0, le=200)]] | None = None


class ParkingIntent(Frozen):
    kind: Literal["CAR", "TWO_WHEELER", "NONE"]
    spaces: Annotated[int, Field(ge=0, le=4)] = 1


class Adjacency(Frozen):
    a: RoomKind
    b: RoomKind
    strength: Literal["PREFERRED", "REQUIRED"] = "PREFERRED"


class RequirementIntent(Frozen):
    """A homeowner's description of the home, as structured facts and preferences. No
    coordinates, sizes in plan units, polygons or walls: those are the engine's."""

    plot: PlotIntent = PlotIntent()
    floors: Annotated[int, Field(ge=1, le=4)] = 1
    bedrooms: Annotated[int, Field(ge=0, le=12)] | None = None
    bathrooms: Annotated[int, Field(ge=0, le=12)] | None = None
    attached_bathrooms: Annotated[int, Field(ge=0, le=12)] | None = None
    pooja_room: bool | None = None
    utility: bool | None = None
    dining: DiningArrangement | None = None
    kitchen: KitchenArrangement | None = None
    parking: ParkingIntent | None = None
    living_size: Literal["LARGE", "STANDARD", "COMPACT"] | None = None
    adjacencies: Annotated[list[Adjacency], Field(default_factory=list, max_length=10)]
    private_rooms: Annotated[list[RoomKind], Field(default_factory=list, max_length=10)]
    circulation: Literal["COMPACT", "GENEROUS"] | None = None
    entrance_side: Literal["FRONT", "SIDE"] | None = None
    vastu: Literal["NOT_NEEDED", "WHERE_POSSIBLE", "MUST_FOLLOW"] | None = None
    accepted_compromises: Annotated[list[ShortText], Field(default_factory=list, max_length=5)]
    clarifications: Annotated[list[ShortText], Field(default_factory=list, max_length=5)]
    unsupported: Annotated[list[UnsupportedTopic], Field(default_factory=list, max_length=5)]


@dataclass(frozen=True)
class RequirementBridge:
    """What the deterministic pipeline can take from a RequirementIntent."""

    answers: dict[str, Any]  # requirement answers in the RQ v1 shape `normalise` reads
    design_inputs: DesignInputs
    missing: tuple[str, ...]  # facts nobody gave: asked back, never assumed
    assumed: tuple[str, ...]  # optional rooms not mentioned, taken as not wanted (shown)
    unsupported: tuple[str, ...]
    preferences: tuple[str, ...]  # kept with the intent; the CP2 solver does not read them yet


def _count(n: int) -> str:
    return str(n) if 1 <= n <= 4 else "5_PLUS"


def requirement_answers(intent: RequirementIntent) -> RequirementBridge:
    missing: list[str] = []
    assumed: list[str] = []
    unsupported: list[str] = list(intent.unsupported)
    preferences: list[str] = []
    plot = intent.plot
    answers: dict[str, Any] = {
        "plot_is_rectangular": True,
        "floors": "G",
        "basement": False,
        "built_up_area_sqft": "NOT_SURE",
    }
    if intent.floors > 1 and "ADD_FLOOR" not in unsupported:
        unsupported.append("ADD_FLOOR")
    if plot.width_ft is None or plot.depth_ft is None:
        missing.append("plot_size")
    else:
        answers["plot_width_ft"] = float(plot.width_ft)
        answers["plot_depth_ft"] = float(plot.depth_ft)
    if plot.facing is None:
        missing.append("facing")
    else:
        answers["facing"] = plot.facing.value
    if plot.setbacks_ft is None or set(plot.setbacks_ft) != set(SetbackSide):
        missing.append("setbacks")
    else:
        answers["setbacks"] = {k.value: float(v) for k, v in plot.setbacks_ft.items()}
    di: dict[str, Any] = {"stair": "NONE"}
    for key, value, exact in (
        ("bedrooms", intent.bedrooms, "bedrooms_exact"),
        ("bathrooms", intent.bathrooms, "bathrooms_exact"),
    ):
        if value is None or value == 0:
            missing.append(key)
            continue
        answers[key] = _count(value)
        if value > 4:
            di[exact] = value
    if intent.attached_bathrooms is not None:
        di["attached_bathrooms"] = intent.attached_bathrooms
    else:
        missing.append("attached_bathrooms")
    if intent.pooja_room is None:
        assumed.append("pooja_room")
    answers["pooja_room"] = bool(intent.pooja_room)
    if intent.utility is None:
        assumed.append("utility")
    di["utility"] = bool(intent.utility)
    if intent.dining is None:
        missing.append("dining")
    else:
        di["dining"] = intent.dining.value
    if intent.kitchen is None:
        missing.append("kitchen")
    else:
        di["kitchen"] = intent.kitchen.value
    parking = intent.parking
    if parking is None:
        missing.append("parking")
    elif parking.kind == "NONE" or parking.spaces == 0:
        answers["car_parking"] = False
    else:
        answers["car_parking"] = True
        di["parking_kind"] = ParkingKind(parking.kind).value
        di["parking_spaces"] = parking.spaces
    answers["vastu"] = intent.vastu or "NOT_NEEDED"
    if intent.living_size:
        preferences.append(f"living_size:{intent.living_size}")
    preferences += [f"adjacent:{a.a}-{a.b}:{a.strength}" for a in intent.adjacencies]
    preferences += [f"private:{r}" for r in intent.private_rooms]
    if intent.circulation:
        preferences.append(f"circulation:{intent.circulation}")
    if intent.entrance_side:
        preferences.append(f"entrance:{intent.entrance_side}")
    return RequirementBridge(
        answers=answers,
        design_inputs=DesignInputs.model_validate(di),
        missing=tuple(missing),
        assumed=tuple(assumed),
        unsupported=tuple(dict.fromkeys(unsupported)),
        preferences=tuple(preferences),
    )


# ---------- edit intent ----------


class ResizeRoom(Frozen):
    action: Literal["RESIZE_ROOM"] = "RESIZE_ROOM"
    room: Id
    change: Literal["LARGER", "SMALLER"]
    amount: Literal["SLIGHT", "MODERATE", "LOTS"] = "MODERATE"


class MoveRoomToward(Frozen):
    action: Literal["MOVE_ROOM_TOWARD"] = "MOVE_ROOM_TOWARD"
    room: Id
    target: Id


class AddRoomIntent(Frozen):
    action: Literal["ADD_ROOM"] = "ADD_ROOM"
    room_type: RoomType
    area: Literal["FORECOURT", "SIDE_YARD", "REAR_YARD", "COURT", "ANY"] = "ANY"


class ChangeRoomType(Frozen):
    action: Literal["CHANGE_ROOM_TYPE"] = "CHANGE_ROOM_TYPE"
    room: Id
    room_type: RoomType


class RemoveRoom(Frozen):
    action: Literal["REMOVE_ROOM"] = "REMOVE_ROOM"
    room: Id


class RenameRoomIntent(Frozen):
    action: Literal["RENAME_ROOM"] = "RENAME_ROOM"
    room: Id
    name: RoomName


class MoveOpeningIntent(Frozen):
    action: Literal["MOVE_OPENING"] = "MOVE_OPENING"
    room: Id
    opening: Literal["DOOR", "WINDOW"]
    direction: Literal["TOWARD_START", "TOWARD_END", "EITHER"] = "EITHER"


class ResizeOpeningIntent(Frozen):
    action: Literal["RESIZE_OPENING"] = "RESIZE_OPENING"
    room: Id
    opening: Literal["DOOR", "WINDOW"]
    change: Literal["WIDER", "NARROWER"]


class UnsupportedIntent(Frozen):
    action: Literal["UNSUPPORTED"] = "UNSUPPORTED"
    topic: UnsupportedTopic


class ClarifyIntent(Frozen):
    action: Literal["CLARIFY"] = "CLARIFY"
    question: ShortText


EditIntent = Annotated[
    ResizeRoom
    | MoveRoomToward
    | AddRoomIntent
    | ChangeRoomType
    | RemoveRoom
    | RenameRoomIntent
    | MoveOpeningIntent
    | ResizeOpeningIntent
    | UnsupportedIntent
    | ClarifyIntent,
    Field(discriminator="action"),
]


class EditInterpretation(Frozen):
    """The model's whole answer for one sentence: exactly one intent."""

    intent: EditIntent


# ---------- compiling an edit intent ----------

STEPS = {"SLIGHT": (300,), "MODERATE": (600, 300), "LOTS": (900, 600, 300)}
MAX_CANDIDATES = 24  # each is one engine edit (a few milliseconds)


@dataclass(frozen=True)
class Proposal:
    ops: tuple[PlanOp, ...]
    result: EditResult  # the plan the batch would make, already validated
    tried: int


@dataclass(frozen=True)
class NoProposal:
    reason: Literal["UNKNOWN_ROOM", "ALREADY_THERE", "NOTHING_VALID", "UNSUPPORTED", "CLARIFY"]
    detail: str  # the topic, question, room id or the refusals seen (for the model's retry)
    tried: int


Compiled = Proposal | NoProposal

_OUTWARD = {RoomSide.LEFT: -1, RoomSide.RIGHT: 1, RoomSide.FRONT: -1, RoomSide.BACK: 1}


def _rooms(plan: HousePlan) -> dict[str, Any]:
    return {r.id: r for f in plan.floors for r in f.rooms}


def _resize(plan: HousePlan, i: ResizeRoom) -> Iterator[list[PlanOp]]:
    sign = 1 if i.change == "LARGER" else -1
    for step in STEPS[i.amount]:
        for side in RoomSide:
            yield [MoveEdge(room=i.room, side=side, delta_mm=_OUTWARD[side] * sign * step)]


def _toward(plan: HousePlan, i: MoveRoomToward) -> Iterator[list[PlanOp]]:
    rects = room_rects(plan.floors[0])
    a, b = rects[i.room], rects[i.target]
    gap_x = max(b.x0 - a.x1, a.x0 - b.x1, 0)
    gap_y = max(b.y0 - a.y1, a.y0 - b.y1, 0)
    if gap_x == 0 and gap_y == 0:
        return
    horizontal = gap_x >= gap_y
    direction = (1 if b.x0 >= a.x1 else -1) if horizontal else (1 if b.y0 >= a.y1 else -1)
    lead, trail = (RoomSide.RIGHT, RoomSide.LEFT) if horizontal else (RoomSide.BACK, RoomSide.FRONT)
    if direction < 0:
        lead, trail = trail, lead
    for step in (300, 600, 900):
        delta = direction * min(step, gap_x if horizontal else gap_y)
        yield [
            MoveEdge(room=i.room, side=lead, delta_mm=delta),
            MoveEdge(room=i.room, side=trail, delta_mm=delta),
        ]
        # or stretch only the side facing the target (the room grows towards it)
        yield [MoveEdge(room=i.room, side=lead, delta_mm=delta)]


def _add(plan: HousePlan, i: AddRoomIntent, ruleset: RulesetContent) -> Iterator[list[PlanOp]]:
    rule = ruleset.rooms.get(i.room_type)
    if rule is None:
        return
    step = ruleset.grid_mm

    def up(v: int) -> int:
        return -(-v // step) * step

    for slot in insertion_slots(plan, ruleset):
        if i.area != "ANY" and slot.open_area_kind != i.area:
            continue
        depth = up(rule.min_short_mm + slot.depth_allowance_mm)
        clear = depth - slot.depth_allowance_mm
        length = up(
            max(rule.min_short_mm, -(-rule.min_area_mm2 // clear)) + slot.length_allowance_mm
        )
        if depth > slot.max_depth_mm or length > slot.length_mm:
            continue
        yield [
            AddRoomOutside(
                host_room=slot.host_room,
                type=i.room_type,
                side=slot.side,
                offset_mm=slot.offset_mm,
                length_mm=length,
                depth_mm=depth,
            )
        ]


def _retype(plan: HousePlan, i: ChangeRoomType) -> Iterator[list[PlanOp]]:
    room = _rooms(plan)[i.room]
    ops: list[PlanOp] = [SetRoomType(room=i.room, type=i.room_type)]
    if room.name in (room_name(room.id, room.type), ROOM_NAMES[room.type]):
        ops.append(RenameRoom(room=i.room, name=room_name(room.id, i.room_type)))
    yield ops


def _remove(plan: HousePlan, i: RemoveRoom) -> Iterator[list[PlanOp]]:
    rects = room_rects(plan.floors[0])
    a = rects[i.room]
    for key, b in rects.items():
        rows = (a.y0, a.y1) == (b.y0, b.y1) and (a.x1 == b.x0 or b.x1 == a.x0)
        cols = (a.x0, a.x1) == (b.x0, b.x1) and (a.y1 == b.y0 or b.y1 == a.y0)
        if key != i.room and (rows or cols):
            yield [DeleteRoom(room=i.room, merge_into=key)]


def _room_openings(plan: HousePlan, room: str, kind: str) -> list[Any]:
    kinds = (
        (OpeningKind.DOOR, OpeningKind.MAIN_ENTRANCE) if kind == "DOOR" else (OpeningKind.WINDOW,)
    )
    analysis = analyse(plan)
    return [
        info.opening
        for key, info in sorted(analysis.openings.items())
        if info.opening.kind in kinds and room in info.connects
    ]


def _move_opening(plan: HousePlan, i: MoveOpeningIntent) -> Iterator[list[PlanOp]]:
    signs = {"TOWARD_START": (-1,), "TOWARD_END": (1,), "EITHER": (1, -1)}[i.direction]
    for opening in _room_openings(plan, i.room, i.opening):
        for step in (300, 600):
            for sign in signs:
                offset = opening.offset_mm + sign * step
                if offset >= 0:
                    yield [MoveOpening(opening=opening.id, offset_mm=offset)]


def _resize_opening(plan: HousePlan, i: ResizeOpeningIntent) -> Iterator[list[PlanOp]]:
    sign = 1 if i.change == "WIDER" else -1
    for opening in _room_openings(plan, i.room, i.opening):
        for step in (300, 200, 100):
            width = opening.width_mm + sign * step
            offset = opening.offset_mm - sign * step // 2
            if width <= 0 or offset < 0:
                continue
            yield [
                SetOpening(
                    opening=opening.id,
                    width_mm=width,
                    height_mm=opening.height_mm,
                    sill_mm=opening.sill_mm,
                    door=opening.door,
                ),
                MoveOpening(opening=opening.id, offset_mm=offset),
            ]


def compile_edit(
    plan: HousePlan,
    intent: Any,
    ruleset: RulesetContent,
    *,
    arch: ArchitecturalIntent | None,
) -> Compiled:
    """The first candidate batch, in a fixed order, that applies and passes the validator."""
    if isinstance(intent, UnsupportedIntent):
        return NoProposal("UNSUPPORTED", intent.topic, 0)
    if isinstance(intent, ClarifyIntent):
        return NoProposal("CLARIFY", intent.question, 0)
    rooms = _rooms(plan)
    for ref in ("room", "target"):
        value = getattr(intent, ref, None)
        if value is not None and value not in rooms:
            return NoProposal("UNKNOWN_ROOM", value, 0)
    if isinstance(intent, MoveRoomToward) and intent.room == intent.target:
        return NoProposal("ALREADY_THERE", intent.room, 0)
    if isinstance(intent, RenameRoomIntent):
        candidates: Iterator[list[PlanOp]] = iter(
            [[RenameRoom(room=intent.room, name=intent.name)]]
        )
    elif isinstance(intent, ResizeRoom):
        candidates = _resize(plan, intent)
    elif isinstance(intent, MoveRoomToward):
        candidates = _toward(plan, intent)
    elif isinstance(intent, AddRoomIntent):
        candidates = _add(plan, intent, ruleset)
    elif isinstance(intent, ChangeRoomType):
        candidates = _retype(plan, intent)
    elif isinstance(intent, RemoveRoom):
        candidates = _remove(plan, intent)
    elif isinstance(intent, MoveOpeningIntent):
        candidates = _move_opening(plan, intent)
    else:
        candidates = _resize_opening(plan, intent)
    seen: list[str] = []
    tried = 0
    for ops in candidates:
        if tried >= MAX_CANDIDATES:
            break
        tried += 1
        try:
            result = edit(
                plan, ops, ruleset, intent=arch, ruleset_version=None, ruleset_sha256=None
            )
        except BatchRejected as rejected:
            seen.append(rejected.rejected.code.value)
            continue
        if result.report.valid:
            return Proposal(tuple(ops), result, tried)
        seen.extend(e.code.value for e in result.report.errors)
    if tried == 0 and isinstance(intent, MoveRoomToward):
        return NoProposal("ALREADY_THERE", intent.target, 0)
    detail = ",".join(sorted(set(seen))) or "NO_CANDIDATE"
    return NoProposal("NOTHING_VALID", detail, tried)


# ---------- what a proposal changes, for the person to read ----------


@dataclass(frozen=True)
class RoomChange:
    room: str
    name: str
    kind: Literal["CHANGED", "ADDED", "REMOVED", "RETYPED", "RENAMED"]
    area_before_mm2: int | None
    area_after_mm2: int | None
    type_before: str | None
    type_after: str | None


@dataclass(frozen=True)
class OpeningChange:
    opening: str
    kind: Literal["MOVED", "RESIZED"]
    width_before_mm: int
    width_after_mm: int


def describe(
    before: HousePlan, after: HousePlan, ruleset: RulesetContent
) -> tuple[list[RoomChange], list[OpeningChange]]:
    """The rooms and openings a proposal changes, with areas from the server's own geometry."""
    g0, g1 = plan_geometry(before, ruleset).floors[0], plan_geometry(after, ruleset).floors[0]
    a0 = {r.id: r for r in g0.rooms}
    a1 = {r.id: r for r in g1.rooms}
    r0, r1 = _rooms(before), _rooms(after)
    rooms: list[RoomChange] = []
    for key in sorted(set(a0) | set(a1)):
        x, y = a0.get(key), a1.get(key)
        ar0 = x.carpet_area_mm2 if x else None
        ar1 = y.carpet_area_mm2 if y else None
        t0 = r0[key].type.value if key in r0 else None
        t1 = r1[key].type.value if key in r1 else None
        name = (r1.get(key) or r0[key]).name
        kind: Literal["CHANGED", "ADDED", "REMOVED", "RETYPED", "RENAMED"] | None = None
        if x is None:
            kind = "ADDED"
        elif y is None:
            kind = "REMOVED"
        elif t0 != t1:
            kind = "RETYPED"
        elif ar0 != ar1:
            kind = "CHANGED"
        elif r0[key].name != r1[key].name:
            kind = "RENAMED"
        if kind:
            rooms.append(RoomChange(key, name, kind, ar0, ar1, t0, t1))
    o0 = {o.id: o for f in before.floors for o in f.openings}
    o1 = {o.id: o for f in after.floors for o in f.openings}
    # where an opening stands on the ground: the rebuild may rename its wall without moving it
    j0 = {o.id: (o.jamb_a, o.jamb_b) for o in g0.openings}
    j1 = {o.id: (o.jamb_a, o.jamb_b) for o in g1.openings}
    openings: list[OpeningChange] = []
    for key in sorted(set(o0) & set(o1)):
        p, q = o0[key], o1[key]
        if p.width_mm != q.width_mm:
            openings.append(OpeningChange(key, "RESIZED", p.width_mm, q.width_mm))
        elif j0.get(key) != j1.get(key):
            openings.append(OpeningChange(key, "MOVED", p.width_mm, q.width_mm))
    return rooms, openings


def plan_summary(plan: HousePlan, ruleset: RulesetContent) -> dict[str, Any]:
    """What the model may know about the plan: ids, names, types, sizes and open areas. No
    coordinates are sent: the model only names rooms and chooses an action."""
    geometry = plan_geometry(plan, ruleset).floors[0]
    openings: dict[str, list[str]] = {}
    for o in geometry.openings:
        for room in o.connects:
            openings.setdefault(room, []).append(o.kind)
    return {
        "rooms": [
            {
                "id": r.id,
                "name": r.name,
                "type": r.type,
                "clear_m": [
                    round((r.clear_w_mm or 0) / 1000, 2),
                    round((r.clear_d_mm or 0) / 1000, 2),
                ],
                "area_m2": round((r.carpet_area_mm2 or 0) / 1_000_000, 2),
                "openings": sorted(set(openings.get(r.id, []))),
            }
            for r in geometry.rooms
        ],
        "open_areas": sorted({a.kind for a in geometry.open_areas or []}),
        "room_types": [t.value for t, rule in ruleset.rooms.items() if rule.enclosed],
    }
