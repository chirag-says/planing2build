"""Topology families and their selection (Checkpoint 2; families added in Checkpoint 2.1).

A topology family is a way of arranging the programme's zones on the plot. Each family below
writes slicing trees (`layout_tree`) with an access plan: which room every room is entered from.
Zone roles come from ruleset data (the entry room, the front band, the room anchored to the entry
room, attached rooms, the zone of every room type); no family names a room type in code except
through those roles.

Families:

SPINE, FRONT_EXTENSION, SIDE_WING
    Front band (parking and the entry room, optionally one more room), a passage spine from the
    entry room, one or two columns of room groups beside it, optional rear room. SIDE_WING puts
    the public and service groups in one column and the private groups in the other.
FRONT_LIVING_REAR_BEDROOM
    Compact, no corridor: the entry room at the front, every other room entered from the entry or
    dining room. Two bands (everything behind the entry room in one row) or three (dining and
    kitchen, then at most two private rooms entered from the dining room).
FRONT_PUBLIC_REAR_PRIVATE
    Public band, dining and kitchen, a cross corridor entered from the dining room (or a short
    passage from the entry room), and the private rooms side by side behind it.
L_CIRCULATION
    A spine beside the dining and service rooms that turns into a rear cross corridor serving the
    private rooms.
CENTRAL_LIVING_BEDROOM_WINGS
    Entry room and dining room in the middle, a wing of rooms on each side entered from them; the
    kitchen at the rear of a wing beside the dining room; parking at the front of a wing.
LINEAR_REAR_CORRIDOR
    One row of rooms along the road, each with a front window, entered from a corridor behind the
    row; parking at one end, full depth. For wide, shallow plots.

Every family may leave an open rear strip (a yard) when the ruleset sets `open_space_min_mm` and
the plot is deep enough. Selection checks each family against sound lower bounds (minimum room
sizes plus the thinnest walls) and records why a family does not apply; the solver sizes the
rest. Enumeration is deterministic and bounded."""

from dataclasses import dataclass

from p2b.core.vocabulary import OpeningKind, RoomType, TopologyFamily, Zone
from p2b.houseplans.engine.fit import FitRule
from p2b.houseplans.engine.geom import ceil_div, ceil_to
from p2b.houseplans.engine.layout_tree import Leaf, Node, Part, xs, ys
from p2b.houseplans.engine.ruleset import RulesetContent
from p2b.houseplans.engine.solver import LayoutProblem, RoomDemand

F = TopologyFamily
SPINE_KEY_2 = "passage_2"
OPEN_REAR = "open_rear"
OPEN_CENTRE = "open_centre"
OPEN_SIDE = "open_side"
OPEN_SERVICE = "open_service"


@dataclass(frozen=True)
class Group:
    keys: tuple[str, ...]  # host first, then rooms reached only through it


@dataclass(frozen=True)
class AccessRule:
    """`room` is entered from one of `vias` (the first with a long enough shared wall)."""

    room: str
    vias: tuple[str, ...]
    kind: OpeningKind


@dataclass(frozen=True)
class Topology:
    family: TopologyFamily
    name: str
    tree: Node
    access: tuple[AccessRule, ...]
    passages: tuple[str, ...]  # circulation rooms the topology adds
    opens: tuple[str, ...]  # open (unbuilt) areas


@dataclass(frozen=True)
class Verdict:
    family: TopologyFamily
    applicable: bool
    candidates: int
    reason: str  # plain English; for an inapplicable family, why


@dataclass(frozen=True)
class Selection:
    topologies: tuple[Topology, ...]
    verdicts: tuple[Verdict, ...]


@dataclass(frozen=True)
class ZoningInputs:
    entry: RoomDemand
    parking: RoomDemand | None
    groups: tuple[Group, ...]  # every room outside the front band, grouped, in column order
    anchored: Group | None  # the group entered from the entry room (dining or kitchen chain)
    rooms: dict[str, RoomDemand]


def zoning_inputs(problem: LayoutProblem) -> ZoningInputs:
    z = problem.zoning
    rooms = {r.key: r for r in problem.rooms}
    entry = next(r for r in problem.rooms if r.room_type == z.entry_room)
    parking = rooms.get(problem.parking.key) if problem.parking else None
    front = set(z.front_band)
    column = [r for r in problem.rooms if r.room_type not in front]
    by_key = {r.key: r for r in column}
    hosts = {rel.room: rel.host for rel in problem.relations}
    deps: dict[str, list[str]] = {}
    for rel in problem.relations:
        if rel.host in by_key and rel.room in by_key:
            deps.setdefault(rel.host, []).append(rel.room)
    heads = [r for r in column if hosts.get(r.key) not in by_key]

    def chain(head: RoomDemand) -> Group:
        out, queue = [head.key], list(deps.get(head.key, []))
        while queue:
            key = queue.pop(0)
            out.append(key)
            queue.extend(deps.get(key, []))
        return Group(tuple(out))

    anchored = next((r for r in heads if hosts.get(r.key) == entry.key), None)
    if anchored is None:
        for room_type in z.anchored_to_entry:
            anchored = next((r for r in heads if r.room_type == room_type), None)
            if anchored is not None:
                break
    rank = {t: i for i, t in enumerate(z.column_order)}
    position = {r.key: i for i, r in enumerate(problem.rooms)}
    others = sorted(
        (r for r in heads if r is not anchored),
        key=lambda r: (rank.get(r.room_type, 10_000), position[r.key]),
    )
    return ZoningInputs(
        entry=entry,
        parking=parking,
        groups=tuple(chain(r) for r in others),
        anchored=chain(anchored) if anchored else None,
        rooms=rooms,
    )


def min_depth(room: RoomDemand, width: int, allowance: int, fit: FitRule | None) -> int:
    """A lower bound on a stacked room's depth at a column width (centreline mm): its minimums,
    and its fittings with the door on either a side wall or the front wall."""
    clear_w = max(1, width - allowance)
    need = max(room.min_short_mm, ceil_div(room.min_area_mm2, clear_w))
    if fit is not None:
        options = [x for x in (fit.min_along(clear_w), fit.min_across(clear_w)) if x is not None]
        need = max(need, min(options) if options else 10 * clear_w)
    return need + allowance


