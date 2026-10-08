"""The constraint compiler (Checkpoint 2; slicing trees in Checkpoint 2.1): a topology becomes a
sizing problem with explicit variables, hard constraints, an access plan and the Scorer as the
objective.

Variables are the topology tree's cut positions (`layout_tree`): absolute millimetres in the
region frame, on the grid. Hard constraints are itemised shortfalls in mm (0 = satisfied):

- room minimums: clear short side and area (exact wall insets), fixture-fit minimums;
- parking clear size;
- circulation: clear width at least the ruleset's passage width, length at least a door's span;
- open areas: at least the ruleset's open-space width;
- access: every room shares, with one of the rooms it may be entered from, a wall at least as
  long as its opening plus jambs;
- windows: every room that needs a window has a stretch of outside wall (region boundary or
  open area) as long as a window plus jambs.

These are necessary conditions used to search. Nothing here relaxes a requirement: the solver
only chooses sizes, and a layout is VALID only when the validator accepts the built plan."""

from dataclasses import dataclass
from math import isqrt

from p2b.core.vocabulary import OpeningKind, RoomType
from p2b.houseplans.engine.fit import FitRule
from p2b.houseplans.engine.footprint import Insets, clear_rect, half, room_insets
from p2b.houseplans.engine.geom import Rect, ceil_to
from p2b.houseplans.engine.layout_tree import Coords, boxes, compile_tree, initial_values
from p2b.houseplans.engine.objective import (
    SIZE_TERMS,
    LayoutFacts,
    QualityScore,
    SizeRule,
    SizingAccumulator,
    score,
    size_rule,
)
from p2b.houseplans.engine.ruleset import RulesetContent
from p2b.houseplans.engine.solver import Access, LayoutProblem, Placed
from p2b.houseplans.engine.zoning import Topology, ZoningInputs, zoning_inputs

Values = tuple[int, ...]
GEOMETRY_PENALTY = 10**6
# min short, min area, fixture fit, parking clear (w, d), passage (min clear width, min length)
_Demand = tuple[int, int, FitRule | None, tuple[int, int] | None, tuple[int, int] | None]


@dataclass(frozen=True)
class Shortfall:
    """One unmet hard constraint: what, which room, by how many mm (or mm for an area's side)."""

    code: str  # MIN_SHORT_SIDE, MIN_AREA, FIXTURE_FIT, PARKING_SIZE, PASSAGE, OPEN_SIZE,
    # ACCESS_SPAN, WINDOW_WALL, GEOMETRY
    room: str
    amount: int
    needed: int
    actual: int


@dataclass(frozen=True)
class _Compiled:
    """Per-candidate constants for the sizing evaluator: wall insets are fixed by the topology."""

    # slot, inset across x, inset across y, demand, size rule, circulation?, window (0: none,
    # -1: any outside wall, > 0: the entry room's front-wall need),
    # slots of the rooms it may be entered from (for the door wall of its fittings)
    rooms: tuple[tuple[int, int, int, _Demand | None, SizeRule, bool, int, tuple[int, ...]], ...]
    opens: tuple[int, ...]
    access: tuple[tuple[int, tuple[int, ...], int], ...]
    weights: tuple[int, ...]  # in `SIZE_TERMS` order
    target: int | None


def door_wall_vertical(room: Coords, vias: list[Coords]) -> bool | None:
    """Whether the wall shared with the entry room (the via with the longest shared wall) runs
    along y; None when no via touches."""
    best, vertical = 0, None
    for b in vias:
        if room[2] == b[0] or b[2] == room[0]:
            run = min(room[3], b[3]) - max(room[1], b[1])
            if run > best:
                best, vertical = run, True
        if room[3] == b[1] or b[3] == room[1]:
            run = min(room[2], b[2]) - max(room[0], b[0])
            if run > best:
                best, vertical = run, False
    return vertical


def fit_shortfall(fit: FitRule, w: int, h: int, vertical: bool | None) -> int:
    """Fixture-fit shortfall for a clear w x h room whose door wall runs along y (vertical), along
    x, or is unknown (the kinder orientation)."""
    if vertical is None:
        return min(fit.shortfall(w, h), fit.shortfall(h, w))
    return fit.shortfall(h, w) if vertical else fit.shortfall(w, h)


