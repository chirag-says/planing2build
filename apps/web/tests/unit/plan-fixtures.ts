// Real engine output for the floor plan tests: plans the API generated with the synthetic test
// ruleset (written by apps/api/scripts/export_web_plan_fixtures.py), not hand-made geometry.
import { readFileSync } from "node:fs";
import path from "node:path";

import type { PlanState } from "@/lib/plan/types";

export const FIXTURES = [
  "1bhk_25x40_south_small",
  "2bhk_30x50_north_twowheeler_open",
  "2bhk_40x80_west_two_cars",
  "3bhk_45x70_two_cars_puja",
  "3bhk_50x60_wide_two_cars",
  "q06_4bhk_60x90_large_two_cars_puja_utility",
  "prop_very_wide_80x28",
  "1bhk_30x40_no_parking",
  "2bhk_22x60_narrow_deep",
] as const;

export type FixtureName = (typeof FIXTURES)[number];

const cache = new Map<string, PlanState>();

export function fixture(name: FixtureName): PlanState {
  const hit = cache.get(name);
  if (hit) return structuredClone(hit);
  const file = path.resolve(__dirname, "../fixtures/houseplans", `${name}.json`);
  const data = JSON.parse(readFileSync(file, "utf-8")) as PlanState;
  cache.set(name, data);
  return structuredClone(data);
}
