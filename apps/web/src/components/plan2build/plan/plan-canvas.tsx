"use client";

// The interactive drawing: zoom, pan, selection and editing gestures. A gesture is drawn as an
// overlay while the pointer moves and becomes typed operations on release (`onCommit`); the plan
// itself changes only when the server answers (HR O.1, O.3). Hit-testing uses the committed
// model, never the moving preview. Editing gestures exist only when `editable`.
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import { PlanDrawing, sideLine, type Overlay } from "@/components/plan2build/plan/plan-drawing";
import {
  hostedOpening,
  moveOpeningOp,
  moveRoomOps,
  moveSideOp,
  openingOffsetAt,
  roomSides,
  snapCoordinate,
  snapLines,
  type Axis,
  type RoomSide,
  type Side,
} from "@/lib/plan/edit";
import type { Drag, EditorAction, EditorState } from "@/lib/plan/editor";
import { renderModel } from "@/lib/plan/render-model";
import type { PlanOp } from "@/lib/plan/types";
import {
  fitViewBox,
  panViewBox,
  pxPerMm,
  screenToSvg,
  toWorld,
  zoomViewBox,
  type Point,
  type ScreenRect,
  type ViewBox,
} from "@/lib/plan/viewport";

const MARGIN_MM = 2500; // room for the dimensions and the road caption around the plot
const SNAP_PX = 10; // snapping reaches this far on screen
const DRAG_START_PX = 4; // movement below this is a click

type Gesture =
  | { kind: "pan"; start: Point; vb: ViewBox; moved: boolean }
  | { kind: "side"; room: string; side: RoomSide; startWorld: Point }
  | { kind: "room"; room: string; startWorld: Point; startScreen: Point; axis: Axis | null }
  | { kind: "opening"; id: string; grab: number; startScreen: Point; moved: boolean };

export interface PlanCanvasHandle {
  zoom: (factor: number) => void;
  fit: () => void;
  focus: () => void;
}