def side_runs(r: Coords, region: Coords, opens: list[Coords]) -> tuple[int, int, int, int]:
    """The outside-wall length on each side (left, front, right, back): the whole side on the
    region boundary, else its longest stretch facing an open area."""
    x0, y0, x1, y1 = r
    rx0, ry0, rx1, ry1 = region
    left = y1 - y0 if x0 == rx0 else 0
    front = x1 - x0 if y0 == ry0 else 0
    right = y1 - y0 if x1 == rx1 else 0
    back = x1 - x0 if y1 == ry1 else 0
    for ox0, oy0, ox1, oy1 in opens:  # inner loop of the sizing search: no temporaries
        if ox1 == x0 or ox0 == x1:
            run = (oy1 if oy1 < y1 else y1) - (oy0 if oy0 > y0 else y0)
            if ox1 == x0 and run > left:
                left = run
            if ox0 == x1 and run > right:
                right = run
        if oy1 == y0 or oy0 == y1:
            run = (ox1 if ox1 < x1 else x1) - (ox0 if ox0 > x0 else x0)
            if oy1 == y0 and run > front:
                front = run
            if oy0 == y1 and run > back:
                back = run
    return (left, front, right, back)


def window_gap(runs: tuple[int, int, int, int], need: int, entry_front: int) -> int:
    """How far a room is from having a wall for its window. For the entry room (`entry_front` > 0)
    the front wall also holds the centred main entrance, so a window there needs `entry_front`."""
    if entry_front:
        best_other = max(runs[0], runs[2], runs[3])
        if best_other >= need or runs[1] >= entry_front:
            return 0
        return min(need - best_other, entry_front - runs[1])
    best = max(runs)
    return need - best if best < need else 0


def shared_coords(a: Coords, b: Coords) -> int:
    if a[2] == b[0] or b[2] == a[0]:
        run = min(a[3], b[3]) - max(a[1], b[1])
        if run > 0:
            return run
    if a[3] == b[1] or b[3] == a[1]:
        return max(0, min(a[2], b[2]) - max(a[0], b[0]))
    return 0


