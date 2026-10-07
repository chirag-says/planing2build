import { describe, expect, it } from "vitest";

import {
  hostedOpening,
  moveOpeningOp,
  moveRoomOps,
  moveSideOp,
  openingOffsetAt,
  roomSides,
  snapCoordinate,
  snapLines,
  wallNormal,
} from "@/lib/plan/edit";
import type { HousePlan, MoveWallOp } from "@/lib/plan/types";

import { FIXTURES, fixture } from "./plan-fixtures";

function nodes(doc: HousePlan) {
  return new Map(doc.floors[0].nodes.map((n) => [n.id, n]));
}

/** Where a MOVE_WALL would move the wall's line, read from the wall and its left normal: the
 * independent check that the editor's delta sign means what the engine does with it. */
function lineAfter(doc: HousePlan, op: MoveWallOp): { axis: "x" | "y"; coord: number } {
  const wall = doc.floors[0].walls.find((w) => w.id === op.wall);
  const map = nodes(doc);
  const a = map.get(wall?.a ?? "");
  const b = map.get(wall?.b ?? "");
  if (!a || !b) throw new Error("wall");
  if (a.y === b.y) return { axis: "y", coord: a.y + Math.sign(b.x - a.x) * op.delta_mm };
  return { axis: "x", coord: a.x - Math.sign(b.y - a.y) * op.delta_mm };
}

describe("room sides from the canonical node graph", () => {
  it.each(FIXTURES)("finds the walls along every side of every room of %s", (name) => {
    const { document } = fixture(name);
    const map = nodes(document);
    for (const room of document.floors[0].rooms) {
      const sides = roomSides(document, room.id);
      if (room.enclosed) {
        expect(sides?.map((s) => s.side)).toEqual(["left", "right", "front", "back"]);
      } else {
        // parking has walls only where it meets the house; its open sides cannot be moved
        expect(sides?.length ?? 0).toBeLessThan(4);
      }
      for (const side of sides ?? []) {
        expect(side.walls.length).toBeGreaterThan(0);
        for (const id of side.walls) {
          const wall = document.floors[0].walls.find((w) => w.id === id);
          const a = map.get(wall?.a ?? "");
          const b = map.get(wall?.b ?? "");
          const coord = side.axis === "x" ? [a?.x, b?.x] : [a?.y, b?.y];
          expect(coord).toEqual([side.coord, side.coord]);
        }
      }
    }
  });

  it("gives nothing for an unknown room", () => {
    expect(roomSides(fixture("1bhk_25x40_south_small").document, "no_such_room")).toBeNull();
  });
});