export function PlanCanvas({
  state,
  dispatch,
  editable,
  onCommit,
  controls,
  flagged,
}: {
  state: EditorState;
  dispatch: (action: EditorAction) => void;
  editable: boolean;
  onCommit: (ops: PlanOp[]) => void;
  controls?: (handle: PlanCanvasHandle) => void;
  flagged: Set<string>;
}) {
  const { document: doc, geometry, editing } = state.plan;
  const model = useMemo(() => renderModel(geometry), [geometry]);
  const box = useRef<HTMLDivElement>(null);
  const [rect, setRect] = useState<ScreenRect>({ left: 0, top: 0, width: 800, height: 600 });
  const [vb, setVb] = useState<ViewBox>(() => fitViewBox(geometry.bounds, 4 / 3, MARGIN_MM));
  const gesture = useRef<Gesture | null>(null);
  const fitted = useRef(false);
  const grid = editing.grid_mm;

  const measure = useCallback((): ScreenRect => {
    const r = box.current?.getBoundingClientRect();
    return r ? { left: r.left, top: r.top, width: r.width, height: r.height } : rect;
  }, [rect]);

  const fit = useCallback(() => {
    const r = measure();
    setVb(fitViewBox(geometry.bounds, r.width / Math.max(r.height, 1), MARGIN_MM));
  }, [geometry.bounds, measure]);

  const zoom = useCallback((factor: number, anchor?: Point) => {
    setVb((v) => zoomViewBox(v, factor, anchor ?? { x: v.x + v.w / 2, y: v.y + v.h / 2 }));
  }, []);

  useEffect(() => {
    controls?.({ zoom: (f) => zoom(f), fit, focus: () => box.current?.focus() });
  }, [controls, zoom, fit]);

  // keep the layout size; fit the plan once the box has a size
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const observer = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      const next = { left: r.left, top: r.top, width: r.width, height: r.height };
      setRect(next);
      if (!fitted.current && r.width > 0 && r.height > 0) {
        fitted.current = true;
        setVb(fitViewBox(geometry.bounds, r.width / r.height, MARGIN_MM));
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [geometry.bounds]);

  // wheel zoom about the pointer (a non-passive listener, so the page does not scroll)
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      const screen = { left: r.left, top: r.top, width: r.width, height: r.height };
      setVb((v) => zoomViewBox(v, Math.exp(-e.deltaY * 0.0015), screenToSvg({ x: e.clientX, y: e.clientY }, screen, v)));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const scale = pxPerMm(rect, vb);
  const selectedRoom =
    state.selection?.kind === "room" ? state.selection.id : state.selection?.kind === "side" ? state.selection.room : null;
  const sides = useMemo(
    () => (editable && selectedRoom ? roomSides(doc, selectedRoom) : null),
    [editable, selectedRoom, doc],
  );
  const lines = useMemo(
    () => ({ x: snapLines(doc, geometry, "x"), y: snapLines(doc, geometry, "y") }),
    [doc, geometry],
  );

  const worldAt = (client: Point): Point => toWorld(screenToSvg(client, measure(), vb), model.flip);

  function snapped(axis: Axis, current: number, proposed: number, free: boolean) {
    return snapCoordinate(current, proposed, lines[axis], grid, SNAP_PX / Math.max(scale, 1e-6), state.snap && !free);
  }

  function onPointerDown(e: PointerEvent<HTMLDivElement>) {
    if (state.busy || e.button !== 0) return;
    const target = (e.target as Element).closest<SVGElement>("[data-hit]");
    const client = { x: e.clientX, y: e.clientY };
    (e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);
    const kind = target?.dataset.hit;
    const id = target?.dataset.id ?? "";
    if (kind === "side" && editable) {
      const side = sides?.find((s) => s.side === (target?.dataset.side as Side));
      if (side) {
        dispatch({ type: "select", selection: { kind: "side", room: id, side: side.side } });
        gesture.current = { kind: "side", room: id, side, startWorld: worldAt(client) };
        return;
      }
    }
    if (kind === "opening") {
      const host = hostedOpening(doc, id);
      const already = state.selection?.kind === "opening" && state.selection.id === id;
      dispatch({ type: "select", selection: { kind: "opening", id } });
      if (editable && host && already) {
        const w = worldAt(client);
        const along = (w.x - host.a.x) * host.ux + (w.y - host.a.y) * host.uy;
        gesture.current = { kind: "opening", id, grab: along - host.offset, startScreen: client, moved: false };
      }
      return;
    }
    if (kind === "room") {
      if (editable && selectedRoom === id && state.selection?.kind === "room") {
        gesture.current = { kind: "room", room: id, startWorld: worldAt(client), startScreen: client, axis: null };
      } else {
        dispatch({ type: "select", selection: { kind: "room", id } });
      }
      return;
    }
    gesture.current = { kind: "pan", start: client, vb, moved: false };
  }

  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    const g = gesture.current;
    if (!g) return;
    const client = { x: e.clientX, y: e.clientY };
    if (g.kind === "pan") {
      const dx = client.x - g.start.x;
      const dy = client.y - g.start.y;
      if (!g.moved && Math.hypot(dx, dy) < DRAG_START_PX) return;
      g.moved = true;
      const s = pxPerMm(measure(), g.vb);
      setVb(panViewBox(g.vb, -dx / s, -dy / s));
      return;
    }
    const w = worldAt(client);
    if (g.kind === "side") {
      const axis = g.side.axis;
      const proposed = g.side.coord + (axis === "x" ? w.x - g.startWorld.x : w.y - g.startWorld.y);
      const snap = snapped(axis, g.side.coord, proposed, e.altKey);
      dispatch({
        type: "drag",
        drag: { kind: "side", room: g.room, side: g.side.side, axis, from: g.side.coord, to: snap.value, guide: snap.line },
      });
      return;
    }
    if (g.kind === "room") {
      const dxs = client.x - g.startScreen.x;
      const dys = client.y - g.startScreen.y;
      if (!g.axis) {
        if (Math.hypot(dxs, dys) < DRAG_START_PX) return;
        g.axis = Math.abs(dxs) >= Math.abs(dys) ? "x" : "y"; // one axis per move, chosen once
      }
      const all = roomSides(doc, g.room);
      const lead = all?.find((s) => s.axis === g.axis && s.side === (g.axis === "x" ? "left" : "front"));
      if (!lead) return;
      const raw = g.axis === "x" ? w.x - g.startWorld.x : w.y - g.startWorld.y;
      const snap = snapped(g.axis, lead.coord, lead.coord + raw, e.altKey);
      dispatch({ type: "drag", drag: { kind: "room", room: g.room, axis: g.axis, delta: snap.value - lead.coord, guide: snap.line } });
      return;
    }
    const host = hostedOpening(doc, g.id);
    if (!host) return;
    if (!g.moved && Math.hypot(client.x - g.startScreen.x, client.y - g.startScreen.y) < DRAG_START_PX) return;
    g.moved = true;
    const offset = openingOffsetAt(host, w, g.grab, state.snap && !e.altKey ? grid : 1);
    dispatch({ type: "drag", drag: { kind: "opening", id: g.id, offset } });
  }

  function onPointerUp() {
    const g = gesture.current;
    gesture.current = null;
    if (!g) return;
    if (g.kind === "pan") {
      if (!g.moved) dispatch({ type: "select", selection: null });
      return;
    }
    const ops = opsFor(state.drag);
    if (ops.length > 0) onCommit(ops);
    else dispatch({ type: "cancel" });
  }

  function opsFor(drag: Drag | null): PlanOp[] {
    if (!drag) return [];
    if (drag.kind === "side") {
      const side = roomSides(doc, drag.room)?.find((s) => s.side === drag.side);
      const op = side ? moveSideOp(doc, drag.room, side, drag.to - drag.from, state.moveMode) : null;
      return op ? [op] : [];
    }
    if (drag.kind === "room") {
      return drag.delta === 0 ? [] : moveRoomOps(doc, drag.room, drag.axis, drag.delta, state.moveMode);
    }
    const host = hostedOpening(doc, drag.id);
    const op = host ? moveOpeningOp(host, drag.offset) : null;
    return op ? [op] : [];
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape") {
      gesture.current = null;
      dispatch({ type: "cancel" });
      e.preventDefault();
      return;
    }
    if (e.key === "+" || e.key === "=") return void zoom(1.25);
    if (e.key === "-") return void zoom(0.8);
    if (e.key === "0") return void fit();
    const dir = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[e.key];
    if (!dir || !editable || state.busy || !state.selection) return;
    e.preventDefault();
    const step = (e.shiftKey ? 10 : 1) * grid;
    const sel = state.selection;
    let ops: PlanOp[] = [];
    if (sel.kind === "room") {
      ops =
        dir[0] !== 0
          ? moveRoomOps(doc, sel.id, "x", dir[0] * step, state.moveMode)
          : moveRoomOps(doc, sel.id, "y", dir[1] * step, state.moveMode);
    } else if (sel.kind === "side") {
      const side = roomSides(doc, sel.room)?.find((s) => s.side === sel.side);
      const along = side?.axis === "x" ? dir[0] : dir[1];
      const op = side && along ? moveSideOp(doc, sel.room, side, along * step, state.moveMode) : null;
      ops = op ? [op] : [];
    } else {
      const host = hostedOpening(doc, sel.id);
      if (host) {
        // along the wall: the arrow whose direction is closest to the wall's
        const sign = Math.sign(dir[0] * host.ux + dir[1] * host.uy);
        const offset = Math.min(Math.max(0, host.length - host.width), Math.max(0, host.offset + sign * step));
        const op = sign !== 0 ? moveOpeningOp(host, offset) : null;
        ops = op ? [op] : [];
      }
    }
    if (ops.length > 0) onCommit(ops);
  }

  const overlay = overlayFor(state.drag, model.flip, model.bounds, sides, doc);

  return (
    <div
      ref={box}
      tabIndex={0}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={() => {
        gesture.current = null;
        dispatch({ type: "cancel" });
      }}
      onKeyDown={onKeyDown}
      className="relative size-full touch-none overflow-hidden rounded-lg border bg-background outline-none focus-visible:ring-2 focus-visible:ring-ring"
      data-plan-canvas=""
      data-busy={state.busy ? "" : undefined}
    >
      <PlanDrawing
        model={model}
        viewBox={vb}
        pxPerMm={scale}
        units={state.units}
        selection={state.selection}
        sides={sides}
        flagged={flagged}
        overlay={overlay}
        interactive
        titleId="plan-title"
        descId="plan-desc"
      />
    </div>
  );
}

