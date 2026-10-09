// The professional's command center as a domain model: what needs them, where their opportunities
// stand, the work on site, how ready their listing is, and their record. Built from the API's
// responses by one pure function (buildConsole), so components never read raw API shapes and the
// rules can be tested. Facts only: no ratings (the directory is not a ranking), no percentages
// (EX-02) and no amounts (CD-09).
import type { components } from "@p2b/contracts";

type S = components["schemas"];
export type Dashboard = S["OwnDashboardOut"];
export type Connection = S["ProConnectionOut"];
export type Invitation = S["ProInvitationSummaryOut"];
export type Inspection = S["AuditorInspectionSummary"];
export type Stage = S["StageOut"];
export type DesignRequest = S["ProDesignRequestOut"];
export type Signoff = S["ProSignoffOut"];
export type HandoverState = S["HandoverState"];

/**
 * An engagement the professional holds, whatever brought it (an accepted request or a selected
 * quote; ADR-024), with its stages and handover when readable. The one record behind the
 * project workspace, the project sheets and the work queue.
 */
export interface Engagement {
  engagementId: string;
  projectCode: string;
  category: string;
  categoryCode: string;
  origin: "rfq" | "connection";
  startedAt: string;
  ended: boolean;
  locality: string | null;
  /** The family's name, shared once the engagement exists. */
  family: string | null;
  stages: Stage[];
  /** The handover's state once one is open; null before. */
  handover: HandoverState | null;
}

/** The trades a professional works in, as the API names them (service_categories). */
export interface Roles {
  contractor: boolean;
  architect: boolean;
  engineer: boolean;
}

export function rolesOf(dashboard: Pick<Dashboard, "categories">): Roles {
  const codes = new Set(dashboard.categories.map((c) => c.code));
  return {
    contractor: codes.has("CONTRACTOR"),
    architect: codes.has("ARCHITECT") || codes.has("INTERIOR_DESIGNER"),
    engineer: codes.has("STRUCTURAL_ENGINEER"),
  };
}

export interface ConsoleInput {
  dashboard: Dashboard;
  connections: Connection[];
  invitations: Invitation[];
  /** Null when the professional is not an appointed auditor. */
  inspections: Inspection[] | null;
  engagements: Engagement[];
  /** Drawing requests addressed to them (architects) and versions to sign (structural engineers). */
  drawings?: DesignRequest[];
  signoffs?: Signoff[];
  now: Date;
}

/**
 * Which dashboard the professional sees. `setup`: building their presence. `review`: submitted,
 * waiting for Plan2Build. `listed`: discoverable, opportunities lead. `working`: projects on site.
 */
export type ConsoleState = "setup" | "review" | "listed" | "working";

export type ListingStatus = "listed" | "review" | "changes" | "draft" | "none" | "suspended";

export type QueueKind = "connection" | "quote" | "inspection" | "finding" | "drawing" | "signoff" | "handover";

/**
 * How Today orders the queue (decided 2026-10-08): what is dated or assigned first, then what
 * waits for an answer, then what waits for a review, then what completes a project. Setup never
 * outranks any of these; the listing notice sits beside the work, not in front of it.
 */
export type QueueGroup = "urgent" | "respond" | "review" | "complete";
export const QUEUE_GROUPS: QueueGroup[] = ["urgent", "respond", "review", "complete"];

export interface QueueItem {
  kind: QueueKind;
  group: QueueGroup;
  id: string;
  href: string;
  title: string;
  place: string | null;
  due: { kind: "respond" | "quotes" | "scheduled"; at: string; soon: boolean } | null;
  /** What the family asked for, as far as the brief says (a request only; names stay private until accepted). */
  brief: { floors: number | null; area: number | null } | null;
}

export interface Attention {
  items: QueueItem[];
  /** The kind of the most urgent item, how many of that kind wait, and when the soonest is due. */
  lead: { kind: QueueKind; count: number; soonest: { when: "today" | "tomorrow" | "later"; at: string } | null } | null;
}

export type PipelineKey = "requests" | "rfqs" | "quoted" | "projects";

export interface PipelineNode {
  key: PipelineKey;
  count: number;
  href: string;
  /** Something here waits on the professional. */
  hot: boolean;
}

