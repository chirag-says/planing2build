"""Where a room can be added in open space (Checkpoint 3.2): derived from a plan, never stored.

A slot is a stretch of a room's outside wall with open, buildable space in front of it: no other
room meets the wall there, no door or window of the room sits there (a new room would cover it;
the jamb clearance is kept free on both sides), no fixture stands against it, it is long enough
for a door, and nothing stands in front of it closer than `max_depth_mm`. Along one outside
wall the space in front can be deep in one part and shallow in another, so each stretch is
offered at every depth its whole length allows (the widest stretch for each depth). A room's
end walls can still cover a neighbour's window; the server refuses that with the window named.

The editor offers these slots, previews a room in one and explains, with these numbers, when a
room type cannot fit. ADD_ROOM_OUTSIDE checks everything again on the server, and the validator
judges the result: a slot is a suggestion, never a permission.

Lengths are centreline lengths, as room rectangles are. A room's clear size is smaller by its
walls: `depth_allowance_mm` (half the shared inside wall and half the outside wall) and
`length_allowance_mm` (half an outside wall at each end)."""

from dataclasses import dataclass
from itertools import pairwise

from p2b.core.vocabulary import RoomSide
from p2b.houseplans.engine.derive import half, open_areas
from p2b.houseplans.engine.geom import Pt, Rect
from p2b.houseplans.engine.graph_edit import (
    GraphEditRejected,
    _seg_of,
    buildable_region,
    room_rects,
    side_line,
    touching,
)
from p2b.houseplans.engine.model import HousePlan
from p2b.houseplans.engine.ruleset import RulesetContent


@dataclass(frozen=True)
class InsertionSlot:
    host_room: str
    side: RoomSide
    offset_mm: int  # from the side's left (LEFT, RIGHT sides: front) end
    length_mm: int
    max_depth_mm: int
    open_area: str | None  # the derived open area in front (PlanGeometry ids), when known
    open_area_kind: str | None
    depth_allowance_mm: int
    length_allowance_mm: int


