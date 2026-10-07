"""Development aid (Checkpoints 2.1, 2.2): before-and-after montage of debug renders, one HTML page.

Not product code. It inlines two sets of debug SVGs (`render_houseplan_debug.render`, written by
`benchmark_houseplans.py --svg-dir`) side by side per case, captioned from each run's benchmark
JSON: topology, quality score (lower is better), rooms over their aspect limit, circulation share.

    cd apps/api && uv run python scripts/render_houseplan_montage.py \\
        BEFORE_DIR BEFORE.json AFTER_DIR AFTER.json OUT.html case_a case_b ...
"""

import html
import json
import sys
from pathlib import Path
from typing import Any


def rows(path: Path) -> tuple[str, dict[str, dict[str, Any]]]:
    data = json.loads(path.read_text("utf-8"))
    return str(data.get("label", path.stem)), {r["case"]: r for r in data["rows"]}


def caption(row: dict[str, Any] | None) -> str:
    if row is None:
        return "not in this run"
    if row["outcome"] != "VALID":
        return f"{row['outcome']} ({row.get('classification') or ''})"
    share = row.get("circulation_share_milli", 0) / 10
    return (
        f"{row.get('topology')}<br>quality {row.get('quality')} (lower is better); "
        f"rooms over aspect limit {row.get('aspect_violations')}; circulation {share:.1f}%"
    )


def cell(directory: Path, out: Path, case: str, row: dict[str, Any] | None) -> str:
    svg = directory / f"{case}.svg"
    if not svg.exists():
        return f"<td><p class='none'>no plan</p><p>{caption(row)}</p></td>"
    del out  # the drawing is inlined, so the page stands alone
    return f"<td><div class='plan'>{svg.read_text('utf-8')}</div><p>{caption(row)}</p></td>"


def main() -> None:
    before_dir, before_json, after_dir, after_json, out = (Path(a) for a in sys.argv[1:6])
    cases = sys.argv[6:]
    (before_label, before), (after_label, after) = rows(before_json), rows(after_json)
    body = [
        "<!doctype html><meta charset='utf-8'><title>Concept plan montage</title>",
        "<style>body{font-family:sans-serif;margin:24px}table{border-collapse:collapse}"
        "td{vertical-align:top;padding:8px;border:1px solid #ddd;width:50%}"
        ".plan svg{max-width:100%;height:auto;max-height:640px}"
        "p{font-size:13px}.none{color:#a00}</style>",
        f"<h1>Concept floor plans: {html.escape(before_label)} (left) and "
        f"{html.escape(after_label)} (right)</h1>",
        "<p>Debug renders from the synthetic test ruleset. Not drawings.</p>",
        "<table>",
    ]
    for case in cases:
        body.append(f"<tr><th colspan='2'>{html.escape(case)}</th></tr><tr>")
        body.append(cell(before_dir, out, case, before.get(case)))
        body.append(cell(after_dir, out, case, after.get(case)))
        body.append("</tr>")
    body.append("</table>")
    out.write_text("\n".join(body), "utf-8")
    print(out)


if __name__ == "__main__":
    main()