export type SegmentLook = "done" | "active" | "held" | "todo";

export type ProjectNext =
  | { key: "rectify"; stage: string }
  | { key: "awaitSignoff"; stage: string }
  | { key: "postUpdate"; stage: string }
  | { key: "start"; stage: string }
  | { key: "onHold"; stage: string }
  | { key: "complete" }
  | { key: "openEngagement" }
  | { key: "contactFamily" };

export interface ProjectSheet {
  id: string;
  href: string;
  code: string | null;
  category: string;
  place: string | null;
  origin: "rfq" | "connection";
  /** The family's name, once they are a client; null when the API has not shared it. */
  family: string | null;
  /** The current stage, as "05 of 16 · Superstructure"; null for a service engagement. */
  stage: { number: number; position: number; total: number; name: string; floor: number | null; look: SegmentLook } | null;
  /** One look per stage number, in building order. */
  segments: SegmentLook[];
  next: ProjectNext;
  since: string;
}

export type CheckpointKey = "profile" | "services" | "evidence" | "portfolio" | "listed";
export type CheckpointState = "done" | "current" | "next" | "attention" | "review";

export type Todo =
  | { key: "profileField"; field: string; href: string }
  | { key: "addService"; href: string }
  | { key: "evidence"; label: string; remaining: number; category: string; href: string }
  | { key: "submit"; category: string; href: string }
  | { key: "changes"; category: string; href: string }
  | { key: "portfolio"; href: string }
  | { key: "review"; category: string; href: string };

export interface Checkpoint {
  key: CheckpointKey;
  state: CheckpointState;
  href: string;
}

/**
 * The slim notice above the work while the listing is not finished: the step to do next and how
 * far along it is. Null once every checkpoint is done, so a finished profile leaves the page.
 */
export interface ListingNotice {
  key: "profile" | "services" | "evidence" | "portfolio" | "listed" | "review" | "attention";
  href: string;
  done: number;
}

export interface Service {
  code: string;
  name: string;
  state: Dashboard["categories"][number]["listing_state"];
  public: boolean;
  hidden: boolean;
  reviewDueAt: string | null;
  message: string | null;
  subtypes: string[];
}

export type RecordFact =
  | { key: "verified"; count: number; names: string[] }
  | { key: "replies"; answered: number; received: number }
  | { key: "quotes"; selected: number; submitted: number }
  | { key: "projects"; count: number }
  | { key: "inspections"; count: number };

export interface Console {
  state: ConsoleState;
  identity: {
    name: string | null;
    firm: string | null;
    /** The trade they are known for: a listed category first, else the first they added. */
    trade: string | null;
    base: string | null;
    years: number | null;
    team: number | null;
    listing: ListingStatus;
  };
  attention: Attention;
  pipeline: PipelineNode[];
  projects: ProjectSheet[];
  checkpoints: Checkpoint[];
  /** Checkpoints done, of five. */
  ready: number;
  notice: ListingNotice | null;
  todos: Todo[];
  services: Service[];
  addOptions: Dashboard["available_categories"];
  record: RecordFact[];
  inspections: { auditor: boolean; upcoming: QueueItem[] };
}

const SOON_MS = 2 * 24 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

const IST_MS = 330 * 60 * 1000;

/** Calendar days from `now` to `at`, in India time (every deadline is shown in IST). */
function dayDiff(at: Date, now: Date): number {
  const day = (d: Date) => Math.floor((d.getTime() + IST_MS) / DAY_MS);
  return day(at) - day(now);
}

/** Which group a thing waiting belongs to: dated and assigned work first. */
export function groupOf(kind: QueueKind, due: QueueItem["due"]): QueueGroup {
  if (kind === "inspection" || kind === "finding") return "urgent";
  if (kind === "connection" || kind === "quote") return due?.soon ? "urgent" : "respond";
  if (kind === "drawing" || kind === "signoff") return "review";
  return "complete";
}

