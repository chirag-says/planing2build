"""Checkpoint 2 research spike (not application code): a zoned layout structure, one objective
shared by every sizer, and adapters into the real Checkpoint 1 engine (plan builder + validator).

Structure "spine" (generalises Checkpoint 1's band-and-spine):
  front band  [parking | entry]  or  [entry | parking]   (parking side is a candidate choice)
  spine       circulation strip at a VARIABLE x (not forced to the centre), from the front band back
  columns     rooms stacked beside the spine, one or two columns (two whenever widths allow)
  rear band   optional: one room spanning the full width behind the spine's end
Variables (mm): front depth f, spine x s, rear depth r, and every cut between stacked rooms.

All preference numbers here (aspect limits, weights, preferred areas where the ruleset has none) are
SYNTHETIC BENCHMARK VALUES for research, not architectural rules (AD-05 pending)."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

from p2b.core.vocabulary import OpeningKind, RoomType
from p2b.houseplans.engine.geom import Rect, ceil_to
from p2b.houseplans.engine.solver import Access, LayoutProblem, Placed, RoomDemand

# Synthetic benchmark preferences (research only).
ASPECT_LIMIT_X10 = {
    RoomType.LIVING: 15, RoomType.DINING: 15, RoomType.KITCHEN: 18, RoomType.BEDROOM: 14,
    RoomType.BATH_ATTACHED: 18, RoomType.BATH_COMMON: 18, RoomType.WC: 18, RoomType.PUJA: 15,
    RoomType.UTILITY: 20, RoomType.STORE: 20,
}  # fmt: skip
PREF_AREA_FACTOR_X100 = 120  # preferred area = min area x 1.2 where the ruleset gives none
W_AREA, W_ASPECT, W_CORRIDOR = 1000, 2000, 1000  # objective weights (per unit, x1000 scale)
BIG = 10**9


def pref_area(room: RoomDemand) -> int:
    if room.target_area_mm2 != room.min_area_mm2:
        return room.target_area_mm2
    return room.min_area_mm2 * PREF_AREA_FACTOR_X100 // 100


def scored(room: RoomDemand) -> bool:
    return room.room_type in ASPECT_LIMIT_X10


@dataclass(frozen=True)
class Group:
    rooms: tuple[RoomDemand, ...]  # host first, then rooms reached only through it


@dataclass(frozen=True)
class Candidate:
    """One zoning: parking side, which group (if any) takes the rear band, which column each
    remaining group goes to, and the order within each column."""

    parking_left: bool
    two_columns: bool
    rear: Group | None
    columns: tuple[tuple[Group, ...], ...]  # left column first
    entry_column: int  # the column the anchored group heads (index into columns)
    anchored: Group | None
    name: str


@dataclass
class Layout:
    """A concrete sizing of a candidate: integer mm cut positions."""

    f: int
    s: int  # spine left x (two columns), ignored for one column
    r: int
    cuts: list[list[int]] = field(default_factory=list)  # per column: depths of all rooms but the last


class Spec:
    """Everything derived once from the problem for a candidate."""

    def __init__(self, problem: LayoutProblem, cand: Candidate):
        self.p, self.c = problem, cand
        reg = problem.region
        self.a = problem.wall_allowance_mm
        self.g = problem.grid_mm
        self.spine_w = ceil_to(problem.passage_clear_mm + self.a, self.g)
        self.entry = next(r for r in problem.rooms if r.room_type == problem.zoning.entry_room)
        park = problem.parking
        self.park_room = next((r for r in problem.rooms if park and r.key == park.key), None)
        self.park_w = ceil_to(park.clear_w_mm + self.a, self.g) if park else 0
        self.park_d = ceil_to(park.clear_d_mm + self.a, self.g) if park else 0
        self.reg = reg
        # front band x ranges
        if cand.parking_left:
            self.park_x = (reg.x0, reg.x0 + self.park_w)
            self.entry_x = (reg.x0 + self.park_w, reg.x1)
        else:
            self.entry_x = (reg.x0, reg.x1 - self.park_w)
            self.park_x = (reg.x1 - self.park_w, reg.x1)

    # ---------- geometry from a layout ----------

    def spine_x(self, lay: Layout) -> tuple[int, int]:
        reg = self.reg
        if self.c.two_columns:
            return lay.s, lay.s + self.spine_w
        if self.c.parking_left:
            return reg.x1 - self.spine_w, reg.x1  # spine on the entry side
        return reg.x0, reg.x0 + self.spine_w

    def column_x(self, lay: Layout) -> list[tuple[int, int]]:
        reg = self.reg
        s0, s1 = self.spine_x(lay)
        if self.c.two_columns:
            return [(reg.x0, s0), (s1, reg.x1)]
        return [(reg.x0, s0)] if self.c.parking_left else [(s1, reg.x1)]

    def rects(self, lay: Layout) -> dict[str, Rect] | None:
        reg = self.reg
        f_y = reg.y0 + lay.f
        rear_y = reg.y1 - (lay.r if self.c.rear else 0)
        if not (reg.y0 < f_y < rear_y <= reg.y1):
            return None
        out: dict[str, Rect] = {}
        try:
            if self.park_room is not None:
                out[self.park_room.key] = Rect(self.park_x[0], reg.y0, self.park_x[1], f_y)
            out[self.entry.key] = Rect(self.entry_x[0], reg.y0, self.entry_x[1], f_y)
            s0, s1 = self.spine_x(lay)
            out[self.p.passage_key] = Rect(s0, f_y, s1, rear_y)
            for (x0, x1), groups, cuts in zip(self.column_x(lay), self.c.columns, lay.cuts, strict=True):
                rooms = [r for g in groups for r in g.rooms]
                y = f_y
                for i, room in enumerate(rooms):
                    y1 = rear_y if i == len(rooms) - 1 else y + cuts[i]
                    out[room.key] = Rect(x0, y, x1, y1)
                    y = y1
            if self.c.rear:
                out[self.c.rear.rooms[0].key] = Rect(reg.x0, rear_y, reg.x1, reg.y1)
        except ValueError:  # a degenerate rectangle
            return None
        return out

    # ---------- hard constraints and objective ----------

    def violation(self, lay: Layout, rects: dict[str, Rect]) -> int:
        """Total shortfall in mm against hard rules (0 = feasible)."""
        a, v = self.a, 0
        for room in self.p.rooms:
            rc = rects[room.key]
            cw, cd = rc.w - a, rc.h - a
            if self.park_room is not None and room.key == self.park_room.key:
                v += max(0, self.p.parking.clear_w_mm - cw) + max(0, self.p.parking.clear_d_mm - cd)
                continue
            v += max(0, room.min_short_mm - min(cw, cd))
            if cw > 0 and cd > 0 and cw * cd < room.min_area_mm2:
                v += math.isqrt(room.min_area_mm2 - cw * cd)
        s0, s1 = self.spine_x(lay)
        e = rects[self.entry.key]
        v += max(0, self.p.void_span_mm - (min(s1, e.x1) - max(s0, e.x0)))
        if self.c.anchored is not None:
            col = self.column_x(lay)[self.c.entry_column]
            v += max(0, self.p.door_span_mm - (min(col[1], e.x1) - max(col[0], e.x0)))
        for groups in self.c.columns:
            for g in groups:
                head = rects[g.rooms[0].key]
                if self.c.anchored is None or g is not self.c.anchored:
                    v += max(0, self.p.door_span_mm - head.h)
        return v

    def objective(self, lay: Layout, rects: dict[str, Rect]) -> int:
        a, total = self.a, 0
        enclosed_area = 0
        for room in self.p.rooms:
            rc = rects[room.key]
            cw, cd = max(1, rc.w - a), max(1, rc.h - a)
            enclosed_area += cw * cd
            if not scored(room):
                continue
            pa = pref_area(room)
            total += W_AREA * abs(cw * cd - pa) // pa
            long, short = max(cw, cd), min(cw, cd)
            excess = max(0, 10 * long - ASPECT_LIMIT_X10[room.room_type] * short)  # x10 mm
            total += W_ASPECT * excess // (10 * math.isqrt(pa))
        sp = rects[self.p.passage_key]
        total += W_CORRIDOR * (sp.w * sp.h) // max(1, enclosed_area)
        return total

    def evaluate(self, lay: Layout) -> tuple[int, int] | None:
        rects = self.rects(lay)
        if rects is None:
            return None
        return self.violation(lay, rects), self.objective(lay, rects)

    # ---------- into the engine ----------

    def placed(self, lay: Layout) -> Placed:
        rects = self.rects(lay)
        assert rects is not None
        p, c = self.p, self.c
        access = [Access(p.passage_key, self.entry.key, OpeningKind.VOID)]
        rel = {r.room: r for r in p.relations}
        groups = [g for col in c.columns for g in col]
        for g in groups:
            head = g.rooms[0]
            if c.anchored is not None and g is c.anchored:
                r = rel.get(head.key)
                kind = r.access if r is not None and r.host == self.entry.key else OpeningKind.VOID
                access.append(Access(head.key, self.entry.key, kind))
            else:
                access.append(Access(head.key, p.passage_key, OpeningKind.DOOR))
            for room in g.rooms[1:]:
                access.append(Access(room.key, rel[room.key].host, rel[room.key].access))
        if c.rear is not None:
            access.append(Access(c.rear.rooms[0].key, p.passage_key, OpeningKind.DOOR))
        return Placed(rects=rects, added_rooms={p.passage_key: p.zoning.circulation_room},
                      access=tuple(access), entry_room=self.entry.key, topology=c.name)  # fmt: skip


# ---------- zoning: candidate enumeration (deterministic) ----------


def groups_of(problem: LayoutProblem) -> tuple[list[Group], Group | None, RoomDemand]:
    z = problem.zoning
    front = set(z.front_band)
    entry = next(r for r in problem.rooms if r.room_type == z.entry_room)
    column = [r for r in problem.rooms if r.room_type not in front]
    by_key = {r.key: r for r in column}
    hosts = {rel.room: rel.host for rel in problem.relations}
    deps: dict[str, list[str]] = {}
    for rel in problem.relations:
        if rel.host in by_key and rel.room in by_key:
            deps.setdefault(rel.host, []).append(rel.room)
    heads = [r for r in column if hosts.get(r.key) not in by_key]

    def chain(head: RoomDemand) -> Group:
        out, queue = [head], list(deps.get(head.key, []))
        while queue:
            k = queue.pop(0)
            out.append(by_key[k])
            queue.extend(deps.get(k, []))
        return Group(tuple(out))

    anchored = next((r for r in heads if hosts.get(r.key) == entry.key), None)
    if anchored is None:
        for t in z.anchored_to_entry:
            anchored = next((r for r in heads if r.room_type == t), None)
            if anchored:
                break
    rank = {t: i for i, t in enumerate(z.column_order)}
    pos = {r.key: i for i, r in enumerate(problem.rooms)}
    others = sorted((r for r in heads if r is not anchored), key=lambda r: (rank.get(r.room_type, 99), pos[r.key]))
    return [chain(r) for r in others], (chain(anchored) if anchored else None), entry


def candidates(problem: LayoutProblem) -> list[Candidate]:
    groups, anchored, _ = groups_of(problem)
    out: list[Candidate] = []
    rear_options: list[Group | None] = [None]
    singles = [g for g in groups if len(g.rooms) == 1 and g.rooms[0].room_type == RoomType.BEDROOM]
    if singles:
        rear_options.append(singles[-1])
    for parking_left in (True, False):
        for rear in rear_options:
            rest = [g for g in groups if g is not rear]
            for two in (True, False):
                if two:
                    entry_col = 1 if parking_left else 0
                    for k, columns in enumerate(assignments(problem, rest, anchored, entry_col)):
                        name = f"spine2_{'pL' if parking_left else 'pR'}_{'rear' if rear else 'norear'}_a{k}"
                        out.append(Candidate(parking_left, True, rear, columns, entry_col, anchored, name))
                else:
                    columns = ((*([anchored] if anchored else []), *rest),)
                    name = f"spine1_{'pL' if parking_left else 'pR'}_{'rear' if rear else 'norear'}"
                    out.append(Candidate(parking_left, False, rear, columns, 0, anchored, name))
    return out


ENUMERATE = os.environ.get("SPIKE_ENUMERATE", "1") == "1"
KEEP = 4


def _min_depth(room: RoomDemand, width: int, a: int) -> int:
    cw = max(1, width - a)
    return max(room.min_short_mm, -(-room.min_area_mm2 // cw)) + a


def assignments(problem: LayoutProblem, rest: list[Group], anchored: Group | None,
                entry_col: int) -> list[tuple[tuple[Group, ...], tuple[Group, ...]]]:  # fmt: skip
    """Two-column splits of the groups. Greedy area balance only (SPIKE_ENUMERATE=0), or every split
    ranked by a cheap depth bound at nominal column widths, keeping the best few (deterministic)."""
    a = problem.wall_allowance_mm
    spine = ceil_to(problem.passage_clear_mm + a, problem.grid_mm)
    width = (problem.region.w - spine) // 2
    if not ENUMERATE:
        cols: list[list[Group]] = [[], []]
        load = [0, 0]
        if anchored:
            cols[entry_col].append(anchored)
            load[entry_col] += sum(pref_area(r) for r in anchored.rooms)
        for g in rest:
            i = min((0, 1), key=lambda k: (load[k], k))
            cols[i].append(g)
            load[i] += sum(pref_area(r) for r in g.rooms)
        return [(tuple(cols[0]), tuple(cols[1]))] if cols[0] and cols[1] else []
    scored_splits = []
    for mask in range(2 ** len(rest)):
        cols = [[], []]
        if anchored:
            cols[entry_col].append(anchored)
        for i, g in enumerate(rest):
            cols[(mask >> i) & 1].append(g)
        if not cols[0] or not cols[1]:
            continue
        depth = [sum(_min_depth(r, width, a) for g in col for r in g.rooms) for col in cols]
        scored_splits.append((max(depth), abs(depth[0] - depth[1]), mask, (tuple(cols[0]), tuple(cols[1]))))
    scored_splits.sort(key=lambda t: t[:3])
    return [t[3] for t in scored_splits[:KEEP]]
