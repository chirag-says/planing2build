// The concept floor plan as SVG: a pure view of the render model (no state, no effects), so the
// same component renders on the server, in tests and inside the interactive canvas. Colours are
// design tokens only; hairlines keep one screen pixel at any zoom (non-scaling strokes); text is
// sized in screen pixels through `pxPerMm`. Interactive hit targets are added only when asked.
import type { ReactNode } from "react";

import type { Selection, Units } from "@/lib/plan/editor";
import type { RoomSide } from "@/lib/plan/edit";
import { getTranslator } from "@/lib/i18n";
import {
  type Box,
  labelDetail,
  type RenderModel,
  type RoomShape,
} from "@/lib/plan/render-model";
import { formatArea, formatDims, formatLength } from "@/lib/plan/units";
import { viewBoxAttr, type ViewBox } from "@/lib/plan/viewport";

const t = getTranslator("Plan");

/** Shapes drawn over the plan while a gesture is in progress (SVG coordinates). Never sent. */
export interface Overlay {
  boxes: Box[];
  lines: { x1: number; y1: number; x2: number; y2: number }[];
  guides: { x1: number; y1: number; x2: number; y2: number }[];
}

export interface PlanDrawingProps {
  model: RenderModel;
  viewBox: ViewBox;
  pxPerMm: number;
  units: Units;
  selection?: Selection | null;
  sides?: RoomSide[] | null; // the selected room's sides, when it can be edited
  flagged?: Set<string>; // "ROOM:id", "OPENING:id", … from validation issues
  overlay?: Overlay | null;
  interactive?: boolean;
  titleId: string;
  descId: string;
}

const ZONE_FILL: Record<RoomShape["zone"], string> = {
  PUBLIC: "fill-secondary",
  PRIVATE: "fill-background",
  SERVICE: "fill-info-muted",
  CIRCULATION: "fill-muted",
  OUTDOOR: "fill-background",
};

const HAIRLINE = { vectorEffect: "non-scaling-stroke" as const, strokeWidth: 1 };

function lineProps(l: { x1: number; y1: number; x2: number; y2: number }) {
  return { x1: l.x1, y1: l.y1, x2: l.x2, y2: l.y2 };
}

