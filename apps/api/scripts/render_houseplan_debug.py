"""Development aid (Checkpoint 1): draw a golden plan's PlanGeometry as plain SVG for review.

Not product code: not served, not used by the web app, not a drawing. It reads only PlanGeometry,
the same derived geometry any future renderer must consume, so it also shows that a picture can be
produced without touching the HousePlan's internals.

    cd apps/api && uv run python scripts/render_houseplan_debug.py OUTPUT_DIR
"""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tests.houseplans_support import golden_plan, ruleset, valid_cases  # noqa: E402

from p2b.houseplans.engine import HousePlan, plan_geometry  # noqa: E402
from p2b.houseplans.engine.derive import GPoint, PlanGeometry  # noqa: E402

ZONE_FILL = {"PUBLIC": "#eef4fb", "PRIVATE": "#f3f0fa", "SERVICE": "#eef8f1",
             "CIRCULATION": "#f7f7f7", "OUTDOOR": "#fdf6e9"}  # fmt: skip
MARGIN = 600


def pts(points: list[GPoint], top: int) -> str:
    return " ".join(f"{p.x},{top - p.y}" for p in points)


def render(geometry: PlanGeometry, title: str) -> str:
    b = geometry.bounds
    top = b.max_y
    width, height = b.max_x - b.min_x + 2 * MARGIN, b.max_y - b.min_y + 2 * MARGIN
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{b.min_x - MARGIN} {-MARGIN} {width} {height}" '
        f'width="{width / 20:.0f}" height="{height / 20:.0f}" font-family="sans-serif">',
        f'<text x="{b.min_x}" y="{-MARGIN / 3:.0f}" font-size="220">{title}</text>',
        f'<polygon points="{pts(geometry.plot, top)}" fill="none" stroke="#999" '
        'stroke-width="20"/>',
    ]
    if geometry.envelope:
        out.append(
            f'<polygon points="{pts(geometry.envelope, top)}" fill="none" stroke="#c55" '
            'stroke-width="15" stroke-dasharray="120 80"/>'
        )
    floor = geometry.floors[0]
    for room in floor.rooms:
        out.append(
            f'<polygon points="{pts(room.polygon, top)}" fill="{ZONE_FILL[room.zone.value]}"/>'
        )
    for wall in floor.walls:
        for piece in wall.outline:
            out.append(f'<polygon points="{pts(piece, top)}" fill="#333"/>')
    for fixture in floor.fixtures:
        if fixture.footprint:
            out.append(
                f'<polygon points="{pts(fixture.footprint, top)}" fill="#fff" stroke="#2a6" '
                'stroke-width="15"/>'
            )
    for opening in floor.openings:
        a, b2 = opening.jamb_a, opening.jamb_b
        colour = "#36c" if opening.kind.value == "WINDOW" else "#c80"
        out.append(
            f'<line x1="{a.x}" y1="{top - a.y}" x2="{b2.x}" y2="{top - b2.y}" '
            f'stroke="{colour}" stroke-width="40"/>'
        )
        if opening.swing:
            sw = opening.swing
            turn = ((sw.end_deg - sw.start_deg + 540) % 360) - 180  # +90 or -90
            arc = []
            for i in range(11):
                angle = math.radians(sw.start_deg + turn * i / 10)
                arc.append(
                    f"{sw.hinge.x + sw.radius_mm * math.cos(angle):.0f},"
                    f"{top - (sw.hinge.y + sw.radius_mm * math.sin(angle)):.0f}"
                )
            out.append(
                f'<polyline points="{sw.hinge.x},{top - sw.hinge.y} {" ".join(arc)}" '
                'fill="none" stroke="#c80" stroke-width="12"/>'
            )
    for room in floor.rooms:
        if room.label_at and room.clear_w_mm and room.clear_d_mm:
            x, y = room.label_at.x, top - room.label_at.y
            out.append(
                f'<text x="{x}" y="{y}" font-size="200" text-anchor="middle">{room.name}</text>'
            )
            out.append(
                f'<text x="{x}" y="{y + 230}" font-size="150" text-anchor="middle" fill="#555">'
                f"{room.clear_w_mm} x {room.clear_d_mm} mm</text>"
            )
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("houseplan-debug")
    target.mkdir(parents=True, exist_ok=True)
    for name in valid_cases():
        plan = HousePlan.model_validate(golden_plan(name)["plan"])
        title = f"{name}: Checkpoint 1 debug render, synthetic test ruleset, not a drawing"
        (target / f"{name}.svg").write_text(render(plan_geometry(plan, ruleset()), title), "utf-8")
        print(target / f"{name}.svg")


if __name__ == "__main__":
    main()
