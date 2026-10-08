"""Exact clear rectangles from room rectangles, before any wall exists (Checkpoint 2; open areas
in Checkpoint 2.1).

Room rectangles sit inside the wall-centreline region; parts of it may stay unbuilt (open areas).
A room's clear (inside-face) rectangle is its rectangle inset on each side by half the thickest
wall on that side, as `derive.analyse` measures it. The walls are the ones `graph.build_graph`
will create:

- a stretch of side with another room beside it gets an interior wall where either room is
  enclosed;
- a stretch with no room beside it (the region boundary, or an open area) gets an exterior wall
  if the room is enclosed, else none.

So the solver and the Scorer measure the same clear dimensions the validator and `PlanGeometry`
derive from the built plan (a test holds the two together)."""

from collections.abc import Mapping

from p2b.houseplans.engine.geom import Rect

Insets = tuple[int, int, int, int]  # left, bottom, right, top
SIDES = ("left", "bottom", "right", "top")


def half(t: int) -> int:
    return (t + 1) // 2


def touching(r: Rect, o: Rect, side: str) -> int:
    """How long `o` runs along `r`'s side `side` (0 when it does not touch that side)."""
    if (side == "left" and o.x1 == r.x0) or (side == "right" and o.x0 == r.x1):
        return max(0, min(o.y1, r.y1) - max(o.y0, r.y0))
    if (side == "bottom" and o.y1 == r.y0) or (side == "top" and o.y0 == r.y1):
        return max(0, min(o.x1, r.x1) - max(o.x0, r.x0))
    return 0


def side_length(r: Rect, side: str) -> int:
    return r.h if side in ("left", "right") else r.w


def room_insets(
    rects: Mapping[str, Rect],
    enclosed: Mapping[str, bool],
    region: Rect,
    *,
    exterior_mm: int,
    interior_mm: int,
) -> dict[str, Insets]:
    del region  # the boundary is wherever no room is beside a side, the region's or an open area's
    out: dict[str, Insets] = {}
    for key, r in rects.items():
        values = []
        for side in SIDES:
            covered, walled_inside = 0, False
            for other, o in rects.items():
                if other == key:
                    continue
                run = touching(r, o, side)
                if run:
                    covered += run
                    walled_inside = walled_inside or enclosed[key] or enclosed[other]
            thickness = []
            if covered < side_length(r, side) and enclosed[key]:
                thickness.append(exterior_mm)
            if walled_inside:
                thickness.append(interior_mm)
            values.append(half(max(thickness)) if thickness else 0)
        out[key] = (values[0], values[1], values[2], values[3])
    return out


def clear_rect(rect: Rect, insets: Insets) -> Rect | None:
    return rect.inset(*insets)


def exterior_runs(key: str, rects: Mapping[str, Rect]) -> int:
    """The longest stretch of `key`'s sides with no room beside it: where an exterior wall, and so
    a window, can go (an open area or the region boundary)."""
    r = rects[key]
    best = 0
    for side in SIDES:
        lo, hi = (r.y0, r.y1) if side in ("left", "right") else (r.x0, r.x1)
        covered = []
        for other, o in rects.items():
            if other != key and touching(r, o, side):
                a, b = (o.y0, o.y1) if side in ("left", "right") else (o.x0, o.x1)
                covered.append((max(a, lo), min(b, hi)))
        cursor = lo
        for a, b in sorted(covered):
            best = max(best, a - cursor)
            cursor = max(cursor, b)
        best = max(best, hi - cursor)
    return best