export function PlanDrawing({
  model,
  viewBox,
  pxPerMm,
  units,
  selection = null,
  sides = null,
  flagged,
  overlay = null,
  interactive = false,
  titleId,
  descId,
}: PlanDrawingProps) {
  const px = (n: number) => n / Math.max(pxPerMm, 1e-6); // screen pixels → millimetres
  const font = px(12);
  const small = px(10.5);
  const tiny = px(9.5);
  const flip = model.flip;
  const sel = selection;
  const selectedRoom = sel?.kind === "room" ? sel.id : sel?.kind === "side" ? sel.room : null;
  const plotBox = boxOfPoints(model.plot);

  return (
    <svg
      role="img"
      aria-labelledby={`${titleId} ${descId}`}
      viewBox={viewBoxAttr(viewBox)}
      preserveAspectRatio="xMidYMid meet"
      className="block size-full select-none bg-background"
      data-plan-drawing=""
    >
      <title id={titleId}>{t("drawingLabel")}</title>
      <desc id={descId}>{t("drawingDescription")}</desc>

      {/* plot boundary and the buildable envelope (the setback line) */}
      <g data-layer="site">
        <polygon
          points={model.plot}
          className="fill-none stroke-input"
          strokeDasharray="8 4"
          {...HAIRLINE}
          data-plot=""
        />
        {model.envelope && (
          <polygon
            points={model.envelope}
            className="fill-none stroke-border"
            strokeDasharray="3 3"
            {...HAIRLINE}
            data-envelope=""
          />
        )}
        {plotBox && (
          <text
            x={plotBox.x + plotBox.w / 2}
            y={plotBox.y + plotBox.h + px(52)}
            fontSize={small}
            textAnchor="middle"
            className="fill-muted-foreground"
          >
            {t("road")}
          </text>
        )}
      </g>

      {/* open areas: unbuilt space, labelled where the geometry implies it (never a room) */}
      <g data-layer="open-areas">
        {model.openAreas.map((area) => (
          <g key={area.id} data-open-area={area.kind}>
            {area.cells.map((c, i) => (
              <rect key={i} x={c.x} y={c.y} width={c.w} height={c.h} className="fill-success-muted" />
            ))}
            {labelDetail(largest(area.cells), pxPerMm, t(`openArea.${area.kind}`).length) !== "none" && (
              <text
                x={area.label.x}
                y={area.label.y}
                fontSize={small}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-muted-foreground italic"
              >
                {t(`openArea.${area.kind}`)}
              </text>
            )}
          </g>
        ))}
      </g>

      {/* rooms */}
      <g data-layer="rooms">
        {model.rooms.map((room) => (
          <polygon
            key={room.id}
            points={room.points}
            className={`${ZONE_FILL[room.zone]} ${
              flagged?.has(`ROOM:${room.id}`) ? "stroke-destructive" : "stroke-border"
            }`}
            strokeDasharray={room.zone === "OUTDOOR" ? "6 3" : undefined}
            {...HAIRLINE}
            data-room={room.id}
            data-room-type={room.type}
          />
        ))}
      </g>

      {/* fittings: simple symbols at their footprints */}
      <g data-layer="fixtures">
        {model.fixtures.map((f) =>
          f.box ? (
            <g key={f.id} data-fixture={f.type}>
              <rect
                x={f.box.x}
                y={f.box.y}
                width={f.box.w}
                height={f.box.h}
                className={`fill-background ${
                  flagged?.has(`FIXTURE:${f.id}`) ? "stroke-destructive" : "stroke-muted-foreground"
                }`}
                {...HAIRLINE}
              />
              {fixtureSymbol(f.type, f.box)}
            </g>
          ) : null,
        )}
      </g>

      {/* walls: solid outlines from the server, openings already cut out */}
      <g data-layer="walls">
        {model.walls.flatMap((w) =>
          w.outline.map((points, i) => (
            <polygon
              key={`${w.id}-${i}`}
              points={points}
              className={flagged?.has(`WALL:${w.id}`) ? "fill-destructive" : "fill-foreground"}
              data-wall={w.id}
              data-wall-kind={w.kind}
            />
          )),
        )}
      </g>

      {/* doors and windows */}
      <g data-layer="openings">
        {model.openings.map((o) => {
          const tone = flagged?.has(`OPENING:${o.id}`) ? "stroke-destructive" : "stroke-foreground";
          return (
            <g key={o.id} data-opening={o.kind} data-opening-id={o.id}>
              {o.across.map((l, i) => (
                <line key={i} {...lineProps(l)} className={tone} {...HAIRLINE} />
              ))}
              {o.leaf && <line {...lineProps(o.leaf)} className={tone} {...HAIRLINE} />}
              {o.arc && (
                <path
                  d={o.arc}
                  className="fill-none stroke-muted-foreground"
                  strokeDasharray="4 3"
                  {...HAIRLINE}
                />
              )}
            </g>
          );
        })}
      </g>

      {/* plot dimensions, outside the plot */}
      <g data-layer="dimensions">
        {model.dimensions
          .filter((d) => d.kind === "PLOT")
          .map((d) => {
            const horizontal = d.a.y === d.b.y;
            const off = px(16);
            const a = horizontal ? { x: d.a.x, y: d.a.y + off } : { x: d.a.x - off, y: d.a.y };
            const b = horizontal ? { x: d.b.x, y: d.b.y + off } : { x: d.b.x - off, y: d.b.y };
            const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
            return (
              <g key={d.id} data-dimension={d.kind}>
                <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="stroke-muted-foreground" {...HAIRLINE} />
                <text
                  x={horizontal ? mid.x : mid.x - px(4)}
                  y={horizontal ? mid.y + px(14) : mid.y}
                  fontSize={small}
                  textAnchor={horizontal ? "middle" : "end"}
                  dominantBaseline="middle"
                  className="fill-muted-foreground"
                >
                  {formatLength(d.valueMm, units)}
                </text>
              </g>
            );
          })}
      </g>

      {/* room labels, simplified as the plan zooms out */}
      <g data-layer="labels">
        {model.rooms.map((room) => {
          const detail = labelDetail(room.box, pxPerMm, room.name.length);
          if (!room.label || detail === "none") return null;
          return (
            <text
              key={room.id}
              x={room.label.x}
              y={room.label.y}
              textAnchor="middle"
              className="fill-foreground"
              data-label={room.id}
            >
              <tspan
                x={room.label.x}
                dy={detail === "full" ? -font * 0.6 : (detail === "compact" ? tiny : font) * 0.35}
                fontSize={detail === "compact" ? tiny : font}
                fontWeight={500}
              >
                {room.name}
              </tspan>
              {detail === "full" && room.clear && (
                <tspan x={room.label.x} dy={font * 1.25} fontSize={small} className="fill-muted-foreground">
                  {formatDims(room.clear.w, room.clear.d, units)}
                </tspan>
              )}
              {detail === "full" && room.areaMm2 != null && (
                <tspan x={room.label.x} dy={small * 1.25} fontSize={small} className="fill-muted-foreground">
                  {formatArea(room.areaMm2, units)}
                </tspan>
              )}
            </text>
          );
        })}
      </g>

      {/* selection */}
      <g data-layer="selection" pointerEvents="none">
        {selectedRoom &&
          model.rooms
            .filter((r) => r.id === selectedRoom)
            .map((r) => (
              <polygon
                key={r.id}
                points={r.points}
                className="fill-none stroke-ring"
                vectorEffect="non-scaling-stroke"
                strokeWidth={2}
                data-selected={r.id}
              />
            ))}
        {sel?.kind === "side" &&
          sides
            ?.filter((s) => s.side === sel.side)
            .map((s) => (
              <line
                key={s.side}
                {...sideLine(s, flip)}
                className="stroke-ring"
                vectorEffect="non-scaling-stroke"
                strokeWidth={4}
                data-selected-side={s.side}
              />
            ))}
        {sel?.kind === "opening" &&
          model.openings
            .filter((o) => o.id === sel.id)
            .map((o) => (
              <line
                key={o.id}
                x1={o.a.x}
                y1={o.a.y}
                x2={o.b.x}
                y2={o.b.y}
                className="stroke-ring"
                vectorEffect="non-scaling-stroke"
                strokeWidth={6}
                strokeOpacity={0.7}
                data-selected-opening={o.id}
              />
            ))}
      </g>

      {/* a gesture's preview, never part of the plan */}
      {overlay && (
        <g data-layer="preview" pointerEvents="none">
          {overlay.guides.map((g, i) => (
            <line key={`g${i}`} {...lineProps(g)} className="stroke-ring" strokeDasharray="6 4" {...HAIRLINE} />
          ))}
          {overlay.boxes.map((b, i) => (
            <rect
              key={`b${i}`}
              x={b.x}
              y={b.y}
              width={b.w}
              height={b.h}
              className="fill-ring/10 stroke-ring"
              strokeDasharray="5 3"
              {...HAIRLINE}
            />
          ))}
          {overlay.lines.map((l, i) => (
            <line
              key={`l${i}`}
              {...lineProps(l)}
              className="stroke-ring"
              vectorEffect="non-scaling-stroke"
              strokeWidth={3}
            />
          ))}
        </g>
      )}

      {/* hit targets for the editor: invisible, on top */}
      {interactive && (
        <g data-layer="hit" className="fill-transparent stroke-transparent">
          {model.rooms.map((r) => (
            <polygon
              key={r.id}
              points={r.points}
              data-hit="room"
              data-id={r.id}
              className={r.id === selectedRoom ? "cursor-move" : "cursor-pointer"}
            />
          ))}
          {sides?.map((s) => (
            <line
              key={s.side}
              {...sideLine(s, flip)}
              data-hit="side"
              data-id={selectedRoom ?? ""}
              data-side={s.side}
              vectorEffect="non-scaling-stroke"
              strokeWidth={16}
              strokeLinecap="butt"
              className={s.axis === "x" ? "cursor-ew-resize" : "cursor-ns-resize"}
            />
          ))}
          {model.openings.map((o) => (
            <line
              key={o.id}
              x1={o.a.x}
              y1={o.a.y}
              x2={o.b.x}
              y2={o.b.y}
              data-hit="opening"
              data-id={o.id}
              vectorEffect="non-scaling-stroke"
              strokeWidth={16}
              className={sel?.kind === "opening" && sel.id === o.id ? "cursor-grab" : "cursor-pointer"}
            />
          ))}
        </g>
      )}
    </svg>
  );
}

