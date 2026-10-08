// Where a homeowner's project stands in the journey, and what needs them next (IHB_FLOW section 34).
// Pure functions over facts the API already returns, so they are unit-tested and the screens never
// read raw API shapes.
//
// The phase follows the project status, and is moved on by facts when the status lags behind
// (decided 2026-10-07; the current slices keep the status at ACCEPTED while quotes and the build
// run):
//   a request for quotes issued         -> COMPARE
//   a comparison published              -> SELECT
//   a contractor selected or engaged,
//   or a stage started                  -> BUILD (VERIFY runs alongside once an inspection exists)
//   status HANDOVER_PENDING             -> HANDOVER
//   status COMPLETED or ARCHIVED        -> BUILD RECORD
import type { components } from "@p2b/contracts";

type ProjectStatus = components["schemas"]["ProjectStatus"];

export const PHASES = ["plan", "compare", "select", "build", "verify", "handover", "record"] as const;
export type Phase = (typeof PHASES)[number];
export type PhaseState = "done" | "current" | "next" | "alongside";

/** The facts the journey is read from. Every field comes from one API response. */
export interface JourneyFacts {
  status: ProjectStatus;
  /** Plan2Build asked for more information about the requirement. */
  needsInfo: boolean;
  packageActive: boolean;
  /** Reviewed and eligible for the package, not bought yet. */
  packageEligible: boolean;
  buildPlan: { acceptedVersionNo: number | null; issuedVersion: { id: string; no: number } | null; canAct: boolean };
  /** Drawing sets submitted by an architect and waiting for the family. */
  drawingSetsToReview: number;
  rfq: {
    canRequest: boolean;
    issued: boolean;
    quotesReceived: number;
    invited: number;
    comparisonPublished: boolean;
    canSelect: boolean;
    selectedContractor: string | null;
  };
  /** Categories still marked "undecided" while the package is active. */
  undecidedServices: number;
  build: {
    contractor: string | null;
    stagesTotal: number;
    stagesCompleted: number;
    current: { name: string; number: number } | null;
    awaitingConfirmation: Array<{ id: string; name: string; number: number }>;
  };
  verify: { inspections: number; gatesCleared: number; gatesTotal: number; openFindings: number };
  designs: { count: number; freeRemaining: number; canGenerate: boolean };
}

const STATUS_PHASE: Partial<Record<ProjectStatus, Phase>> = {
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

/** The furthest phase the status or the facts reach; null while the project is paused or stopped. */
export function currentPhase(facts: JourneyFacts): Phase | null {
  const fromStatus = STATUS_PHASE[facts.status];
  if (!fromStatus) return null;
  let phase: Phase = fromStatus;
  const reach = (candidate: Phase) => {
    if (PHASES.indexOf(candidate) > PHASES.indexOf(phase)) phase = candidate;
  };
  if (facts.rfq.issued) reach("compare");
  if (facts.rfq.comparisonPublished) reach("select");
  const started = facts.build.stagesCompleted > 0 || facts.build.current !== null;
  if (facts.rfq.selectedContractor || facts.build.contractor || started) reach("build");
  return phase;
}

/** done / current / next for each phase. VERIFY runs alongside BUILD once an inspection exists. */
export function phaseStates(facts: JourneyFacts): Record<Phase, PhaseState> {
  const current = currentPhase(facts);
  const at = current ? PHASES.indexOf(current) : -1;
  const states = Object.fromEntries(
    PHASES.map((phase, index) => {
      if (at < 0) return [phase, "next"];
      if (index < at) return [phase, "done"];
      if (index === at) return [phase, current === "record" ? "done" : "current"];
      return [phase, "next"];
    }),
  ) as Record<Phase, PhaseState>;
  if (current === "build" && facts.verify.inspections > 0) states.verify = "alongside";
  return states;
}

export type ActionKey =
  | "finishRequirement"
  | "answerQuestions"
  | "confirmStage"
  | "chooseContractor"
  | "acceptBuildPlan"
  | "reviewDrawings"
  | "buyPackage"
  | "chooseServices"
  | "requestQuotes"
  | "followFindings"
  | "generateDesign";

export interface NextAction {
  key: ActionKey;
  /** Where the action is done, relative to the project's base path ("" = overview). */
  path: string;
  /** Values for the action's message (counts, names, version numbers). */
  values: Record<string, string | number>;
  /** "act" needs the family; "watch" is worth knowing while someone else acts. */
  kind: "act" | "watch";
}

/**
 * What needs the family, most urgent first. The order is the build's own: what blocks the
 * contractor or Plan2Build comes before what only the family is waiting on.
 */
export function nextActions(facts: JourneyFacts): NextAction[] {
  const actions: NextAction[] = [];
  const add = (key: ActionKey, path: string, values: NextAction["values"] = {}, kind: NextAction["kind"] = "act") =>
    actions.push({ key, path, values, kind });

  if (facts.status === "DRAFT") add("finishRequirement", "/requirement");
  if (facts.needsInfo) add("answerQuestions", "/requirement");
  for (const stage of facts.build.awaitingConfirmation) {
    add("confirmStage", "/construction", { stage: stage.name, number: stage.number });
  }
  if (facts.rfq.canSelect && facts.rfq.comparisonPublished && !facts.rfq.selectedContractor) {
    add("chooseContractor", "/quotes", { count: facts.rfq.quotesReceived });
  }
  if (facts.buildPlan.issuedVersion && facts.buildPlan.canAct) {
    add("acceptBuildPlan", `/build-plan/${facts.buildPlan.issuedVersion.id}`, { version: facts.buildPlan.issuedVersion.no });
  }
  if (facts.drawingSetsToReview > 0) add("reviewDrawings", "/build-plan", { count: facts.drawingSetsToReview });
  if (facts.packageEligible && !facts.packageActive) add("buyPackage", "/package");
  if (facts.packageActive && facts.undecidedServices > 0) add("chooseServices", "/services", { count: facts.undecidedServices });
  if (facts.packageActive && facts.rfq.canRequest && !facts.rfq.issued && facts.buildPlan.acceptedVersionNo !== null) {
    add("requestQuotes", "/quotes");
  }
  if (facts.verify.openFindings > 0) add("followFindings", "/construction", { count: facts.verify.openFindings }, "watch");
  if (facts.designs.count === 0 && facts.designs.canGenerate && facts.designs.freeRemaining > 0) {
    add("generateDesign", "/designs", { count: facts.designs.freeRemaining });
  }
  return actions;
}

/** Why nothing needs the family right now, when nothing does. */
export type WaitingReason = "review" | "quotes" | "build" | "none";

export function waitingReason(facts: JourneyFacts): WaitingReason {
  if (facts.status === "SUBMITTED") return "review";
  if (facts.rfq.issued && !facts.rfq.comparisonPublished) return "quotes";
  if (facts.build.contractor) return "build";
  return "none";
}
