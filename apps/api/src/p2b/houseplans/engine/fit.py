"""Fixture-fit minimums (Checkpoint 2; door-wall aware in Checkpoint 2.1).

For each room type with a fixture template, which clear sizes the real placement routine can fit
the template into, beside a standard door at its usual offset. The answer depends on which wall
holds the door, so it is kept as a staircase of minimal (along, across) pairs: `along` is the
clear length of the wall with the door, `across` the other clear dimension. Derived from the
ruleset itself, never a separate number, and cached per ruleset content.

The door is tried at both ends of its wall, since the real door may sit at either end relative
to the fittings (Checkpoint 2.2). It is a bound, not a guarantee: a real room has other doors and
windows. The pipeline therefore
still builds and validates each candidate and moves to the next one on failure."""

from dataclasses import dataclass
from typing import Any

from p2b.core.vocabulary import DoorLeaf, HingeSide, OpeningKind, RoomType, WallSide
from p2b.houseplans.engine.canonical import sha256_of
from p2b.houseplans.engine.footprint import half
from p2b.houseplans.engine.geom import Rect, ceil_to
from p2b.houseplans.engine.graph import build_graph
from p2b.houseplans.engine.model import DoorSpec, Opening
from p2b.houseplans.engine.place import PlacementFailure, place_fixtures
from p2b.houseplans.engine.ruleset import RulesetContent

SEARCH_LIMIT_MM = 8_000


@dataclass(frozen=True)
class FitRule:
    """Minimal clear sizes, as (along the door wall, across) pairs; any size at least as large as
    one pair in both directions fits."""

    points: tuple[tuple[int, int], ...]

    @property
    def short(self) -> int:
        """The smallest clear dimension any fitting room has."""
        return min(min(a, c) for a, c in self.points)

    def shortfall(self, along: int, across: int) -> int:
        """How far (mm, summed over both directions) the size is from the nearest fitting one."""
        best = -1
        for a, c in self.points:
            gap = (a - along if a > along else 0) + (c - across if c > across else 0)
            if gap == 0:
                return 0
            if best < 0 or gap < best:
                best = gap
        return best

    def min_along(self, across: int) -> int | None:
        """The shortest door wall that fits when the other side is `across`."""
        return min((a for a, c in self.points if c <= across), default=None)

    def min_across(self, along: int) -> int | None:
        return min((c for a, c in self.points if a <= along), default=None)


_CACHE: dict[str, dict[RoomType, FitRule]] = {}


def _fits(room_type: RoomType, along: int, across: int, ruleset: RulesetContent) -> bool:
    """Whether the template fits a room of clear size `along` (the door wall) by `across`. The
    door is in an interior wall shared with a hall, as every door is; the other walls are
    exterior. Placement is greedy and depends on wall order and direction, so the room is tried
    with the hall on each of its four sides and the door at either end of its wall: a size fits
    only if all eight do."""
    from p2b.houseplans.engine.build import wall_infos  # build imports place; avoid a cycle

    ext, inner = half(ruleset.walls.exterior_mm), half(ruleset.walls.interior_mm)
    hall_d = 2 * ruleset.passage_min_width_mm
    o = ruleset.openings
    for side in ("below", "above", "left", "right"):
        vertical = side in ("left", "right")
        w, h = (
            (across + inner + ext, along + 2 * ext)
            if vertical
            else (along + 2 * ext, across + inner + ext)
        )
        room = Rect(0, 0, w, h)
        hall, clear = {
            "below": (Rect(0, -hall_d, w, 0), room.inset(ext, inner, ext, ext)),
            "above": (Rect(0, h, w, h + hall_d), room.inset(ext, ext, ext, inner)),
            "left": (Rect(-hall_d, 0, 0, h), room.inset(inner, ext, ext, ext)),
            "right": (Rect(w, 0, w + hall_d, h), room.inset(ext, ext, inner, ext)),
        }[side]
        graph = build_graph(
            {"room": room, "hall": hall},
            {"room": True, "hall": True},
            exterior_mm=ruleset.walls.exterior_mm,
            interior_mm=ruleset.walls.interior_mm,
        )
        walls = wall_infos(graph)
        host = next(
            w
            for w in walls.values()
            if "room" in w.left_rooms + w.right_rooms and "hall" in w.left_rooms + w.right_rooms
        )
        # The door starts a jamb clearance from its wall's end node; that node sits half the
        # crossing wall's thickness outside the clear corner (exterior or interior), so the door
        # may start 0 or (ext - inner) further in. Both ends, both positions.
        shift = ext - inner
        starts = (o.jamb_clearance_mm, o.jamb_clearance_mm + shift)
        offsets = {*starts, *(host.length - s - o.door_width_mm for s in starts)}
        for offset in sorted(offsets):
            if not _fits_with_door(room_type, walls, host, clear, offset, ruleset):
                return False
    return True


def _fits_with_door(
    room_type: RoomType,
    walls: dict[str, Any],
    host: Any,
    clear: Rect | None,
    offset: int,
    ruleset: RulesetContent,
) -> bool:
    o = ruleset.openings
    door = Opening(
        id="door",
        kind=OpeningKind.DOOR,
        wall=host.id,
        offset_mm=offset,
        width_mm=o.door_width_mm,
        height_mm=o.door_height_mm,
        sill_mm=0,
        door=DoorSpec(
            leaf=DoorLeaf.SINGLE,
            hinge=HingeSide.A_SIDE,
            opens_to=WallSide.LEFT if "room" in host.left_rooms else WallSide.RIGHT,
        ),
    )
    try:
        place_fixtures({"room": room_type}, walls, {"room": clear}, [door], ruleset)
    except PlacementFailure:
        return False
    return True


def fixture_fit(ruleset: RulesetContent) -> dict[RoomType, FitRule]:
    key = sha256_of(ruleset)
    if key in _CACHE:
        return _CACHE[key]
    g = ruleset.grid_mm
    door_span = ruleset.openings.door_width_mm + 2 * ruleset.openings.jamb_clearance_mm
    out: dict[RoomType, FitRule] = {}
    same: dict[tuple[object, ...], FitRule] = {}  # room types with one template and minimum
    for room_type, template in sorted(ruleset.templates.items()):
        rule = ruleset.rooms.get(room_type)
        if rule is None or not template:
            continue
        shape = (tuple(template), rule.min_short_mm)
        if shape in same:
            out[room_type] = same[shape]
            continue
        floor = ceil_to(rule.min_short_mm, g)
        points: list[tuple[int, int]] = []
        # The least `across` for each `along` never grows as `along` grows: walk `along` up from
        # the door's own span and lower `across` while the template still fits.
        along = ceil_to(max(floor, door_span), g)
        across: int | None = None
        while along <= SEARCH_LIMIT_MM and (across is None or across > floor):
            if across is None:
                if not _fits(room_type, along, SEARCH_LIMIT_MM, ruleset):
                    along += g
                    continue
                lo, hi = floor, SEARCH_LIMIT_MM  # the least fitting `across`, by bisection
                while lo < hi:
                    mid = floor + (lo - floor + hi - floor) // (2 * g) * g
                    if _fits(room_type, along, mid, ruleset):
                        hi = mid
                    else:
                        lo = mid + g
                across = lo
            else:
                while across - g >= floor and _fits(room_type, along, across - g, ruleset):
                    across -= g
            if not points or across < points[-1][1]:
                points.append((along, across))
            along += g
        if points:
            out[room_type] = same[shape] = FitRule(tuple(points))
    _CACHE[key] = out
    return out
