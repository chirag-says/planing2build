"""Integer, axis-aligned geometry. Exact: no floats, so containment and overlap never depend on a
tolerance, and the same input gives the same answer on every machine.

Points are (x, y) tuples in millimetres. The plot frame has +y pointing away from the road
(HousePlan schema, section E.1 of the Checkpoint 1 plan)."""

from collections.abc import Sequence
from dataclasses import dataclass

Pt = tuple[int, int]


@dataclass(frozen=True, order=True)
class Rect:
    """A closed axis-aligned rectangle [x0, x1] by [y0, y1] with positive width and height."""

    x0: int
    y0: int
    x1: int
    y1: int

    def __post_init__(self) -> None:
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError(f"degenerate rectangle {self}")

    @property
    def w(self) -> int:
        return self.x1 - self.x0

    @property
    def h(self) -> int:
        return self.y1 - self.y0

    @property
    def area(self) -> int:
        return self.w * self.h

    @property
    def short_side(self) -> int:
        return min(self.w, self.h)

    @property
    def centre2(self) -> Pt:
        """Twice the centre, so it stays an integer."""
        return (self.x0 + self.x1, self.y0 + self.y1)

    def contains(self, other: "Rect") -> bool:
        return (
            self.x0 <= other.x0
            and self.y0 <= other.y0
            and other.x1 <= self.x1
            and other.y1 <= self.y1
        )

    def overlap_area(self, other: "Rect") -> int:
        w = min(self.x1, other.x1) - max(self.x0, other.x0)
        h = min(self.y1, other.y1) - max(self.y0, other.y0)
        return w * h if w > 0 and h > 0 else 0

    def inset(self, left: int, bottom: int, right: int, top: int) -> "Rect | None":
        x0, y0, x1, y1 = self.x0 + left, self.y0 + bottom, self.x1 - right, self.y1 - top
        return Rect(x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None

    def corners(self) -> list[Pt]:
        """Counter-clockwise from the bottom-left corner."""
        return [(self.x0, self.y0), (self.x1, self.y0), (self.x1, self.y1), (self.x0, self.y1)]


def rect_or_none(x0: int, y0: int, x1: int, y1: int) -> Rect | None:
    return Rect(x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def signed_area2(points: Sequence[Pt]) -> int:
    """Twice the signed area (shoelace): positive for counter-clockwise."""
    n = len(points)
    return sum(
        points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
        for i in range(n)
    )


def is_axis_aligned(points: Sequence[Pt]) -> bool:
    n = len(points)
    return all(
        points[i][0] == points[(i + 1) % n][0] or points[i][1] == points[(i + 1) % n][1]
        for i in range(n)
    )


def drop_collinear(points: Sequence[Pt]) -> list[Pt]:
    """Removes repeated points and vertices that lie straight between their neighbours."""
    pts: list[Pt] = []
    for p in points:
        if not pts or pts[-1] != p:
            pts.append(p)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    changed = True
    while changed and len(pts) > 2:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            if cross == 0:
                pts.pop(i)
                changed = True
                break
    return pts


def as_rect(points: Sequence[Pt]) -> Rect | None:
    """The rectangle a polygon describes (collinear vertices allowed), or None if it is not an
    axis-aligned, counter-clockwise rectangle."""
    if not is_axis_aligned(points) or signed_area2(points) <= 0:
        return None
    pts = drop_collinear(points)
    if len(pts) != 4:
        return None
    xs, ys = sorted({p[0] for p in pts}), sorted({p[1] for p in pts})
    if len(xs) != 2 or len(ys) != 2:
        return None
    rect = Rect(xs[0], ys[0], xs[1], ys[1])
    return rect if set(pts) == set(rect.corners()) else None


def on_segment(p: Pt, a: Pt, b: Pt) -> bool:
    """Whether p lies on the closed axis-aligned segment ab."""
    if a[0] == b[0]:
        return p[0] == a[0] and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    if a[1] == b[1]:
        return p[1] == a[1] and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
    return False


def collinear_overlap(a: Pt, b: Pt, c: Pt, d: Pt) -> int:
    """Length shared by two axis-aligned segments on one line (0 if not collinear)."""
    if a[0] == b[0] == c[0] == d[0]:
        lo, hi = max(min(a[1], b[1]), min(c[1], d[1])), min(max(a[1], b[1]), max(c[1], d[1]))
        return max(0, hi - lo)
    if a[1] == b[1] == c[1] == d[1]:
        lo, hi = max(min(a[0], b[0]), min(c[0], d[0])), min(max(a[0], b[0]), max(c[0], d[0]))
        return max(0, hi - lo)
    return 0


def segment_covered(a: Pt, b: Pt, pieces: Sequence[tuple[Pt, Pt]]) -> bool:
    """Whether the axis-aligned segment ab is fully covered by the union of collinear pieces."""
    horizontal = a[1] == b[1]
    lo, hi = sorted((a[0], b[0]) if horizontal else (a[1], b[1]))
    spans = []
    for c, d in pieces:
        if collinear_overlap(a, b, c, d) > 0:
            s0, s1 = sorted((c[0], d[0]) if horizontal else (c[1], d[1]))
            spans.append((max(lo, s0), min(hi, s1)))
    reach = lo
    for s0, s1 in sorted(spans):
        if s0 > reach:
            return False
        reach = max(reach, s1)
    return reach >= hi


def ceil_to(value: int, step: int) -> int:
    return -(-value // step) * step


def ceil_div(a: int, b: int) -> int:
    return -(-a // b)
