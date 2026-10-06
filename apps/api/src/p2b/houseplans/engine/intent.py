"""Requirement normalisation: locked requirement answers (RQ v1) plus provisional design inputs
become an ArchitecturalIntent. Deterministic, and it never guesses: a missing fact is NeedsInput,
a case the engine does not support is Unsupported, and a provisional input that contradicts a
requirement answer is an InputConflict. No language model (PD-28, AD-07).

Provisional design inputs (CP1-03) are a separate, versioned object marked PROVISIONAL. They only
supply facts RQ v1 does not hold or holds as "Not sure"; they never replace an answer, except the
facing, which AD-15 lets the design brief correct, and that correction is recorded as such."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import Field

from p2b.core.vocabulary import (
    ConstraintStrength,
    DesignInputKey,
    DiningArrangement,
    Facing,
    KitchenArrangement,
    MissingInputReason,
    OrientationMode,
    OriginKind,
    ParkingKind,
    ParkingPlacement,
    RelationKind,
    RoomType,
    SetbackSide,
    SetbackSource,
    StairChoice,
    UnsupportedReason,
)
from p2b.houseplans.engine.canonical import sha256_of
from p2b.houseplans.engine.model import Frozen, Id, NonNegMm, Origin, PosMm
from p2b.houseplans.engine.ruleset import RulesetContent
from p2b.houseplans.engine.units import ft_to_mm

INTENT_VERSION = "1.0.0"
SUPPORTED_QUESTION_SETS = frozenset({1})
FACING_BEARING = {
    Facing.N: 0,
    Facing.NE: 45,
    Facing.E: 90,
    Facing.SE: 135,
    Facing.S: 180,
    Facing.SW: 225,
    Facing.W: 270,
    Facing.NW: 315,
}
SETBACK_KEY = {
    SetbackSide.FRONT: DesignInputKey.SETBACK_FRONT,
    SetbackSide.BACK: DesignInputKey.SETBACK_BACK,
    SetbackSide.LEFT: DesignInputKey.SETBACK_LEFT,
    SetbackSide.RIGHT: DesignInputKey.SETBACK_RIGHT,
}
COUNT_CHOICES = {"1": 1, "2": 2, "3": 3, "4": 4}
SetbackFt = Annotated[Decimal, Field(ge=0, le=200, max_digits=6, decimal_places=2)]


class DesignInputs(Frozen):
    """PROVISIONAL (CP1-03): stands in for the design brief until AD-03 is decided. Versioned,
    stored apart from the requirement, accepted only where houseplans are enabled."""

    kind: Literal["PROVISIONAL_DESIGN_INPUTS"] = "PROVISIONAL_DESIGN_INPUTS"
    version: Literal[1] = 1
    facing_override: Facing | None = None
    setbacks_ft: dict[SetbackSide, SetbackFt] | None = None
    bedrooms_exact: Annotated[int, Field(ge=5, le=12)] | None = None
    bathrooms_exact: Annotated[int, Field(ge=5, le=12)] | None = None
    attached_bathrooms: Annotated[int, Field(ge=0, le=12)] | None = None
    parking_spaces: Annotated[int, Field(ge=1, le=4)] | None = None
    parking_kind: ParkingKind | None = None
    dining: DiningArrangement | None = None
    kitchen: KitchenArrangement | None = None
    stair: StairChoice | None = None
    utility: bool | None = None


class IntentSources(Frozen):
    question_set_version: int
    requirement_version: int
    design_inputs_sha256: str | None
    ruleset_version: int
    ruleset_sha256: str


class SiteIntent(Frozen):
    frontage_mm: PosMm  # plot width, parallel to the primary road edge (CP1-01)
    depth_mm: PosMm
    facing: Facing
    facing_origin: Origin
    north_angle_deg: Annotated[int, Field(ge=0, lt=360)]
    setbacks_mm: dict[SetbackSide, NonNegMm]  # all four sides
    setback_sources: dict[SetbackSide, SetbackSource]


class ProgrammeItem(Frozen):
    key: Id  # becomes the room id
    room_type: RoomType
    must_have: bool
    origin: Origin


class Relation(Frozen):
    """`room` is reached only from `host`, through a door (ADJACENT_WITH_DOOR) or an open
    connection (ADJACENT_OPEN)."""

    kind: RelationKind
    room: Id
    host: Id
    strength: ConstraintStrength
    origin: Origin


class ParkingIntent(Frozen):
    spaces: Annotated[int, Field(ge=1, le=4)]
    kind: ParkingKind
    placement: ParkingPlacement
    origin: Origin


class ArchitecturalIntent(Frozen):
    intent_version: Literal["1.0.0"] = "1.0.0"
    sources: IntentSources
    site: SiteIntent
    floors: Literal[1] = 1  # single storey (AD-04 pending; basements unsupported, CP1-10)
    programme: list[ProgrammeItem]
    relations: list[Relation]
    orientation: OrientationMode  # recorded only until AD-13
    parking: ParkingIntent | None
    stair: StairChoice
    target_built_up_mm2: int | None


@dataclass(frozen=True)
class Missing:
    key: DesignInputKey
    reason: MissingInputReason


@dataclass(frozen=True)
class NeedsInput:
    missing: tuple[Missing, ...]


@dataclass(frozen=True)
class Unsupported:
    reasons: tuple[UnsupportedReason, ...]


@dataclass(frozen=True)
class InputConflict:
    keys: tuple[DesignInputKey, ...]


@dataclass(frozen=True)
class Normalised:
    intent: ArchitecturalIntent


Outcome = Normalised | NeedsInput | Unsupported | InputConflict


def _origin(kind: OriginKind, ref: str) -> Origin:
    return Origin(kind=kind, ref=ref)


def north_angle(facing: Facing) -> int:
    """Clockwise angle from +y (away from the road) to north: the road side faces `facing`, so +y
    points the opposite way."""
    return (180 - FACING_BEARING[facing]) % 360


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return Decimal(str(value))


def normalise(
    answers: Mapping[str, Any],
    inputs: DesignInputs | None,
    ruleset: RulesetContent,
    *,
    question_set_version: int,
    requirement_version: int,
    ruleset_version: int,
    ruleset_sha256: str,
) -> Outcome:
    di = inputs or DesignInputs()
    unsupported: list[UnsupportedReason] = []
    missing: list[Missing] = []
    conflicts: list[DesignInputKey] = []

    if question_set_version not in SUPPORTED_QUESTION_SETS:
        return Unsupported((UnsupportedReason.QUESTION_SET_NOT_SUPPORTED,))

    # Plot: rectangular only (MVP). Width runs along the primary road edge (CP1-01).
    if answers.get("plot_is_rectangular") is not True:
        unsupported.append(UnsupportedReason.PLOT_NOT_RECTANGULAR)
    width, depth = _number(answers.get("plot_width_ft")), _number(answers.get("plot_depth_ft"))
    if answers.get("plot_is_rectangular") is True and (not width or not depth):
        unsupported.append(UnsupportedReason.ANSWER_INVALID)
    if answers.get("floors") != "G":
        unsupported.append(UnsupportedReason.FLOORS_NOT_SUPPORTED)
    if answers.get("basement") is not False:
        unsupported.append(UnsupportedReason.BASEMENT_NOT_SUPPORTED)
    if di.stair in (StairChoice.INTERNAL, StairChoice.EXTERNAL):
        unsupported.append(UnsupportedReason.STAIR_NOT_YET_SUPPORTED)
    if unsupported:
        return Unsupported(tuple(dict.fromkeys(unsupported)))
    if width is None or depth is None:
        return Unsupported((UnsupportedReason.ANSWER_INVALID,))

    # Facing: the road and main-entrance side (AD-15), correctable through the inputs.
    facing_answer = answers.get("facing")
    if di.facing_override is not None:
        facing, facing_origin = (
            di.facing_override,
            _origin(OriginKind.DESIGN_INPUT, "inputs:facing_override"),
        )
    elif isinstance(facing_answer, str) and facing_answer in Facing.__members__:
        facing, facing_origin = (
            Facing(facing_answer),
            _origin(OriginKind.REQUIREMENT, "requirement:facing"),
        )
    else:
        facing, facing_origin = Facing.N, _origin(OriginKind.REQUIREMENT, "requirement:facing")
        missing.append(Missing(DesignInputKey.FACING, MissingInputReason.NOT_SURE))

    # Setbacks: numeric answers stand; "Not sure" sides only from the provisional inputs.
    raw_setbacks = answers.get("setbacks")
    raw_setbacks = raw_setbacks if isinstance(raw_setbacks, Mapping) else {}
    given = di.setbacks_ft or {}
    setbacks_mm: dict[SetbackSide, int] = {}
    setback_sources: dict[SetbackSide, SetbackSource] = {}
    for side in SetbackSide:
        answered = _number(raw_setbacks.get(side.value))
        if answered is not None:
            if side in given:
                conflicts.append(SETBACK_KEY[side])
            setbacks_mm[side], setback_sources[side] = ft_to_mm(answered), SetbackSource.REQUIREMENT
        elif side in given:
            setbacks_mm[side], setback_sources[side] = (
                ft_to_mm(given[side]),
                SetbackSource.DESIGN_INPUT,
            )
        else:
            reason = (
                MissingInputReason.NOT_SURE
                if raw_setbacks.get(side.value) == "NOT_SURE"
                else MissingInputReason.NOT_ANSWERED
            )
            missing.append(Missing(SETBACK_KEY[side], reason))

    def count(key: str, exact: int | None, input_key: DesignInputKey) -> int:
        value = answers.get(key)
        if value in COUNT_CHOICES:
            if exact is not None:
                conflicts.append(input_key)
            return COUNT_CHOICES[value]
        if value == "5_PLUS":
            if exact is None:
                missing.append(Missing(input_key, MissingInputReason.NOT_ANSWERED))
                return 0
            return exact
        unsupported.append(UnsupportedReason.ANSWER_INVALID)
        return 0

    bedrooms = count("bedrooms", di.bedrooms_exact, DesignInputKey.BEDROOMS_EXACT)
    bathrooms = count("bathrooms", di.bathrooms_exact, DesignInputKey.BATHROOMS_EXACT)
    if di.attached_bathrooms is None:
        missing.append(Missing(DesignInputKey.ATTACHED_BATHROOMS, MissingInputReason.NOT_ANSWERED))
    elif bedrooms and bathrooms and di.attached_bathrooms > min(bedrooms, bathrooms):
        missing.append(Missing(DesignInputKey.ATTACHED_BATHROOMS, MissingInputReason.OUT_OF_RANGE))

    car_parking = answers.get("car_parking")
    if car_parking is True:
        if di.parking_spaces is None:
            missing.append(Missing(DesignInputKey.PARKING_SPACES, MissingInputReason.NOT_ANSWERED))
        if di.parking_kind is None:
            missing.append(Missing(DesignInputKey.PARKING_KIND, MissingInputReason.NOT_ANSWERED))
    elif car_parking is False:
        if di.parking_spaces is not None:
            conflicts.append(DesignInputKey.PARKING_SPACES)
        if di.parking_kind is not None:
            conflicts.append(DesignInputKey.PARKING_KIND)
    else:
        unsupported.append(UnsupportedReason.ANSWER_INVALID)
    if answers.get("pooja_room") not in (True, False):
        unsupported.append(UnsupportedReason.ANSWER_INVALID)
    for value, key in (
        (di.dining, DesignInputKey.DINING),
        (di.kitchen, DesignInputKey.KITCHEN),
        (di.stair, DesignInputKey.STAIR),
        (di.utility, DesignInputKey.UTILITY),
    ):
        if value is None:
            missing.append(Missing(key, MissingInputReason.NOT_ANSWERED))

    if unsupported:
        return Unsupported(tuple(dict.fromkeys(unsupported)))
    if conflicts:
        return InputConflict(tuple(dict.fromkeys(conflicts)))
    if missing:
        return NeedsInput(tuple(missing))

    # Programme: ruleset base rooms first (CP1-09), then what the answers and inputs ask for.
    programme: list[ProgrammeItem] = []

    def add(key: str, room_type: RoomType, origin: Origin) -> None:
        programme.append(ProgrammeItem(key=key, room_type=room_type, must_have=True, origin=origin))

    for room_type in ruleset.base_programme:
        add(
            room_type.value.lower(),
            room_type,
            _origin(OriginKind.RULESET, "ruleset:base_programme"),
        )
    if di.dining == DiningArrangement.SEPARATE:
        add("dining", RoomType.DINING, _origin(OriginKind.DESIGN_INPUT, "inputs:dining"))
    if di.utility:
        add("utility", RoomType.UTILITY, _origin(OriginKind.DESIGN_INPUT, "inputs:utility"))
    if answers.get("pooja_room") is True:
        add("puja", RoomType.PUJA, _origin(OriginKind.REQUIREMENT, "requirement:pooja_room"))
    if car_parking is True:
        add("parking", RoomType.PARKING, _origin(OriginKind.REQUIREMENT, "requirement:car_parking"))
    for i in range(1, bedrooms + 1):
        add(
            f"bedroom_{i}",
            RoomType.BEDROOM,
            _origin(OriginKind.REQUIREMENT, "requirement:bedrooms"),
        )
    attached = di.attached_bathrooms or 0
    for i in range(1, attached + 1):
        add(
            f"bath_attached_{i}",
            RoomType.BATH_ATTACHED,
            _origin(OriginKind.DESIGN_INPUT, "inputs:attached_bathrooms"),
        )
    for i in range(1, bathrooms - attached + 1):
        add(
            f"bath_common_{i}",
            RoomType.BATH_COMMON,
            _origin(OriginKind.REQUIREMENT, "requirement:bathrooms"),
        )

    keys = {p.key for p in programme}
    relations: list[Relation] = []
    if "kitchen" in keys:
        host = "dining" if "dining" in keys else ruleset.zoning.entry_room.value.lower()
        kind = (
            RelationKind.ADJACENT_WITH_DOOR
            if di.kitchen == KitchenArrangement.CLOSED
            else RelationKind.ADJACENT_OPEN
        )
        if host in keys:
            relations.append(
                Relation(
                    kind=kind,
                    room="kitchen",
                    host=host,
                    strength=ConstraintStrength.HARD,
                    origin=_origin(OriginKind.DESIGN_INPUT, "inputs:kitchen"),
                )
            )
    first_of_type: dict[RoomType, str] = {}
    for item in programme:
        first_of_type.setdefault(item.room_type, item.key)
    for item in programme:
        host_type = ruleset.zoning.attached_to.get(item.room_type)
        if host_type is not None and host_type in first_of_type:
            relations.append(
                Relation(
                    kind=RelationKind.ADJACENT_WITH_DOOR,
                    room=item.key,
                    host=first_of_type[host_type],
                    strength=ConstraintStrength.HARD,
                    origin=_origin(OriginKind.RULESET, "ruleset:zoning.attached_to"),
                )
            )
    for i in range(1, attached + 1):
        relations.append(
            Relation(
                kind=RelationKind.ADJACENT_WITH_DOOR,
                room=f"bath_attached_{i}",
                host=f"bedroom_{i}",
                strength=ConstraintStrength.HARD,
                origin=_origin(OriginKind.DESIGN_INPUT, "inputs:attached_bathrooms"),
            )
        )

    parking = None
    if car_parking is True:
        if di.parking_spaces is None or di.parking_kind is None:
            return NeedsInput(
                (Missing(DesignInputKey.PARKING_SPACES, MissingInputReason.NOT_ANSWERED),)
            )
        parking = ParkingIntent(
            spaces=di.parking_spaces,
            kind=di.parking_kind,
            placement=ParkingPlacement.INSIDE_FOOTPRINT,
            origin=_origin(OriginKind.REQUIREMENT, "requirement:car_parking"),
        )

    built_up = _number(answers.get("built_up_area_sqft"))
    vastu = answers.get("vastu")
    orientation = {
        "MUST_FOLLOW": OrientationMode.SOFT_HIGH,
        "WHERE_POSSIBLE": OrientationMode.SOFT,
    }.get(vastu if isinstance(vastu, str) else "", OrientationMode.OFF)

    intent = ArchitecturalIntent(
        sources=IntentSources(
            question_set_version=question_set_version,
            requirement_version=requirement_version,
            design_inputs_sha256=sha256_of(inputs) if inputs is not None else None,
            ruleset_version=ruleset_version,
            ruleset_sha256=ruleset_sha256,
        ),
        site=SiteIntent(
            frontage_mm=ft_to_mm(width),
            depth_mm=ft_to_mm(depth),
            facing=facing,
            facing_origin=facing_origin,
            north_angle_deg=north_angle(facing),
            setbacks_mm=setbacks_mm,
            setback_sources=setback_sources,
        ),
        programme=programme,
        relations=relations,
        orientation=orientation,
        parking=parking,
        stair=di.stair or StairChoice.NONE,
        target_built_up_mm2=int(built_up * 92_903) if built_up else None,  # 1 sq ft = 92,903.04 mm²
    )
    return Normalised(intent)