function overlayFor(
  drag: Drag | null,
  flip: number,
  bounds: { min_x: number; min_y: number; max_x: number; max_y: number },
  sides: RoomSide[] | null,
  doc: EditorState["plan"]["document"],
): Overlay | null {
  if (!drag) return null;
  const guideAt = (axis: Axis, coord: number | null) =>
    coord === null
      ? []
      : axis === "x"
        ? [{ x1: coord, y1: flip - bounds.min_y, x2: coord, y2: flip - bounds.max_y }]
        : [{ x1: bounds.min_x, y1: flip - coord, x2: bounds.max_x, y2: flip - coord }];
  if (drag.kind === "side") {
    const side = sides?.find((s) => s.side === drag.side);
    if (!side) return null;
    return { boxes: [], lines: [sideLine({ ...side, coord: drag.to }, flip)], guides: guideAt(drag.axis, drag.guide) };
  }
  if (drag.kind === "room") {
    const all = roomSides(doc, drag.room);
    if (!all) return null;
    const get = (s: Side) => all.find((x) => x.side === s)?.coord ?? 0;
    const [x0, x1, y0, y1] = [get("left"), get("right"), get("front"), get("back")];
    const dx = drag.axis === "x" ? drag.delta : 0;
    const dy = drag.axis === "y" ? drag.delta : 0;
    return {
      boxes: [{ x: x0 + dx, y: flip - (y1 + dy), w: x1 - x0, h: y1 - y0 }],
      lines: [],
      guides: guideAt(drag.axis, drag.guide),
    };
  }
  const host = hostedOpening(doc, drag.id);
  if (!host) return null;
  const a = { x: host.a.x + host.ux * drag.offset, y: host.a.y + host.uy * drag.offset };
  const b = { x: a.x + host.ux * host.width, y: a.y + host.uy * host.width };
  return { boxes: [], lines: [{ x1: a.x, y1: flip - a.y, x2: b.x, y2: flip - b.y }], guides: [] };
}
