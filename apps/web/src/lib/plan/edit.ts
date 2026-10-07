// Editor gestures as typed HousePlan operations (Checkpoint 3). A gesture never changes the plan
// here: it becomes MOVE_WALL or MOVE_OPENING operations that the API applies, validates and
// stores (HR O.1). These helpers only find which canonical wall or opening a gesture addresses,
// in the document's own node graph, and turn a world displacement into the operation's integer
// millimetres. No geometry rule (sizes, clearances, validity) runs here.
import type { HousePlan, MoveOpeningOp, MoveWallOp, PlanGeometry, PlanOp } from "./types";

export type Side = "left" | "right" | "front" | "back"; // world: −x, +x, road (−y), back (+y)
export type Axis = "x" | "y";

type Floor = HousePlan["floors"][number];

export interface RoomSide {
  side: Side;
  axis: Axis; // the axis the side moves along
  coord: number; // the side's line: x for left/right, y for front/back (world mm)
  from: number; // its extent along the other axis
  to: number;
  walls: string[]; // the canonical walls along it
}

function floorOf(doc: HousePlan): Floor | undefined {
  return doc.floors[0];
}

function nodeMap(floor: Floor): Map<string, { x: number; y: number }> {
  return new Map(floor.nodes.map((n) => [n.id, { x: n.x, y: n.y }]));
}