/** Most urgent group first; within a group by the date due, undated last. */
export function sortQueue(items: QueueItem[]): QueueItem[] {
  return [...items].sort(
    (a, b) =>
      QUEUE_GROUPS.indexOf(a.group) - QUEUE_GROUPS.indexOf(b.group) ||
      (a.due?.at ?? "9999").localeCompare(b.due?.at ?? "9999"),
  );
}

export interface QueueWork {
  drawings: DesignRequest[];
  signoffs: Signoff[];
  engagements: Engagement[];
}

/**
 * The work queue: everything waiting on the professional, from every domain the API has
 * (requests, requests to quote, inspections, drawing sets, structural sign-offs, handover), each
 * keeping its own kind. Open findings join through findingItems.
 */
export function buildQueue(
  connections: Connection[],
  invitations: Invitation[],
  inspections: Inspection[] | null,
  now: Date,
  work: QueueWork = { drawings: [], signoffs: [], engagements: [] },
): QueueItem[] {
  const due = (kind: "respond" | "quotes" | "scheduled", at: string) => ({
    kind,
    at,
    soon: new Date(at).getTime() - now.getTime() < SOON_MS,
  });
  const item = (kind: QueueKind, rest: Omit<QueueItem, "kind" | "group">): QueueItem => ({
    kind,
    group: groupOf(kind, rest.due),
    ...rest,
  });
  return sortQueue([
    ...connections
      .filter((c) => c.state === "SENT")
      .map((c) =>
        item("connection", {
          id: c.id,
          href: `/connections/${c.id}`,
          title: c.category_name,
          place: c.brief.locality ?? null,
          due: due("respond", c.respond_by),
          brief: { floors: c.brief.floors ?? null, area: c.brief.built_up_area_sqft ?? null },
        }),
      ),
    ...invitations.filter(waitsOnQuote).map((i) => {
      const at = i.state === "SENT" ? i.respond_by : i.quotes_due_at;
      return item("quote", {
        id: i.id,
        href: `/quotes/${i.id}`,
        title: i.locality ?? "",
        place: null,
        due: at ? due(i.state === "SENT" ? "respond" : "quotes", at) : null,
        brief: null,
      });
    }),
    ...(inspections ?? [])
      .filter((i) => i.state === "SCHEDULED" || i.state === "IN_PROGRESS")
      .map((i) =>
        item("inspection", {
          id: i.id,
          href: `/inspections/${i.id}`,
          title: `${i.project_code} · ${i.stage_number}. ${i.stage_name}`,
          place: null,
          due: due("scheduled", i.scheduled_at),
          brief: null,
        }),
      ),
    // A drawing request with no set on its way to the family yet (none, a draft, or changes asked).
    ...work.drawings
      .filter((d) => d.request.can_provide && !d.request.sets.some((s) => ["SUBMITTED", "IN_CHECK", "APPROVED"].includes(s.state)))
      .map((d) => item("drawing", { id: d.request.id, href: "/build-plan", title: d.project_code, place: null, due: null, brief: null })),
    ...work.signoffs
      .filter((s) => s.state === "IN_REVIEW" && s.lines.some((line) => !line.signed))
      .map((s) =>
        item("signoff", {
          id: s.version_id,
          href: `/build-plan/signoffs/${s.version_id}`,
          title: `${s.project_code} · v${s.version_no}`,
          place: null,
          due: null,
          brief: null,
        }),
      ),
    ...work.engagements
      .filter((e) => !e.ended && e.handover === "OPEN")
      .map((e) =>
        item("handover", {
          id: e.engagementId,
          href: `/engagements/${e.engagementId}/execution#handover`,
          title: e.projectCode,
          place: e.locality,
          due: null,
          brief: null,
        }),
      ),
  ]);
}

/** An invitation waiting on the professional: to agree to quote, or open with no quote yet. */
function waitsOnQuote(i: Invitation): boolean {
  return i.state === "SENT" || (i.state === "ACCEPTED" && i.rfq_open && !i.outcome);
}

/** An open inspection finding on a project: work that waits on the professional, undated. */
export function findingItems(projects: ProjectSheet[]): QueueItem[] {
  return projects
    .filter((sheet) => sheet.next.key === "rectify")
    .map((sheet) => ({
      kind: "finding" as const,
      group: "urgent" as const,
      id: sheet.id,
      href: sheet.href,
      title: `${sheet.code ?? sheet.category} · ${"stage" in sheet.next ? sheet.next.stage : ""}`,
      place: sheet.place,
      due: null,
      brief: null,
    }));
}

