import { describe, expect, it } from "vitest";

import {
  fitViewBox,
  flipOf,
  MIN_VIEW_MM,
  panViewBox,
  pxPerMm,
  screenToSvg,
  svgToScreen,
  toSvg,
  toWorld,
  zoomViewBox,
} from "@/lib/plan/viewport";

const bounds = { min_x: 0, min_y: 0, max_x: 9144, max_y: 15240 }; // 30 x 50 ft

describe("plan viewport", () => {
  it("flips y once so the road edge is at the bottom, and back", () => {
    const flip = flipOf(bounds);
    expect(toSvg({ x: 100, y: 0 }, flip)).toEqual({ x: 100, y: 15240 });
    expect(toSvg({ x: 100, y: 15240 }, flip)).toEqual({ x: 100, y: 0 });
    expect(toWorld(toSvg({ x: 123, y: 4567 }, flip), flip)).toEqual({ x: 123, y: 4567 });
  });

  it("fits the plot with a margin at the container's aspect ratio, centred", () => {
    const vb = fitViewBox(bounds, 2, 1000);
    expect(vb.h).toBe(15240 + 2000);
    expect(vb.w).toBe(vb.h * 2);
    expect(vb.x + vb.w / 2).toBe(9144 / 2);
    expect(vb.y + vb.h / 2).toBe(15240 / 2);
    const tall = fitViewBox(bounds, 0.25, 1000);
    expect(tall.w).toBe(9144 + 2000);
    expect(tall.w / tall.h).toBeCloseTo(0.25);
  });

  it("zooms about an anchor that stays put, within limits", () => {
    const vb = fitViewBox(bounds, 1, 0);
    const anchor = { x: 2000, y: 3000 };
    const zoomed = zoomViewBox(vb, 2, anchor);
    expect(zoomed.w).toBeCloseTo(vb.w / 2);
    // the anchor keeps its relative position in the view
    expect((anchor.x - zoomed.x) / zoomed.w).toBeCloseTo((anchor.x - vb.x) / vb.w);
    expect((anchor.y - zoomed.y) / zoomed.h).toBeCloseTo((anchor.y - vb.y) / vb.h);
    expect(zoomViewBox(vb, 1e6, anchor).w).toBe(MIN_VIEW_MM);
  });

  it("pans in millimetres", () => {
    const vb = { x: 0, y: 0, w: 100, h: 100 };
    expect(panViewBox(vb, 10, -5)).toEqual({ x: 10, y: -5, w: 100, h: 100 });
  });

  it("maps screen to SVG and back through the letterboxed layout", () => {
    const vb = { x: -1000, y: -1000, w: 20000, h: 10000 };
    const rect = { left: 50, top: 20, width: 800, height: 800 }; // taller than the view: letterboxed
    expect(pxPerMm(rect, vb)).toBeCloseTo(0.04);
    const p = { x: 4321, y: 1234 };
    const back = screenToSvg(svgToScreen(p, rect, vb), rect, vb);
    expect(back.x).toBeCloseTo(p.x);
    expect(back.y).toBeCloseTo(p.y);
    // the view's top-left corner sits below the letterbox band
    const corner = svgToScreen({ x: vb.x, y: vb.y }, rect, vb);
    expect(corner).toEqual({ x: 50, y: 20 + (800 - 10000 * 0.04) / 2 });
  });
});
