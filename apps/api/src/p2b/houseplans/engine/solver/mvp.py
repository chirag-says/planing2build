"""DeterministicMVPLayoutSolver: the Checkpoint 1 solver (band and spine).

No randomness and no dependency; the seed is accepted for the interface and unused. It tiles the
wall-centreline region completely, so rooms cannot overlap or leave gaps; the validator still
checks. Layout, in the plot frame (+y away from the road):

1. Front band across the full width: the ruleset's `zoning.front_band` types left to right; the
   entry room takes the width the others leave.
2. A circulation spine (`zoning.circulation_room`) of the passage width from the back of the front
   band to the rear.
3. Columns beside the spine hold every other room in groups: a group is a host room followed by
   the rooms reached only through it (relations). The anchored group (a room whose host is the
   entry room, else the first present `zoning.anchored_to_entry` type) sits first in the column
   behind the entry room; the rest fill the shallower column, in `zoning.column_order`.
4. Configurations tried in order, first feasible wins: two columns with a centred spine; one
   column with the spine on the right; one column with the spine on the left.

Sizes are conservative: a room's centreline size is its clear minimum plus the exterior wall
thickness, so walls of any kind leave the clear minimum intact. Anything that does not fit is
INFEASIBLE with the arithmetic; this solver never returns a layout it knows breaks a hard rule.
It does not attempt orientation, Vastu, daylight or wet-area clustering (CP-SAT's job)."""

from dataclasses import dataclass

from p2b.core.vocabulary import InfeasibleReason, OpeningKind, SolverKind
from p2b.houseplans.engine.geom import Rect, ceil_div, ceil_to
from p2b.houseplans.engine.solver import (
    Access,
    Infeasible,
    InfeasibleDetail,
    LayoutProblem,
    Placed,
    RoomDemand,
    SolveOutcome,
)

UNORDERED = 10_000


@dataclass(frozen=True)
class _Group:
    rooms: tuple[RoomDemand, ...]  # head first


class _Fail(Exception):
    def __init__(self, code: InfeasibleReason, **params: int | str):
        super().__init__(code.value)
        self.detail = InfeasibleDetail(code, dict(params))