function pairKey(a: string, b: string): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`;
}

/** The four sides of a room, each with the canonical walls along it, read from the room's node
 * cycle. Null for an unknown room. Sides of a non-rectangular room that are not on its bounding
 * box are not editable and are left out. */
export function roomSides(doc: HousePlan, roomId: string): RoomSide[] | null {
  const floor = floorOf(doc);
  const room = floor?.rooms.find((r) => r.id === roomId);
  if (!floor || !room) return null;
  const nodes = nodeMap(floor);
  const wallsByPair = new Map(floor.walls.map((w) => [pairKey(w.a, w.b), w.id]));
  const pts = room.boundary.map((id) => nodes.get(id)).filter((p) => p !== undefined);
  if (pts.length < 3) return null;
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const sides: RoomSide[] = [
    { side: "left", axis: "x", coord: minX, from: minY, to: maxY, walls: [] },
    { side: "right", axis: "x", coord: maxX, from: minY, to: maxY, walls: [] },
    { side: "front", axis: "y", coord: minY, from: minX, to: maxX, walls: [] },
    { side: "back", axis: "y", coord: maxY, from: minX, to: maxX, walls: [] },
  ];
  room.boundary.forEach((id, i) => {
    const next = room.boundary[(i + 1) % room.boundary.length];
    const a = nodes.get(id);
    const b = nodes.get(next);
    const wall = wallsByPair.get(pairKey(id, next));
    if (!a || !b || !wall) return;
    for (const s of sides) {
      const onLine = s.axis === "x" ? a.x === s.coord && b.x === s.coord : a.y === s.coord && b.y === s.coord;
      if (onLine && !s.walls.includes(wall)) s.walls.push(wall);
    }
  });
  return sides.filter((s) => s.walls.length > 0);
}

/** The left normal of a wall (looking from node a to node b): the direction a positive
 * MOVE_WALL delta moves it (`engine/ops.py`). */
export function wallNormal(doc: HousePlan, wallId: string): { x: number; y: number } | null {
  const floor = floorOf(doc);
  const wall = floor?.walls.find((w) => w.id === wallId);
  if (!floor || !wall) return null;
  const nodes = nodeMap(floor);
  const a = nodes.get(wall.a);
  const b = nodes.get(wall.b);
  if (!a || !b) return null;
  if (a.y === b.y && a.x !== b.x) return { x: 0, y: Math.sign(b.x - a.x) };
  if (a.x === b.x && a.y !== b.y) return { x: -Math.sign(b.y - a.y), y: 0 };
  return null;
}

/** MOVE_WALL that moves a room side `delta` mm along its axis (+x or +y in the world). */
export function moveSideOp(doc: HousePlan, side: RoomSide, delta: number): MoveWallOp | null {
  const d = Math.round(delta);
  if (d === 0 || side.walls.length === 0) return null;
  const wall = side.walls[0];
  const n = wallNormal(doc, wall);
  if (!n) return null;
  const k = side.axis === "x" ? n.x : n.y;
  if (k === 0) return null;
  return { op: "MOVE_WALL", wall, delta_mm: d * k };
}

/** Moving a whole room: its two opposite sides by the same delta, as one batch. The leading side
 * moves first, so the walls between them stretch before they shrink. */
export function moveRoomOps(doc: HousePlan, roomId: string, axis: Axis, delta: number): PlanOp[] {
  const sides = roomSides(doc, roomId);
  if (!sides) return [];
  const [low, high] = axis === "x" ? ["left", "right"] : ["front", "back"];
  const lowSide = sides.find((s) => s.side === low);
  const highSide = sides.find((s) => s.side === high);
  if (!lowSide || !highSide) return [];
  const ordered = delta > 0 ? [highSide, lowSide] : [lowSide, highSide];
  const ops = ordered.map((s) => moveSideOp(doc, s, delta));
  return ops.every((o) => o !== null) ? (ops as PlanOp[]) : [];
}

export interface HostedOpening {
  id: string;
  wall: string;
  a: { x: number; y: number };
  ux: number;
  uy: number;
  length: number;
  offset: number;
  width: number;
}

/** An opening with its host wall's frame (world mm), for moving it along the wall. */
export function hostedOpening(doc: HousePlan, openingId: string): HostedOpening | null {
  const floor = floorOf(doc);
  const opening = floor?.openings.find((o) => o.id === openingId);
  if (!floor || !opening) return null;
  const wall = floor.walls.find((w) => w.id === opening.wall);
  if (!wall) return null;
  const nodes = nodeMap(floor);
  const a = nodes.get(wall.a);
  const b = nodes.get(wall.b);
  if (!a || !b) return null;
  const length = Math.hypot(b.x - a.x, b.y - a.y);
  return {
    id: opening.id,
    wall: wall.id,
    a,
    ux: (b.x - a.x) / length,
    uy: (b.y - a.y) / length,
    length: Math.round(length),
    offset: opening.offset_mm,
    width: opening.width_mm,
  };
}

/** The offset along the host wall for a pointer at `world`, keeping the grab point under the
 * pointer, kept on the wall (0 … length − width) and on the grid. The opening cannot leave its
 * host: only the offset changes. */
export function openingOffsetAt(
  host: HostedOpening,
  world: { x: number; y: number },
  grab: number,
  grid: number,
): number {
  const along = (world.x - host.a.x) * host.ux + (world.y - host.a.y) * host.uy - grab;
  const max = Math.max(0, host.length - host.width);
  const stepped = grid > 0 ? host.offset + Math.round((along - host.offset) / grid) * grid : along;
  return Math.min(max, Math.max(0, Math.round(stepped)));
}

export function moveOpeningOp(host: HostedOpening, offset: number): MoveOpeningOp | null {
  return offset === host.offset ? null : { op: "MOVE_OPENING", opening: host.id, offset_mm: offset };
}

// ---------- snapping (world millimetres) ----------

/** Lines worth snapping a side to, along `axis`: existing wall lines, the buildable envelope
 * and the plot boundary. */
export function snapLines(doc: HousePlan, geometry: PlanGeometry, axis: Axis): number[] {
  const floor = floorOf(doc);
  const out = new Set<number>();
  if (floor) {
    const nodes = nodeMap(floor);
    for (const w of floor.walls) {
      const a = nodes.get(w.a);
      const b = nodes.get(w.b);
      if (!a || !b) continue;
      if (axis === "x" && a.x === b.x) out.add(a.x);
      if (axis === "y" && a.y === b.y) out.add(a.y);
    }
  }
  for (const poly of [geometry.plot, geometry.envelope ?? []]) {
    for (const p of poly) out.add(axis === "x" ? p.x : p.y);
  }
  return [...out].sort((a, b) => a - b);
}

export interface Snap {
  value: number; // the snapped line (world mm, integer)
  line: number | null; // the line it snapped to, for a guide; null when it stepped on the grid
}

/** A side moving from `current` towards `proposed`: onto the nearest snap line within
 * `tolerance`, else by whole grid steps; with snapping off, by whole millimetres. */
export function snapCoordinate(
  current: number,
  proposed: number,
  lines: number[],
  grid: number,
  tolerance: number,
  enabled: boolean,
): Snap {
  if (!enabled) return { value: Math.round(proposed), line: null };
  let best: number | null = null;
  for (const line of lines) {
    if (line === current) continue;
    if (Math.abs(line - proposed) <= tolerance && (best === null || Math.abs(line - proposed) < Math.abs(best - proposed))) {
      best = line;
    }
  }
  if (best !== null) return { value: best, line: best };
  const step = grid > 0 ? grid : 1;
  return { value: current + Math.round((proposed - current) / step) * step, line: null };
}