describe("gestures as typed operations", () => {
  it.each(FIXTURES)("moves a side of each room of %s exactly where it was dragged", (name) => {
    const { document } = fixture(name);
    for (const room of document.floors[0].rooms) {
      for (const side of roomSides(document, room.id) ?? []) {
        for (const delta of [150, -100]) {
          // "line" is the Checkpoint 3 MOVE_WALL; "edge" (MOVE_EDGE) is tested in plan-edit-cp31
          const op = moveSideOp(document, room.id, side, delta, "line");
          expect(op).not.toBeNull();
          if (!op || op.op !== "MOVE_WALL") throw new Error("not MOVE_WALL");
          expect(Number.isInteger(op.delta_mm)).toBe(true);
          expect(lineAfter(document, op)).toEqual({ axis: side.axis, coord: side.coord + delta });
        }
      }
    }
  });

  it("does not send a move of nothing", () => {
    const { document } = fixture("1bhk_25x40_south_small");
    const side = roomSides(document, "living")?.[0];
    if (!side) throw new Error("no side");
    expect(moveSideOp(document, "living", side, 0, "line")).toBeNull();
    expect(moveSideOp(document, "living", side, 0.4)).toBeNull();
  });

  it("moves a room as one batch, leading side first", () => {
    const { document } = fixture("3bhk_50x60_wide_two_cars");
    const sides = roomSides(document, "kitchen");
    const right = sides?.find((s) => s.side === "right");
    const left = sides?.find((s) => s.side === "left");
    if (!right || !left) throw new Error("no sides");
    const forward = moveRoomOps(document, "kitchen", "x", 300, "line") as MoveWallOp[];
    expect(forward.map((op) => lineAfter(document, op).coord)).toEqual([right.coord + 300, left.coord + 300]);
    const back = moveRoomOps(document, "kitchen", "x", -300, "line") as MoveWallOp[];
    expect(back.map((op) => lineAfter(document, op).coord)).toEqual([left.coord - 300, right.coord - 300]);
  });

  it("keeps a door on its host wall wherever the pointer goes", () => {
    const { document } = fixture("2bhk_40x80_west_two_cars");
    const door = document.floors[0].openings.find((o) => o.kind === "DOOR");
    const host = door ? hostedOpening(document, door.id) : null;
    if (!door || !host) throw new Error("no door");
    expect(host.wall).toBe(door.wall);
    const far = { x: host.a.x + host.ux * 1e6 + 5000, y: host.a.y + host.uy * 1e6 - 7000 };
    expect(openingOffsetAt(host, far, 0, 50)).toBe(host.length - host.width);
    const before = { x: host.a.x - host.ux * 1e6, y: host.a.y - host.uy * 1e6 };
    expect(openingOffsetAt(host, before, 0, 50)).toBe(0);
    // on the grid, relative to where it was
    const near = { x: host.a.x + host.ux * (host.offset + 70), y: host.a.y + host.uy * (host.offset + 70) };
    const offset = openingOffsetAt(host, near, 0, 50);
    expect((offset - host.offset) % 50).toBe(0);
    const op = moveOpeningOp(host, offset);
    expect(op).toEqual(offset === host.offset ? null : { op: "MOVE_OPENING", opening: door.id, offset_mm: offset });
  });

  it("keeps a window on its host wall too", () => {
    const { document } = fixture("prop_very_wide_80x28");
    const window = document.floors[0].openings.find((o) => o.kind === "WINDOW");
    const host = window ? hostedOpening(document, window.id) : null;
    if (!window || !host) throw new Error("no window");
    const offset = openingOffsetAt(host, { x: -1e7, y: 1e7 }, 0, 50);
    expect(offset).toBeGreaterThanOrEqual(0);
    expect(offset).toBeLessThanOrEqual(host.length - host.width);
    expect(moveOpeningOp(host, offset)?.opening ?? window.id).toBe(window.id);
  });

  it("serialises operations as the contract's plain JSON", () => {
    const { document } = fixture("2bhk_30x50_north_twowheeler_open");
    const ops = moveRoomOps(document, "living", "y", 100, "line");
    expect(JSON.parse(JSON.stringify(ops))).toEqual(ops);
    for (const op of ops) {
      expect(Object.keys(op).sort()).toEqual(["delta_mm", "op", "wall"]);
      expect(wallNormal(document, (op as MoveWallOp).wall)).not.toBeNull();
    }
  });
});

describe("snapping in world millimetres", () => {
  const lines = [0, 3000, 4200, 9000];

  it("snaps onto a nearby line", () => {
    expect(snapCoordinate(3000, 4150, lines, 50, 120, true)).toEqual({ value: 4200, line: 4200 });
  });

  it("never snaps a side to the line it starts on", () => {
    expect(snapCoordinate(3000, 3020, lines, 50, 120, true)).toEqual({ value: 3000, line: null });
  });

  it("steps on the grid away from lines", () => {
    expect(snapCoordinate(3000, 3640, lines, 50, 120, true)).toEqual({ value: 3650, line: null });
  });

  it("moves freely when snapping is off", () => {
    expect(snapCoordinate(3000, 4150.4, lines, 50, 120, false)).toEqual({ value: 4150, line: null });
  });

  it("collects wall lines, the envelope and the plot boundary", () => {
    const { document, geometry } = fixture("1bhk_25x40_south_small");
    const xs = snapLines(document, geometry, "x");
    for (const p of geometry.plot) expect(xs).toContain(p.x);
    for (const p of geometry.envelope ?? []) expect(xs).toContain(p.x);
    expect([...xs].sort((a, b) => a - b)).toEqual(xs);
  });
});
