// The render model: PlanGeometry (derived by the API from the HousePlan) projected into SVG
// drawing primitives. Presentation only: it computes no areas, no wall outlines and no validity;
// every size and position comes from the server's geometry (HR O.2). Pure and deterministic: the
// same geometry gives the same model.
import type {
  DimensionChain,
  FixtureGeom,
  FloorGeometry,
  GPoint,
  OpenArea,
  OpeningGeom,
  PlanGeometry,
  RoomGeom,
  WallGeom,
} from "./types";
import { flipOf, type Point, toSvg } from "./viewport";

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface RoomShape {
  id: string;
  type: RoomGeom["type"];
  zone: RoomGeom["zone"];
  name: string;
  points: string;
  box: Box; // SVG bounding box of the room polygon
  clear: { w: number; d: number } | null;
  areaMm2: number | null;
  label: Point | null;
}

export interface WallShape {
  id: string;
  kind: WallGeom["kind"];
  outline: string[]; // solid parts, openings already cut out by the server
  a: Point;
  b: Point;
  thickness: number;
  length: number;
}

export interface OpeningShape {
  id: string;
  kind: OpeningGeom["kind"];
  wall: string;
  a: Point;
  b: Point;
  // the symbol across the wall: jamb lines and, for a window, the glazing line
  across: { x1: number; y1: number; x2: number; y2: number }[];
  leaf: { x1: number; y1: number; x2: number; y2: number } | null;
  arc: string | null;
}

export interface FixtureShape {
  id: string;
  type: FixtureGeom["type"];
  room: string;
  box: Box | null;
}

export interface OpenAreaShape {
  id: string;
  kind: OpenArea["kind"];
  cells: Box[];
  label: Point;
  areaMm2: number;
}

export interface DimensionShape {
  id: string;
  kind: DimensionChain["kind"];
  a: Point;
  b: Point;
  valueMm: number;
}

export interface RenderModel {
  flip: number;
  bounds: { min_x: number; min_y: number; max_x: number; max_y: number };
  plot: string;
  envelope: string | null;
  rooms: RoomShape[];
  walls: WallShape[];
  openings: OpeningShape[];
  fixtures: FixtureShape[];
  openAreas: OpenAreaShape[];
  dimensions: DimensionShape[];
}

function pointsAttr(points: GPoint[], flip: number): string {
  return points.map((p) => `${p.x},${flip - p.y}`).join(" ");
}

function boxOf(points: GPoint[], flip: number): Box {
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => flip - p.y);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}

function room(r: RoomGeom, flip: number): RoomShape {
  return {
    id: r.id,
    type: r.type,
    zone: r.zone,
    name: r.name,
    points: pointsAttr(r.polygon, flip),
    box: boxOf(r.polygon, flip),
    clear:
      r.clear_w_mm != null && r.clear_d_mm != null ? { w: r.clear_w_mm, d: r.clear_d_mm } : null,
    areaMm2: r.carpet_area_mm2 ?? null,
    label: r.label_at ? toSvg(r.label_at, flip) : null,
  };
}

function wall(w: WallGeom, flip: number): WallShape {
  return {
    id: w.id,
    kind: w.kind,
    outline: w.outline.map((poly) => pointsAttr(poly, flip)),
    a: toSvg(w.a, flip),
    b: toSvg(w.b, flip),
    thickness: w.thickness_mm,
    length: w.length_mm,
  };
}

/** Unit vector along a→b and its normal, in SVG coordinates. */
function frame(a: Point, b: Point): { ux: number; uy: number; nx: number; ny: number } {
  const len = Math.hypot(b.x - a.x, b.y - a.y) || 1;
  const ux = (b.x - a.x) / len;
  const uy = (b.y - a.y) / len;
  return { ux, uy, nx: -uy, ny: ux };
}

