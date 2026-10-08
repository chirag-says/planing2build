"""The Scorer: the single definition of layout quality (Checkpoint 2; ZONE_ORDER, BEDROOM_GROUPING
and open-area exposure added in Checkpoint 2.1).

Every soft term is measured from room rectangles and their exact clear rectangles, with a weight
and an origin from the ruleset, an integer score (milli; 0 = fully met) and a result state. The
solver ranks candidates with this function, and the API scores a stored plan with it, from the same
quantities, so the two always agree.

Terms never decide validity: a plan is VALID only by the validator. Terms with no rule data are
NOT_EVALUATED (for example ORIENTATION until AD-13), never guessed."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import NamedTuple

from p2b.core.vocabulary import (
    ConstraintKind,
    ConstraintOutcome,
    ConstraintStrength,
    OpeningKind,
    RoomType,
    SetbackSide,
)
from p2b.houseplans.engine.footprint import Insets, clear_rect, exterior_runs, half, room_insets
from p2b.houseplans.engine.geom import Rect, rect_or_none, signed_area2
from p2b.houseplans.engine.model import HousePlan
from p2b.houseplans.engine.ruleset import RulesetContent

K = ConstraintKind
SOFT_TERMS = (
    K.AREA_DEVIATION,
    K.DIMENSION_DEVIATION,
    K.ASPECT_EXCESS,
    K.CIRCULATION_SHARE,
    K.OVERSIZE,
    K.ADJACENCY,
    K.WET_CLUSTER,
    K.EXTERIOR_EXPOSURE,
    K.PRIVACY,
    K.PARKING_CONVENIENCE,
    K.ZONE_ORDER,
    K.BEDROOM_GROUPING,
    K.ORIENTATION,
)


@dataclass(frozen=True)
class TermScore:
    kind: ConstraintKind
    weight: int
    score_milli: int | None  # None = NOT_EVALUATED
    outcome: ConstraintOutcome
    subjects: tuple[str, ...] = ()  # rooms that cost score, for highlighting


@dataclass(frozen=True)
class RoomQuality:
    key: str
    room_type: RoomType
    clear_w_mm: int
    clear_d_mm: int
    aspect_x100: int
    over_aspect: bool


@dataclass(frozen=True)
class QualityScore:
    total: int  # sum of weight * score_milli over evaluated terms
    terms: tuple[TermScore, ...]
    rooms: tuple[RoomQuality, ...]
    circulation_share_milli: int
    aspect_violations: int


@dataclass
class LayoutFacts:
    """What the Scorer reads. `insets` may be precomputed per topology (they depend only on which
    rooms touch, not on sizes) so the solver can score thousands of sizings cheaply."""

    rects: Mapping[str, Rect]
    types: Mapping[str, RoomType]
    region: Rect
    entry: str
    parking: str | None
    insets: Mapping[str, Insets] = field(default_factory=dict)
    # Door and open connections as (room, room) pairs, and (room, host) pairs of rooms reached
    # only through a host (attached bathrooms, the kitchen from the dining room): the solver's
    # access plan, or a stored plan's openings and RELATION constraints.
    links: tuple[tuple[str, str], ...] = ()
    attached: frozenset[tuple[str, str]] = frozenset()


# ---------- size terms: one definition, shared by `score` and the compiled evaluator ----------


class SizeRule(NamedTuple):
    enclosed: bool
    pref_area: int | None
    pref_short: int | None
    pref_long: int | None
    aspect_limit_x10: int | None
    max_area: int | None


def size_rule(ruleset: RulesetContent, room_type: RoomType) -> SizeRule:
    r = ruleset.rooms[room_type]
    pair = bool(r.pref_short_mm and r.pref_long_mm)
    return SizeRule(
        r.enclosed,
        r.pref_area_mm2 or None,
        r.pref_short_mm if pair else None,
        r.pref_long_mm if pair else None,
        r.aspect_limit_x10,
        r.max_area_mm2 or None,
    )


class RoomTerms(NamedTuple):
    area_dev: int | None
    dim_dev: int | None
    aspect_excess: int  # 0 unless over the limit
    oversize: int
    aspect_x100: int
    over_aspect: bool


@lru_cache(maxsize=1 << 15)
def room_terms(rule: SizeRule, w: int, h: int) -> RoomTerms:
    """One enclosed room's size terms from its clear width and depth (mm, both > 0). Cached: the
    sizing search asks for the same room sizes many times (bounded, so a worker's memory is)."""
    short, long = (w, h) if w <= h else (h, w)
    area = w * h
    area_dev = abs(area - rule.pref_area) * 1000 // rule.pref_area if rule.pref_area else None
    dim_dev = None
    if rule.pref_short and rule.pref_long:
        dim_dev = (
            abs(short - rule.pref_short) * 1000 // rule.pref_short
            + abs(long - rule.pref_long) * 1000 // rule.pref_long
        )
    limit = rule.aspect_limit_x10
    over = limit is not None and 10 * long > limit * short
    excess = (1000 * long - 100 * limit * short) // short if over and limit is not None else 0
    oversize = (
        (area - rule.max_area) * 1000 // rule.max_area
        if rule.max_area and area > rule.max_area
        else 0
    )
    return RoomTerms(area_dev, dim_dev, excess, oversize, 100 * long // short, over)


SIZE_TERMS = (
    K.AREA_DEVIATION,
    K.DIMENSION_DEVIATION,
    K.ASPECT_EXCESS,
    K.OVERSIZE,
    K.CIRCULATION_SHARE,
    K.ROOM_SIZE_OUTLIER,
)


class SizingAccumulator:
    """Sums the size terms over rooms exactly as `score` reports them."""

    __slots__ = (
        "area_n",
        "area_sum",
        "aspect",
        "dim_n",
        "dim_sum",
        "oversize",
        "passage_area",
        "total_area",
        "worst_area_dev",
    )

    def __init__(self) -> None:
        self.area_sum = self.area_n = self.dim_sum = self.dim_n = 0
        self.aspect = self.oversize = self.passage_area = self.total_area = 0
        self.worst_area_dev: int | None = None

    def add(self, rule: SizeRule, w: int, h: int, circulation: bool) -> RoomTerms | None:
        if rule.enclosed:
            self.total_area += w * h
        if circulation:
            self.passage_area += w * h
            return None
        if not rule.enclosed:
            return None
        t = room_terms(rule, w, h)
        if t.area_dev is not None:
            self.area_sum += t.area_dev
            self.area_n += 1
            if self.worst_area_dev is None or t.area_dev > self.worst_area_dev:
                self.worst_area_dev = t.area_dev
        if t.dim_dev is not None:
            self.dim_sum += t.dim_dev
            self.dim_n += 1
        self.aspect += t.aspect_excess
        self.oversize += t.oversize
        return t

    def share(self) -> int:
        return self.passage_area * 1000 // self.total_area if self.total_area else 0

    def value_tuple(self, target: int | None) -> tuple[int | None, ...]:
        """The size terms in `SIZE_TERMS` order."""
        return (
            self.area_sum // self.area_n if self.area_n else None,
            self.dim_sum // self.dim_n if self.dim_n else None,
            self.aspect,
            self.oversize,
            max(0, self.share() - target) if target is not None else None,
            self.worst_area_dev,
        )

    def values(self, target: int | None) -> dict[ConstraintKind, int | None]:
        return dict(zip(SIZE_TERMS, self.value_tuple(target), strict=True))

    def total(self, weights: Sequence[int], target: int | None) -> int:
        """Sum of weight * value; `weights` in `SIZE_TERMS` order."""
        values = self.value_tuple(target)
        return sum(w * v for w, v in zip(weights, values, strict=True) if v is not None)


def facts_insets(facts: LayoutFacts, ruleset: RulesetContent) -> Mapping[str, Insets]:
    if facts.insets:
        return facts.insets
    enclosed = {k: ruleset.rooms[t].enclosed for k, t in facts.types.items()}
    return room_insets(
        facts.rects,
        enclosed,
        facts.region,
        exterior_mm=ruleset.walls.exterior_mm,
        interior_mm=ruleset.walls.interior_mm,
    )


def _outcome(score: int) -> ConstraintOutcome:
    if score == 0:
        return ConstraintOutcome.MET
    return ConstraintOutcome.PARTIAL if score < 1000 else ConstraintOutcome.UNMET


def _shared(a: Rect, b: Rect) -> int:
    if a.x1 == b.x0 or b.x1 == a.x0:
        return max(0, min(a.y1, b.y1) - max(a.y0, b.y0))
    if a.y1 == b.y0 or b.y1 == a.y0:
        return max(0, min(a.x1, b.x1) - max(a.x0, b.x0))
    return 0


def score(
    facts: LayoutFacts, ruleset: RulesetContent, *, sizing_only: bool = False
) -> QualityScore:
    """All terms, or (`sizing_only`) just the size-dependent ones the local search moves: area,
    dimensions, aspect, oversize and circulation. Topology terms do not change while a candidate is
    sized, so ranking by the full score after sizing is exact."""
    obj = ruleset.objective
    weights = obj.weights if obj else {}
    insets = facts_insets(facts, ruleset)
    circulation = ruleset.zoning.circulation_room
    clear: dict[str, Rect | None] = {k: clear_rect(r, insets[k]) for k, r in facts.rects.items()}
    terms: list[TermScore] = []

    def add(kind: ConstraintKind, value: int | None, subjects: list[str] | None = None) -> None:
        if value is None:
            terms.append(
                TermScore(kind, weights.get(kind, 0), None, ConstraintOutcome.NOT_EVALUATED)
            )
        else:
            terms.append(
                TermScore(kind, weights.get(kind, 0), value, _outcome(value), tuple(subjects or ()))
            )

    acc = SizingAccumulator()
    rooms: list[RoomQuality] = []
    area_rooms: list[str] = []
    dim_rooms: list[str] = []
    aspect_rooms: list[str] = []
    oversize_rooms: list[str] = []
    for key, room_type in facts.types.items():
        c = clear[key]
        if c is None:
            continue
        size = size_rule(ruleset, room_type)
        terms_of = acc.add(size, c.w, c.h, room_type == circulation)
        if terms_of is None:
            continue
        rooms.append(
            RoomQuality(key, room_type, c.w, c.h, terms_of.aspect_x100, terms_of.over_aspect)
        )
        for flag, bucket in (
            (terms_of.area_dev, area_rooms),
            (terms_of.dim_dev, dim_rooms),
            (terms_of.over_aspect, aspect_rooms),
            (terms_of.oversize, oversize_rooms),
        ):
            if flag:
                bucket.append(key)
    target = ruleset.circulation.target_share_milli if ruleset.circulation else None
    values = acc.values(target)
    add(K.AREA_DEVIATION, values[K.AREA_DEVIATION], area_rooms)
    add(K.DIMENSION_DEVIATION, values[K.DIMENSION_DEVIATION], dim_rooms)
    add(K.ASPECT_EXCESS, values[K.ASPECT_EXCESS], aspect_rooms)
    add(K.OVERSIZE, values[K.OVERSIZE], oversize_rooms)
    add(
        K.CIRCULATION_SHARE,
        values[K.CIRCULATION_SHARE],
        [k for k, t in facts.types.items() if t == circulation],
    )
    # ROOM_SIZE_OUTLIER: the worst room's area deviation from its preferred area. The mean in
    # AREA_DEVIATION lets one absurd room (a 13 m long living room) hide among right-sized ones.
    worst = values[K.ROOM_SIZE_OUTLIER]
    outliers = [r.key for r in rooms if worst and _area_dev(ruleset, r) == worst]
    add(K.ROOM_SIZE_OUTLIER, worst, outliers)
    share = acc.share()

    if not sizing_only:
        rects = facts.rects
        by_type: dict[RoomType, list[str]] = {}
        for k, t in facts.types.items():
            by_type.setdefault(t, []).append(k)
        span = ruleset.openings.door_width_mm + 2 * ruleset.openings.jamb_clearance_mm
        # ADJACENCY: each soft relation rule whose types are present is met by some pair sharing a
        # wall long enough for a door.
        rules = [r for r in ruleset.relations_soft if r.a in by_type and r.b in by_type]
        unmet = [
            r
            for r in rules
            if not any(
                _shared(rects[x], rects[y]) >= span for x in by_type[r.a] for y in by_type[r.b]
            )
        ]
        add(
            K.ADJACENCY,
            1000 * len(unmet) // len(rules) if rules else None,
            [k for r in unmet for k in by_type[r.a] + by_type[r.b]],
        )
        # WET_CLUSTER: wet rooms that share no wall with another wet room.
        wet = [k for k, t in facts.types.items() if ruleset.rooms[t].wet]
        alone = [k for k in wet if not any(_shared(rects[k], rects[o]) > 0 for o in wet if o != k)]
        add(K.WET_CLUSTER, 1000 * len(alone) // len(wet) if len(wet) > 1 else None, alone)
        # EXTERIOR_EXPOSURE: rooms needing a window whose longest stretch of outside wall (on the
        # boundary or facing an open area) is shorter than the ruleset asks.
        needing = [k for k, t in facts.types.items() if ruleset.rooms[t].needs_window]
        minimum = obj.exposure_min_mm if obj else None
        short_exp = [k for k in needing if minimum and exterior_runs(k, rects) < minimum]
        add(
            K.EXTERIOR_EXPOSURE,
            1000 * len(short_exp) // len(needing) if needing and minimum else None,
            short_exp,
        )
        # PRIVACY: bedrooms in the front band or sharing a wall with the entry room.
        beds = by_type.get(RoomType.BEDROOM, [])
        exposed = [
            k
            for k in beds
            if rects[k].y0 == facts.region.y0 or _shared(rects[k], rects[facts.entry]) > 0
        ]
        add(K.PRIVACY, 1000 * len(exposed) // len(beds) if beds else None, exposed)
        # PARKING_CONVENIENCE: parking shares a wall with the entry room.
        if facts.parking is not None:
            ok = _shared(rects[facts.parking], rects[facts.entry]) > 0
            add(K.PARKING_CONVENIENCE, 0 if ok else 1000, [] if ok else [facts.parking])
        else:
            add(K.PARKING_CONVENIENCE, None)
        # ZONE_ORDER: the ruleset's front-to-back zone order (`zoning.depth_order`). A pair of
        # rooms breaks it when the room of the later (more private) zone lies wholly in front of
        # the other. Pairs joined by a relation (an attached bathroom behind its bedroom) are not
        # compared. Score: the share of comparable pairs that break the order.
        rank = {zone: i for i, zone in enumerate(ruleset.zoning.depth_order)}
        zoned = [
            (k, rank[z]) for k, t in facts.types.items() if (z := ruleset.rooms[t].zone) in rank
        ]
        pairs = broken = 0
        late: list[str] = []
        for i, (a, ra) in enumerate(zoned):
            for b, rb in zoned[i + 1 :]:
                if ra == rb or (a, b) in facts.attached or (b, a) in facts.attached:
                    continue
                pairs += 1
                front, back = (a, b) if ra < rb else (b, a)
                if rects[back].y1 <= rects[front].y0:
                    broken += 1
                    late.append(back)
        add(K.ZONE_ORDER, 1000 * broken // pairs if pairs else None, sorted(set(late)))
        # BEDROOM_GROUPING: bedrooms should open off one shared space (a passage, or one hall)
        # rather than be scattered. Score: (distinct rooms bedrooms are entered from - 1) /
        # (bedrooms - 1); a bedroom's own attached rooms do not count.
        hosts: set[str] = set()
        for bed in beds:
            own = {r for r, h in facts.attached if h == bed}
            hosts |= {x for p in facts.links if bed in p for x in p if x != bed and x not in own}
        grouping = 1000 * max(0, len(hosts) - 1) // (len(beds) - 1) if len(beds) > 1 else None
        add(K.BEDROOM_GROUPING, grouping, beds if grouping else [])
        add(K.ORIENTATION, None)  # AD-13: no approved orientation table, never guessed

    total = sum(t.weight * t.score_milli for t in terms if t.score_milli is not None)
    return QualityScore(
        total=total,
        terms=tuple(terms),
        rooms=tuple(rooms),
        circulation_share_milli=share,
        aspect_violations=sum(r.over_aspect for r in rooms),
    )


def _area_dev(ruleset: RulesetContent, r: RoomQuality) -> int | None:
    pref = ruleset.rooms[r.room_type].pref_area_mm2
    if not pref:
        return None
    return abs(r.clear_w_mm * r.clear_d_mm - pref) * 1000 // pref


def plan_facts(plan: HousePlan, ruleset: RulesetContent) -> LayoutFacts | None:
    """The Scorer's view of a stored plan: room rectangles from their boundaries, the region from
    the site. None when a room is not an axis-aligned rectangle (an edited plan, later): quality is
    then not reported rather than approximated."""
    floor = plan.floors[0]
    nodes = {n.id: (n.x, n.y) for n in floor.nodes}
    rects: dict[str, Rect] = {}
    types: dict[str, RoomType] = {}
    for room in floor.rooms:
        points = [nodes[i] for i in room.boundary]
        box = rect_or_none(
            min(p[0] for p in points),
            min(p[1] for p in points),
            max(p[0] for p in points),
            max(p[1] for p in points),
        )
        # Boundaries carry extra nodes where other walls meet. A rectangle: every node on the
        # bounding box, and the polygon's area equal to the box's.
        if (
            box is None
            or room.type not in ruleset.rooms
            or abs(signed_area2(points)) != 2 * box.area
            or not all(p[0] in (box.x0, box.x1) or p[1] in (box.y0, box.y1) for p in points)
        ):
            return None
        rects[room.id] = box
        types[room.id] = room.type
    vertices = plan.site.plot.vertices
    plot = Rect(
        min(v.x for v in vertices),
        min(v.y for v in vertices),
        max(v.x for v in vertices),
        max(v.y for v in vertices),
    )
    side_of = {e.id: e.side for e in plan.site.plot.edges}
    d = {side_of[s.edge]: s.distance_mm for s in plan.site.setbacks}
    t = half(ruleset.walls.exterior_mm)
    region = plot.inset(
        d[SetbackSide.LEFT] + t,
        d[SetbackSide.FRONT] + t,
        d[SetbackSide.RIGHT] + t,
        d[SetbackSide.BACK] + t,
    )
    entry = next((k for k, v in types.items() if v == ruleset.zoning.entry_room), None)
    if region is None or entry is None:
        return None
    parking = next((k for k, v in types.items() if v == RoomType.PARKING), None)
    from p2b.houseplans.engine.derive import analyse  # derive is heavier; only stored plans need it

    links = []
    for info in analyse(plan).openings.values():
        if info.opening.kind in (OpeningKind.DOOR, OpeningKind.VOID):
            a, b = info.connects
            links.append((a, b))
    attached = frozenset(
        (c.subjects[0], c.subjects[1])
        for c in plan.constraints
        if c.kind == ConstraintKind.RELATION
        and c.strength == ConstraintStrength.HARD
        and len(c.subjects) == 2
    )
    return LayoutFacts(
        rects=rects,
        types=types,
        region=region,
        entry=entry,
        parking=parking,
        links=tuple(sorted(links)),
        attached=attached,
    )


def score_plan(plan: HousePlan, ruleset: RulesetContent) -> QualityScore | None:
    facts = plan_facts(plan, ruleset)
    return score(facts, ruleset) if facts is not None else None
