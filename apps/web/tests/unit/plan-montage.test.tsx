// The Checkpoint 3 visual review page: the real PlanDrawing over the real engine plans, at a
// readable zoom and zoomed out. Written only when PLAN_MONTAGE_OUT names a file (and
// PLAN_MONTAGE_CSS the app's compiled stylesheet), so the normal test run skips it.
import { readFileSync, writeFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PlanDrawing } from "@/components/plan2build/plan/plan-drawing";
import { renderModel } from "@/lib/plan/render-model";
import { fitViewBox } from "@/lib/plan/viewport";

import { FIXTURES, fixture } from "./plan-fixtures";

const OUT = process.env.PLAN_MONTAGE_OUT;
const CSS = process.env.PLAN_MONTAGE_CSS;

describe.runIf(Boolean(OUT))("visual review montage", () => {
  it("writes the montage", () => {
    const css = CSS ? readFileSync(CSS, "utf-8") : "";
    const sections = FIXTURES.map((name) => {
      const { geometry, document } = fixture(name);
      const model = renderModel(geometry);
      const vb = fitViewBox(geometry.bounds, 0.8, 1500);
      const width = 560;
      const px = width / vb.w;
      const svg = (pxPerMm: number) =>
        renderToStaticMarkup(
          <PlanDrawing model={model} viewBox={vb} pxPerMm={pxPerMm} units="m" titleId={`${name}-t`} descId={`${name}-d`} />,
        );
      const rooms = document.floors[0].rooms.length;
      const openings = document.floors[0].openings.length;
      return `<section><h2>${name}</h2><p>${rooms} rooms, ${openings} openings, ${
        geometry.floors[0].open_areas?.length ?? 0
      } open areas; geometry ${geometry.geometry_version}</p><div class="row">
<figure><div class="frame" style="width:${width}px;height:${Math.round(vb.h * px)}px">${svg(px)}</div><figcaption>fitted</figcaption></figure>
<figure><div class="frame" style="width:${Math.round(width / 2)}px;height:${Math.round((vb.h * px) / 2)}px">${svg(px / 2)}</div><figcaption>zoomed out (labels simplify)</figcaption></figure>
</div></section>`;
    });
    const html = `<!doctype html><meta charset="utf-8"><title>Checkpoint 3 floor plan renderer: visual review</title>
<style>${css}
body{font-family:system-ui,sans-serif;margin:24px;color:var(--foreground)}section{margin-bottom:40px}
.row{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap}.frame{border:1px solid var(--border)}figure{margin:0}
figcaption{font-size:12px;color:var(--muted-foreground)}</style>
<h1>Checkpoint 3: concept floor plan renderer, real CP2.2.1 plans</h1>
<p>Rendered by the production PlanDrawing component from the API's PlanGeometry (synthetic test ruleset). Concept floor plan. Not a construction, structural or approval drawing.</p>
${sections.join("\n")}`;
    writeFileSync(OUT as string, html, "utf-8");
    expect(html.length).toBeGreaterThan(1000);
  });
});