class Context:
    """What every family generator needs, and sound size lower bounds for selection."""

    def __init__(
        self,
        problem: LayoutProblem,
        ruleset: RulesetContent,
        fit: dict[RoomType, FitRule],
    ):
        self.p, self.rules, self.fit = problem, ruleset, fit
        self.inp = zoning_inputs(problem)
        self.a = problem.wall_allowance_mm
        self.g = problem.grid_mm
        self.sw = ceil_to(problem.passage_clear_mm + self.a, self.g)
        self.w, self.h = problem.region.w, problem.region.h
        self.spine = problem.passage_key
        thin = min(ruleset.walls.exterior_mm, ruleset.walls.interior_mm)
        self.wall_lb = 2 * ((thin + 1) // 2)
        self.open_min = ruleset.zoning.open_space_min_mm
        rel = {r.room: r for r in problem.relations}
        self.rel = rel
        self.entry = self.inp.entry.key
        chain = self.inp.anchored.keys if self.inp.anchored else ()
        types = {k: self.inp.rooms[k].room_type for k in chain}
        self.dining = next((k for k in chain if types[k] == RoomType.DINING), None)
        self.kitchen_chain = tuple(k for k in chain if k != self.dining)

    # ---------- sizes ----------

    def lb(self, key: str) -> int:
        """A lower bound on the room's centreline size in either direction."""
        room = self.inp.rooms[key]
        park = self.p.parking
        if park is not None and key == park.key:
            return min(park.clear_w_mm, park.clear_d_mm)
        core = room.min_short_mm
        fit = self.fit.get(room.room_type)
        if fit is not None:
            core = max(core, fit.short)
        return core + self.wall_lb

    def lb_w(self, key: str) -> int:
        park = self.p.parking
        return park.clear_w_mm if park is not None and key == park.key else self.lb(key)

    def lb_d(self, key: str) -> int:
        park = self.p.parking
        return park.clear_d_mm if park is not None and key == park.key else self.lb(key)

    def zone(self, key: str) -> Zone:
        return self.rules.rooms[self.inp.rooms[key].room_type].zone

    def private(self, group: Group) -> bool:
        return self.zone(group.keys[0]) == Zone.PRIVATE

    # ---------- shared pieces ----------

    def front_keys(self, parking_left: bool, extension: str | None) -> list[str]:
        park = self.inp.parking.key if self.inp.parking else None
        side = [k for k in (park, extension) if k is not None]
        return [*side, self.entry] if parking_left else [self.entry, *reversed(side)]

    def front(self, parking_left: bool, extension: str | None = None) -> Node:
        return xs(*[Leaf(k) for k in self.front_keys(parking_left, extension)])

    def front_lb(self, extension: str | None = None) -> tuple[int, int]:
        keys = self.front_keys(True, extension)
        return sum(self.lb_w(k) for k in keys), max(self.lb_d(k) for k in keys)

    def carport_court(self) -> bool:
        """Whether the parking is wide enough to leave an open court beside rooms behind it."""
        park = self.p.parking
        return (
            park is not None
            and self.open_min is not None
            and park.clear_w_mm >= self.open_min + min(self.lb(k) for k in self.inp.rooms)
        )

    def sides(self) -> tuple[bool, ...]:
        return (True, False) if self.inp.parking is not None else (True,)

    def group_rules(self, group: Group, vias: tuple[str, ...]) -> list[AccessRule]:
        """The head is entered from `vias` by a door; dependants from their hosts."""
        out = [AccessRule(group.keys[0], vias, OpeningKind.DOOR)]
        for key in group.keys[1:]:
            r = self.rel[key]
            out.append(AccessRule(key, (r.host,), r.access))
        return out

    def anchored_rules(self, via: str) -> list[AccessRule]:
        """The dining or kitchen chain: its head is entered from the entry room."""
        g = self.inp.anchored
        if g is None:
            return []
        r = self.rel.get(g.keys[0])
        kind = r.access if r is not None and r.host == self.entry else OpeningKind.VOID
        out = [AccessRule(g.keys[0], (via,), kind)]
        for key in g.keys[1:]:
            rr = self.rel[key]
            out.append(AccessRule(key, (rr.host,), rr.access))
        return out

    def kitchen_cell(self) -> Node | None:
        """Kitchen with the rooms reached through it stacked behind it."""
        if not self.kitchen_chain:
            return None
        return ys(*[Leaf(k) for k in self.kitchen_chain])

    def stack(self, group: Group, flipped: bool = False) -> Node:
        """The group front to back (host first), or `flipped`: its dependants in front."""
        keys = [*group.keys[1:], group.keys[0]] if flipped else list(group.keys)
        return ys(*[Leaf(k) for k in keys])

    def wet(self, key: str) -> bool:
        return self.rules.rooms[self.inp.rooms[key].room_type].wet

    def row_orders(self, groups: list[Group]) -> list[list[tuple[Group, bool]]]:
        """Orders for a row of groups, each with its pair orientation (`True`: the attached room
        on the left). Programme order; its mirror; and, where it differs, a wet-aware order:
        attached bathrooms turned towards each other with the common bathrooms between them,
        so the wet rooms share walls."""
        forward = [(g, False) for g in groups]
        mirror = [(g, True) for g in reversed(groups)]
        suites = [g for g in groups if len(g.keys) > 1 and self.wet(g.keys[-1])]
        wet_singles = [g for g in groups if len(g.keys) == 1 and self.wet(g.keys[0])]
        rest = [g for g in groups if g not in suites and g not in wet_singles]
        wet_order: list[tuple[Group, bool]] = []
        if suites:
            wet_order.append((suites[0], False))  # bedroom | bath ->
            wet_order += [(g, False) for g in wet_singles]
            wet_order += [(g, True) for g in suites[1:2]]  # <- bath | bedroom
            wet_order += [(g, False) for g in suites[2:]]
            wet_order += [(g, False) for g in rest]
        elif wet_singles and len(rest) > 1:
            half = len(rest) // 2
            wet_order = [(g, False) for g in rest[:half] + wet_singles + rest[half:]]
        orders = [forward, mirror]
        if wet_order and wet_order not in orders:
            orders.append(wet_order)
        return orders

    def stepped(
        self, parking_left: bool, behind_parking: Node, behind_entry: Node, court: bool = False
    ) -> Node:
        """A front that steps: the parking keeps its own depth with `behind_parking` behind it,
        the entry room its own with `behind_entry` behind it, so the living room is no longer
        as deep as the car. `court`: the rooms behind the parking keep to the house side and an
        open court takes the outer side, so a wide carport does not stretch them."""
        park = self.inp.parking.key if self.inp.parking else ""
        if court:
            behind_parking = (
                xs(Leaf(OPEN_SIDE), behind_parking)
                if parking_left
                else xs(behind_parking, Leaf(OPEN_SIDE))
            )
        side = ys(Leaf(park), behind_parking)
        main = ys(Leaf(self.entry), behind_entry)
        return xs(side, main) if parking_left else xs(main, side)

    def row(self, order: list[tuple[Group, bool]]) -> Node:
        return xs(*[self.pair(g, mirrored) for g, mirrored in order])

    def pair(self, group: Group, mirrored: bool = False) -> Node:
        keys = list(reversed(group.keys)) if mirrored else list(group.keys)
        return xs(*[Leaf(k) for k in keys])

    def stack_lb(self, group: Group) -> tuple[int, int]:
        return max(self.lb(k) for k in group.keys), sum(self.lb(k) for k in group.keys)

    def pair_lb(self, group: Group) -> tuple[int, int]:
        return sum(self.lb(k) for k in group.keys), max(self.lb(k) for k in group.keys)

    def with_open(self, node: Node, depth_lb: int) -> list[tuple[Node, tuple[str, ...], str]]:
        """The layout as it is, and with an open rear strip when the plot is deep enough."""
        out: list[tuple[Node, tuple[str, ...], str]] = [(node, (), "")]
        if self.open_min is not None and self.h - depth_lb >= self.open_min:
            out.append((ys(node, Leaf(OPEN_REAR)), (OPEN_REAR,), "_open"))
        return out


def m(mm: int) -> str:
    return f"{mm / 1000:.2f} m"


# ---------- SPINE, FRONT_EXTENSION, SIDE_WING ----------


def _splits(
    ctx: Context,
    groups: list[Group],
    entry_column: int,
    widths: tuple[int, int],
    keep: int,
) -> list[tuple[tuple[Group, ...], tuple[Group, ...]]]:
    """Every split of the groups over two columns (anchored group first in the entry column),
    ranked by (deepest column bound, imbalance, mask); splits that only exchange rooms of the same
    types are dropped; the best `keep` are returned."""
    inp = ctx.inp
    ranked = []
    for mask in range(2 ** len(groups)):
        cols: list[list[Group]] = [[], []]
        if inp.anchored:
            cols[entry_column].append(inp.anchored)
        for i, g in enumerate(groups):
            cols[(mask >> i) & 1].append(g)
        if not cols[0] or not cols[1]:
            continue
        depth = [
            sum(
                min_depth(inp.rooms[k], widths[c], ctx.a, ctx.fit.get(inp.rooms[k].room_type))
                for g in col
                for k in g.keys
            )
            for c, col in enumerate(cols)
        ]
        ranked.append(
            (max(depth), abs(depth[0] - depth[1]), mask, (tuple(cols[0]), tuple(cols[1])))
        )
    ranked.sort(key=lambda t: t[:3])
    out: list[tuple[tuple[Group, ...], tuple[Group, ...]]] = []
    seen: set[tuple[tuple[tuple[RoomType, ...], ...], ...]] = set()
    for *_, split in ranked:
        shape = tuple(
            tuple(tuple(inp.rooms[k].room_type for k in g.keys) for g in col) for col in split
        )
        if shape in seen:
            continue
        seen.add(shape)
        out.append(split)
        if len(out) == keep:
            break
    return out


def _spine_tree(
    ctx: Context,
    variant: str,
    parking_left: bool,
    extension: str | None,
    columns: tuple[tuple[Group, ...], ...],
) -> Node | None:
    cols = [ys(*[Leaf(k) for g in col for k in g.keys]) for col in columns]
    spine = Part(Leaf(ctx.spine), ctx.sw)
    if variant == "two":
        return ys(ctx.front(parking_left, extension), xs(cols[0], spine, cols[1]))
    if variant == "one":
        body = xs(cols[0], spine) if parking_left else xs(spine, cols[0])
        return ys(ctx.front(parking_left, extension), body)
    park = ctx.inp.parking.key if ctx.inp.parking else None
    side = [Leaf(k) for k in (park, extension) if k is not None]
    if not side:
        return None
    if parking_left:
        return xs(ys(xs(*side), cols[0]), ys(Leaf(ctx.entry), xs(spine, cols[1])))
    return xs(ys(Leaf(ctx.entry), xs(cols[0], spine)), ys(xs(*reversed(side)), cols[1]))


def spine_families(ctx: Context) -> tuple[list[Topology], list[Verdict]]:
    obj = ctx.rules.objective
    inp, z = ctx.inp, ctx.rules.zoning
    keep = obj.split_limit if obj else 4
    extensions: list[str | None] = [None]
    singles = [g for g in inp.groups if len(g.keys) == 1]
    for room_type in z.front_band_extension:  # one of each permitted type, the last in order
        match = [g.keys[0] for g in singles if inp.rooms[g.keys[0]].room_type == room_type]
        if match:
            extensions.append(match[-1])
    rears: list[str | None] = [None]
    for room_type in z.rear_band:
        match = [g.keys[0] for g in singles if inp.rooms[g.keys[0]].room_type == room_type]
        if match:
            rears.append(match[-1])

    out: list[Topology] = []
    counts = {F.SPINE: 0, F.FRONT_EXTENSION: 0, F.SIDE_WING: 0}
    for extension in extensions:
        for rear in rears:
            if rear is not None and rear == extension:
                continue
            rest = [g for g in inp.groups if g.keys[0] not in (extension, rear)]
            zoned = (
                tuple(g for g in rest if not ctx.private(g)),
                tuple(g for g in rest if ctx.private(g)),
            )
            for parking_left in ctx.sides():
                if inp.parking is None and extension is None and not parking_left:
                    continue
                tag = f"{'pL' if parking_left else 'pR'}" + (f"_x_{extension}" if extension else "")
                tag += f"_rear_{rear}" if rear else ""
                entry_col = 1 if parking_left else 0
                half_width = (ctx.w - ctx.sw) // 2
                plans: list[tuple[TopologyFamily, str, tuple[tuple[Group, ...], ...], str]] = []
                for variant in ("two", "stepped"):
                    family = F.SPINE if extension is None else F.FRONT_EXTENSION
                    splits = _splits(ctx, rest, entry_col, (half_width, half_width), keep)
                    for k, split in enumerate(splits):
                        plans.append((family, variant, split, f"s{k}"))
                    # SIDE_WING: public and service groups in the entry column, private groups in
                    # the other, whatever the depth balance.
                    if extension is None and zoned[0] and zoned[1] and inp.anchored is not None:
                        cols: list[tuple[Group, ...]] = [(), ()]
                        cols[entry_col] = (inp.anchored, *zoned[0])
                        cols[1 - entry_col] = zoned[1]
                        plans.append((F.SIDE_WING, variant, (cols[0], cols[1]), "z"))
                single = (*([inp.anchored] if inp.anchored else []), *rest)
                if single:
                    family = F.SPINE if extension is None else F.FRONT_EXTENSION
                    plans.append((family, "one", (tuple(single),), ""))
                for family, variant, columns, suffix in plans:
                    tree = _spine_tree(ctx, variant, parking_left, extension, columns)
                    if tree is None:
                        continue
                    if rear is not None:
                        tree = ys(tree, Leaf(rear))
                    access = [AccessRule(ctx.spine, (ctx.entry,), OpeningKind.VOID)]
                    entry_column = columns[0] if variant == "one" else columns[entry_col]
                    for col in columns:
                        for g in col:
                            if (
                                inp.anchored is not None
                                and g == inp.anchored
                                and col is entry_column
                            ):
                                access += ctx.anchored_rules(ctx.entry)
                            else:
                                access += ctx.group_rules(g, (ctx.spine,))
                    if extension is not None:
                        kind = (
                            OpeningKind.VOID
                            if inp.rooms[extension].room_type in z.anchored_to_entry
                            else OpeningKind.DOOR
                        )
                        access.append(AccessRule(extension, (ctx.entry,), kind))
                    if rear is not None:
                        access.append(AccessRule(rear, (ctx.spine,), OpeningKind.DOOR))
                    base = f"{family.value}_{variant}_{tag}" + (f"_{suffix}" if suffix else "")
                    depth_lb = ctx.front_lb(extension)[1] + max(
                        sum(ctx.lb(k) for g in col for k in g.keys) for col in columns
                    )
                    for node, opens, open_tag in ctx.with_open(tree, depth_lb):
                        out.append(
                            Topology(
                                family,
                                base + open_tag,
                                node,
                                tuple(access),
                                (ctx.spine,),
                                opens,
                            )
                        )
                        counts[family] += 1
    verdicts = [
        Verdict(F.SPINE, counts[F.SPINE] > 0, counts[F.SPINE], "always applicable"),
        Verdict(
            F.FRONT_EXTENSION,
            counts[F.FRONT_EXTENSION] > 0,
            counts[F.FRONT_EXTENSION],
            "a room may join the front band"
            if counts[F.FRONT_EXTENSION]
            else "no room type the ruleset lets join the front band",
        ),
        Verdict(
            F.SIDE_WING,
            counts[F.SIDE_WING] > 0,
            counts[F.SIDE_WING],
            "public and service rooms can take one column, private rooms the other"
            if counts[F.SIDE_WING]
            else "needs both private rooms and public or service rooms behind the front band",
        ),
    ]
    return out, verdicts


# ---------- FRONT_LIVING_REAR_BEDROOM ----------


def hub_family(ctx: Context) -> tuple[list[Topology], Verdict]:
    family = F.FRONT_LIVING_REAR_BEDROOM
    others = list(ctx.inp.groups)
    hubs = (ctx.entry, ctx.dining) if ctx.dining else (ctx.entry,)
    kitchen = list(ctx.kitchen_chain)
    out: list[Topology] = []
    _, front_d = ctx.front_lb()
    reasons = []

    # Two bands: every room behind the entry room in one row, each touching the rear boundary.
    block_keys = [*([ctx.dining] if ctx.dining else []), *kitchen]
    row_w = sum(ctx.lb(k) for k in block_keys) + sum(ctx.pair_lb(g)[0] for g in others)
    row_d = max([ctx.lb(k) for k in block_keys] + [ctx.pair_lb(g)[1] for g in others])
    if row_w > ctx.w:
        reasons.append(
            f"one row behind the living room needs {m(row_w)} of width; the plot has {m(ctx.w)}"
        )
    elif front_d + row_d > ctx.h:
        reasons.append(f"two bands need {m(front_d + row_d)} of depth; the plot has {m(ctx.h)}")
    else:
        blocks = [block_keys, list(reversed(block_keys))] if len(block_keys) > 1 else [block_keys]
        for parking_left in ctx.sides():
            for b, block in enumerate(blocks):
                for pos in range(len(others) + 1):
                    cells: list[Node] = [ctx.pair(g) for g in others[:pos]]
                    cells += [Leaf(k) for k in block]
                    cells += [ctx.pair(g) for g in others[pos:]]
                    tree = ys(ctx.front(parking_left), xs(*cells))
                    access = ctx.anchored_rules(ctx.entry)
                    for g in others:
                        access += ctx.group_rules(g, hubs)
                    name = f"{family.value}_2band_{'pL' if parking_left else 'pR'}_b{b}_at{pos}"
                    for node, opens, tag in ctx.with_open(tree, front_d + row_d):
                        out.append(Topology(family, name + tag, node, tuple(access), (), opens))

    # Three bands: dining and kitchen, then at most two rooms entered from the dining room.
    if ctx.dining is None:
        reasons.append("three bands need a separate dining room")
    elif len(others) > 2:
        reasons.append("three bands hold at most two rooms behind the dining room")
    else:
        kcell = ctx.kitchen_cell()
        mid_w = ctx.lb(ctx.dining) + max([ctx.lb(k) for k in kitchen] or [0])
        mid_d = max([ctx.lb(ctx.dining), sum(ctx.lb(k) for k in kitchen)])
        rear_w = sum(ctx.stack_lb(g)[0] for g in others)
        rear_d = max([ctx.stack_lb(g)[1] for g in others] or [0])
        if max(mid_w, rear_w) > ctx.w or front_d + mid_d + rear_d > ctx.h:
            reasons.append(
                f"three bands need {m(front_d + mid_d + rear_d)} of depth and "
                f"{m(max(mid_w, rear_w))} of width"
            )
        else:
            mids = (
                [xs(Leaf(ctx.dining), kcell), xs(kcell, Leaf(ctx.dining))]
                if kcell
                else [Leaf(ctx.dining)]
            )
            orders = [others, list(reversed(others))] if len(others) > 1 else [others]
            for parking_left in ctx.sides():
                for mi, mid in enumerate(mids):
                    for oi, order in enumerate(orders):
                        bands = [ctx.front(parking_left), mid]
                        if order:
                            bands.append(xs(*[ctx.stack(g) for g in order]))
                        tree = ys(*bands)
                        access = ctx.anchored_rules(ctx.entry)
                        for g in order:
                            access += ctx.group_rules(g, (ctx.dining,))
                        name = f"{family.value}_3band_{'pL' if parking_left else 'pR'}_m{mi}_o{oi}"
                        for node, opens, tag in ctx.with_open(tree, front_d + mid_d + rear_d):
                            out.append(Topology(family, name + tag, node, tuple(access), (), opens))
                        if mi == 0 and kcell is not None and ctx.inp.parking is not None:
                            # stepped: the kitchen behind the parking, the dining room behind
                            # the living room, the private rooms across the rear
                            for court in (False, True) if ctx.carport_court() else (False,):
                                top = ctx.stepped(parking_left, kcell, Leaf(ctx.dining), court)
                                tree = ys(top, xs(*[ctx.stack(g) for g in order])) if order else top
                                name = (
                                    f"{family.value}_3band_stepped{'_court' if court else ''}"
                                    f"_{'pL' if parking_left else 'pR'}_o{oi}"
                                )
                                court_open: tuple[str, ...] = (OPEN_SIDE,) if court else ()
                                for node, opens, tag in ctx.with_open(
                                    tree, front_d + mid_d + rear_d
                                ):
                                    out.append(
                                        Topology(
                                            family,
                                            name + tag,
                                            node,
                                            tuple(access),
                                            (),
                                            court_open + opens,
                                        )
                                    )
    reason = "; ".join(reasons) if not out else "compact layouts without a corridor fit"
    return out, Verdict(family, bool(out), len(out), reason)


# ---------- FRONT_PUBLIC_REAR_PRIVATE ----------


def transverse_family(ctx: Context) -> tuple[list[Topology], Verdict]:
    family = F.FRONT_PUBLIC_REAR_PRIVATE
    corridor = Part(Leaf(ctx.spine), ctx.sw)
    kcell = ctx.kitchen_cell()
    kitchen = list(ctx.kitchen_chain)
    extensions: list[str | None] = [None]
    lone_bedrooms = [g for g in ctx.inp.groups if len(g.keys) == 1 and ctx.private(g)]
    if lone_bedrooms and RoomType.BEDROOM in ctx.rules.zoning.front_band_extension:
        extensions.append(lone_bedrooms[-1].keys[0])
    out: list[Topology] = []
    reasons: list[str] = []
    for extension in extensions:
        private = [g for g in ctx.inp.groups if g.keys[0] != extension]
        if not private:
            reasons.append("no private rooms for a rear band")
            continue
        private_w = sum(ctx.pair_lb(g)[0] for g in private)
        private_d = max(ctx.pair_lb(g)[1] for g in private)
        front_w, front_d = ctx.front_lb(extension)
        if ctx.dining is not None:
            mid_w = ctx.lb(ctx.dining) + max([ctx.lb(k) for k in kitchen] or [0])
            mid_d = max(ctx.lb(ctx.dining), sum(ctx.lb(k) for k in kitchen))
        else:
            mid_w = ctx.sw + max([ctx.lb(k) for k in kitchen] or [0])
            mid_d = sum(ctx.lb(k) for k in kitchen) if kitchen else ctx.lb(ctx.entry)
        depth = front_d + mid_d + ctx.sw + private_d
        label = f" with {extension} in the front band" if extension else ""
        if max(private_w, mid_w, front_w) > ctx.w:
            reasons.append(
                f"the private rooms side by side{label} need {m(private_w)} of width; "
                f"the plot has {m(ctx.w)}"
            )
            continue
        if depth > ctx.h:
            reasons.append(f"four bands{label} need {m(depth)} of depth; the plot has {m(ctx.h)}")
            continue
        if ctx.dining is not None:
            mids = (
                [xs(Leaf(ctx.dining), kcell), xs(kcell, Leaf(ctx.dining))]
                if kcell
                else [Leaf(ctx.dining)]
            )
            corridor_via = ctx.dining
            passages: tuple[str, ...] = (ctx.spine,)
        elif kcell is not None:
            stub = Part(Leaf(SPINE_KEY_2), ctx.sw)
            mids = [xs(kcell, stub), xs(stub, kcell)]
            corridor_via = SPINE_KEY_2
            passages = (ctx.spine, SPINE_KEY_2)
        else:
            reasons.append("needs a dining room or a kitchen between the bands")
            continue
        # stepped: the kitchen behind the parking, the dining room behind the living room
        stepped = (
            ctx.dining is not None
            and kcell is not None
            and extension is None
            and ctx.inp.parking is not None
        )
        tops: list[tuple[int, Node | None]] = list(enumerate(mids))
        if stepped:
            tops.append((-1, None))  # stepped
            if ctx.carport_court():
                tops.append((-2, None))  # stepped, with a court beside the kitchen
        for parking_left in ctx.sides():
            for mi, mid in tops:
                for oi, order in enumerate(ctx.row_orders(private)):
                    rear = ctx.row(order)
                    if mid is not None:
                        tree = ys(ctx.front(parking_left, extension), mid, corridor, rear)
                    elif kcell is not None and ctx.dining is not None:  # stepped
                        top = ctx.stepped(parking_left, kcell, Leaf(ctx.dining), court=mi == -2)
                        tree = ys(top, corridor, rear)
                    else:
                        continue
                    access = ctx.anchored_rules(ctx.entry)
                    access.append(AccessRule(ctx.spine, (corridor_via,), OpeningKind.VOID))
                    if SPINE_KEY_2 in passages:
                        access.append(AccessRule(SPINE_KEY_2, (ctx.entry,), OpeningKind.VOID))
                    for g in private:
                        access += ctx.group_rules(g, (ctx.spine,))
                    if extension is not None:
                        access.append(AccessRule(extension, (ctx.entry,), OpeningKind.DOOR))
                    name = (
                        f"{family.value}_{'pL' if parking_left else 'pR'}"
                        + ({-1: "_stepped", -2: "_stepped_court"}.get(mi, f"_m{mi}"))
                        + f"_o{oi}"
                        + (f"_x_{extension}" if extension else "")
                    )
                    court_open: tuple[str, ...] = (OPEN_SIDE,) if mi == -2 else ()
                    for node, opens, tag in ctx.with_open(tree, depth):
                        out.append(
                            Topology(
                                family,
                                name + tag,
                                node,
                                tuple(access),
                                passages,
                                court_open + opens,
                            )
                        )
    reason = (
        "; ".join(dict.fromkeys(reasons))
        if not out
        else "a cross corridor and a rear private band fit"
    )
    return out, Verdict(family, bool(out), len(out), reason)


# ---------- L_CIRCULATION ----------


def l_family(ctx: Context) -> tuple[list[Topology], Verdict]:
    family = F.L_CIRCULATION
    inp = ctx.inp
    corridor = Part(Leaf(SPINE_KEY_2), ctx.sw)
    spine = Part(Leaf(ctx.spine), ctx.sw)
    service = [g for g in inp.groups if not ctx.private(g)]
    private = [g for g in inp.groups if ctx.private(g)]
    out: list[Topology] = []
    reasons: list[str] = []
    if inp.anchored is None or not private:
        reason = "needs a dining or kitchen column and private rooms for the rear band"
        return out, Verdict(family, False, 0, reason)
    # Private rooms that do not fit side by side move to the service column, last first.
    side = list(service)
    while private and sum(ctx.pair_lb(g)[0] for g in private) > ctx.w:
        side.append(private.pop())
    if not private:
        return out, Verdict(
            family, False, 0, "the private rooms do not fit side by side across the plot"
        )
    col_a = ys(*[Leaf(k) for k in inp.anchored.keys])
    col_b = ys(*[Leaf(k) for g in side for k in g.keys]) if side else None
    a_w = max(ctx.lb(k) for k in inp.anchored.keys)
    b_w = max([ctx.lb(k) for g in side for k in g.keys] or [0])
    a_d = sum(ctx.lb(k) for k in inp.anchored.keys)
    b_d = sum(ctx.lb(k) for g in side for k in g.keys)
    _, front_d = ctx.front_lb()
    private_d = max(ctx.pair_lb(g)[1] for g in private)
    depth = front_d + max(a_d, b_d) + ctx.sw + private_d
    width = a_w + ctx.sw + b_w
    if width > ctx.w or depth > ctx.h:
        reasons.append(f"needs {m(width)} by {m(depth)}; the plot has {m(ctx.w)} by {m(ctx.h)}")
        return out, Verdict(family, False, 0, "; ".join(reasons))
    for parking_left in ctx.sides():
        tops: list[tuple[str, Node, tuple[str, ...]]] = []
        for a_left in (True, False):
            if col_b is None:
                body = xs(col_a, spine) if a_left else xs(spine, col_a)
            else:
                body = xs(col_a, spine, col_b) if a_left else xs(col_b, spine, col_a)
            tops.append(("aL" if a_left else "aR", ys(ctx.front(parking_left), body), ()))
        if inp.parking is not None:
            # stepped: the side column (or an open court) behind the parking; the spine and the
            # dining column behind the living room, the dining room touching it
            behind = col_b if col_b is not None else Leaf(OPEN_SIDE)
            main = xs(spine, col_a) if parking_left else xs(col_a, spine)
            court = () if col_b is not None else (OPEN_SIDE,)
            tops.append(("stepped", ctx.stepped(parking_left, behind, main), court))
            if col_b is not None and ctx.carport_court():
                stepped_court = ctx.stepped(parking_left, col_b, main, court=True)
                tops.append(("stepped_court", stepped_court, (OPEN_SIDE,)))
        for top_name, top, top_opens in tops:
            for oi, order in enumerate(ctx.row_orders(private)):
                rear = ctx.row(order)
                tree = ys(top, corridor, rear)
                access = [AccessRule(ctx.spine, (ctx.entry,), OpeningKind.VOID)]
                access += ctx.anchored_rules(ctx.entry)
                access.append(AccessRule(SPINE_KEY_2, (ctx.spine,), OpeningKind.VOID))
                for g in side:
                    access += ctx.group_rules(g, (ctx.spine,))
                for g in private:
                    access += ctx.group_rules(g, (SPINE_KEY_2,))
                name = f"{family.value}_{'pL' if parking_left else 'pR'}_{top_name}_o{oi}"
                for node, opens, tag in ctx.with_open(tree, depth):
                    passages = (ctx.spine, SPINE_KEY_2)
                    out.append(
                        Topology(
                            family, name + tag, node, tuple(access), passages, top_opens + opens
                        )
                    )
    return out, Verdict(family, True, len(out), "a spine turning into a rear corridor fits")


# ---------- CENTRAL_LIVING_BEDROOM_WINGS ----------


def wings_family(ctx: Context) -> tuple[list[Topology], Verdict]:
    """Living and dining in the centre, room wings either side. Variants per wing split:

    plain     wing rooms entered from the living or dining room beside them; the kitchen at the
              rear of a wing, beside the dining room;
    gallery   the wing without parking gets a corridor along the centre, entered from the living
              or dining room, so a deep wing's rooms are all reached;
    court     the centre is living, dining and kitchen, then an open court; the wing without
              parking keeps its gallery along the court.

    Each may also leave an open rear strip across the plot."""
    family = F.CENTRAL_LIVING_BEDROOM_WINGS
    inp = ctx.inp
    if ctx.dining is None:
        return [], Verdict(
            family, False, 0, "needs a dining room behind the living room in the centre"
        )
    others = list(inp.groups)
    kcell = ctx.kitchen_cell()
    kitchen = list(ctx.kitchen_chain)
    park = inp.parking.key if inp.parking else None
    centre_w = max(ctx.lb(ctx.entry), ctx.lb(ctx.dining))
    centre_d = ctx.lb(ctx.entry) + ctx.lb(ctx.dining)
    hubs = (ctx.entry, ctx.dining)
    out: list[Topology] = []
    best_reason = ""
    for park_left in ctx.sides() if park else (True,):
        for kitchen_left in (True, False) if kcell else (True,):
            # the groups split between the wings, in order; balanced splits first
            splits = []
            for k in range(len(others) + 1):
                left, right = others[:k], others[k:]
                wings = []
                for is_left, groups in ((True, left), (False, right)):
                    keys = [k2 for g in groups for k2 in g.keys]
                    if park and park_left == is_left:
                        keys = [park, *keys]
                    if kcell and kitchen_left == is_left:
                        keys = [*keys, *kitchen]
                    wings.append(keys)
                if not wings[0] or not wings[1]:
                    continue
                wd = [sum(ctx.lb_d(x) for x in w) for w in wings]
                ww = [max(ctx.lb_w(x) for x in w) for w in wings]
                if ww[0] + centre_w + ww[1] > ctx.w:
                    best_reason = (
                        f"two wings and the centre need {m(ww[0] + centre_w + ww[1])} of width"
                    )
                    continue
                if max(wd) > ctx.h or centre_d > ctx.h:
                    best_reason = f"a wing needs {m(max(wd))} of depth; the plot has {m(ctx.h)}"
                    continue
                splits.append((max(wd), abs(wd[0] - wd[1]), k, wings, ww))
            splits.sort(key=lambda t: t[:3])
            for _, _, k, wings, ww in splits[:2]:
                left, right = others[:k], others[k:]
                gallery_left = not park_left if park else ww[0] >= ww[1]
                depth_lb = max(sum(ctx.lb_d(x) for x in w) for w in wings)
                tag0 = f"{family.value}_{'pL' if park_left else 'pR'}_s{k}"

                def wing(
                    groups: list[Group],
                    is_left: bool,
                    with_kitchen: bool,
                    gallery: bool,
                    park_left: bool = park_left,
                    wet: bool = False,
                ) -> Node:
                    nodes: list[Node] = []
                    if park and park_left == is_left:
                        nodes.append(Leaf(park))
                    # `wet`: every second suite turned round, so bathrooms meet bathrooms
                    suites = 0
                    for g in groups:
                        flip = wet and len(g.keys) > 1 and suites % 2 == 1
                        suites += len(g.keys) > 1
                        nodes.append(ctx.stack(g, flipped=flip))
                    if with_kitchen and kcell is not None:
                        nodes.append(kcell)
                    stack = ys(*nodes)
                    if not gallery:
                        return stack
                    corridor = Part(Leaf(ctx.spine), ctx.sw)
                    return xs(stack, corridor) if is_left else xs(corridor, stack)

                def rules(gallery_wing: list[Group] | None) -> list[AccessRule]:
                    access = ctx.anchored_rules(ctx.entry)
                    if gallery_wing is not None:
                        access.append(AccessRule(ctx.spine, hubs, OpeningKind.VOID))
                    for g in others:
                        in_gallery = gallery_wing is not None and g in gallery_wing
                        access += ctx.group_rules(g, (ctx.spine,) if in_gallery else hubs)
                    return access

                gallery_groups = left if gallery_left else right
                plain_centre = ys(Leaf(ctx.entry), Leaf(ctx.dining))
                designs: list[
                    tuple[str, Node, list[AccessRule], tuple[str, ...], tuple[str, ...]]
                ] = []
                for gallery in (False, True):
                    tree = xs(
                        wing(left, True, kitchen_left, gallery and gallery_left),
                        plain_centre,
                        wing(right, False, not kitchen_left, gallery and not gallery_left),
                    )
                    name = f"{tag0}_{'kL' if kitchen_left else 'kR'}" + (
                        "_gallery" if gallery else ""
                    )
                    passages: tuple[str, ...] = (ctx.spine,) if gallery else ()
                    designs.append(
                        (name, tree, rules(gallery_groups if gallery else None), passages, ())
                    )
                tree = xs(
                    wing(left, True, kitchen_left, False, wet=True),
                    plain_centre,
                    wing(right, False, not kitchen_left, False, wet=True),
                )
                if tree != designs[0][1]:
                    name = f"{tag0}_{'kL' if kitchen_left else 'kR'}_wet"
                    designs.append((name, tree, rules(None), (), ()))
                for name, tree, access, passages, centre_opens in designs:
                    # and with a rear yard across the plot, when it is deep enough
                    for node, opens, yard in ctx.with_open(tree, max(depth_lb, centre_d)):
                        out.append(
                            Topology(
                                family,
                                name + yard,
                                node,
                                tuple(access),
                                passages,
                                centre_opens + opens,
                            )
                        )
    out += _courtyard(ctx, others, kcell, kitchen, park, centre_w, hubs)
    reason = (
        "living and dining in the centre with room wings fit"
        if out
        else (best_reason or "no wing split fits")
    )
    return out, Verdict(family, bool(out), len(out), reason)


def _courtyard(
    ctx: Context,
    others: list[Group],
    kcell: Node | None,
    kitchen: list[str],
    park: str | None,
    centre_w: int,
    hubs: tuple[str, ...],
) -> list[Topology]:
    """The courtyard variant of the wings family: parking with the kitchen (and the rooms
    reached through it) directly behind it on one side; living, dining and an open court in the
    centre, the dining room looking onto the court; the bedroom suites along a gallery on the
    other side, entered from the living or dining room; optionally a rear yard. The dining room
    and the kitchen keep their outside walls (the court and the side), and leftover depth becomes
    the court, not a longer hall."""
    family = F.CENTRAL_LIVING_BEDROOM_WINGS
    if kcell is None or ctx.dining is None or ctx.open_min is None:
        return []
    out: list[Topology] = []
    gallery_w = ctx.sw
    service_keys = ([park] if park else []) + kitchen
    service_w = max(ctx.lb_w(k) for k in service_keys)
    for park_left in ctx.sides() if park else (True,):
        for k, court in [
            (k, c) for k in (0, 1) for c in ((False, True) if ctx.carport_court() else (False,))
        ]:
            # k: private groups that stay on the service side, behind the kitchen; court: an open
            # court beside the kitchen, so a wide carport does not stretch it
            near, far = others[:k], others[k:]
            if not far:
                continue
            far_w = max(ctx.lb(x) for g in far for x in g.keys) + gallery_w
            if service_w + centre_w + far_w > ctx.w:
                continue
            behind = ys(*[Leaf(x) for x in kitchen], *[ctx.stack(g) for g in near])
            if court and park:
                behind = xs(Leaf(OPEN_SIDE), behind) if park_left else xs(behind, Leaf(OPEN_SIDE))
            service = ys(
                *([Leaf(park)] if park else []),
                behind,
                Leaf(OPEN_SERVICE),  # a service yard: the kitchen stays beside the dining room
            )
            stacks = ys(
                *[ctx.stack(g, flipped=i % 2 == 1 and len(g.keys) > 1) for i, g in enumerate(far)]
            )
            corridor = Part(Leaf(ctx.spine), gallery_w)
            centre = ys(Leaf(ctx.entry), Leaf(ctx.dining), Leaf(OPEN_CENTRE))
            if park_left:
                tree = xs(service, centre, corridor, stacks)
            else:
                tree = xs(stacks, corridor, centre, service)
            access = ctx.anchored_rules(ctx.entry)
            access.append(AccessRule(ctx.spine, hubs, OpeningKind.VOID))
            for g in near:
                access += ctx.group_rules(g, hubs)
            for g in far:
                access += ctx.group_rules(g, (ctx.spine,))
            depth_lb = max(
                sum(ctx.lb_d(x) for x in service_keys),
                sum(ctx.lb(x) for g in far for x in g.keys),
            )
            name = f"{family.value}_{'pL' if park_left else 'pR'}_court_n{k}" + (
                "_side" if court else ""
            )
            for node, opens, yard in ctx.with_open(tree, depth_lb):
                out.append(
                    Topology(
                        family,
                        name + yard,
                        node,
                        tuple(access),
                        (ctx.spine,),
                        (OPEN_CENTRE, OPEN_SERVICE, *((OPEN_SIDE,) if court else ()), *opens),
                    )
                )
    return out


# ---------- LINEAR_REAR_CORRIDOR ----------


def linear_family(ctx: Context) -> tuple[list[Topology], Verdict]:
    """One row of rooms along the road, every room with a front window, entered from a corridor
    behind the row; parking takes the full depth at one end. For wide, shallow plots."""
    family = F.LINEAR_REAR_CORRIDOR
    inp = ctx.inp
    corridor = Part(Leaf(ctx.spine), ctx.sw)
    public = [*([ctx.dining] if ctx.dining else []), *ctx.kitchen_chain]
    others = list(inp.groups)
    cells_w = ctx.lb_w(ctx.entry) + sum(ctx.lb(k) for k in public)
    cells_w += sum(ctx.pair_lb(g)[0] for g in others)
    park = inp.parking.key if inp.parking else None
    width = cells_w + (ctx.lb_w(park) if park else 0)
    row_d = max(
        [ctx.lb(ctx.entry)] + [ctx.lb(k) for k in public] + [ctx.pair_lb(g)[1] for g in others]
    )
    depth = max(row_d + ctx.sw, ctx.lb_d(park) if park else 0)
    if width > ctx.w:
        reason = f"one row of every room needs {m(width)} of width; the plot has {m(ctx.w)}"
        return [], Verdict(family, False, 0, reason)
    if depth > ctx.h:
        return [], Verdict(family, False, 0, f"a row and its corridor need {m(depth)} of depth")
    out: list[Topology] = []
    for parking_left in ctx.sides():
        for private_first in (False, True):
            keys: list[Node] = [Leaf(ctx.entry)]
            public_cells: list[Node] = [Leaf(k) for k in public]
            private_cells: list[Node] = [ctx.pair(g) for g in others]
            keys += private_cells + public_cells if private_first else public_cells + private_cells
            row = keys if parking_left else list(reversed(keys))
            blocks: list[tuple[Node, tuple[str, ...], str]] = [(ys(xs(*row), corridor), (), "")]
            if ctx.open_min is not None and ctx.h - row_d - ctx.sw >= ctx.open_min:
                # a yard behind the row and its corridor only: the row is no longer as deep as
                # the car beside it
                yard = ys(xs(*row), corridor, Leaf(OPEN_REAR))
                blocks.append((yard, (OPEN_REAR,), "_yard"))
            access = [AccessRule(ctx.spine, (ctx.entry,), OpeningKind.VOID)]
            access += ctx.anchored_rules(ctx.entry)
            for g in others:
                access += ctx.group_rules(g, (ctx.spine,))
            side = "pL" if parking_left else "pR"
            name = f"{family.value}_{side}_{'priv' if private_first else 'pub'}"
            for block, opens, tag in blocks:
                if park:
                    tree = xs(Leaf(park), block) if parking_left else xs(block, Leaf(park))
                else:
                    tree = block
                out.append(Topology(family, name + tag, tree, tuple(access), (ctx.spine,), opens))
    return out, Verdict(family, True, len(out), "one row of rooms with a corridor behind fits")


def select(
    problem: LayoutProblem, ruleset: RulesetContent, fit: dict[RoomType, FitRule]
) -> Selection:
    """Every applicable family's candidate topologies, in a fixed order, and a verdict per
    family."""
    ctx = Context(problem, ruleset, fit)
    topologies, verdicts = spine_families(ctx)
    for generator in (hub_family, transverse_family, l_family, wings_family, linear_family):
        tops, verdict = generator(ctx)
        topologies += tops
        verdicts.append(verdict)
    # The same tree and access plan can arise in two families (a zoned split that is also the
    # best-balanced one): keep the first.
    seen: set[tuple[Node, tuple[AccessRule, ...], tuple[str, ...]]] = set()
    unique = []
    for t in topologies:
        key = (t.tree, t.access, t.opens)
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return Selection(tuple(unique), tuple(verdicts))
