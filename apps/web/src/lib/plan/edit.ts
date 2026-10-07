// Editor gestures as typed HousePlan operations (Checkpoints 3 and 3.1). A gesture never changes
// the plan here: it becomes typed operations that the API applies, validates and stores (HR O.1).
// These helpers only find which canonical room, wall or opening a gesture addresses, in the
// document's own node graph, and turn a world displacement into the operation's integer
// millimetres. No geometry rule (sizes, clearances, validity) runs here: the server decides.
import type {
  EditingInfo,
  HousePlan,
  MoveOpeningOp,
  MoveWallOp,
  Opening,
  PlanGeometry,
  PlanOp,
  RoomSideName,
  RoomType,
} from "./types";

export type Side = "left" | "right" | "front" | "back"; // world: −x, +x, road (−y), back (+y)
export type Axis = "x" | "y";

/** How a side moves (Checkpoint 3.1): only the part of its line that must move with it
 * (MOVE_EDGE, the default), or the whole straight line through the plan (MOVE_WALL). */
export type MoveMode = "edge" | "line";

const SIDE_NAME: Record<Side, RoomSideName> = { left: "LEFT", right: "RIGHT", front: "FRONT", back: "BACK" };
export const SIDES: Side[] = ["left", "right", "front", "back"];

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

/** The operation that moves a room side `delta` mm along its axis (+x or +y in the world):
 * MOVE_EDGE for "edge", MOVE_WALL (the side's whole straight line) for "line". */
export function moveSideOp(
  doc: HousePlan,
  room: string,
  side: RoomSide,
  delta: number,
  mode: MoveMode = "edge",
): PlanOp | null {
  const d = Math.round(delta);
  if (d === 0) return null;
  if (mode === "edge") return { op: "MOVE_EDGE", room, side: SIDE_NAME[side.side], delta_mm: d };
  return moveLineOp(doc, side, d);
}

function moveLineOp(doc: HousePlan, side: RoomSide, d: number): MoveWallOp | null {
  if (side.walls.length === 0) return null;
  const wall = side.walls[0];
  const n = wallNormal(doc, wall);
  if (!n) return null;
  const k = side.axis === "x" ? n.x : n.y;
  if (k === 0) return null;
  return { op: "MOVE_WALL", wall, delta_mm: d * k };
}

/** Moving a whole room: its two opposite sides by the same delta, as one batch. The leading side
 * moves first, so the walls between them stretch before they shrink. */
