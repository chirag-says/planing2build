"""Contrast check for the design tokens in apps/web/src/app/globals.css (UI_DESIGN_SYSTEM.md section 4).

Reads every `--name: oklch(...)` in :root, converts to sRGB, and checks the pairs the design system
promises: text 4.5:1 (WCAG 1.4.3), control borders and focus 3:1 (WCAG 1.4.11).
Usage: python tools/check_contrast.py   (exit code 1 on a failing pair)
"""

import math
import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "apps" / "web" / "src" / "app" / "globals.css"

# (foreground token, background token, minimum ratio, why)
PAIRS = [
    ("foreground", "background", 4.5, "body text"),
    ("muted-foreground", "background", 4.5, "secondary text"),
    ("muted-foreground", "muted", 4.5, "secondary text on muted panels"),
    ("primary-foreground", "primary", 4.5, "primary button text"),
    ("input", "background", 3.0, "control borders"),
    ("ring", "background", 3.0, "focus indicator"),
    ("destructive", "background", 4.5, "error text"),
    ("destructive", "destructive-muted", 4.5, "error alert and badge"),
    ("success", "success-muted", 4.5, "success alert and badge"),
    ("warning", "warning-muted", 4.5, "warning alert and badge"),
    ("info", "info-muted", 4.5, "info alert and badge"),
    ("foreground", "warning-muted", 4.5, "alert description on warning"),
    ("foreground", "accent", 4.5, "text on hover and selected rows"),
]


def oklch_to_linear_srgb(l: float, c: float, h: float) -> tuple[float, float, float]:
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (l - 0.0894841775 * a - 1.2914855480 * b) ** 3
    r = 4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
    g = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
    bl = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_
    return tuple(min(1.0, max(0.0, v)) for v in (r, g, bl))  # type: ignore[return-value]


def luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def tokens() -> dict[str, tuple[float, float, float]]:
    root = CSS.read_text(encoding="utf-8").split(":root", 1)[1].split("}", 1)[0]
    values: dict[str, str] = dict(re.findall(r"--([\w-]+):\s*([^;]+);", root))
    resolved: dict[str, tuple[float, float, float]] = {}
    for name in values:
        raw = values[name]
        while raw.startswith("var(--"):
            raw = values[raw[6:-1]]
        match = re.match(r"oklch\(([\d.]+) ([\d.]+) ([\d.]+)\)", raw)
        if match:
            resolved[name] = oklch_to_linear_srgb(*map(float, match.groups()))
    return resolved


def main() -> int:
    colours = tokens()
    failed = 0
    for fg, bg, minimum, why in PAIRS:
        l1, l2 = sorted((luminance(colours[fg]), luminance(colours[bg])), reverse=True)
        ratio = (l1 + 0.05) / (l2 + 0.05)
        ok = ratio >= minimum
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {ratio:5.2f}:1 (need {minimum}) {fg} on {bg}: {why}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