function opening(o: OpeningGeom, walls: Map<string, WallGeom>, flip: number): OpeningShape {
  const a = toSvg(o.jamb_a, flip);
  const b = toSvg(o.jamb_b, flip);
  const host = walls.get(o.wall);
  const half = host ? host.thickness_mm / 2 : 0;
  const { nx, ny } = frame(a, b);
  const across = [a, b].map((p) => ({
    x1: p.x - nx * half,
    y1: p.y - ny * half,
    x2: p.x + nx * half,
    y2: p.y + ny * half,
  }));
  if (o.kind === "WINDOW") {
    // the usual window symbol: both wall faces and the glazing along the centre
    for (const k of [-half, 0, half]) {
      across.push({ x1: a.x + nx * k, y1: a.y + ny * k, x2: b.x + nx * k, y2: b.y + ny * k });
    }
  }
  let leaf: OpeningShape["leaf"] = null;
  let arc: string | null = null;
  if (o.swing) {
    const s = o.swing;
    const hinge = toSvg(s.hinge, flip);
    // world angles are counter-clockwise from +x; the y-flip mirrors them on screen
    const at = (deg: number): Point => {
      const rad = (deg * Math.PI) / 180;
      return {
        x: hinge.x + s.radius_mm * Math.cos(rad),
        y: hinge.y - s.radius_mm * Math.sin(rad),
      };
    };
    const closed = at(s.start_deg);
    const open = at(s.end_deg);
    const turn = ((((s.end_deg - s.start_deg) % 360) + 540) % 360) - 180; // ±90
    leaf = { x1: hinge.x, y1: hinge.y, x2: round(open.x), y2: round(open.y) };
    // A turn counter-clockwise in the world still looks counter-clockwise once flipped onto the
    // screen, which is SVG's negative-angle direction (sweep flag 0).
    const sweep = turn > 0 ? 0 : 1;
    arc =
      `M ${round(closed.x)} ${round(closed.y)} ` +
      `A ${s.radius_mm} ${s.radius_mm} 0 0 ${sweep} ${round(open.x)} ${round(open.y)}`;
  }
  return { id: o.id, kind: o.kind, wall: o.wall, a, b, across, leaf, arc };
}

function round(v: number): number {
  return Math.round(v);
}

/** The render model of one floor of the plan's geometry. */
export function renderModel(geometry: PlanGeometry, level = 0): RenderModel {
  const floor: FloorGeometry | undefined =
    geometry.floors.find((f) => f.level === level) ?? geometry.floors[0];
  const flip = flipOf(geometry.bounds);
  const walls = new Map((floor?.walls ?? []).map((w) => [w.id, w]));
  return {
    flip,
    bounds: geometry.bounds,
    plot: pointsAttr(geometry.plot, flip),
    envelope: geometry.envelope ? pointsAttr(geometry.envelope, flip) : null,
    rooms: (floor?.rooms ?? []).map((r) => room(r, flip)),
    walls: (floor?.walls ?? []).map((w) => wall(w, flip)),
    openings: (floor?.openings ?? []).map((o) => opening(o, walls, flip)),
    fixtures: (floor?.fixtures ?? []).map((f) => ({
      id: f.id,
      type: f.type,
      room: f.room,
      box: f.footprint ? boxOf(f.footprint, flip) : null,
    })),
    openAreas: (floor?.open_areas ?? []).map((a) => ({
      id: a.id,
      kind: a.kind,
      cells: a.cells.map((c) => boxOf(c, flip)),
      label: toSvg(a.label_at, flip),
      areaMm2: a.area_mm2,
    })),
    dimensions: (floor?.dimensions ?? []).map((d) => ({
      id: d.id,
      kind: d.kind,
      a: toSvg(d.start, flip),
      b: toSvg(d.end, flip),
      valueMm: d.value_mm,
    })),
  };
}

/** How much a room label can show at the current zoom: everything, the name, the name in a
 * smaller size, or nothing. */
export type LabelDetail = "full" | "name" | "compact" | "none";

/** `chars`: the name's length, so a long name never spills over the walls (about 7 px a
 * character at the 12 px label size, 5.5 px at the 9.5 px compact size). The size and area
 * lines need about 104 px. */
export function labelDetail(box: Box, pxPerMm: number, chars = 0): LabelDetail {
  const w = box.w * pxPerMm;
  const h = box.h * pxPerMm;
  const name = chars * 7 + 8;
  if (w >= Math.max(104, name) && h >= 44) return "full";
  if (w >= Math.max(48, name) && h >= 18) return "name";
  if (w >= Math.max(28, chars * 5.5 + 4) && h >= 14) return "compact";
  return "none";
}
