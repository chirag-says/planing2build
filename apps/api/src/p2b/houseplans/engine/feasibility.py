"""Feasibility (Checkpoint 2): before zoning, and after a search that found nothing.

PROVEN is claimed only for arithmetic that holds for ANY arrangement of rectangles inside the
buildable envelope under the current ruleset: the envelope is empty; a room or the parking cannot
fit in the envelope in any orientation; or the rooms' least footprints (minimum clear size plus
the thinnest possible walls) exceed the envelope's area. Fixture-fit minimums are not used here:
they assume a door position, so they are a search bound, not a proof.

NO_SUPPORTED_LAYOUT means the programme passed those checks but none of the layouts this engine
version can produce fits (CP2-U4). The homeowner is never told it is impossible; the explanation
names the closest supported layout's shortfalls.

Explanations are plain English in metres and name the hard constraints involved. Nothing here
relaxes a requirement."""

from dataclasses import dataclass, field
from math import isqrt

from p2b.core.vocabulary import FeasibilityClass, InfeasibleReason, RoomType, SetbackSide
from p2b.houseplans.engine.footprint import half
from p2b.houseplans.engine.geom import Rect
from p2b.houseplans.engine.intent import ArchitecturalIntent
from p2b.houseplans.engine.ruleset import RulesetContent

MESSAGE_NO_SUPPORTED_LAYOUT = (
    "We could not fit this home on your plot with the layouts we can generate today. "
    "A Plan2Build architect can still design it."
)  # CP2-U4, approved
MESSAGE_PROVEN = (
    "This home cannot fit on your plot under the current planning rules. "
    "A Plan2Build architect can review the requirement with you."
)  # DRAFT wording: only the NO_SUPPORTED_LAYOUT message is approved (CP2-U4)


@dataclass(frozen=True)
class InvolvedConstraint:
    kind: str  # ROOM_PRESENT, INSIDE_ENVELOPE, PARKING_PROVIDED, RULESET
    subject: str
    origin: str


@dataclass(frozen=True)
class FeasibilityReport:
    classification: FeasibilityClass
    code: InfeasibleReason
    explanation: str
    params: dict[str, int | str]
    constraints: tuple[InvolvedConstraint, ...] = field(default_factory=tuple)

    @property
    def message_key(self) -> str:
        return f"houseplans.infeasible.{self.classification.value.lower()}"

    @property
    def message(self) -> str:
        return (
            MESSAGE_PROVEN
            if self.classification == FeasibilityClass.PROVEN
            else MESSAGE_NO_SUPPORTED_LAYOUT
        )

    def as_json(self) -> dict[str, object]:
        return {
            "classification": self.classification.value,
            "code": self.code.value,
            "message_key": self.message_key,
            "message": self.message,
            "explanation": self.explanation,
            "params": self.params,
            "constraints": [c.__dict__ for c in self.constraints],
            "reasons": [
                {
                    "code": self.code.value,
                    "params": self.params,
                    "message_key": f"houseplans.infeasible.{self.code.value.lower()}",
                }
            ],
        }


def m(mm: int) -> str:
    return f"{mm / 1000:.2f} m"


def m2(mm2: int) -> str:
    return f"{mm2 / 1_000_000:.2f} m²"


def envelope_of(intent: ArchitecturalIntent) -> Rect | None:
    s = intent.site.setbacks_mm
    plot = Rect(0, 0, intent.site.frontage_mm, intent.site.depth_mm)
    return plot.inset(
        s[SetbackSide.LEFT], s[SetbackSide.FRONT], s[SetbackSide.RIGHT], s[SetbackSide.BACK]
    )


def _setbacks_constraint(intent: ArchitecturalIntent) -> InvolvedConstraint:
    s = intent.site.setbacks_mm
    text = ", ".join(f"{side.value.lower()} {m(s[side])}" for side in SetbackSide)
    return InvolvedConstraint("INSIDE_ENVELOPE", f"setbacks {text}", "requirement:setbacks")


def _wall_pair(enclosed: bool, ruleset: RulesetContent) -> int:
    """The least wall a room can have across one dimension: an enclosed room has a wall on both
    sides, at least half the thinner wall type each; an unenclosed room may have none."""
    if not enclosed:
        return 0
    return 2 * half(min(ruleset.walls.exterior_mm, ruleset.walls.interior_mm))


def _min_footprint(min_area: int, min_short: int, walls: int) -> int:
    """A lower bound on a room's centreline area. With clear sides a, b (ab >= A, a, b >= s) and
    walls w across each: (a+w)(b+w) = ab + w(a+b) + w² >= max(A, s²) + 2w·max(⌊√A⌋, s) + w²."""
    return (
        max(min_area, min_short * min_short)
        + 2 * walls * max(isqrt(min_area), min_short)
        + walls * walls
    )