export function moveRoomOps(
  doc: HousePlan,
  roomId: string,
  axis: Axis,
  delta: number,
  mode: MoveMode = "edge",
): PlanOp[] {
  const sides = roomSides(doc, roomId);
  if (!sides) return [];
  const [low, high] = axis === "x" ? ["left", "right"] : ["front", "back"];
  const lowSide = sides.find((s) => s.side === low);
  const highSide = sides.find((s) => s.side === high);
  if (!lowSide || !highSide) return [];
  const ordered = delta > 0 ? [highSide, lowSide] : [lowSide, highSide];
  const ops = ordered.map((s) => moveSideOp(doc, roomId, s, delta, mode));
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

// ---------- rooms (Checkpoint 3.1) ----------

export interface Rect {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

/** A room's rectangle from its node cycle (world mm), or null for an unknown room. */
export function roomRect(doc: HousePlan, roomId: string): Rect | null {
  const floor = floorOf(doc);
  const room = floor?.rooms.find((r) => r.id === roomId);
  if (!floor || !room) return null;
  const nodes = nodeMap(floor);
  const pts = room.boundary.map((id) => nodes.get(id)).filter((p) => p !== undefined);
  if (pts.length < 4) return null;
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
}

/** Rooms a room can merge into when it is removed: those sharing one whole side with it and
 * enclosed alike (DELETE_ROOM; the server checks again). */
export function mergeTargets(doc: HousePlan, roomId: string): string[] {
  const floor = floorOf(doc);
  const room = floor?.rooms.find((r) => r.id === roomId);
  const a = roomRect(doc, roomId);
  if (!floor || !room || !a) return [];
  return floor.rooms
    .filter((other) => other.id !== roomId && other.enclosed === room.enclosed)
    .filter((other) => {
      const b = roomRect(doc, other.id);
      if (!b) return false;
      const rows = a.y0 === b.y0 && a.y1 === b.y1 && (a.x1 === b.x0 || b.x1 === a.x0);
      const columns = a.x0 === b.x0 && a.x1 === b.x1 && (a.y1 === b.y0 || b.y1 === a.y0);
      return rows || columns;
    })
    .map((other) => other.id);
}

export function addRoomOp(host: string, type: RoomType, side: Side, depthMm: number): PlanOp | null {
  const depth = Math.round(depthMm);
  return depth > 0 ? { op: "ADD_ROOM", host_room: host, type, side: SIDE_NAME[side], depth_mm: depth } : null;
}

export function deleteRoomOp(room: string, mergeInto: string): PlanOp {
  return { op: "DELETE_ROOM", room, merge_into: mergeInto };
}

/** The engine's default name for a room of `type` with id `id` ("Bedroom 2" for bedroom_2), from
 * the type names the API sends (`editing.room_types`). */
export function defaultRoomName(editing: EditingInfo, id: string, type: string): string | null {
  const base = editing.room_types.find((t) => t.type === type)?.name;
  if (!base) return null;
  const suffix = id.split("_").pop() ?? "";
  return /^\d+$/.test(suffix) ? `${base} ${suffix}` : base;
}

/** SET_ROOM_TYPE, with a RENAME_ROOM to the new type's default name when the room still has its
 * old type's default name (a renamed room keeps its name). */
export function setRoomTypeOps(doc: HousePlan, editing: EditingInfo, roomId: string, type: RoomType): PlanOp[] {
  const room = floorOf(doc)?.rooms.find((r) => r.id === roomId);
  if (!room || room.type === type) return [];
  const ops: PlanOp[] = [{ op: "SET_ROOM_TYPE", room: roomId, type }];
  const next = defaultRoomName(editing, roomId, type);
  if (next && room.name === defaultRoomName(editing, roomId, room.type)) {
    ops.push({ op: "RENAME_ROOM", room: roomId, name: next });
  }
  return ops;
}

export function renameRoomOp(doc: HousePlan, roomId: string, name: string): PlanOp | null {
  const room = floorOf(doc)?.rooms.find((r) => r.id === roomId);
  const trimmed = name.trim();
  if (!room || trimmed.length === 0 || trimmed.length > 120 || trimmed === room.name) return null;
  return { op: "RENAME_ROOM", room: roomId, name: trimmed };
}

// ---------- openings (Checkpoint 3.1) ----------

/** SET_OPENING to a new width keeping its height, sill and door, then MOVE_OPENING so it keeps
 * its centre on the wall. Nothing is clamped to make it fit: a width that does not fit is for the
 * server to refuse. Empty when nothing changes. */
export function resizeOpeningOps(doc: HousePlan, openingId: string, widthMm: number): PlanOp[] {
  const opening = floorOf(doc)?.openings.find((o) => o.id === openingId);
  const width = Math.round(widthMm);
  if (!opening || width <= 0 || width === opening.width_mm) return [];
  const offset = opening.offset_mm + Math.round((opening.width_mm - width) / 2);
  const ops: PlanOp[] = [
    {
      op: "SET_OPENING",
      opening: opening.id,
      width_mm: width,
      height_mm: opening.height_mm,
      sill_mm: opening.sill_mm,
      door: opening.door ?? null,
    },
  ];
  if (offset !== opening.offset_mm) {
    ops.push({ op: "MOVE_OPENING", opening: opening.id, offset_mm: Math.max(0, offset) });
  }
  return ops;
}

export function deleteOpeningOp(openingId: string): PlanOp {
  return { op: "DELETE_OPENING", opening: openingId };
}

function uniqueId(base: string, used: Set<string>): string {
  let candidate = base;
  for (let n = 2; used.has(candidate); n += 1) candidate = `${base}_${n}`;
  return candidate;
}

/** ADD_OPENING of a door or window centred on the longest wall along a room's side, sized from
 * the ruleset (`editing.openings`). A door opens into the room. Null when the side has no wall
 * or the API sent no sizes. Whether it may go there (exterior wall, clearances) is for the
 * server to check. */
export function addOpeningOp(
  doc: HousePlan,
  editing: EditingInfo,
  roomId: string,
  side: Side,
  kind: "DOOR" | "WINDOW",
): PlanOp | null {
  const floor = floorOf(doc);
  const sizes = editing.openings;
  const along = roomSides(doc, roomId)?.find((s) => s.side === side);
  const rect = roomRect(doc, roomId);
  if (!floor || !sizes || !along || !rect) return null;
  const nodes = nodeMap(floor);
  let best: { id: string; length: number; a: { x: number; y: number } } | null = null;
  for (const id of along.walls) {
    const wall = floor.walls.find((w) => w.id === id);
    const a = wall && nodes.get(wall.a);
    const b = wall && nodes.get(wall.b);
    if (!wall || !a || !b) continue;
    const length = Math.abs(b.x - a.x) + Math.abs(b.y - a.y);
    if (!best || length > best.length || (length === best.length && id < best.id)) best = { id, length, a };
  }
  if (!best) return null;
  const width = kind === "DOOR" ? sizes.door_width_mm : sizes.window_width_mm;
  const used = new Set(floor.openings.map((o) => o.id));
  const base = `${kind === "DOOR" ? "door" : "window"}_${roomId}`.slice(0, 44);
  let door: Opening["door"] = null;
  if (kind === "DOOR") {
    // the room's side of the wall: left of a→b when its centre lies along the left normal
    const n = wallNormal(doc, best.id);
    const cx = (rect.x0 + rect.x1) / 2 - best.a.x;
    const cy = (rect.y0 + rect.y1) / 2 - best.a.y;
    const left = n ? cx * n.x + cy * n.y > 0 : true;
    door = { leaf: "SINGLE", hinge: "A_SIDE", opens_to: left ? "LEFT" : "RIGHT" };
  }
  const opening: Opening = {
    id: uniqueId(base, used),
    kind,
    wall: best.id,
    offset_mm: Math.max(0, Math.floor((best.length - width) / 2)),
    width_mm: width,
    height_mm: kind === "DOOR" ? sizes.door_height_mm : sizes.window_height_mm,
    sill_mm: kind === "DOOR" ? 0 : sizes.window_sill_mm,
    door,
  };
  return { op: "ADD_OPENING", opening };
}