function boxOfPoints(points: string): Box | null {
  const pairs = points
    .split(" ")
    .filter(Boolean)
    .map((p) => p.split(",").map(Number));
  if (pairs.length === 0) return null;
  const xs = pairs.map((p) => p[0]);
  const ys = pairs.map((p) => p[1]);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}

function largest(cells: Box[]): Box {
  return cells.reduce((a, b) => (b.w * b.h > a.w * a.h ? b : a), cells[0] ?? { x: 0, y: 0, w: 0, h: 0 });
}

/** A room side as an SVG line (sides are kept in world coordinates). */
export function sideLine(s: RoomSide, flip: number) {
  return s.axis === "x"
    ? { x1: s.coord, y1: flip - s.from, x2: s.coord, y2: flip - s.to }
    : { x1: s.from, y1: flip - s.coord, x2: s.to, y2: flip - s.coord };
}

function fixtureSymbol(type: string, b: Box): ReactNode {
  const cx = b.x + b.w / 2;
  const cy = b.y + b.h / 2;
  const r = Math.min(b.w, b.h) / 2;
  const stroke = { className: "fill-none stroke-muted-foreground", ...HAIRLINE };
  switch (type) {
    case "WC_WESTERN":
    case "WC_INDIAN":
      return <ellipse cx={cx} cy={cy} rx={r * 0.55} ry={r * 0.75} {...stroke} />;
    case "WASH_BASIN":
      return <circle cx={cx} cy={cy} r={r * 0.6} {...stroke} />;
    case "KITCHEN_SINK":
      return <rect x={cx - r * 0.6} y={cy - r * 0.45} width={r * 1.2} height={r * 0.9} {...stroke} />;
    case "SHOWER_AREA":
      return (
        <>
          <line x1={b.x} y1={b.y} x2={b.x + b.w} y2={b.y + b.h} {...stroke} />
          <line x1={b.x + b.w} y1={b.y} x2={b.x} y2={b.y + b.h} {...stroke} />
        </>
      );
    default:
      return null;
  }
}