class DeterministicMVPLayoutSolver:
    kind = SolverKind.DETERMINISTIC_MVP
    version = "1.0.0"

    def solve(self, problem: LayoutProblem, *, seed: int) -> SolveOutcome:
        try:
            self._area_budget(problem)
            front, entry, front_y = self._front_band(problem)
        except _Fail as fail:
            return Infeasible((fail.detail,))
        groups, anchored = self._groups(problem, entry)
        reasons: list[InfeasibleDetail] = []
        for topology in (
            "two_columns_centre_spine",
            "one_column_spine_right",
            "one_column_spine_left",
        ):
            try:
                return self._columns(problem, topology, front, entry, front_y, groups, anchored)
            except _Fail as fail:
                reasons.append(
                    InfeasibleDetail(fail.detail.code, {**fail.detail.params, "topology": topology})
                )
        return Infeasible(tuple(reasons))

    # ---------- sizes ----------

    @staticmethod
    def _depth(problem: LayoutProblem, room: RoomDemand, width: int) -> int:
        """Centreline depth for a room of this centreline width, or _Fail if too narrow."""
        a, g = problem.wall_allowance_mm, problem.grid_mm
        clear_w = width - a
        if clear_w < room.min_short_mm:
            raise _Fail(
                InfeasibleReason.WIDTH_TOO_NARROW,
                room=room.key,
                width_mm=clear_w,
                needed_mm=room.min_short_mm,
            )
        clear_d = max(
            room.min_short_mm,
            ceil_div(room.target_area_mm2, clear_w),
            ceil_div(room.min_area_mm2, clear_w),
        )
        return ceil_to(clear_d + a, g)

    @staticmethod
    def _area_budget(problem: LayoutProblem) -> None:
        a = problem.wall_allowance_mm
        needed = 0
        for room in problem.rooms:
            if problem.parking is not None and room.key == problem.parking.key:
                needed += (problem.parking.clear_w_mm + a) * (problem.parking.clear_d_mm + a)
            else:
                needed += (room.min_short_mm + a) * (
                    ceil_div(room.min_area_mm2, room.min_short_mm) + a
                )
        if needed > problem.region.area:
            raise _Fail(
                InfeasibleReason.AREA_BUDGET, needed_mm2=needed, available_mm2=problem.region.area
            )

    # ---------- front band ----------

    def _front_band(self, problem: LayoutProblem) -> tuple[dict[str, Rect], RoomDemand, int]:
        z, r, g, a = problem.zoning, problem.region, problem.grid_mm, problem.wall_allowance_mm
        order = {t: i for i, t in enumerate(z.front_band)}
        members = sorted(
            (room for room in problem.rooms if room.room_type in order),
            key=lambda room: order[room.room_type],
        )
        entries = [room for room in members if room.room_type == z.entry_room]
        if not entries:
            raise _Fail(InfeasibleReason.RULESET_INCOMPLETE, missing="entry_room")
        entry = entries[0]
        widths: dict[str, int] = {}
        depths: dict[str, int] = {}
        for room in members:
            if room is entry:
                continue
            if problem.parking is not None and room.key == problem.parking.key:
                widths[room.key] = ceil_to(problem.parking.clear_w_mm + a, g)
                depths[room.key] = ceil_to(problem.parking.clear_d_mm + a, g)
            else:
                widths[room.key] = ceil_to(room.min_short_mm + a, g)
                depths[room.key] = self._depth(problem, room, widths[room.key])
        widths[entry.key] = r.w - sum(widths.values())
        if widths[entry.key] - a < entry.min_short_mm:
            code = (
                InfeasibleReason.PARKING_TOO_WIDE
                if problem.parking is not None
                else InfeasibleReason.WIDTH_TOO_NARROW
            )
            raise _Fail(
                code,
                room=entry.key,
                width_mm=max(0, widths[entry.key] - a),
                needed_mm=entry.min_short_mm,
            )
        depths[entry.key] = self._depth(problem, entry, widths[entry.key])
        front_y = r.y0 + max(depths.values())
        if front_y >= r.y1:
            raise _Fail(InfeasibleReason.DEPTH_EXCEEDED, needed_mm=front_y - r.y0, available_mm=r.h)
        rects: dict[str, Rect] = {}
        x = r.x0
        for room in members:
            x1 = x + widths[room.key]
            rects[room.key] = Rect(x, r.y0, x1, front_y)
            x = x1
        return rects, entry, front_y

    # ---------- groups ----------

    @staticmethod
    def _groups(problem: LayoutProblem, entry: RoomDemand) -> tuple[list[_Group], _Group | None]:
        z = problem.zoning
        front_types = set(z.front_band)
        column = [room for room in problem.rooms if room.room_type not in front_types]
        by_key = {room.key: room for room in column}
        hosts = {rel.room: rel.host for rel in problem.relations}
        dependents: dict[str, list[str]] = {}
        for rel in problem.relations:
            if rel.host in by_key and rel.room in by_key:
                dependents.setdefault(rel.host, []).append(rel.room)
        heads = [room for room in column if hosts.get(room.key) not in by_key]

        def chain(head: RoomDemand) -> _Group:
            out, queue = [head], list(dependents.get(head.key, []))
            while queue:
                key = queue.pop(0)
                out.append(by_key[key])
                queue.extend(dependents.get(key, []))
            return _Group(tuple(out))

        anchored_head = next((room for room in heads if hosts.get(room.key) == entry.key), None)
        if anchored_head is None:
            for room_type in z.anchored_to_entry:
                anchored_head = next((room for room in heads if room.room_type == room_type), None)
                if anchored_head is not None:
                    break
        rank = {t: i for i, t in enumerate(z.column_order)}
        position = {room.key: i for i, room in enumerate(problem.rooms)}
        others = sorted(
            (room for room in heads if room is not anchored_head),
            key=lambda room: (rank.get(room.room_type, UNORDERED), position[room.key]),
        )
        return [chain(room) for room in others], chain(anchored_head) if anchored_head else None

    # ---------- columns ----------

    def _columns(
        self,
        problem: LayoutProblem,
        topology: str,
        front: dict[str, Rect],
        entry: RoomDemand,
        front_y: int,
        groups: list[_Group],
        anchored: _Group | None,
    ) -> Placed:
        r, g, a = problem.region, problem.grid_mm, problem.wall_allowance_mm
        spine_w = ceil_to(problem.passage_clear_mm + a, g)
        if topology == "two_columns_centre_spine":
            left_w = (r.w - spine_w) // 2 // g * g
            spine = (r.x0 + left_w, r.x0 + left_w + spine_w)
            columns = [(r.x0, spine[0]), (spine[1], r.x1)]
        elif topology == "one_column_spine_right":
            spine = (r.x1 - spine_w, r.x1)
            columns = [(r.x0, spine[0])]
        else:
            spine = (r.x0, r.x0 + spine_w)
            columns = [(spine[1], r.x1)]
        if any(x1 <= x0 for x0, x1 in columns):
            raise _Fail(
                InfeasibleReason.WIDTH_TOO_NARROW,
                room=problem.passage_key,
                width_mm=r.w,
                needed_mm=spine_w,
            )
        entry_rect = front[entry.key]
        spine_overlap = min(spine[1], entry_rect.x1) - max(spine[0], entry_rect.x0)
        if spine_overlap < problem.void_span_mm:
            raise _Fail(
                InfeasibleReason.ACCESS_SPAN,
                room=problem.passage_key,
                span_mm=max(0, spine_overlap),
                needed_mm=problem.void_span_mm,
            )

        def overlap_with_entry(col: tuple[int, int]) -> int:
            return min(col[1], entry_rect.x1) - max(col[0], entry_rect.x0)

        entry_col = max(range(len(columns)), key=lambda i: (overlap_with_entry(columns[i]), -i))
        filled = [0] * len(columns)
        stacks: list[list[tuple[RoomDemand, int]]] = [[] for _ in columns]

        def put(group: _Group, i: int) -> None:
            width = columns[i][1] - columns[i][0]
            for room in group.rooms:
                depth = self._depth(problem, room, width)
                stacks[i].append((room, depth))
                filled[i] += depth

        if anchored is not None:
            put(anchored, entry_col)
        for group in groups:
            put(group, min(range(len(columns)), key=lambda i: (filled[i], i)))
        available = r.y1 - front_y
        for i, depth in enumerate(filled):
            if depth > available:
                raise _Fail(
                    InfeasibleReason.DEPTH_EXCEEDED,
                    column=i,
                    needed_mm=depth,
                    available_mm=available,
                )
            if not stacks[i]:
                raise _Fail(InfeasibleReason.WIDTH_TOO_NARROW, column=i, width_mm=0, needed_mm=0)

        rects = dict(front)
        rects[problem.passage_key] = Rect(spine[0], front_y, spine[1], r.y1)
        for i, stack in enumerate(stacks):
            # The column's leftover depth goes to its room with the largest target area (the
            # first such room on a tie), not to whichever room happens to be last: a bedroom grows,
            # a bathroom does not.
            slack = available - filled[i]
            grow = max(range(len(stack)), key=lambda n: (stack[n][0].target_area_mm2, -n))
            y = front_y
            for n, (room, depth) in enumerate(stack):
                y1 = y + depth + (slack if n == grow else 0)
                rects[room.key] = Rect(columns[i][0], y, columns[i][1], y1)
                y = y1

        access: list[Access] = [Access(problem.passage_key, entry.key, OpeningKind.VOID)]
        relation_access = {rel.room: rel for rel in problem.relations}
        if anchored is not None:
            head = anchored.rooms[0]
            span = min(columns[entry_col][1], entry_rect.x1) - max(
                columns[entry_col][0], entry_rect.x0
            )
            rel = relation_access.get(head.key)
            kind = rel.access if rel is not None and rel.host == entry.key else OpeningKind.VOID
            needed = problem.door_span_mm if kind == OpeningKind.DOOR else problem.void_span_mm
            if span < needed:
                raise _Fail(
                    InfeasibleReason.ACCESS_SPAN,
                    room=head.key,
                    span_mm=max(0, span),
                    needed_mm=needed,
                )
            access.append(Access(head.key, entry.key, kind))
        for group in ([anchored] if anchored else []) + groups:
            head = group.rooms[0]
            if anchored is None or head is not anchored.rooms[0]:
                if rects[head.key].h < problem.door_span_mm:
                    raise _Fail(
                        InfeasibleReason.ACCESS_SPAN,
                        room=head.key,
                        span_mm=rects[head.key].h,
                        needed_mm=problem.door_span_mm,
                    )
                access.append(Access(head.key, problem.passage_key, OpeningKind.DOOR))
            for room in group.rooms[1:]:
                rel = relation_access[room.key]
                access.append(Access(room.key, rel.host, rel.access))
        for room in problem.rooms:
            if room.room_type in problem.zoning.front_band and room is not entry and room.enclosed:
                access.append(Access(room.key, entry.key, OpeningKind.DOOR))
        return Placed(
            rects=rects,
            added_rooms={problem.passage_key: problem.zoning.circulation_room},
            access=tuple(access),
            entry_room=entry.key,
            topology=topology,
        )
