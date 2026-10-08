// World (plan millimetres) ↔ SVG ↔ screen. The plan frame has +y away from the road; SVG has +y
// down, so drawing coordinates are y-flipped once: svg.y = flip − world.y, with `flip` fixed per
// plan (bounds.min_y + bounds.max_y) so the road edge is at the bottom of the drawing. The
// viewBox is in millimetres: zoom and pan change only the viewBox; geometry is never re-projected
// and never written back (HR O.2). All functions are pure.

export interface Point {
  x: number;
  y: number;
}

export interface ViewBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Bounds {
  min_x: number;
  min_y: number;
  max_x: number;
  max_y: number;
}

export interface ScreenRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** The y-flip constant for a plan: road edge at the bottom of the drawing. */
export function flipOf(bounds: Bounds): number {
  return bounds.min_y + bounds.max_y;
}

export function toSvg(p: Point, flip: number): Point {
  return { x: p.x, y: flip - p.y };
}

export function toWorld(p: Point, flip: number): Point {
  return { x: p.x, y: flip - p.y };
}

/** The viewBox showing `bounds` with `margin` mm around it, widened in one direction to the
 * container's aspect ratio so the plan is centred. */
export function fitViewBox(bounds: Bounds, aspect: number, margin: number): ViewBox {
  let w = bounds.max_x - bounds.min_x + 2 * margin;
  let h = bounds.max_y - bounds.min_y + 2 * margin;
  const safeAspect = aspect > 0 && Number.isFinite(aspect) ? aspect : 1;
  if (w / h < safeAspect) w = h * safeAspect;
  else h = w / safeAspect;
  const cx = (bounds.min_x + bounds.max_x) / 2;
  const cy = (bounds.min_y + bounds.max_y) / 2; // the flip maps this centre onto itself
  return { x: cx - w / 2, y: cy - h / 2, w, h };
}

export const MIN_VIEW_MM = 1500;
export const MAX_VIEW_MM = 400_000;

/** Zoom by `factor` (> 1 in, < 1 out) keeping `anchor` (SVG coordinates) where it is. */
export function zoomViewBox(vb: ViewBox, factor: number, anchor: Point): ViewBox {
  const w = Math.min(MAX_VIEW_MM, Math.max(MIN_VIEW_MM, vb.w / factor));
  const k = w / vb.w;
  const h = vb.h * k;
  return { x: anchor.x - (anchor.x - vb.x) * k, y: anchor.y - (anchor.y - vb.y) * k, w, h };
}

export function panViewBox(vb: ViewBox, dx: number, dy: number): ViewBox {
  return { ...vb, x: vb.x + dx, y: vb.y + dy };
}

/** Screen pixels per millimetre for an SVG laid out in `rect` with `preserveAspectRatio` meet. */
export function pxPerMm(rect: ScreenRect, vb: ViewBox): number {
  return Math.min(rect.width / vb.w, rect.height / vb.h);
}

/** A screen point (client coordinates) in SVG coordinates, honouring the letterboxing of
 * `preserveAspectRatio="xMidYMid meet"`. */
export function screenToSvg(client: Point, rect: ScreenRect, vb: ViewBox): Point {
  const s = pxPerMm(rect, vb);
  const ox = (rect.width - vb.w * s) / 2;
  const oy = (rect.height - vb.h * s) / 2;
  return { x: vb.x + (client.x - rect.left - ox) / s, y: vb.y + (client.y - rect.top - oy) / s };
}

export function svgToScreen(p: Point, rect: ScreenRect, vb: ViewBox): Point {
  const s = pxPerMm(rect, vb);
  const ox = (rect.width - vb.w * s) / 2;
  const oy = (rect.height - vb.h * s) / 2;
  return { x: rect.left + ox + (p.x - vb.x) * s, y: rect.top + oy + (p.y - vb.y) * s };
}

export function viewBoxAttr(vb: ViewBox): string {
  return `${round(vb.x)} ${round(vb.y)} ${round(vb.w)} ${round(vb.h)}`;
}

function round(v: number): number {
  return Math.round(v * 100) / 100;
}
