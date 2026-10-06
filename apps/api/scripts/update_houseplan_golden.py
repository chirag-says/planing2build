"""Regenerate the concept plan golden files from the requirement fixtures (Checkpoint 1).

Run deliberately, read the diff, commit it with the engine change that caused it. CI never runs
this; `tests/test_houseplan_golden.py` compares fresh output with the committed files.

    cd apps/api && uv run python scripts/update_houseplan_golden.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tests.houseplans_support import GOLDEN, generate_case, valid_cases  # noqa: E402

from p2b.houseplans.engine.model import dump  # noqa: E402


def main() -> None:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    for name in valid_cases():
        result = generate_case(name)
        if result.outcome != "VALID" or result.plan is None:
            raise SystemExit(f"{name}: expected VALID, got {result.outcome}")
        path = GOLDEN / f"{name}.json"
        before = path.read_text("utf-8") if path.exists() else None
        payload = {
            "case": name,
            "topology": result.topology,
            "body_sha256": result.plan.meta.body_sha256,
            "plan": dump(result.plan),
        }
        after = json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
        path.write_text(after, "utf-8", newline="\n")
        print(name, "unchanged" if before == after else "UPDATED", result.plan.meta.body_sha256)


if __name__ == "__main__":
    main()