def _subtract(lo: int, hi: int, cuts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    runs, at = [], lo
    for a, b in sorted(cuts):
        if b <= at:
            continue
        if a > at:
            runs.append((at, min(a, hi)))
        at = max(at, b)
        if at >= hi:
            break
    if at < hi:
        runs.append((at, hi))
    return [(a, b) for a, b in runs if a < b]


def _depth(rects: dict[str, Rect], host: str, side: RoomSide, region: Rect, s: int, e: int) -> int:
    """How far the open space in front of `host`'s `side` reaches over [s, e]: to the buildable
    region's edge or the nearest room in front, whichever is closer."""
    line, _, _ = side_line(rects[host], side)
    across = side in (RoomSide.LEFT, RoomSide.RIGHT)
    lowward = side in (RoomSide.LEFT, RoomSide.FRONT)  # the space lies towards lower x or y
    edges = (region.x0, region.x1) if across else (region.y0, region.y1)
    limit = edges[0] if lowward else edges[1]
    for key, r in rects.items():
        if key == host:
            continue
        a0, a1 = (r.y0, r.y1) if across else (r.x0, r.x1)
        if not (a0 < e and a1 > s):
            continue
        near, far = (r.x1, r.x0) if across else (r.y1, r.y0)
        if lowward and near <= line:
            limit = max(limit, near)
        elif not lowward and far >= line:
            limit = min(limit, far)
    return line - limit if lowward else limit - line


def _obstacle_ends(rects: dict[str, Rect], host: str, side: RoomSide, a: int, b: int) -> set[int]:
    line, _, _ = side_line(rects[host], side)
    across = side in (RoomSide.LEFT, RoomSide.RIGHT)
    lowward = side in (RoomSide.LEFT, RoomSide.FRONT)
    out = {a, b}
    for key, r in rects.items():
        if key == host:
            continue
        in_front = (
            ((r.x1 if across else r.y1) <= line)
            if lowward
            else ((r.x0 if across else r.y0) >= line)
        )
        if not in_front:
            continue
        for v in (r.y0, r.y1) if across else (r.x0, r.x1):
            if a < v < b:
                out.add(v)
    return out


def insertion_slots(plan: HousePlan, ruleset: RulesetContent) -> list[InsertionSlot]:
    """Every slot on the ground floor, in room order, then side order, then along the side."""
    region = buildable_region(plan, ruleset)
    if region is None or not plan.floors:
        return []
    floor = plan.floors[0]
    try:
        rects = room_rects(floor)
    except GraphEditRejected:
        return []
    o = ruleset.openings
    jamb = o.jamb_clearance_mm
    min_length = o.door_width_mm + 2 * jamb
    nodes: dict[str, Pt] = {n.id: (n.x, n.y) for n in floor.nodes}
    walls = {w.id: w for w in floor.walls}
    depth_allowance = half(ruleset.walls.interior_mm) + half(ruleset.walls.exterior_mm)
    length_allowance = 2 * half(ruleset.walls.exterior_mm)
    areas = open_areas(region, [[nodes[n] for n in r.boundary] for r in floor.rooms])

    def area_at(x: int, y: int) -> tuple[str | None, str | None]:
        for area in areas:
            for cell in area.cells:
                xs = [p.x for p in cell]
                ys = [p.y for p in cell]
                if min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys):
                    return area.id, area.kind
        return None, None

    out: list[InsertionSlot] = []
    for room in floor.rooms:
        if not room.enclosed:
            continue
        h = rects[room.id]
        for side in RoomSide:
            line, lo, hi = side_line(h, side)
            across = side in (RoomSide.LEFT, RoomSide.RIGHT)
            cuts = list(touching(rects, room.id, side))
            for opening in floor.openings:
                wall = walls.get(opening.wall)
                if wall is None:
                    continue
                seg, reversed_ = _seg_of(nodes[wall.a], nodes[wall.b])
                if seg.axis != ("y" if across else "x") or seg.coord != line:
                    continue
                start = (
                    seg.hi - opening.offset_mm - opening.width_mm
                    if reversed_
                    else seg.lo + opening.offset_mm
                )
                cuts.append((start - jamb, start + opening.width_mm + jamb))
            for fixture in floor.fixtures:  # a new wall junction must not split a fixture's wall
                wall = walls.get(fixture.wall)
                if wall is None:
                    continue
                seg, reversed_ = _seg_of(nodes[wall.a], nodes[wall.b])
                if seg.axis != ("y" if across else "x") or seg.coord != line:
                    continue
                start = (
                    seg.hi - fixture.offset_mm - fixture.w_mm
                    if reversed_
                    else seg.lo + fixture.offset_mm
                )
                cuts.append((start, start + fixture.w_mm))
            for a, b in _subtract(lo, hi, cuts):
                ends = sorted(_obstacle_ends(rects, room.id, side, a, b))
                pieces = list(pairwise(ends))
                depths = [_depth(rects, room.id, side, region, s, e) for s, e in pieces]
                seen: set[tuple[int, int, int]] = set()
                for i, d in enumerate(depths):
                    if d <= 0:
                        continue
                    j0 = i
                    while j0 > 0 and depths[j0 - 1] >= d:
                        j0 -= 1
                    j1 = i
                    while j1 + 1 < len(depths) and depths[j1 + 1] >= d:
                        j1 += 1
                    s, e = pieces[j0][0], pieces[j1][1]
                    if e - s < min_length or (s, e, d) in seen:
                        continue
                    seen.add((s, e, d))
                    mid = (s + e) // 2
                    beyond = (
                        line - d // 2 if side in (RoomSide.LEFT, RoomSide.FRONT) else line + d // 2
                    )
                    area_id, kind = area_at(beyond, mid) if across else area_at(mid, beyond)
                    out.append(
                        InsertionSlot(
                            host_room=room.id,
                            side=side,
                            offset_mm=s - lo,
                            length_mm=e - s,
                            max_depth_mm=d,
                            open_area=area_id,
                            open_area_kind=kind,
                            depth_allowance_mm=depth_allowance,
                            length_allowance_mm=length_allowance,
                        )
                    )
    return out
