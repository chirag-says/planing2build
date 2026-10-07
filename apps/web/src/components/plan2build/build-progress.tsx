// The house, drawn as the website's elevation drawing (Safety section) and filled in by stage:
// ink where the stage is complete, brass where work is in progress, blueprint dashes where it has
// not started. Facts only (EX-04): stage states from the execution API, no dates or percentages.
import type { components } from "@p2b/contracts";
import { cn } from "cn";
import type { CSSProperties, ReactNode } from "react";

import { getTranslator } from "@/lib/i18n";
import "./build-progress.css";

type Stage = components["schemas"]["StageOut"];
type Look = "done" | "active" | "todo" | "held";

const W = 720;
const GROUND = 236;
const FLOOR_H = 46;
const LEFT = 170;
const RIGHT = 550;

/** One look for a group of stage instances (a stage number, optionally on one floor). */
function lookOf(stages: Stage[]): Look {
  if (!stages.length) return "todo";
  if (stages.some((s) => s.state === "BLOCKED" || s.state === "ON_HOLD")) return "held";
  if (stages.every((s) => s.state === "COMPLETED")) return "done";
  if (stages.some((s) => s.state !== "NOT_STARTED")) return "active";
  return "todo";
}

export function BuildProgress({ stages, label }: { stages: Stage[]; label: (stage: Stage) => string }) {
  const t = getTranslator("Execution");
  const of = (number: number, floor?: number | null) =>
    lookOf(stages.filter((s) => s.stage_number === number && (floor === undefined || (s.floor ?? null) === floor)));
  const floors = [...new Set(stages.filter((s) => s.stage_number === 5 && s.floor !== null && s.floor !== undefined).map((s) => s.floor as number))].sort((a, b) => a - b);
  const above = floors.filter((f) => f >= 0);
  const basement = floors.includes(-1);
  const done = stages.filter((s) => s.state === "COMPLETED").length;
  const current = stages.find((s) => s.state === "IN_PROGRESS" || s.state === "COMPLETION_REQUESTED");
  // y of the top of a floor above ground (0 = ground floor).
  const top = (floor: number) => GROUND - (floor + 1) * FLOOR_H;
  const roofY = top(Math.max(0, above.length - 1));
  let order = 0;
  const part = (look: Look, node: ReactNode, key: string) => (
    <g key={key} className={cn("bp-part", `bp-${look}`)} style={{ "--i": order++ } as CSSProperties}>
      {node}
    </g>
  );
  const parts: ReactNode[] = [];

  // 1 Pre-construction: the dimension line over the building.
  parts.push(part(of(1), <path pathLength={1} d={`M${LEFT} ${roofY - 34}H${RIGHT}M${LEFT} ${roofY - 42}v16M${RIGHT} ${roofY - 42}v16`} />, "dims"));
  // 2 Site preparation: the excavated ground.
  parts.push(part(of(2), <path pathLength={1} d={`M40 ${GROUND}H${W - 40}M${LEFT - 30} ${GROUND}v${basement ? 70 : 34}H${RIGHT + 30}v-${basement ? 70 : 34}`} />, "site"));
  // 3 Foundations and 4 plinth.
  const footY = GROUND + (basement ? FLOOR_H : 0);
  parts.push(part(of(3), <path pathLength={1} d={`M${LEFT - 14} ${footY + 18}h38v12h-38zM${(LEFT + RIGHT) / 2 - 19} ${footY + 18}h38v12h-38zM${RIGHT - 24} ${footY + 18}h38v12h-38z`} />, "footings"));
  if (basement) {
    parts.push(part(of(5, -1), <path pathLength={1} d={`M${LEFT} ${GROUND + FLOOR_H}V${GROUND}M${RIGHT} ${GROUND + FLOOR_H}V${GROUND}`} />, "b-cols"));
    parts.push(part(of(6, -1), <rect x={LEFT - 6} y={GROUND - 3} width={RIGHT - LEFT + 12} height={6} />, "b-slab"));
  }
  parts.push(part(of(4), <rect x={LEFT - 10} y={GROUND - 10} width={RIGHT - LEFT + 20} height={10} />, "plinth"));
  // 5 columns, 7 blockwork, 9 services, 12 openings, 6 slab: floor by floor.
  for (const floor of above) {
    const y = top(floor);
    const mid = (LEFT + RIGHT) / 2;
    parts.push(part(of(7), <path pathLength={1} d={`M${LEFT + 8} ${y + 6}H${mid - 6}V${y + FLOOR_H - 4}H${LEFT + 8}zM${mid + 6} ${y + 6}H${RIGHT - 8}V${y + FLOOR_H - 4}H${mid + 6}z`} />, `wall-${floor}`));
    parts.push(part(of(12), <path pathLength={1} d={`M${LEFT + 40} ${y + 14}h60v20h-60zM${mid + 50} ${y + 14}h60v20h-60z`} />, `win-${floor}`));
    parts.push(part(of(9, floor), <path pathLength={1} d={`M${mid - 30} ${y + 4}V${y + FLOOR_H}M${RIGHT - 30} ${y + 4}V${y + FLOOR_H}`} />, `mep-${floor}`));
    parts.push(part(of(5, floor), <path pathLength={1} d={`M${LEFT} ${y + FLOOR_H}V${y}M${mid} ${y + FLOOR_H}V${y}M${RIGHT} ${y + FLOOR_H}V${y}`} />, `cols-${floor}`));
    parts.push(part(of(6, floor), <rect x={LEFT - 8} y={y - 3} width={RIGHT - LEFT + 16} height={6} />, `slab-${floor}`));
  }
  // 8 roof and parapet, 10 waterproofing, 11 plaster, 13 to 15 finishes, 16 external works.
  parts.push(part(of(8), <path pathLength={1} d={`M${LEFT - 8} ${roofY - 3}v-14M${RIGHT + 8} ${roofY - 3}v-14M${RIGHT - 90} ${roofY - 3}v-22h60v22`} />, "roof"));
  parts.push(part(of(10), <path pathLength={1} d={`M${LEFT - 4} ${roofY - 8}H${RIGHT + 4}`} className="bp-thick" />, "wp"));
  parts.push(part(lookOf(stages.filter((s) => [11, 13, 14, 15].includes(s.stage_number))), <path pathLength={1} d={`M${LEFT - 14} ${GROUND - 10}V${roofY - 4}M${RIGHT + 14} ${GROUND - 10}V${roofY - 4}`} />, "finish"));
  parts.push(part(of(16), <path pathLength={1} d={`M50 ${GROUND}v-16h${LEFT - 110}M${W - 50} ${GROUND}v-16h-${W - RIGHT - 110}M${RIGHT + 64} ${GROUND}v-26h20v26`} />, "external"));

  const summary = t("drawing.summary", { done, total: stages.length });
  return (
    <figure className="bp">
      <figcaption className="bp-cap">
        <span className="bp-title font-heading">{t("drawing.title")}</span>
        <span className="bp-sum font-mono">
          {summary}
          {" · "}
          {current ? t("drawing.now", { stage: label(current) }) : t("drawing.none")}
        </span>
      </figcaption>
      <svg viewBox={`0 ${roofY - 60} ${W} ${GROUND + (basement ? 110 : 70) - (roofY - 60)}`} role="img" aria-label={t("drawing.alt", { done, total: stages.length })} className="bp-svg">
        <defs>
          <pattern id="bp-grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M24 0H0V24" className="bp-gridline" />
          </pattern>
        </defs>
        <rect y={roofY - 60} width={W} height={GROUND + (basement ? 110 : 70) - (roofY - 60)} fill="url(#bp-grid)" />
        {parts}
      </svg>
      <ul className="bp-legend font-mono" aria-hidden="true">
        {(["done", "active", "todo", "held"] as const).map((look) => (
          <li key={look} className={`bp-key bp-${look}`}>
            <i />
            {t(`drawing.legend.${look}`)}
          </li>
        ))}
      </ul>
    </figure>
  );
}
