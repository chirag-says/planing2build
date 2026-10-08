import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PlanDrawing } from "@/components/plan2build/plan/plan-drawing";
import { renderModel } from "@/lib/plan/render-model";
import { fitViewBox } from "@/lib/plan/viewport";

import { FIXTURES, fixture, type FixtureName } from "./plan-fixtures";

function draw(name: FixtureName, pxPerMm = 0.06, interactive = false): string {
  const { geometry } = fixture(name);
  const model = renderModel(geometry);
  return renderToStaticMarkup(
    <PlanDrawing
      model={model}
      viewBox={fitViewBox(geometry.bounds, 4 / 3, 1500)}
      pxPerMm={pxPerMm}
      units="m"
      interactive={interactive}
      titleId="t"
      descId="d"
    />,
  );
}

function count(svg: string, attr: string): number {
  return svg.split(` ${attr}`).length - 1;
}

/** A structural summary of the SVG: what is drawn and where, without styling. */
function structure(svg: string): string[] {
  const out: string[] = [];
  const re = /<(polygon|line|path|rect|ellipse|circle|text)([^>]*)>/g;
  for (const m of svg.matchAll(re)) {
    const attrs = m[2];
    const data = [...attrs.matchAll(/ (data-[a-z-]+)="([^"]*)"/g)].map((d) => `${d[1]}=${d[2]}`);
    const geom = [...attrs.matchAll(/ (points|x1|y1|x2|y2|d|x|y|width|height)="([^"]*)"/g)].map(
      (g) => `${g[1]}=${g[2]}`,
    );
    out.push([m[1], ...data, ...geom].join(" "));
  }
  return out;
}

describe("plan drawing (SVG)", () => {
  it.each(FIXTURES)("draws the whole plan of %s", (name) => {
    const { geometry, document } = fixture(name);
    const floor = geometry.floors[0];
    const svg = draw(name);
    expect(count(svg, "data-plot=")).toBe(1);
    expect(count(svg, "data-envelope=")).toBe(geometry.envelope ? 1 : 0);
    expect(count(svg, "data-room=")).toBe(floor.rooms.length);
    expect(count(svg, "data-wall=")).toBe(floor.walls.reduce((n, w) => n + w.outline.length, 0));
    expect(count(svg, "data-opening-id=")).toBe(floor.openings.length);
    expect(count(svg, "data-fixture=")).toBe(floor.fixtures.filter((f) => f.footprint).length);
    expect(count(svg, "data-open-area=")).toBe((floor.open_areas ?? []).length);
    expect(count(svg, 'data-dimension="PLOT"')).toBe(2);
    // a room for every canonical room, parking included where the requirement asked for it
    const parking = document.floors[0].rooms.some((r) => r.type === "PARKING");
    expect(svg.includes('data-room-type="PARKING"')).toBe(parking);
  });

  it.each(FIXTURES)("renders %s deterministically", (name) => {
    expect(draw(name)).toBe(draw(name));
  });

  it("labels rooms with name, clear size and area from the server when there is room", () => {
    const { geometry } = fixture("3bhk_45x70_two_cars_puja");
    const svg = draw("3bhk_45x70_two_cars_puja", 0.08);
    const living = geometry.floors[0].rooms.find((r) => r.type === "LIVING");
    if (!living?.clear_w_mm || !living.clear_d_mm) throw new Error("no living room size");
    expect(svg).toContain(`>${living.name}</tspan>`);
    expect(svg).toContain(`${(living.clear_w_mm / 1000).toFixed(2)} m × ${(living.clear_d_mm / 1000).toFixed(2)} m`);
    // zoomed far out the labels give way
    expect(count(draw("3bhk_45x70_two_cars_puja", 0.004), "data-label=")).toBe(0);
  });

  it("labels open areas as open space, not rooms", () => {
    const svg = draw("3bhk_50x60_wide_two_cars");
    expect(svg).toMatch(/data-open-area="(FORECOURT|SIDE_YARD|REAR_YARD|COURT)"/);
    expect(svg).toMatch(/>(Forecourt|Side yard|Rear yard|Open court)</);
  });

  it("adds hit targets only for the interactive canvas", () => {
    expect(count(draw("1bhk_25x40_south_small"), "data-hit=")).toBe(0);
    const { geometry } = fixture("1bhk_25x40_south_small");
    const floor = geometry.floors[0];
    expect(count(draw("1bhk_25x40_south_small", 0.06, true), "data-hit=")).toBe(
      floor.rooms.length + floor.openings.length,
    );
  });

  it("uses design tokens only, never raw colours", () => {
    const svg = draw("q06_4bhk_60x90_large_two_cars_puja_utility");
    expect(svg).not.toMatch(/(fill|stroke)="(#|rgb|hsl|oklch)/);
    expect(svg).not.toMatch(/style="[^"]*(#[0-9a-f]{3}|rgb\()/i);
  });

  it.each(["2bhk_30x50_north_twowheeler_open", "3bhk_50x60_wide_two_cars"] as const)(
    "keeps the structure of %s",
    (name) => {
      expect(structure(draw(name))).toMatchSnapshot();
    },
  );
});