function attentionOf(queue: QueueItem[], now: Date): Attention {
  const first = queue[0];
  if (!first) return { items: [], lead: null };
  const same = queue.filter((item) => item.kind === first.kind);
  const soonest = same.find((item) => item.due)?.due ?? null;
  const days = soonest ? dayDiff(new Date(soonest.at), now) : null;
  return {
    items: queue,
    lead: {
      kind: first.kind,
      count: same.length,
      soonest:
        soonest && days !== null && soonest.soon
          ? { when: days <= 0 ? "today" : days === 1 ? "tomorrow" : "later", at: soonest.at }
          : null,
    },
  };
}

function lookOf(stages: Stage[]): SegmentLook {
  if (stages.some((s) => s.state === "BLOCKED" || s.state === "ON_HOLD")) return "held";
  if (stages.every((s) => s.state === "COMPLETED")) return "done";
  if (stages.some((s) => s.state !== "NOT_STARTED")) return "active";
  return "todo";
}

/** An engagement as a sheet: one segment per stage number, the current stage and the next step. */
export function sheetOf(project: Engagement): ProjectSheet {
  const sorted = [...project.stages].sort((a, b) => a.sequence - b.sequence);
  const numbers = [...new Set(sorted.map((s) => s.stage_number))];
  const groups = numbers.map((n) => sorted.filter((s) => s.stage_number === n));
  const segments = groups.map(lookOf);
  const at = segments.findIndex((look) => look !== "done");
  const group = at >= 0 ? groups[at] : null;
  // Within the current stage number, the instance being worked (a floor), else the first open one.
  const instance =
    group?.find((s) => s.state !== "NOT_STARTED" && s.state !== "COMPLETED") ?? group?.find((s) => s.state !== "COMPLETED") ?? null;
  const label = (s: Stage) => (s.floor !== null && s.floor !== undefined ? `${s.name} (${floorName(s.floor)})` : s.name);

  let next: ProjectNext;
  const open = sorted.find((s) => s.gate_status === "OPEN_NC");
  const asked = sorted.find((s) => s.state === "COMPLETION_REQUESTED");
  const working = sorted.find((s) => s.state === "IN_PROGRESS");
  const held = sorted.find((s) => s.state === "BLOCKED" || s.state === "ON_HOLD");
  if (sorted.length === 0) next = { key: project.origin === "connection" ? "contactFamily" : "openEngagement" };
  else if (open) next = { key: "rectify", stage: label(open) };
  else if (held) next = { key: "onHold", stage: label(held) };
  else if (working) next = { key: "postUpdate", stage: label(working) };
  else if (asked) next = { key: "awaitSignoff", stage: label(asked) };
  else if (instance) next = { key: "start", stage: label(instance) };
  else next = { key: "complete" };

  return {
    id: project.engagementId,
    href: sorted.length ? `/engagements/${project.engagementId}/execution` : `/engagements/${project.engagementId}`,
    code: project.projectCode,
    category: project.category,
    place: project.locality,
    origin: project.origin,
    family: project.family,
    stage:
      instance && at >= 0
        ? {
            number: instance.stage_number,
            position: at + 1,
            total: groups.length,
            name: instance.name,
            floor: instance.floor ?? null,
            look: segments[at],
          }
        : null,
    segments,
    next,
    since: project.startedAt,
  };
}

function floorName(floor: number): string {
  if (floor < 0) return "basement";
  if (floor === 0) return "ground floor";
  return `floor ${floor}`;
}

function listingOf(categories: Dashboard["categories"]): ListingStatus {
  const states = categories.map((c) => c.listing_state);
  if (states.includes("LISTED")) return "listed";
  if (states.includes("CHANGES_REQUESTED")) return "changes";
  if (states.includes("PENDING_REVIEW")) return "review";
  if (states.includes("SUSPENDED")) return "suspended";
  if (states.length) return "draft";
  return "none";
}