def precheck(intent: ArchitecturalIntent, ruleset: RulesetContent) -> FeasibilityReport | None:
    """PROVEN when no arrangement of rectangles can meet the hard rules; None when this arithmetic
    cannot decide (the layout search then does). Assumes a complete ruleset (compile_problem)."""
    setbacks = _setbacks_constraint(intent)
    envelope = envelope_of(intent)
    if envelope is None:
        return FeasibilityReport(
            FeasibilityClass.PROVEN,
            InfeasibleReason.ENVELOPE_EMPTY,
            f"The setbacks leave no buildable area on a {m(intent.site.frontage_mm)} by "
            f"{m(intent.site.depth_mm)} plot.",
            {"frontage_mm": intent.site.frontage_mm, "depth_mm": intent.site.depth_mm},
            (setbacks,),
        )
    # Measured against the envelope itself, not the centreline region: weaker, but it holds for
    # any wall arrangement, so a PROVEN claim cannot depend on how this engine places walls.
    narrow = min(envelope.w, envelope.h)
    # One room cannot fit across the envelope's narrower side in any orientation.
    for item in intent.programme:
        if item.room_type == RoomType.PARKING:
            continue
        rule = ruleset.rooms[item.room_type]
        need = rule.min_short_mm + _wall_pair(rule.enclosed, ruleset)
        if need > narrow:
            name = item.room_type.value.lower().replace("_", " ")
            return FeasibilityReport(
                FeasibilityClass.PROVEN,
                InfeasibleReason.WIDTH_TOO_NARROW,
                f"The buildable area is {m(envelope.w)} wide and {m(envelope.h)} deep after "
                "setbacks. The "
                f"{name} needs at least {m(need)} in both directions including its walls.",
                {"room": item.key, "needed_mm": need, "available_mm": narrow},
                (setbacks, InvolvedConstraint("ROOM_PRESENT", item.key, item.origin.ref)),
            )
    if intent.parking is not None:
        space = ruleset.parking[intent.parking.kind]
        pw, pd = intent.parking.spaces * space.space_w_mm, space.space_d_mm
        if not ((pw <= envelope.w and pd <= envelope.h) or (pw <= envelope.h and pd <= envelope.w)):
            return FeasibilityReport(
                FeasibilityClass.PROVEN,
                InfeasibleReason.PARKING_TOO_WIDE,
                f"Parking for {intent.parking.spaces} needs {m(pw)} by {m(pd)}. "
                "The buildable area after "
                f"setbacks is {m(envelope.w)} by {m(envelope.h)}.",
                {
                    "needed_w_mm": pw,
                    "needed_d_mm": pd,
                    "available_w_mm": envelope.w,
                    "available_d_mm": envelope.h,
                },
                (
                    setbacks,
                    InvolvedConstraint("PARKING_PROVIDED", "parking", intent.parking.origin.ref),
                ),
            )
    # Room rectangles (wall centrelines) are disjoint and inside the envelope, so their least
    # footprints must fit in its area.
    needed = 0
    for item in intent.programme:
        if item.room_type == RoomType.PARKING and intent.parking is not None:
            space = ruleset.parking[intent.parking.kind]
            needed += intent.parking.spaces * space.space_w_mm * space.space_d_mm
            continue
        rule = ruleset.rooms[item.room_type]
        needed += _min_footprint(
            rule.min_area_mm2, rule.min_short_mm, _wall_pair(rule.enclosed, ruleset)
        )
    if needed > envelope.area:
        return FeasibilityReport(
            FeasibilityClass.PROVEN,
            InfeasibleReason.AREA_BUDGET,
            f"The buildable area after setbacks is {m(envelope.w)} by {m(envelope.h)} "
            f"({m2(envelope.area)}). "
            f"The requested rooms need at least {m2(needed)} at their minimum sizes with walls, "
            "before "
            "any passage, so they cannot fit in any arrangement.",
            {"needed_mm2": needed, "available_mm2": envelope.area},
            (
                setbacks,
                *[
                    InvolvedConstraint("ROOM_PRESENT", item.key, item.origin.ref)
                    for item in intent.programme
                ],
            ),
        )
    return None


_CODE_OF = {
    "ACCESS_SPAN": InfeasibleReason.ACCESS_SPAN,
    "FIXTURE_FIT": InfeasibleReason.FIXTURE_FIT,
    "PARKING_SIZE": InfeasibleReason.PARKING_TOO_WIDE,
    "OPENING_FIT": InfeasibleReason.OPENING_FIT,
}


def no_supported_layout(
    intent: ArchitecturalIntent,
    closest: list[tuple[str, str, int, int, int]],
    tried: int,
    topology: str | None,
) -> FeasibilityReport:
    """The search found no supported layout. `closest` lists the closest candidate's shortfalls as
    (code, room, shortfall, needed, actual), largest first."""
    lines = []
    for code, room, _, needed, actual in closest[:3]:
        name = room.replace("_", " ")
        if code == "MIN_AREA":
            lines.append(f"{name} would have {m2(actual)}; the rules need {m2(needed)}")
        elif code == "ACCESS_SPAN":
            lines.append(
                f"{name} would share only {m(actual)} of wall with the room it opens from; "
                f"a door needs {m(needed)}"
            )
        elif code == "PARKING_SIZE":
            lines.append(f"the parking would be {m(actual)} where {m(needed)} is needed")
        elif code == "FIXTURE_FIT":
            lines.append(f"{name} would be {m(actual)} where its fittings need {m(needed)}")
        else:
            lines.append(f"{name} would be {m(actual)} across; the rules need {m(needed)}")
    detail = "; ".join(lines) if lines else "no candidate layout could be sized"
    explanation = (
        f"None of the {tried} layouts this version of the engine can produce fits this "
        "programme on the "
        f"plot. In the closest one, {detail}. This does not mean the home is impossible to design."
    )
    params: dict[str, int | str] = {"candidates_tried": tried}
    if topology:
        params["closest_topology"] = topology
    if closest:
        params["largest_shortfall_mm"] = closest[0][2]
    return FeasibilityReport(
        FeasibilityClass.NO_SUPPORTED_LAYOUT,
        _CODE_OF.get(closest[0][0], InfeasibleReason.DEPTH_EXCEEDED)
        if closest
        else InfeasibleReason.DEPTH_EXCEEDED,
        explanation,
        params,
        (
            _setbacks_constraint(intent),
            *[
                InvolvedConstraint("ROOM_PRESENT", item.key, item.origin.ref)
                for item in intent.programme
            ],
        ),
    )
