// The Checkpoint 3.1 visual review page: each real plan as generated and after the first accepted
// edit of each kind (apps/api/scripts/review_houseplan_edits.py writes the steps), drawn by the
// production PlanDrawing. Written only when PLAN_EDIT_REVIEW_IN and PLAN_EDIT_REVIEW_OUT are set
// (PLAN_MONTAGE_CSS for the app's compiled stylesheet), so the normal test run skips it.
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PlanDrawing } from "@/components/plan2build/plan/plan-drawing";
import { renderModel } from "@/lib/plan/render-model";
import type { PlanGeometry } from "@/lib/plan/types";
import { fitViewBox } from "@/lib/plan/viewport";

const IN = process.env.PLAN_EDIT_REVIEW_IN;
const OUT = process.env.PLAN_EDIT_REVIEW_OUT;
const CSS = process.env.PLAN_MONTAGE_CSS;
const TITLE = process.env.PLAN_EDIT_REVIEW_TITLE ?? "Checkpoint 3.1: real CP2.2.1 plans, first accepted edit of each kind";

const CASES = [
  "1bhk_25x40_south_small",
  "2bhk_30x50_north_twowheeler_open",
  "2bhk_40x80_west_two_cars",
  "3bhk_45x70_two_cars_puja",
  "3bhk_50x60_wide_two_cars",
  "q06_4bhk_60x90_large_two_cars_puja_utility",
  "prop_very_wide_80x28",
  "1bhk_30x40_no_parking",
];

interface Step {
  label: string;
  op: Record<string, unknown> | null;
  geometry: PlanGeometry | null;
  changed_rooms?: string[];
}

function escape(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

describe.runIf(Boolean(IN && OUT))("editing review montage", () => {
  it("writes the montage", () => {
    const css = CSS ? readFileSync(CSS, "utf-8") : "";
    const sections = CASES.map((name) => {
      const { steps } = JSON.parse(readFileSync(path.join(IN as string, `${name}.json`), "utf-8")) as { steps: Step[] };
      const base = steps[0].geometry;
      if (!base) throw new Error("no generated geometry");
      // one frame for every step, so movement is visible between figures
      const vb = fitViewBox(base.bounds, 0.8, 1500);
      const width = 340;
      const px = width / vb.w;
      const figures = steps.map((step, i) => {
        const caption = step.op
          ? `${escape(step.label)}: ${escape(JSON.stringify(step.op))}<br>changed rooms: ${escape((step.changed_rooms ?? []).join(", ") || "none")}`
          : step.geometry
            ? "generated"
            : `${escape(step.label)}: no accepted edit found`;
        const svg = step.geometry
          ? renderToStaticMarkup(
              <PlanDrawing
                model={renderModel(step.geometry)}
                viewBox={vb}
                pxPerMm={px}
                units="m"
                titleId={`${name}-${i}-t`}
                descId={`${name}-${i}-d`}
              />,
            )
          : "";
        return `<figure><div class="frame" style="width:${width}px;height:${Math.round(vb.h * px)}px">${svg}</div><figcaption>${caption}</figcaption></figure>`;
      });
      return `<section><h2>${name}</h2><div class="row">${figures.join("\n")}</div></section>`;
    });
    const html = `<!doctype html><meta charset="utf-8"><title>${escape(TITLE)}</title>
<style>${css}
body{font-family:system-ui,sans-serif;margin:24px;color:var(--foreground)}section{margin-bottom:40px}
.row{display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap}.frame{border:1px solid var(--border)}figure{margin:0;max-width:340px}
figcaption{font-size:11px;color:var(--muted-foreground);word-break:break-all}</style>
<h1>${escape(TITLE)}</h1>
<p>Rendered by the production PlanDrawing component from PlanGeometry after each edit the validator passed (synthetic test ruleset). Concept floor plan. Not a construction, structural or approval drawing.</p>
${sections.join("\n")}`;
    writeFileSync(OUT as string, html, "utf-8");
    expect(html.length).toBeGreaterThan(1000);
  });
});
