"""Export real engine output as web app fixtures (Checkpoint 3).

For each listed benchmark case: the plan the engine generates (synthetic test ruleset, the
production solver), its PlanGeometry and validation report, written to
`apps/web/tests/fixtures/houseplans/<case>.json` in the shape of the API's plan detail (only the
fields the renderer and editor read). The web renderer and editor tests run on these, so they test
the real geometry rather than a hand-made model. Deterministic: rerunning writes identical files.

    cd apps/api && uv run python scripts/export_web_plan_fixtures.py
"""

import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT / "scripts"))

from benchmark_houseplans import intent_of, load  # noqa: E402

from p2b.houseplans.engine import (  # noqa: E402
    ZonedLocalSearchSolver,
    fixture_fit,
    generate,
    plan_geometry,
)
from p2b.houseplans.engine.model import dump  # noqa: E402
from p2b.houseplans.router import editing_block  # noqa: E402

CASES = (
    "1bhk_25x40_south_small",  # small, two-wheeler
    "2bhk_30x50_north_twowheeler_open",  # two-wheeler bay and forecourt
    "2bhk_40x80_west_two_cars",  # two cars, forecourt and rear yard
    "3bhk_45x70_two_cars_puja",  # two cars, attached bathrooms
    "3bhk_50x60_wide_two_cars",  # parking bay with open remainder
    "q06_4bhk_60x90_large_two_cars_puja_utility",  # large, courtyard
    "prop_very_wide_80x28",  # wide-shallow, linear
    "1bhk_30x40_no_parking",  # no parking
    "2bhk_22x60_narrow_deep",  # narrow, passage
)
OUT = API_ROOT.parent / "web" / "tests" / "fixtures" / "houseplans"


def main() -> None:
    corpus, rules, _ = load(API_ROOT / "tests" / "fixtures" / "houseplans")
    solver = ZonedLocalSearchSolver(rules, fixture_fit(rules))
    OUT.mkdir(parents=True, exist_ok=True)
    for name in CASES:
        result = generate(
            intent_of(corpus[name], rules),
            rules,
            ruleset_version=1,
            ruleset_sha256="0" * 64,
            solver=solver,
            seed=0,
        )
        if result.plan is None or result.report is None or not result.report.valid:
            raise SystemExit(f"{name}: no valid plan")
        detail = {
            "case": name,
            "document": dump(result.plan),
            "geometry": dump(plan_geometry(result.plan, rules)),
            "validation": dump(result.report),
            "editing": dump(editing_block(rules, True, 0, result.plan)),
        }
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(detail, sort_keys=True, separators=(",", ":")) + "\n", "utf-8")
        print(path.name, path.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