/**
 * The five checkpoints of a listing (PROFESSIONALS_FLOW 44.2) in the order the API needs them:
 * profile, a service, portfolio photos (most trades need them before submitting), the trade's own
 * verification requirements (from the API, never a fixed list), then submitting for review.
 */
export function readinessOf(dashboard: Dashboard): { checkpoints: Checkpoint[]; todos: Todo[]; ready: number } {
  const { profile, categories, portfolio } = dashboard;
  const states = categories.map((c) => c.listing_state);
  const draft = categories.find((c) => c.listing_state === "DRAFT" || c.listing_state === "CHANGES_REQUESTED");
  const submitted = states.some((s) => s !== "DRAFT");
  const listed = states.includes("LISTED");
  const changes = categories.find((c) => c.listing_state === "CHANGES_REQUESTED");
  const reviewing = categories.find((c) => c.listing_state === "PENDING_REVIEW");

  const done: Record<CheckpointKey, boolean> = {
    profile: profile.missing.length === 0,
    services: categories.length > 0,
    evidence: submitted && !changes,
    portfolio: portfolio.length > 0,
    listed,
  };
  const href: Record<CheckpointKey, string> = {
    profile: "/profile",
    services: "/services#add",
    evidence: draft ? `/categories/${draft.code}` : "/services",
    portfolio: "/portfolio",
    // Submitting happens on the service's own page, where the button is.
    listed: draft ? `/categories/${draft.code}` : "/services",
  };
  const order: CheckpointKey[] = ["profile", "services", "portfolio", "evidence", "listed"];
  const firstOpen = order.findIndex((key) => !done[key]);
  const checkpoints = order.map((key, index): Checkpoint => {
    let state: CheckpointState = done[key] ? "done" : index === firstOpen ? "current" : "next";
    if (key === "evidence" && changes) state = "attention";
    if (key === "listed" && !listed && reviewing) state = "review";
    return { key, state, href: href[key] };
  });

  const todos: Todo[] = [];
  if (!listed) {
    // One line per named field; any field the console does not name yet shares one line.
    const named = new Set(["display_name", "base_locality", "base_geom", "service_radius_km", "years_experience", "bio"]);
    const fields = [...new Set(profile.missing.map((field) => (named.has(field) ? field : "other")))];
    for (const field of fields) todos.push({ key: "profileField", field, href: "/profile" });
    if (categories.length === 0) todos.push({ key: "addService", href: "/services#add" });
    if (changes) todos.push({ key: "changes", category: changes.name, href: `/categories/${changes.code}` });
    const working = categories.find((c) => c.listing_state === "DRAFT");
    if (working) {
      // What the API says is still needed before submitting; a site visit is Plan2Build's to make.
      const gaps = working.requirements.filter(
        (r) => working.missing_requirements.includes(r.id) && !(r.accepts.length === 1 && r.accepts[0] === "SITE_VISIT"),
      );
      for (const gap of gaps)
        todos.push({
          key: "evidence",
          label: gap.label,
          remaining: Math.max(1, gap.count - gap.provided),
          category: working.name,
          href: `/categories/${working.code}`,
        });
      if (gaps.length === 0 && profile.missing.length === 0)
        todos.push({ key: "submit", category: working.name, href: `/categories/${working.code}` });
    }
    if (portfolio.length === 0) todos.push({ key: "portfolio", href: "/portfolio" });
    if (reviewing && !changes) todos.push({ key: "review", category: reviewing.name, href: `/categories/${reviewing.code}` });
  }
  return { checkpoints, todos, ready: order.filter((key) => done[key]).length };
}

