import { describe, expect, it } from "vitest";

import { labelDetail, renderModel } from "@/lib/plan/render-model";

import { FIXTURES, fixture } from "./plan-fixtures";

describe("plan render model (from the server's PlanGeometry)", () => {
  it.each(FIXTURES)("draws every room, wall, opening and fitting of %s", (name) => {
    const { geometry } = fixture(name);
    const floor = geometry.floors[0];
    const model = renderModel(geometry);
    expect(model.rooms.map((r) => r.id)).toEqual(floor.rooms.map((r) => r.id));
    expect(model.walls.map((w) => w.id)).toEqual(floor.walls.map((w) => w.id));
    expect(model.walls.every((w) => w.outline.length > 0)).toBe(true);
    expect(model.openings.map((o) => o.id)).toEqual(floor.openings.map((o) => o.id));
    expect(model.fixtures.map((f) => f.id)).toEqual(floor.fixtures.map((f) => f.id));
    expect(model.openAreas.map((a) => a.id)).toEqual((floor.open_areas ?? []).map((a) => a.id));
    expect(model.plot.split(" ")).toHaveLength(geometry.plot.length);
  });

  it.each(FIXTURES)("is deterministic for %s", (name) => {
    expect(renderModel(fixture(name).geometry)).toEqual(renderModel(fixture(name).geometry));
  });

  it("takes sizes from the server and never measures them", () => {
    const { geometry } = fixture("3bhk_50x60_wide_two_cars");
    const model = renderModel(geometry);
    for (const room of geometry.floors[0].rooms) {
      const shape = model.rooms.find((r) => r.id === room.id);
      expect(shape?.clear).toEqual(
        room.clear_w_mm != null && room.clear_d_mm != null ? { w: room.clear_w_mm, d: room.clear_d_mm } : null,
      );
      expect(shape?.areaMm2).toBe(room.carpet_area_mm2 ?? null);
    }
  });

  it("flips y so the road edge (y = 0) is at the bottom of the drawing", () => {
    const { geometry } = fixture("2bhk_30x50_north_twowheeler_open");
    const model = renderModel(geometry);
    const front = geometry.plot.filter((p) => p.y === geometry.bounds.min_y);
    expect(front.length).toBeGreaterThan(0);
    for (const p of front) expect(model.flip - p.y).toBe(geometry.bounds.max_y);
  });

  it("draws doors with a leaf and a quarter arc from the hinge, and windows with three lines", () => {
    const { geometry } = fixture("2bhk_40x80_west_two_cars");
    const model = renderModel(geometry);
    const doors = model.openings.filter((o) => o.kind === "DOOR" || o.kind === "MAIN_ENTRANCE");
    expect(doors.length).toBeGreaterThan(0);
    for (const door of doors) {
      const geom = geometry.floors[0].openings.find((o) => o.id === door.id);
      expect(geom?.swing).toBeTruthy();
      if (!geom?.swing || !door.leaf || !door.arc) throw new Error("door without swing");
      const hinge = { x: geom.swing.hinge.x, y: model.flip - geom.swing.hinge.y };
      expect(door.leaf.x1).toBe(hinge.x);
      expect(door.leaf.y1).toBe(hinge.y);
      expect(Math.hypot(door.leaf.x2 - hinge.x, door.leaf.y2 - hinge.y)).toBeCloseTo(geom.swing.radius_mm, 0);
      expect(door.arc).toMatch(new RegExp(`A ${geom.swing.radius_mm} ${geom.swing.radius_mm} 0 0 [01] `));
    }
    const windows = model.openings.filter((o) => o.kind === "WINDOW");
    expect(windows.length).toBeGreaterThan(0);
    for (const w of windows) {
      expect(w.leaf).toBeNull();
      expect(w.across).toHaveLength(5); // two jambs, two faces, the glazing
    }
  });

  it("represents open areas without inventing rooms", () => {
    const { geometry, document } = fixture("3bhk_50x60_wide_two_cars");
    const model = renderModel(geometry);
    expect(model.openAreas.length).toBeGreaterThan(0);
    const roomIds = new Set(document.floors[0].rooms.map((r) => r.id));
    for (const area of model.openAreas) {
      expect(roomIds.has(area.id)).toBe(false);
      expect(area.cells.length).toBeGreaterThan(0);
    }
    expect(model.rooms).toHaveLength(document.floors[0].rooms.length);
  });

  it("simplifies labels as the plan zooms out", () => {
    const box = { x: 0, y: 0, w: 3000, h: 3000 };
    expect(labelDetail(box, 0.05)).toBe("full"); // 150 px square
    expect(labelDetail(box, 0.02)).toBe("name"); // 60 px
    expect(labelDetail(box, 0.01)).toBe("compact"); // 30 px: the name, smaller
    expect(labelDetail(box, 0.005)).toBe("none"); // 15 px
    // a long name needs its own width: 17 characters do not fit a 1.8 m room at 0.05 px/mm
    expect(labelDetail({ x: 0, y: 0, w: 1800, h: 3000 }, 0.05, 17)).toBe("none");
    expect(labelDetail({ x: 0, y: 0, w: 2840, h: 3200 }, 0.02, 9)).toBe("compact");
    expect(labelDetail({ x: 0, y: 0, w: 1800, h: 3000 }, 0.05, 6)).toBe("name");
  });
});
