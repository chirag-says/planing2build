// Everything the project's home screen shows, read in one pass and mapped from API shapes to a
// small domain model (lib/journey.ts for the phase and the next actions). Components receive this
// model, never raw responses. Each request is optional: a project still under review has no
// quotes, stages or inspections yet, and their absence is a fact, not an error.
import "server-only";

import type { ApiClient, components } from "@p2b/contracts";
import { cache } from "react";

import { serverApi } from "@/lib/api/server";
import { nextActions, phaseStates, currentPhase, waitingReason, type JourneyFacts, type NextAction, type Phase, type PhaseState, type WaitingReason } from "@/lib/journey";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, hasStagesAndLines, loadProject, type ProjectDetail } from "@/lib/project";
import { formatAnswer, questionsByKey, type FormatLabels } from "@/lib/questions";

type Stage = components["schemas"]["StageOut"];
type Design = components["schemas"]["DesignOut"];
type UnavailableReason = NonNullable<components["schemas"]["ProjectEstimateOut"]["unavailable_reason"]>;
type DesignBlock = components["schemas"]["DesignListOut"]["quota"]["block"];

/** The one-line notes per phase (messages Overview.notes). */
export type PhaseNoteKey =
  | "planAccepted"
  | "planPackage"
  | "planReview"
  | "planDraft"
  | "planFree"
  | "compareReady"
  | "compareWaiting"
  | "selectDone"
  | "buildNow"
  | "buildCount"
  | "verifyGates";

/** The requirement answers the home screen shows as the house's facts, in this order. */
const FACT_KEYS = ["built_up_area_sqft", "floors", "quality_tier", "bedrooms", "facing"] as const;
export type FactKey = (typeof FACT_KEYS)[number] | "plot";

export interface TeamMember {
  id: string;
  /** The person or firm, as the engagement names them. */
  name: string;
  firm: string | null;
  /** The category they were engaged for ("Contractor", "Architect"). */
  role: string;
  code: string;
  /** The contractor doing the build: the family's first contact. */
  primary: boolean;
  /** Engaged outside Plan2Build (the family's own professional). */
  outside: boolean;
  phone: string | null;
  email: string | null;
  since: string;
}

export type PlanningStep = "requirement" | "review" | "package" | "buildPlan" | "quotes" | "contractor";

export interface Progress {
  planning: Array<{ key: PlanningStep; done: boolean }>;
  /** Null until the build has stages, gates, specification lines or payment milestones. */
  construction: { done: number; total: number } | null;
  verification: { done: number; total: number } | null;
  decisions: { done: number; total: number } | null;
  payments: { done: number; total: number } | null;
}

export type ActivityKind =
  | "submitted"
  | "design"
  | "planIssued"
  | "planAccepted"
  | "quotesRequested"
  | "quotesCompared"
  | "contractorChosen"
  | "teamJoined"
  | "stageStarted"
  | "stageDone"
  | "inspectionPassed"
  | "findingClosed";

export interface ActivityItem {
  id: string;
  kind: ActivityKind;
  at: string;
  values: Record<string, string | number>;
}