export function buildConsole(input: ConsoleInput): Console {
  const { dashboard, connections, invitations, inspections, engagements, drawings = [], signoffs = [], now } = input;
  const listing = listingOf(dashboard.categories);

  // Every active engagement, whatever brought it. An accepted request the API has not linked to
  // its engagement (older contracts) still shows, through the request page.
  const known = new Set(engagements.map((e) => e.engagementId));
  const projects: ProjectSheet[] = [
    ...engagements.filter((p) => !p.ended).map(sheetOf),
    ...connections
      .filter((c) => c.engagement_state === "ACTIVE" && !(c.engagement_id && known.has(c.engagement_id)))
      .map(
        (c): ProjectSheet => ({
          id: c.id,
          href: `/connections/${c.id}`,
          code: null,
          category: c.category_name,
          place: c.brief.locality ?? null,
          origin: "connection",
          family: c.family_contact?.name ?? null,
          stage: null,
          segments: [],
          next: { key: "contactFamily" },
          since: c.responded_at ?? c.sent_at,
        }),
      ),
  ];

  const queue = sortQueue([...buildQueue(connections, invitations, inspections, now, { drawings, signoffs, engagements }), ...findingItems(projects)]);
  const requests = connections.filter((c) => c.state === "SENT").length;
  const rfqs = invitations.filter(waitsOnQuote).length;
  const quoted = invitations.filter((i) => i.outcome === "SUBMITTED").length;
  const pipeline: PipelineNode[] = [
    { key: "requests", count: requests, href: "/connections", hot: requests > 0 },
    { key: "rfqs", count: rfqs, href: "/quotes", hot: rfqs > 0 },
    { key: "quoted", count: quoted, href: "/quotes", hot: false },
    { key: "projects", count: projects.length, href: "/projects", hot: false },
  ];

  const { checkpoints, todos, ready } = readinessOf(dashboard);
  const next = checkpoints.find((cp) => cp.state !== "done");
  const notice: ListingNotice | null = next
    ? {
        key: next.state === "review" ? "review" : next.state === "attention" ? "attention" : next.key,
        href: next.href,
        done: ready,
      }
    : null;

  const listedCats = dashboard.categories.filter((c) => c.listing_state === "LISTED");
  const answered = connections.filter((c) => c.responded_at).length;
  const expired = connections.filter((c) => c.state === "EXPIRED" && !c.responded_at).length;
  const submittedQuotes = invitations.filter((i) => i.outcome && i.outcome !== "WITHDRAWN").length;
  const selected = invitations.filter((i) => i.outcome === "SELECTED").length;
  const worked = new Set([...engagements.map((e) => e.engagementId), ...connections.flatMap((c) => (c.engagement_state && !c.engagement_id ? [c.id] : []))]).size;
  const signed = (inspections ?? []).filter((i) => i.state === "SUBMITTED" || i.state === "APPROVED").length;
  const record: RecordFact[] = [
    ...(listedCats.length ? [{ key: "verified" as const, count: listedCats.length, names: listedCats.map((c) => c.name) }] : []),
    ...(answered + expired > 0 ? [{ key: "replies" as const, answered, received: answered + expired }] : []),
    ...(submittedQuotes > 0 ? [{ key: "quotes" as const, selected, submitted: submittedQuotes }] : []),
    ...(worked > 0 ? [{ key: "projects" as const, count: worked }] : []),
    ...(inspections && signed > 0 ? [{ key: "inspections" as const, count: signed }] : []),
  ];

  const state: ConsoleState =
    projects.length > 0
      ? "working"
      : listing === "listed" || queue.length > 0
        ? "listed"
        : listing === "review"
          ? "review"
          : "setup";

  const added = new Set(dashboard.categories.map((c) => c.code));
  const trade = listedCats[0]?.name ?? dashboard.categories[0]?.name ?? null;

  return {
    state,
    identity: {
      name: dashboard.profile.display_name,
      firm: dashboard.profile.firm_name,
      trade,
      base: dashboard.profile.base_locality,
      years: dashboard.profile.years_experience,
      team: dashboard.profile.team_size,
      listing,
    },
    attention: attentionOf(queue, now),
    pipeline,
    projects,
    checkpoints,
    ready,
    notice,
    todos,
    services: dashboard.categories.map((c) => ({
      code: c.code,
      name: c.name,
      state: c.listing_state,
      public: c.public,
      hidden: c.hidden,
      reviewDueAt: c.review_due_at,
      message: c.message,
      subtypes: c.subtypes,
    })),
    addOptions: dashboard.available_categories.filter((c) => !c.parent_code && !added.has(c.code)),
    record,
    inspections: { auditor: inspections !== null, upcoming: queue.filter((item) => item.kind === "inspection") },
  };
}
