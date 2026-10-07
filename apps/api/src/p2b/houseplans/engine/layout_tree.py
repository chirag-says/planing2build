"""Slicing layouts (Checkpoint 2.1): the one geometry engine behind every topology family.

A layout is a tree. The root is the wall-centreline region; a split divides a rectangle along x
(parts left to right) or y (parts from the road backwards); a leaf is a room, a circulation room
or an open (unbuilt) area. Every topology family is a way of writing such a tree, so the solver,
the compiler and the Scorer never depend on which family produced a layout.

Variables are absolute cut positions (mm, region frame): one per boundary between consecutive
parts, except where a part has a fixed size (a passage of the ruleset's width). The last part of
a split takes the rest. Moving one variable therefore moves one cut line and resizes only the two
rooms (or room groups) beside it; deeper cuts keep their absolute positions."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from p2b.houseplans.engine.geom import ceil_to

Axis = Literal["x", "y"]
Coords = tuple[int, int, int, int]  # x0, y0, x1, y1


@dataclass(frozen=True)
class Leaf:
    key: str


@dataclass(frozen=True)
class Part:
    node: "Node"
    fixed_mm: int | None = None  # a fixed centreline size; None: a cut variable (or the rest)


@dataclass(frozen=True)
class Split:
    axis: Axis
    parts: tuple[Part, ...]


Node = Leaf | Split


def _part(item: "Node | Part") -> Part:
    return item if isinstance(item, Part) else Part(item)


def _split(axis: Axis, items: tuple["Node | Part", ...]) -> Node:
    """A split; a flexible part that is itself a split along the same axis is spliced in (the
    same rectangles, but its cut lines join this split's, so the search can move them together);
    a single flexible part is returned as itself."""
    parts: list[Part] = []
    for item in items:
        part = _part(item)
        if part.fixed_mm is None and isinstance(part.node, Split) and part.node.axis == axis:
            parts.extend(part.node.parts)
        else:
            parts.append(part)
    if len(parts) == 1 and parts[0].fixed_mm is None:
        return parts[0].node
    return Split(axis, tuple(parts))


def xs(*items: "Node | Part") -> Node:
    """Parts left to right."""
    return _split("x", items)


def ys(*items: "Node | Part") -> Node:
    """Parts from the road backwards."""
    return _split("y", items)


def leaves(node: Node) -> list[str]:
    if isinstance(node, Leaf):
        return [node.key]
    return [k for p in node.parts for k in leaves(p.node)]


@dataclass(frozen=True)
class Program:
    """The tree compiled for fast evaluation: splits in parent-before-child order. Each child is
    (slot, variable or -1, fixed size or 0, tail or -1): a variable part ends at its cut; a fixed
    part ends `fixed` after its start; the one flexible part without a variable (the rest) ends
    `tail` before the split's end, `tail` being the fixed parts after it."""

    slots: int
    ops: tuple[tuple[int, bool, tuple[tuple[int, int, int, int], ...]], ...]
    leaf_slot: dict[str, int]
    var_axis: tuple[Axis, ...]
    var_names: tuple[str, ...]
    # consecutive cut variables of one split (fixed parts between them move with them): moving
    # both by the same step shifts everything between, keeping its size
    siblings: tuple[tuple[int, int], ...]


def compile_tree(root: Node) -> Program:
    ops: list[tuple[int, bool, tuple[tuple[int, int, int, int], ...]]] = []
    leaf_slot: dict[str, int] = {}
    var_axis: list[Axis] = []
    var_names: list[str] = []
    siblings: list[tuple[int, int]] = []
    count = 1

    def visit(node: Node, slot: int) -> None:
        nonlocal count
        if isinstance(node, Leaf):
            leaf_slot[node.key] = slot
            return
        flexible = [i for i, p in enumerate(node.parts) if p.fixed_mm is None]
        if not flexible:
            raise ValueError("a split needs a part without a fixed size")
        rest = flexible[-1]
        tail = sum(p.fixed_mm or 0 for p in node.parts[rest + 1 :])
        children: list[tuple[int, int, int, int]] = []
        previous_var = -1
        for i, part in enumerate(node.parts):
            child = count
            count += 1
            if part.fixed_mm is not None:
                # a fixed part (a corridor) rides along when the cuts either side move together
                children.append((child, -1, part.fixed_mm, -1))
            elif i == rest:
                children.append((child, -1, 0, tail))
            else:
                var = len(var_axis)
                var_axis.append(node.axis)
                var_names.append(f"{node.axis}{var}:{leaves(part.node)[-1]}")
                children.append((child, var, 0, -1))
                if previous_var >= 0:
                    siblings.append((previous_var, var))
                previous_var = var
        ops.append((slot, node.axis == "x", tuple(children)))
        for part, (child, _, _, _) in zip(node.parts, children, strict=True):
            visit(part.node, child)

    visit(root, 0)
    return Program(count, tuple(ops), leaf_slot, tuple(var_axis), tuple(var_names), tuple(siblings))


def boxes(prog: Program, region: Coords, values: Sequence[int]) -> list[Coords] | None:
    """Every slot's rectangle, or None if any part would be empty or inverted."""
    box: list[Coords] = [region] * prog.slots
    for parent, is_x, children in prog.ops:
        x0, y0, x1, y1 = box[parent]
        start, hi = (x0, x1) if is_x else (y0, y1)
        for slot, var, fixed, tail in children:
            if var >= 0:
                end = values[var]
            elif tail >= 0:
                end = hi - tail
            else:
                end = start + fixed
            if end <= start or end > hi:
                return None
            box[slot] = (start, y0, end, y1) if is_x else (x0, start, x1, end)
            start = end
    return box


def min_extent(node: Node, axis: Axis, minimum: dict[str, tuple[int, int]]) -> int:
    """A node's least size along `axis` from its leaves' least (x, y) sizes."""
    if isinstance(node, Leaf):
        x, y = minimum.get(node.key, (0, 0))
        return x if axis == "x" else y
    sizes = [
        p.fixed_mm if p.fixed_mm is not None else min_extent(p.node, axis, minimum)
        for p in node.parts
    ]
    return sum(sizes) if node.axis == axis else max(sizes)


def initial_values(
    root: Node,
    prog: Program,
    region: Coords,
    weight: dict[str, int],
    grid: int,
    minimum: dict[str, tuple[int, int]] | None = None,
) -> tuple[int, ...]:
    """A deterministic start: every split gives each flexible part its least size (from its
    leaves' minimums), then shares what is left in proportion to the parts' weights (preferred
    clear areas). Where the minimums do not fit, it shares the length in their proportion.
    Cuts snap to
    a grid anchored at the region's origin, so every move of one grid step stays on the lattice."""
    values = [0] * len(prog.var_axis)
    order = iter(prog.ops)
    least = minimum or {}

    def total(node: Node) -> int:
        return sum(weight.get(k, 0) for k in leaves(node))

    def visit(node: Node, box: Coords) -> None:
        if isinstance(node, Leaf):
            return
        _, is_x, children = next(order)
        x0, y0, x1, y1 = box
        lo, hi = (x0, x1) if is_x else (y0, y1)
        origin = region[0] if is_x else region[1]
        axis: Axis = "x" if is_x else "y"
        free = hi - lo - sum(p.fixed_mm or 0 for p in node.parts)
        weights = [total(p.node) if p.fixed_mm is None else 0 for p in node.parts]
        mins = [min_extent(p.node, axis, least) if p.fixed_mm is None else 0 for p in node.parts]
        extra = free - sum(mins)
        if extra < 0:  # the minimums do not fit: share the length in their proportion instead
            weights, mins, extra = mins, [0] * len(mins), free
        share = max(1, sum(weights))
        start, fixed_so_far, acc_w, acc_min = lo, 0, 0, 0
        for i, (part, (_, var, fixed, tail)) in enumerate(zip(node.parts, children, strict=True)):
            if var >= 0:
                acc_w += weights[i]
                acc_min += mins[i]
                end = lo + fixed_so_far + acc_min + extra * acc_w // share
                end = origin + ceil_to(end - origin, grid)
                end = min(hi - grid, max(start + grid, end))
                values[var] = end
            elif tail >= 0:
                end = hi - tail
                acc_w += weights[i]
                acc_min += mins[i]
            else:
                end = start + fixed
                fixed_so_far += fixed
            visit(part.node, (start, y0, end, y1) if is_x else (x0, start, x1, end))
            start = end

    visit(root, region)
    return tuple(values)