export interface ProjectOverview {
  project: { id: string; code: string; locality: string | null; status: ProjectDetail["project"]["status"] };
  facts: Array<{ key: FactKey; value: string }>;
  floorsAbove: number;
  phase: Phase | null;
  phases: Record<Phase, PhaseState>;
  /** One line per phase saying where it stands, as message values for the screen to word. */
  phaseNotes: Partial<Record<Phase, { key: PhaseNoteKey; values?: Record<string, string | number> }>>;
  actions: NextAction[];
  waiting: WaitingReason;
  /** Null until the dashboard opens; `range` is null when no estimate can be made, with the reason. */
  estimate: {
    range: { low: string; high: string } | null;
    isDemo: boolean;
    unavailable: { reason: UnavailableReason; city: string } | null;
  } | null;
  /** The latest finished concept designs, at most four. */
  designs: Design[];
  /** The newest finished concept with an image: the house visual on the overview (always marked illustrative). */
  heroDesign: Design | null;
  /**
   * The newest photo a contractor posted on one of this project's stage updates, from their own
   * dashboard: the house as it stands on site. Null until a contractor has posted one.
   */
  siteVisual: { url: string; stage: string; postedAt: string; by: string | null } | null;
  /** Independent assurance: the auditor Plan2Build appointed (only their code reaches the family). */
  assurance: { auditorCode: string | null; inspections: number; scheduled: number } | null;
  /** The Plan2Build package, as a state only (the package page has the rest). */
  pkg: { state: ProjectDetail["package"]["state"]; availability: ProjectDetail["package"]["availability"]; purchasable: boolean };
  designQuota: {
    count: number;
    freeRemaining: number;
    freeTotal: number;
    canGenerate: boolean;
    block: DesignBlock | null;
  } | null;
  /** The people working on the house through Plan2Build, with how to reach them. */
  team: TeamMember[];
  /** How far the project is, from facts only: planning steps, then the build's own counts. */
  progress: Progress;
  /** What happened, newest first, read from the dates the API records. */
  activity: ActivityItem[];
  /**
   * Contractor quotes, request to choice (Slice 3.6): whether a request can go out and, if not,
   * what it waits for; how far the comparison is. Null until the dashboard opens.
   */
  quotes: {
    request: "sent" | "ready" | "needsPackage" | "needsPlan" | "unavailable";
    compare: "ready" | "waiting" | "notYet";
    invited: number;
    received: number;
    canSelect: boolean;
    selected: string | null;
  } | null;
  stages: Stage[];
}

async function settle<T>(request: Promise<{ data?: T }> | null): Promise<T | undefined> {
  if (!request) return undefined;
  try {
    return (await request).data;
  } catch {
    return undefined;
  }
}

/**
 * The latest site photo: from the stages with the newest updates, the first update (newest first)
 * that has a photo, as a short-lived signed link to private storage. Never throws.
 */
async function loadSiteVisual(api: ApiClient, projectId: string, stages: Stage[]): Promise<ProjectOverview["siteVisual"]> {
  const newest = stages
    .filter((stage) => stage.update_count > 0 && stage.last_update_at)
    .sort((a, b) => (b.last_update_at ?? "").localeCompare(a.last_update_at ?? ""))
    .slice(0, 3);
  for (const stage of newest) {
    const updates = await settle(
      api.GET("/api/v1/projects/{project_id}/stages/{stage_id}/updates", {
        params: { path: { project_id: projectId, stage_id: stage.id } },
      }),
    );
    for (const update of updates?.updates ?? []) {
      const photo = update.photos[0];
      if (!photo) continue;
      const link = await settle(
        api.GET("/api/v1/projects/{project_id}/stages/{stage_id}/files/{file_id}/url", {
          params: { path: { project_id: projectId, stage_id: stage.id, file_id: photo.file_id } },
        }),
      );
      if (link?.url) return { url: link.url, stage: stage.name, postedAt: update.posted_at, by: update.contractor_name };
    }
  }
  return null;
}

/** Floors above ground from the requirement's floors answer ("G_PLUS_2" -> 2, "G" -> 0). */
function floorsAbove(value: unknown): number {
  const match = typeof value === "string" ? value.match(/(\d+)$/) : null;
  return match ? Number(match[1]) : 0;
}

