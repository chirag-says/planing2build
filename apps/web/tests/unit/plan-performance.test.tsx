// Renderer cost on the largest real plan (development machine, Node, server-side render as a
// stand-in for React's render work; the browser adds layout and paint). Loose bounds catch an
// accidental quadratic; the measured numbers go to the Checkpoint 3 report.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PlanDrawing } from "@/components/plan2build/plan/plan-drawing";
import { roomSides, snapLines } from "@/lib/plan/edit";
import { editorReducer, initialState } from "@/lib/plan/editor";
import { renderModel } from "@/lib/plan/render-model";
import { fitViewBox, zoomViewBox } from "@/lib/plan/viewport";

import { fixture } from "./plan-fixtures";

function time(runs: number, fn: () => void): { median: number; p95: number } {
  const samples: number[] = [];
  for (let i = 0; i < runs; i++) {
    const t = performance.now();
    fn();
    samples.push(performance.now() - t);
  }
  samples.sort((a, b) => a - b);
  return { median: samples[Math.floor(runs / 2)], p95: samples[Math.floor(runs * 0.95)] };
}

describe("renderer performance (largest fixture, 60 x 90 ft 4BHK)", () => {
  const plan = fixture("q06_4bhk_60x90_large_two_cars_puja_utility");
  const vb = fitViewBox(plan.geometry.bounds, 4 / 3, 2500);

  it("builds the render model and draws it quickly", () => {
    const model = renderModel(plan.geometry);
    const build = time(50, () => renderModel(plan.geometry));
    const draw = time(50, () =>
      renderToStaticMarkup(
        <PlanDrawing model={model} viewBox={vb} pxPerMm={0.04} units="m" interactive titleId="t" descId="d" />,
      ),
    );
    // a drag: 60 preview updates, each a reducer step and a full redraw
    let state = initialState(plan);
    state = editorReducer(state, { type: "select", selection: { kind: "room", id: "kitchen" } });
    const sides = roomSides(plan.document, "kitchen");
    const drag = time(60, () => {
      state = editorReducer(state, {
        type: "drag",
        drag: { kind: "side", room: "kitchen", side: "left", axis: "x", from: 0, to: Math.random() * 1000, guide: null },
      });
      renderToStaticMarkup(
        <PlanDrawing model={model} viewBox={vb} pxPerMm={0.04} units="m" selection={state.selection} sides={sides} interactive titleId="t" descId="d" />,
      );
    });
    const zoom = time(200, () => zoomViewBox(vb, 1.1, { x: 1000, y: 1000 }));
    const lines = time(50, () => snapLines(plan.document, plan.geometry, "x"));
    console.info(
      JSON.stringify({ build, draw, dragFrame: drag, zoom, snapLines: lines }, (_, v) =>
        typeof v === "number" ? Math.round(v * 100) / 100 : v,
      ),
    );
    expect(build.p95).toBeLessThan(20);
    expect(draw.p95).toBeLessThan(100);
    expect(drag.p95).toBeLessThan(100);
  });
});
