// The project's place in the homeowner journey (IHB_FLOW section 34): seven phases from Plan to the
// Build Record, drawn as the public website's stage rail. Presentational only: the phase comes from
// the project status and the package state the page already has; nothing here is a screen of its
// own. Verification runs during the build, so while building it shows as "alongside".
import type { components } from "@p2b/contracts";
import { cn } from "cn";
import type { CSSProperties } from "react";

import { getTranslator } from "@/lib/i18n";
import "./journey-rail.css";

type ProjectStatus = components["schemas"]["ProjectStatus"];
type PackageOffer = components["schemas"]["PackageOfferOut"];

const PHASES = ["plan", "compare", "select", "build", "verify", "handover", "record"] as const;
type Phase = (typeof PHASES)[number];
type State = "done" | "current" | "next" | "alongside";

/** The phase a status belongs to; null where the project is paused or stopped. */
const PHASE_OF: Partial<Record<ProjectStatus, Phase>> = {
  DRAFT: "plan",
  SUBMITTED: "plan",
  NEEDS_INFO: "plan",
  ACCEPTED: "plan",
  PLANNING: "plan",
  PLAN_ISSUED: "plan",
  SOURCING: "compare",
  CONTRACTED: "select",
  BUILDING: "build",
  HANDOVER_PENDING: "handover",
  COMPLETED: "record",
  ARCHIVED: "record",
};

function stateOf(phase: Phase, current: Phase | null, status: ProjectStatus): State {
  if (current === null) return "next";
  const at = PHASES.indexOf(current);
  const index = PHASES.indexOf(phase);
  if (phase === "verify" && status === "BUILDING") return "alongside";
  if (index < at) return "done";
  if (index === at) return status === "COMPLETED" || status === "ARCHIVED" ? "done" : "current";
  return "next";
}

/** The phase a project is in, numbered from 1, or null while it is paused or stopped. */
export function journeyPhase(status: ProjectStatus): { number: number; name: string } | null {
  const phase = PHASE_OF[status];
  if (!phase) return null;
  return { number: PHASES.indexOf(phase) + 1, name: getTranslator("Journey")(`phases.${phase}.name`) };
}

export function JourneyRail({
  status,
  pkg,
  compact = false,
  labelledBy,
}: {
  status: ProjectStatus;
  pkg: PackageOffer;
  /** The dashboard card: names and bars only, the phase contents left out. */
  compact?: boolean;
  /** A visible heading outside the rail that names it; otherwise the rail names itself. */
  labelledBy?: string;
}) {
  const t = getTranslator("Journey");
  const current = PHASE_OF[status] ?? null;
  const packageNote =
    pkg.state === "ACTIVE"
      ? t("package.active")
      : pkg.availability === "ELIGIBLE"
        ? t("package.eligible")
        : t("package.waiting");
  return (
    <section aria-labelledby={labelledBy ?? "journey-title"} className={cn("jr", compact && "jr-compact")}>
      {!labelledBy && (
        <h2 id="journey-title" className="sr-only">
          {t("title")}
        </h2>
      )}
      {/* Scrolls sideways on phones: focusable and named, so it scrolls from the keyboard too. */}
      <div className="jr-scroll" role="region" tabIndex={0} aria-labelledby={labelledBy ?? "journey-title"}>
        <ol className="jr-rail">
          {PHASES.map((phase, index) => {
            const state = stateOf(phase, current, status);
            const name = t(`phases.${phase}.name`);
            return (
              <li
                key={phase}
                className={cn("jr-step", `is-${state}`)}
                aria-current={state === "current" ? "step" : undefined}
                style={{ "--i": index } as CSSProperties}
              >
                <span className="jr-bar" aria-hidden="true" />
                <p className="jr-top font-mono" aria-hidden="true">
                  <b>{String(index + 1).padStart(2, "0")}</b>
                  <span>{t(`states.${state}`)}</span>
                </p>
                <p className="jr-name font-heading">
                  <span aria-hidden="true">{name}</span>
                  <span className="sr-only">{t(`sr.${state}`, { phase: name })}</span>
                </p>
                <p className="jr-items">{t(`phases.${phase}.items`)}</p>
                {phase === "plan" && (
                  <p className={cn("jr-gate font-mono", pkg.state === "ACTIVE" && "is-open")}>
                    <span className="jr-tape" aria-hidden="true" />
                    <span>{packageNote}</span>
                  </p>
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