export async function loadProjectOverview(detail: ProjectDetail, labels: FormatLabels): Promise<ProjectOverview> {
  const { project } = detail;
  const id = project.project_id;
  const api = await serverApi();
  const path = { params: { path: { project_id: id } } };
  const open = dashboardOpen(project.status);
  const built = hasStagesAndLines(project.status);

  const [questions, estimate, designs, rfqs, buildPlan, services, execution, assurance, workspace, payments] = await Promise.all([
    settle(api.GET("/api/v1/public/requirement-questions")),
    settle(open ? api.GET("/api/v1/projects/{project_id}/estimate", path) : null),
    settle(open ? api.GET("/api/v1/projects/{project_id}/designs", path) : null),
    settle(open ? api.GET("/api/v1/projects/{project_id}/rfqs", path) : null),
    settle(open ? api.GET("/api/v1/projects/{project_id}/build-plan", path) : null),
    settle(open ? api.GET("/api/v1/projects/{project_id}/services", path) : null),
    settle(built ? api.GET("/api/v1/projects/{project_id}/execution", path) : null),
    settle(built ? api.GET("/api/v1/projects/{project_id}/assurance", path) : null),
    settle(built ? api.GET("/api/v1/projects/{project_id}/workspace", path) : null),
    settle(built ? api.GET("/api/v1/projects/{project_id}/payment-marks", path) : null),
  ]);

  // The house, as the family described it.
  const answers = detail.requirement.answers as Record<string, unknown>;
  const byKey = questions ? questionsByKey(questions) : new Map();
  const facts: ProjectOverview["facts"] = [];
  for (const key of FACT_KEYS) {
    const question = byKey.get(key);
    const text = question ? formatAnswer(question, answers[key], labels) : "";
    // The area as a number with the unit; an answer that is not a number keeps its own wording.
    const area = key === "built_up_area_sqft" ? Number(answers[key]) : Number.NaN;
    if (text) facts.push({ key, value: Number.isFinite(area) ? `${area.toLocaleString("en-IN")} sq ft` : text });
  }
  if (typeof answers.plot_width_ft === "number" && typeof answers.plot_depth_ft === "number") {
    facts.splice(1, 0, { key: "plot", value: `${answers.plot_width_ft} × ${answers.plot_depth_ft} ft` });
  }

  // The latest request for quotes that is still alive.
  const rfq = rfqs?.rfqs.find((r) => r.state !== "CANCELLED") ?? null;
  const stages = execution?.stages ?? [];
  const versions = buildPlan?.versions ?? [];
  const issued = versions.find((v) => v.state === "ISSUED");
  const accepted = versions.find((v) => v.id === buildPlan?.accepted_version_id);
  const inspections = assurance?.inspections ?? [];
  const gates = stages.filter((s) => s.is_gate);

  const journey: JourneyFacts = {
    status: project.status,
    needsInfo: detail.review_message?.status === "NEEDS_INFO",
    packageActive: detail.package.state === "ACTIVE",
    packageEligible: detail.package.availability === "ELIGIBLE",
    buildPlan: {
      acceptedVersionNo: accepted?.version_no ?? null,
      issuedVersion: issued ? { id: issued.id, no: issued.version_no } : null,
      canAct: Boolean(buildPlan?.can_act),
    },
    // The Build Plan screen offers the family's decision on a SUBMITTED set (FamilyDecision).
    drawingSetsToReview: (buildPlan?.design_requests ?? []).flatMap((r) => r.sets).filter((s) => s.state === "SUBMITTED").length,
    rfq: {
      canRequest: Boolean(rfqs?.can_request),
      issued: rfq?.state === "ISSUED" || rfq?.state === "CLOSED",
      invited: rfq?.invitations.length ?? 0,
      quotesReceived: rfq?.comparison?.quotes.length ?? rfq?.invitations.filter((i) => i.latest_quote).length ?? 0,
      comparisonPublished: Boolean(rfq?.comparison),
      canSelect: Boolean(rfq?.can_select),
      selectedContractor: rfq?.selection?.contractor_name ?? rfq?.selection?.firm_name ?? rfqs?.engaged_contractor ?? null,
    },
    undecidedServices:
      detail.package.state === "ACTIVE" ? (services?.categories ?? []).filter((c) => c.need === "UNDECIDED").length : 0,
    build: {
      contractor: execution?.contractor?.name ?? null,
      stagesTotal: stages.length,
      stagesCompleted: stages.filter((s) => s.state === "COMPLETED").length,
      current: (() => {
        const active = stages.find((s) => s.state === "IN_PROGRESS" || s.state === "COMPLETION_REQUESTED");
        return active ? { name: active.name, number: active.stage_number } : null;
      })(),
      awaitingConfirmation:
        execution?.is_owner === false
          ? []
          : stages.filter((s) => s.state === "COMPLETION_REQUESTED").map((s) => ({ id: s.id, name: s.name, number: s.stage_number })),
    },
    verify: {
      inspections: inspections.length,
      gatesCleared: gates.filter((s) => s.gate_status === "CLEARED").length,
      gatesTotal: gates.length,
      openFindings: (assurance?.findings ?? []).filter((f) => f.state !== "CLOSED").length,
    },
    designs: {
      count: designs?.items.length ?? 0,
      freeRemaining: designs?.quota.free_remaining ?? 0,
      canGenerate: Boolean(designs?.quota.can_generate),
    },
  };

  const phase = currentPhase(journey);
  const phaseNotes: ProjectOverview["phaseNotes"] = {
    plan: accepted
      ? { key: "planAccepted", values: { version: accepted.version_no } }
      : journey.packageActive
        ? { key: "planPackage" }
        : project.status === "SUBMITTED"
          ? { key: "planReview" }
          : project.status === "DRAFT"
            ? { key: "planDraft" }
            : { key: "planFree" },
  };
  if (rfq) {
    phaseNotes.compare = rfq.comparison
      ? { key: "compareReady", values: { count: journey.rfq.quotesReceived } }
      : { key: "compareWaiting", values: { count: journey.rfq.invited } };
  }
  if (journey.rfq.selectedContractor) phaseNotes.select = { key: "selectDone", values: { name: journey.rfq.selectedContractor } };
  if (stages.length) {
    phaseNotes.build = journey.build.current
      ? { key: "buildNow", values: { number: journey.build.current.number, name: journey.build.current.name } }
      : { key: "buildCount", values: { done: journey.build.stagesCompleted, total: stages.length } };
  }
  if (gates.length) phaseNotes.verify = { key: "verifyGates", values: { done: journey.verify.gatesCleared, total: gates.length } };

  const contractorEngagement = execution?.contractor?.engagement_id ?? null;
  const team: TeamMember[] = (services?.categories ?? [])
    .flatMap((category) => {
      const engagement = category.engagement;
      if (!engagement || engagement.state !== "ACTIVE") return [];
      const contact = engagement.professional_contact;
      return [
        {
          id: engagement.id,
          name: contact?.name ?? engagement.name ?? engagement.firm ?? category.name,
          firm: contact?.firm ?? engagement.firm ?? null,
          role: category.name,
          code: category.code,
          primary: engagement.id === contractorEngagement || category.code === "CONTRACTOR",
          outside: engagement.party === "OUTSIDE",
          phone: contact?.phone ?? (engagement.party === "OUTSIDE" ? (engagement.contact ?? null) : null),
          email: contact?.email ?? null,
          since: engagement.started_at,
        },
      ];
    })
    .sort((a, b) => Number(b.primary) - Number(a.primary));

  const lines = (workspace?.groups ?? []).flatMap((group) => group.lines);
  const milestones = payments?.milestones ?? [];
  const reviewed = !["DRAFT", "SUBMITTED", "NEEDS_INFO"].includes(project.status);
  const progress: Progress = {
    planning: [
      { key: "requirement", done: project.status !== "DRAFT" },
      { key: "review", done: reviewed },
      { key: "package", done: journey.packageActive },
      { key: "buildPlan", done: accepted !== undefined },
      { key: "quotes", done: journey.rfq.issued },
      { key: "contractor", done: Boolean(journey.rfq.selectedContractor || journey.build.contractor) },
    ],
    construction: stages.length ? { done: journey.build.stagesCompleted, total: stages.length } : null,
    verification: gates.length ? { done: journey.verify.gatesCleared, total: gates.length } : null,
    decisions: lines.length
      ? { done: lines.filter((line) => line.state !== "SPECIFIED" && line.state !== "OPTIONS_ISSUED").length, total: lines.length }
      : null,
    payments: milestones.length
      ? { done: milestones.filter((milestone) => milestone.paid?.value === "YES").length, total: milestones.length }
      : null,
  };

  // What happened, from the dates each record keeps. Nothing here is a stored event: a date the
  // API does not record (a message, a payment amount) does not appear.
  const activity: ActivityItem[] = [];
  const add = (id: string, kind: ActivityKind, at: string | null | undefined, values: ActivityItem["values"] = {}) => {
    if (at) activity.push({ id, kind, at, values });
  };
  add("submitted", "submitted", project.submitted_at);
  for (const design of designs?.items ?? []) {
    if (design.state === "SUCCEEDED") add(`design-${design.design_id}`, "design", design.created_at, { number: design.sequence });
  }
  for (const version of versions) {
    add(`plan-${version.id}`, "planIssued", version.issued_at, { version: version.version_no });
    add(`plan-accepted-${version.id}`, "planAccepted", version.accepted_at, { version: version.version_no });
  }
  if (rfq) {
    add(`rfq-${rfq.id}`, "quotesRequested", rfq.issued_at, { count: rfq.invitations.length });
    add(`comparison-${rfq.id}`, "quotesCompared", rfq.comparison?.published_at, { count: journey.rfq.quotesReceived });
    add(`selection-${rfq.id}`, "contractorChosen", rfq.selection?.selected_at, {
      name: rfq.selection?.firm_name ?? rfq.selection?.contractor_name ?? "",
    });
  }
  for (const member of team) add(`team-${member.id}`, "teamJoined", member.since, { name: member.firm ?? member.name, role: member.role });
  for (const stage of stages) {
    const values = { number: stage.stage_number, name: stage.name };
    add(`start-${stage.id}`, "stageStarted", stage.actual_start, values);
    add(`end-${stage.id}`, "stageDone", stage.actual_end, values);
  }
  for (const inspection of inspections) {
    if (inspection.state === "APPROVED") {
      add(`inspection-${inspection.id}`, "inspectionPassed", inspection.approved_at, { gate: inspection.gate, name: inspection.stage_name });
    }
  }
  for (const finding of assurance?.findings ?? []) {
    add(`finding-${finding.id}`, "findingClosed", finding.closed_at, { name: finding.stage_name });
  }
  // Stage dates are days, not moments: a day sorts as its end, so "started today" sits with today.
  const moment = (at: string) => (at.length === 10 ? `${at}T23:59:59.999Z` : new Date(at).toISOString());
  activity.sort((a, b) => moment(b.at).localeCompare(moment(a.at)));

  return {
    project: { id, code: project.code, locality: project.locality ?? null, status: project.status },
    facts,
    floorsAbove: floorsAbove(answers.floors),
    phase,
    phases: phaseStates(journey),
    phaseNotes,
    actions: nextActions(journey),
    waiting: waitingReason(journey),
    estimate: estimate
      ? {
          range: estimate.figures ? { low: estimate.figures.total_low, high: estimate.figures.total_high } : null,
          isDemo: Boolean(estimate.figures?.rate_card.is_demo),
          unavailable: estimate.figures
            ? null
            : { reason: estimate.unavailable_reason ?? "NO_RATE_CARD", city: estimate.inputs.city },
        }
      : null,
    designs: (designs?.items ?? []).filter((d) => d.state === "SUCCEEDED").slice(0, 4),
    heroDesign:
      [...(designs?.items ?? [])]
        .filter((d) => d.state === "SUCCEEDED" && d.image_url)
        .sort((a, b) => b.sequence - a.sequence)[0] ?? null,
    siteVisual: built ? await loadSiteVisual(api, id, stages) : null,
    assurance: built
      ? {
          auditorCode:
            [...inspections].sort((a, b) => b.scheduled_at.localeCompare(a.scheduled_at)).find((i) => i.auditor_code)
              ?.auditor_code ?? null,
          inspections: inspections.length,
          scheduled: inspections.filter((i) => i.state === "SCHEDULED" || i.state === "IN_PROGRESS").length,
        }
      : null,
    pkg: {
      state: detail.package.state,
      availability: detail.package.availability,
      purchasable: detail.package.purchasable,
    },
    designQuota: designs
      ? {
          count: designs.items.length,
          freeRemaining: designs.quota.free_remaining,
          freeTotal: designs.quota.free_total,
          canGenerate: designs.quota.can_generate,
          block: designs.quota.block ?? null,
        }
      : null,
    team,
    progress,
    activity,
    quotes: open
      ? {
          request: journey.rfq.issued
            ? "sent"
            : !journey.packageActive
              ? "needsPackage"
              : journey.buildPlan.acceptedVersionNo === null
                ? "needsPlan"
                : journey.rfq.canRequest
                  ? "ready"
                  : "unavailable",
          compare: journey.rfq.comparisonPublished ? "ready" : journey.rfq.issued ? "waiting" : "notYet",
          invited: journey.rfq.invited,
          received: journey.rfq.quotesReceived,
          canSelect: journey.rfq.canSelect,
          selected: journey.rfq.selectedContractor,
        }
      : null,
    stages,
  };
}

/** One overview per request, shared by the project layout (its journey navigation) and the overview page. */
export const getProjectOverview = cache(async (projectId: string): Promise<ProjectOverview> => {
  const common = getTranslator("Common");
  return loadProjectOverview(await loadProject(projectId), {
    yes: common("yes"),
    no: common("no"),
    notSure: common("notSure"),
  });
});
