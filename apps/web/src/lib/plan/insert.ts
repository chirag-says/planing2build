// Rooms added in open space against an outside wall (Checkpoint 3.2). The server derives the
// insertion slots (`editing.insertion_slots`): where a room can attach, how far the open space
// reaches and how long the wall stretch is. Here a chosen slot, room type and size become one
// typed ADD_ROOM_OUTSIDE (a position along a known side, never free coordinates), a preview
// rectangle for the drawing (UI only, never sent), and the reasons a size cannot fit, read from
// the server's numbers before anything is sent. The server checks everything again and the
// validator judges the result.
import { roomRect, type Rect } from "./edit";
import type { EditingInfo, HousePlan, InsertionSlot, PlanOp, RoomType } from "./types";

export type Align = "start" | "end";

type RoomTypeInfo = EditingInfo["room_types"][number];

export interface Size {
  depth: number; // centreline millimetres, away from the wall
  length: number; // centreline millimetres, along the wall
}

export type FitProblem =
  | { kind: "shallow"; available: number; needed: number } // clear depth
  | { kind: "narrow"; available: number; needed: number } // clear length
  | { kind: "small"; area: number; needed: number } // clear area
  | { kind: "tooDeep"; available: number } // centreline depth beyond the open space
  | { kind: "tooLong"; available: number }; // centreline length beyond the wall stretch

function up(value: number, step: number): number {
  return step > 0 ? Math.ceil(value / step) * step : Math.ceil(value);
}

/** The smallest room of the type that meets its clear minimums, on the grid. */
export function smallestSize(slot: InsertionSlot, type: RoomTypeInfo, grid: number): Size {
  const depth = up(type.min_short_mm + slot.depth_allowance_mm, grid);
  const clearDepth = depth - slot.depth_allowance_mm;
  const forArea = type.min_area_mm2 ? Math.ceil(type.min_area_mm2 / clearDepth) : 0;
  const length = up(Math.max(type.min_short_mm, forArea) + slot.length_allowance_mm, grid);
  return { depth, length };
}

/** Why a room of this size and type cannot go in the slot; empty when nothing stops it here. */
export function fitProblems(slot: InsertionSlot, type: RoomTypeInfo, size: Size): FitProblem[] {
  const out: FitProblem[] = [];
  const clearDepth = size.depth - slot.depth_allowance_mm;
  const clearLength = size.length - slot.length_allowance_mm;
  if (size.depth > slot.max_depth_mm) out.push({ kind: "tooDeep", available: slot.max_depth_mm });
  if (size.length > slot.length_mm) out.push({ kind: "tooLong", available: slot.length_mm });
  const maxClearDepth = slot.max_depth_mm - slot.depth_allowance_mm;
  if (Math.min(clearDepth, maxClearDepth) < type.min_short_mm) {
    out.push({ kind: "shallow", available: Math.min(clearDepth, maxClearDepth), needed: type.min_short_mm });
  }
  const maxClearLength = slot.length_mm - slot.length_allowance_mm;
  if (Math.min(clearLength, maxClearLength) < type.min_short_mm) {
    out.push({ kind: "narrow", available: Math.min(clearLength, maxClearLength), needed: type.min_short_mm });
  }
  const area = Math.max(0, clearDepth) * Math.max(0, clearLength);
  if (type.min_area_mm2 && area < type.min_area_mm2) out.push({ kind: "small", area, needed: type.min_area_mm2 });
  return out;
}

function start(slot: InsertionSlot, length: number, align: Align): number {
  return slot.offset_mm + (align === "end" ? slot.length_mm - length : 0);
}

export function addOutsideOp(slot: InsertionSlot, type: RoomType, size: Size, align: Align): PlanOp | null {
  const depth = Math.round(size.depth);
  const length = Math.round(size.length);
  if (depth <= 0 || length <= 0 || length > slot.length_mm) return null;
  return {
    op: "ADD_ROOM_OUTSIDE",
    host_room: slot.host_room,
    type,
    side: slot.side,
    offset_mm: start(slot, length, align),
    length_mm: length,
    depth_mm: depth,
  };
}

/** Where the new room would stand (world mm): drawn as a preview only. */
export function previewRect(doc: HousePlan, slot: InsertionSlot, size: Size, align: Align): Rect | null {
  const h = roomRect(doc, slot.host_room);
  if (!h || size.depth <= 0 || size.length <= 0) return null;
  const across = slot.side === "LEFT" || slot.side === "RIGHT";
  const lo = across ? h.y0 : h.x0;
  const a = lo + start(slot, size.length, align);
  const b = a + size.length;
  switch (slot.side) {
    case "LEFT":
      return { x0: h.x0 - size.depth, y0: a, x1: h.x0, y1: b };
    case "RIGHT":
      return { x0: h.x1, y0: a, x1: h.x1 + size.depth, y1: b };
    case "FRONT":
      return { x0: a, y0: h.y0 - size.depth, x1: b, y1: h.y0 };
    default:
      return { x0: a, y0: h.y1, x1: b, y1: h.y1 + size.depth };
  }
}

/** The slots that face an open area, deepest first. */
export function slotsFacing(editing: EditingInfo, areaId: string): InsertionSlot[] {
  return editing.insertion_slots
    .filter((s) => s.open_area === areaId)
    .sort((a, b) => b.max_depth_mm - a.max_depth_mm || b.length_mm - a.length_mm);
}
