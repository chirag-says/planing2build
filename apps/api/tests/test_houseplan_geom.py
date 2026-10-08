"""Integer geometry (Checkpoint 1, section K): exact, tolerance-free primitives."""

import pytest

from p2b.houseplans.engine.geom import (
    Rect,
    as_rect,
    ceil_to,
    collinear_overlap,
    drop_collinear,
    on_segment,
    segment_covered,
    signed_area2,
)
from p2b.houseplans.engine.units import ft_to_mm


def test_rectangles_measure_exactly() -> None:
    r = Rect(0, 0, 4000, 3000)
    assert (r.w, r.h, r.area, r.short_side) == (4000, 3000, 12_000_000, 3000)
    assert r.inset(100, 100, 50, 50) == Rect(100, 100, 3950, 2950)
    assert r.inset(2000, 0, 2000, 0) is None
    with pytest.raises(ValueError, match="degenerate"):
        Rect(0, 0, 0, 10)


def test_touching_is_not_overlapping_and_containment_includes_the_boundary() -> None:
    a, b = Rect(0, 0, 10, 10), Rect(10, 0, 20, 10)
    assert a.overlap_area(b) == 0
    assert a.overlap_area(Rect(5, 5, 15, 15)) == 25
    assert a.contains(Rect(0, 0, 10, 10))
    assert not a.contains(Rect(0, 0, 11, 10))


def test_polygon_orientation_and_rectangles_with_collinear_vertices() -> None:
    ccw = [(0, 0), (10, 0), (20, 0), (20, 10), (0, 10)]
    assert signed_area2(ccw) == 400
    assert drop_collinear(ccw) == [(0, 0), (20, 0), (20, 10), (0, 10)]
    assert as_rect(ccw) == Rect(0, 0, 20, 10)
    assert as_rect(list(reversed(ccw))) is None  # clockwise
    assert as_rect([(0, 0), (20, 0), (20, 10), (10, 10), (10, 20), (0, 20)]) is None  # L-shape
    assert as_rect([(0, 0), (10, 5), (0, 10)]) is None  # not axis-aligned


def test_segments() -> None:
    assert on_segment((5, 0), (0, 0), (10, 0))
    assert not on_segment((5, 1), (0, 0), (10, 0))
    assert collinear_overlap((0, 0), (10, 0), (5, 0), (20, 0)) == 5
    assert collinear_overlap((0, 0), (10, 0), (10, 0), (20, 0)) == 0
    assert segment_covered((0, 0), (10, 0), [((0, 0), (4, 0)), ((4, 0), (10, 0))])
    assert not segment_covered((0, 0), (10, 0), [((0, 0), (4, 0)), ((5, 0), (10, 0))])


def test_units_round_half_even_through_decimal() -> None:
    assert ft_to_mm(30) == 9144
    assert ft_to_mm(30.5) == 9296
    assert ft_to_mm("3.5") == 1067
    assert ceil_to(3758, 50) == 3800
