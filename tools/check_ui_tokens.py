"""No raw colours outside the token file (UI_DESIGN_SYSTEM.md sections 3 and 14).

Scans apps/web/src for Tailwind palette classes (`bg-blue-700`, `text-white`), colour literals
(`#1d4ed8`, `rgb(`, `hsl(`, `oklch(`) and named colours in style props. Only
apps/web/src/app/globals.css may define colour values.
Usage: python tools/check_ui_tokens.py   (exit code 1 on any finding)
"""

import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "apps" / "web" / "src"
TOKEN_FILE = SRC / "app" / "globals.css"

PALETTE = (
    "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|"
    "indigo|violet|purple|fuchsia|pink|rose"
)
UTILITIES = (
    "bg|text|border|border-[trblxy]|ring|ring-offset|outline|fill|stroke|from|via|to|decoration|"
    "divide|placeholder|caret|accent|shadow"
)
PATTERNS = [
    ("palette class", re.compile(rf"\b(?:{UTILITIES})-(?:{PALETTE})-\d{{2,3}}\b")),
    ("black or white class", re.compile(rf"\b(?:{UTILITIES})-(?:black|white)\b")),
    ("hex colour", re.compile(r"(?<![\w&/])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")),
    ("colour function", re.compile(r"\b(?:rgba?|hsla?|oklch|oklab|lab|lch)\(")),
]


def main() -> int:
    findings = 0
    for path in sorted(SRC.rglob("*")):
        if path.suffix not in {".ts", ".tsx", ".css"} or path == TOKEN_FILE:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for what, pattern in PATTERNS:
                for match in pattern.finditer(line):
                    findings += 1
                    print(f"{path.relative_to(SRC.parents[2])}:{number}: {what}: {match.group(0)}")
    print(f"raw colour findings: {findings}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