class ZonedProblem:
    def __init__(
        self,
        problem: LayoutProblem,
        ruleset: RulesetContent,
        topology: Topology,
        fit: dict[RoomType, FitRule],
        inputs: ZoningInputs | None = None,
    ):
        self.p, self.rules, self.topology, self.fit = problem, ruleset, topology, fit
        self.inputs = inputs or zoning_inputs(problem)
        self.name = topology.name
        self.family = topology.family
        self.region = problem.region
        self.g = problem.grid_mm
        self.prog = compile_tree(topology.tree)
        self.var_names = self.prog.var_names
        self.types: dict[str, RoomType] = {k: r.room_type for k, r in self.inputs.rooms.items()}
        for key in topology.passages:
            self.types[key] = ruleset.zoning.circulation_room
        self.enclosed = {k: ruleset.rooms[t].enclosed for k, t in self.types.items()}
        self.access = topology.access
        self.opens = topology.opens
        self._insets: dict[str, Insets] | None = None
        self._compiled: _Compiled | None = None
        r = self.region
        self._region: Coords = (r.x0, r.y0, r.x1, r.y1)
        self.window_need = ruleset.openings.window_width_mm + 2 * ruleset.openings.jamb_clearance_mm
        self.entered_from = {a.room: a.vias for a in topology.access}
        o = ruleset.openings
        # a centred main entrance with a window beside it on the same front wall
        self.entry_front = (
            o.main_entrance_width_mm + 2 * o.window_width_mm + 4 * o.jamb_clearance_mm
        )
        # the parking bay (Checkpoint 2.2.1): the car space keeps its required size, and leftover
        # in its cell wide enough for an open strip stays open instead (see `bay`)
        park, open_min = problem.parking, ruleset.zoning.open_space_min_mm
        self._park_slot = self.prog.leaf_slot.get(park.key, -1) if park else -1
        self._bay: tuple[int, int, int] | None = None
        if park is not None and open_min is not None and self._park_slot >= 0:
            walls = 2 * half(ruleset.walls.interior_mm)  # at most an interior wall either side
            self._bay = (
                ceil_to(park.clear_w_mm + walls, self.g),
                ceil_to(park.clear_d_mm + walls, self.g),
                open_min,
            )

    # ---------- geometry ----------

    def boxes(self, v: Values) -> list[Coords] | None:
        """Every slot's rectangle, the parking slot as its bay; None if degenerate."""
        box = boxes(self.prog, self._region, v)
        if box is not None and self._bay is not None:
            box[self._park_slot] = self.bay(box[self._park_slot])
        return box

    def bay(self, cell: Coords) -> Coords:
        """The parking within its layout cell. Along each axis the car space keeps its required
        clear size (plus at most an interior wall either side, on the grid) whenever the rest of
        the cell is at least `zoning.open_space_min_mm`; that rest is left unbuilt, an open court
        or forecourt. A smaller rest stays with the parking as apron: a strip too narrow to use.
        The bay keeps the road side (front) and the house side: at a side boundary of the region
        it moves away from it, elsewhere towards the region's centre line."""
        if self._bay is None:
            return cell
        need_w, need_d, open_min = self._bay
        x0, y0, x1, y1 = cell
        rx0, _, rx1, _ = self._region
        if x1 - x0 - need_w >= open_min:
            at_left = x0 == rx0 and x1 != rx1
            inner = x0 != rx0 and x1 != rx1 and x0 + x1 < rx0 + rx1
            if at_left or inner:
                x0 = x1 - need_w
            else:
                x1 = x0 + need_w
        if y1 - y0 - need_d >= open_min:
            y1 = y0 + need_d
        return (x0, y0, x1, y1)

    def coords(self, v: Values) -> dict[str, Coords] | None:
        """Every leaf's rectangle (rooms, circulation and open areas), or None if degenerate."""
        box = self.boxes(v)
        if box is None:
            return None
        return {k: box[s] for k, s in self.prog.leaf_slot.items()}

    def rects(self, v: Values) -> dict[str, Rect] | None:
        co = self.coords(v)
        if co is None:
            return None
        return {k: Rect(*q) for k, q in co.items() if k in self.types}

    def insets(self, rects: dict[str, Rect]) -> dict[str, Insets]:
        """Which sides carry which walls depends only on the topology, so insets are fixed for the
        candidate once computed; `exact` checks the assumption on the final sizing."""
        if self._insets is None:
            self._insets = room_insets(
                rects,
                self.enclosed,
                self.region,
                exterior_mm=self.rules.walls.exterior_mm,
                interior_mm=self.rules.walls.interior_mm,
            )
        return self._insets

    def exact(self, rects: dict[str, Rect]) -> bool:
        fresh = room_insets(
            rects,
            self.enclosed,
            self.region,
            exterior_mm=self.rules.walls.exterior_mm,
            interior_mm=self.rules.walls.interior_mm,
        )
        return fresh == self.insets(rects)

    def reset_insets(self, rects: dict[str, Rect]) -> None:
        self._insets = None
        self._compiled = None
        self.insets(rects)

    # ---------- hard constraints ----------

    def _demand(self, key: str) -> _Demand | None:
        park = self.p.parking
        room = self.inputs.rooms.get(key)
        if room is not None:
            parking = (park.clear_w_mm, park.clear_d_mm) if park and key == park.key else None
            return (
                room.min_short_mm,
                room.min_area_mm2,
                self.fit.get(room.room_type),
                parking,
                None,
            )
        if key in self.topology.passages:
            return (0, 0, None, None, (self.rules.passage_min_width_mm, self.p.door_span_mm))
        return None

    def _span(self, kind: OpeningKind) -> int:
        return self.p.door_span_mm if kind == OpeningKind.DOOR else self.p.void_span_mm

    def shortfalls(self, v: Values) -> list[Shortfall]:
        """Every unmet hard constraint, itemised (the readable form of `evaluate`)."""
        co = self.coords(v)
        if co is None:
            return [Shortfall("GEOMETRY", "layout", GEOMETRY_PENALTY, 0, 0)]
        rects = {k: Rect(*q) for k, q in co.items() if k in self.types}
        out: list[Shortfall] = []
        insets = self.insets(rects)
        for key in self.types:
            demand = self._demand(key)
            if demand is None:
                continue
            clear = clear_rect(rects[key], insets[key])
            if clear is None:
                out.append(Shortfall("GEOMETRY", key, GEOMETRY_PENALTY, 0, 0))
                continue
            min_short, min_area, fit, parking, passage = demand
            short = min(clear.w, clear.h)
            if parking is not None:
                for needed, actual in ((parking[0], clear.w), (parking[1], clear.h)):
                    if actual < needed:
                        out.append(Shortfall("PARKING_SIZE", key, needed - actual, needed, actual))
                continue
            if passage is not None:
                length = max(rects[key].w, rects[key].h)
                if short < passage[0]:
                    out.append(Shortfall("PASSAGE", key, passage[0] - short, passage[0], short))
                if length < passage[1]:
                    out.append(Shortfall("PASSAGE", key, passage[1] - length, passage[1], length))
                continue
            if short < min_short:
                out.append(Shortfall("MIN_SHORT_SIDE", key, min_short - short, min_short, short))
            if clear.area < min_area:
                gap = isqrt(min_area - clear.area)
                out.append(Shortfall("MIN_AREA", key, gap, min_area, clear.area))
            if fit is not None:
                vias = [co[v] for v in self.entered_from.get(key, ())]
                gap = fit_shortfall(fit, clear.w, clear.h, door_wall_vertical(co[key], vias))
                if gap:
                    out.append(Shortfall("FIXTURE_FIT", key, gap, fit.short, short))
        open_min = self.rules.zoning.open_space_min_mm or 0
        for key in self.opens:
            x0, y0, x1, y1 = co[key]
            side = min(x1 - x0, y1 - y0)
            if side < open_min:
                out.append(Shortfall("OPEN_SIZE", key, open_min - side, open_min, side))
        for rule in self.access:
            span = self._span(rule.kind)
            shared = max(shared_coords(co[rule.room], co[via]) for via in rule.vias)
            if shared < span:
                out.append(Shortfall("ACCESS_SPAN", rule.room, span - shared, span, shared))
        open_boxes = [co[k] for k in self.opens]
        for key, t in self.types.items():
            if self.rules.rooms[t].needs_window:
                runs = side_runs(co[key], self._region, open_boxes)
                entry = self.entry_front if key == self.inputs.entry.key else 0
                gap = window_gap(runs, self.window_need, entry)
                if gap:
                    out.append(Shortfall("WINDOW_WALL", key, gap, self.window_need, max(runs)))
        return out

    # ---------- evaluation ----------

    def _compile(self, co: dict[str, Coords]) -> _Compiled:
        rects = {k: Rect(*q) for k, q in co.items() if k in self.types}
        insets = self.insets(rects)
        slot = self.prog.leaf_slot
        rooms = []
        circulation_type = self.rules.zoning.circulation_room
        for key, room_type in self.types.items():
            ins = insets[key]
            needs_window = self.rules.rooms[room_type].needs_window
            rooms.append(
                (
                    slot[key],
                    ins[0] + ins[2],
                    ins[1] + ins[3],
                    self._demand(key),
                    size_rule(self.rules, room_type),
                    room_type == circulation_type,
                    (self.entry_front if key == self.inputs.entry.key else -1)
                    if needs_window
                    else 0,
                    tuple(slot[v] for v in self.entered_from.get(key, ())),
                )
            )
        access = tuple(
            (slot[a.room], tuple(slot[v] for v in a.vias), self._span(a.kind)) for a in self.access
        )
        obj = self.rules.objective
        target = self.rules.circulation.target_share_milli if self.rules.circulation else None
        weights = tuple((obj.weights.get(k, 0) if obj else 0) for k in SIZE_TERMS)
        return _Compiled(tuple(rooms), tuple(slot[k] for k in self.opens), access, weights, target)

    def evaluate(self, v: Values) -> tuple[int, int] | None:
        """(total hard shortfall, size-dependent objective), or None for degenerate geometry.

        The compiled form of `sum(shortfalls)` and `score(..., sizing_only=True).total`: the same
        rules and the same Scorer helpers on integer tuples (a test holds them equal)."""
        box = self.boxes(v)
        if box is None:
            return None
        cp = self._compiled
        if cp is None:
            cp = self._compiled = self._compile({k: box[s] for k, s in self.prog.leaf_slot.items()})
        violation = 0
        acc = SizingAccumulator()
        open_boxes = [box[o] for o in cp.opens]
        for slot, iw, ih, demand, size, circulation, need_window, vias in cp.rooms:
            x0, y0, x1, y1 = box[slot]
            w, h = x1 - x0 - iw, y1 - y0 - ih
            if w <= 0 or h <= 0:
                if demand is not None:
                    violation += GEOMETRY_PENALTY
                continue
            if demand is not None:
                min_short, min_area, fit, park, passage = demand
                short = w if w <= h else h
                if park is not None:
                    violation += max(0, park[0] - w) + max(0, park[1] - h)
                elif passage is not None:
                    violation += max(0, passage[0] - short)
                    violation += max(0, passage[1] - max(x1 - x0, y1 - y0))
                else:
                    if short < min_short:
                        violation += min_short - short
                    if w * h < min_area:
                        violation += isqrt(min_area - w * h)
                    if fit is not None:
                        vertical = door_wall_vertical(box[slot], [box[s] for s in vias])
                        violation += fit_shortfall(fit, w, h, vertical)
            if need_window:
                runs = side_runs(box[slot], self._region, open_boxes)
                violation += window_gap(runs, self.window_need, max(0, need_window))
            acc.add(size, w, h, circulation)
        open_min = self.rules.zoning.open_space_min_mm or 0
        for x0, y0, x1, y1 in open_boxes:
            side = min(x1 - x0, y1 - y0)
            if side < open_min:
                violation += open_min - side
        for room, vias, span in cp.access:
            r = box[room]
            shared = 0
            for via in vias:
                run = shared_coords(r, box[via])
                if run > shared:
                    shared = run
            if shared < span:
                violation += span - shared
        return violation, acc.total(cp.weights, cp.target)

    def resolved_access(self, co: dict[str, Coords]) -> tuple[Access, ...]:
        """Each room's entry: of the rooms it may be entered from, the one sharing the longest wall
        (ties: the first listed)."""
        out = []
        for rule in self.access:
            best = rule.vias[0]
            best_run = shared_coords(co[rule.room], co[best])
            for via in rule.vias[1:]:
                run = shared_coords(co[rule.room], co[via])
                if run > best_run:
                    best, best_run = via, run
            out.append(Access(rule.room, best, rule.kind))
        return tuple(out)

    def facts(self, v: Values) -> LayoutFacts:
        co = self.coords(v)
        if co is None:
            raise ValueError("degenerate sizing")
        rects = {k: Rect(*q) for k, q in co.items() if k in self.types}
        links = tuple((a.room, a.via) for a in self.resolved_access(co))
        return LayoutFacts(
            rects=rects,
            types=self.types,
            region=self.region,
            entry=self.inputs.entry.key,
            parking=self.inputs.parking.key if self.inputs.parking else None,
            insets=self.insets(rects),
            links=links,
            attached=frozenset((r.room, r.host) for r in self.p.relations),
        )

    def full_score(self, v: Values) -> QualityScore:
        return score(self.facts(v), self.rules)

    def placed(self, v: Values) -> Placed:
        co = self.coords(v)
        if co is None:
            raise ValueError("degenerate sizing")
        rects = {k: Rect(*q) for k, q in co.items() if k in self.types}
        circulation = self.rules.zoning.circulation_room
        return Placed(
            rects=rects,
            added_rooms={k: circulation for k in self.topology.passages},
            access=self.resolved_access(co),
            entry_room=self.inputs.entry.key,
            topology=self.name,
        )

    # ---------- a starting point ----------

    def initial(self) -> Values:
        """Proportional to preferred areas, snapped to the grid; open areas take the slack."""
        rules, r = self.rules, self.region
        weight: dict[str, int] = {}
        for key, room in self.inputs.rooms.items():
            pref = rules.rooms[room.room_type].pref_area_mm2 or room.target_area_mm2
            weight[key] = pref
        # parking and passages start at their least size and take no share of the rest: a car
        # space has no use for more, and spare room belongs to rooms or open areas
        if self.p.parking is not None:
            weight[self.p.parking.key] = 0
        for key in self.topology.passages:
            weight[key] = 0
        slack = r.area - sum(weight.values()) * 13 // 10
        open_min = rules.zoning.open_space_min_mm or self.g
        for key in self.opens:
            weight[key] = max(open_min * min(r.w, r.h), slack // max(1, len(self.opens)))
        # least centreline sizes: clear minimums (and fittings) plus a typical wall pair, half an
        # exterior and half an interior wall
        walls = self.rules.walls
        a = (walls.exterior_mm + 1) // 2 + (walls.interior_mm + 1) // 2
        minimum: dict[str, tuple[int, int]] = {}
        for key, room in self.inputs.rooms.items():
            core = room.min_short_mm
            fit = self.fit.get(room.room_type)
            if fit is not None:
                core = max(core, fit.short)
            minimum[key] = (core + a, core + a)
        if self.p.parking is not None:
            park = self.p.parking
            minimum[park.key] = (park.clear_w_mm + a // 2, park.clear_d_mm + a // 2)
        for key in self.opens:
            minimum[key] = (open_min, open_min)
        return initial_values(self.topology.tree, self.prog, self._region, weight, self.g, minimum)
