"""Room rectangles to the planar wall graph: nodes at every room corner, walls on every shared or
exterior edge segment between consecutive nodes (T-junctions split edges), and each room's
boundary as a counter-clockwise cycle of node ids. A segment gets a wall when at least one room
beside it is enclosed; an open room's outside edges (parking) get none.

Ids are deterministic: nodes and walls are numbered in sorted coordinate order."""

from dataclasses import dataclass
from itertools import pairwise

from p2b.core.vocabulary import WallKind
from p2b.houseplans.engine.geom import Pt, Rect, on_segment


@dataclass(frozen=True)
class GraphWall:
    id: str
    a: str
    b: str
    kind: WallKind
    thickness_mm: int
    left_room: str | None  # side of +90° from a→b
    right_room: str | None


@dataclass(frozen=True)
class Graph:
    nodes: dict[str, Pt]
    walls: tuple[GraphWall, ...]
    boundaries: dict[str, list[str]]


def build_graph(
    rects: dict[str, Rect],
    enclosed: dict[str, bool],
    *,
    exterior_mm: int,
    interior_mm: int,
) -> Graph:
    points = sorted({p for rect in rects.values() for p in rect.corners()})
    node_id = {p: f"n{i}" for i, p in enumerate(points, start=1)}

    def edge_points(a: Pt, b: Pt) -> list[Pt]:
        on = [p for p in points if on_segment(p, a, b)]
        return sorted(on, key=lambda p: abs(p[0] - a[0]) + abs(p[1] - a[1]))

    boundaries: dict[str, list[str]] = {}
    sides: dict[tuple[Pt, Pt], dict[str, str]] = {}  # segment (low, high) -> side -> room
    for key, rect in rects.items():
        corners = rect.corners()  # CCW from bottom-left
        cycle: list[Pt] = []
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            run = edge_points(a, b)
            cycle.extend(run[:-1])
            for p, q in pairwise(run):
                low, high = min(p, q), max(p, q)
                # Walking CCW, the room is on the left of p→q; relative to low→high it is on the
                # left when p→q runs the same way, else on the right.
                side = "left" if (p, q) == (low, high) else "right"
                sides.setdefault((low, high), {})[side] = key
        boundaries[key] = [node_id[p] for p in cycle]

    walls: list[GraphWall] = []
    for low, high in sorted(sides):
        left, right = sides[(low, high)].get("left"), sides[(low, high)].get("right")
        rooms = [r for r in (left, right) if r is not None]
        if not any(enclosed[r] for r in rooms):
            continue
        exterior = len(rooms) == 1
        walls.append(
            GraphWall(
                id=f"w{len(walls) + 1}",
                a=node_id[low],
                b=node_id[high],
                kind=WallKind.EXTERIOR if exterior else WallKind.INTERIOR,
                thickness_mm=exterior_mm if exterior else interior_mm,
                left_room=left,
                right_room=right,
            )
        )
    return Graph(nodes={node_id[p]: p for p in points}, walls=tuple(walls), boundaries=boundaries)
