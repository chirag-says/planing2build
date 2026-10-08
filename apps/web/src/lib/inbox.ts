// The homeowner's inbox: notifications and messages. PREVIEW (decided 2026-10-08): the API has no
// notifications or messaging yet, so this module builds them on the client side of the contract.
// What can be real is real: "action required" comes from the next actions (lib/journey.ts) and
// project updates from the dates the API records (ProjectOverview.activity). Message threads are
// sample conversations, marked as a preview wherever they appear, and nothing is sent anywhere.
// When the backend gains notifications and messages, only this module changes.
import type { NextAction } from "@/lib/journey";
import type { ActivityItem, ActivityKind, ProjectOverview, TeamMember } from "@/lib/project-overview";

export type NotificationKind = "action" | "update" | "quote" | "inspection" | "payment" | "message";

export interface InboxNotification {
  id: string;
  kind: NotificationKind;
  at: string;
  unread: boolean;
  /** Where it leads, relative to the project's base path. */
  path: string;
  /** What it says: a next action, an activity, or a message preview. */
  source:
    | { type: "action"; action: NextAction }
    | { type: "activity"; item: ActivityItem }
    | { type: "message"; from: string; role: string; text: string };
  /** Sample data, not from the server. */
  preview: boolean;
}

export interface ThreadMessage {
  id: string;
  from: "them" | "me";
  text: string;
  at: string;
}

export interface Thread {
  /** A team member's engagement id, or "plan2build". */
  id: string;
  name: string;
  role: string;
  phone: string | null;
  email: string | null;
  messages: ThreadMessage[];
  unread: number;
}

const ACTIVITY_KIND: Record<ActivityKind, NotificationKind> = {
  submitted: "update",
  design: "update",
  planIssued: "update",
  planAccepted: "update",
  quotesRequested: "quote",
  quotesCompared: "quote",
  contractorChosen: "quote",
  teamJoined: "update",
  stageStarted: "update",
  stageDone: "update",
  inspectionPassed: "inspection",
  findingClosed: "inspection",
};

const ACTIVITY_PATH: Record<ActivityKind, string> = {
  submitted: "/answers",
  design: "/designs",
  planIssued: "/build-plan",
  planAccepted: "/build-plan",
  quotesRequested: "/quotes",
  quotesCompared: "/quotes",
  contractorChosen: "/quotes",
  teamJoined: "/services",
  stageStarted: "/construction",
  stageDone: "/construction",
  inspectionPassed: "/construction#inspections",
  findingClosed: "/construction#inspections",
};

/** Minutes before `from`, as an ISO date: sample messages sit just behind the latest real event. */
function before(from: string, minutes: number): string {
  return new Date(new Date(from).getTime() - minutes * 60_000).toISOString();
}

/** Sample opening lines by role; plain and specific, the way a contractor or architect writes. */
const SAMPLE: Record<string, string[]> = {
  CONTRACTOR: [
    "Namaste. I have gone through the Build Plan and the site photos.",
    "Can we meet at the site on Saturday at 10 am to mark the setbacks?",
  ],
  ARCHITECT: [
    "The revised ground floor plan is ready. I moved the pooja room to the north-east as you asked.",
    "Shall I share it before Thursday's review?",
  ],
  default: ["Hello, I am looking forward to working on your home.", "Tell me a good time to call."],
};

function sampleThread(member: TeamMember, latest: string): Thread {
  const lines = SAMPLE[member.code] ?? SAMPLE.default;
  return {
    id: member.id,
    name: member.firm ?? member.name,
    role: member.role,
    phone: member.phone,
    email: member.email,
    messages: lines.map((text, index) => ({
      id: `${member.id}-${index}`,
      from: "them" as const,
      text,
      at: before(latest, (lines.length - index) * 37),
    })),
    unread: 1,
  };
}

/** The Plan2Build team's thread: always present, the project's own line to the people watching over it. */
function plan2buildThread(overview: ProjectOverview, latest: string, contact: { phone: string; email: string }): Thread {
  return {
    id: "plan2build",
    name: "Plan2Build",
    role: "Your project team",
    phone: contact.phone,
    email: contact.email,
    messages: [
      {
        id: "p2b-0",
        from: "them",
        text: `Welcome to Plan2Build. We are looking after project ${overview.project.code} with you; write here any time.`,
        at: before(latest, 24 * 60),
      },
    ],
    unread: 0,
  };
}

export function buildThreads(overview: ProjectOverview, contact: { phone: string; email: string }, now: string): Thread[] {
  const latest = overview.activity[0]?.at ?? now;
  return [...overview.team.map((member) => sampleThread(member, latest)), plan2buildThread(overview, latest, contact)];
}

export function buildNotifications(
  overview: ProjectOverview,
  threads: Thread[],
  now: string,
): InboxNotification[] {
  const items: InboxNotification[] = [
    ...overview.actions.map((action, index) => ({
      id: `action-${action.key}-${index}`,
      kind: "action" as const,
      at: now,
      unread: true,
      path: action.path,
      source: { type: "action" as const, action },
      preview: false,
    })),
    ...overview.activity.map((item) => ({
      id: `activity-${item.id}`,
      kind: ACTIVITY_KIND[item.kind],
      at: item.at,
      unread: false,
      path: ACTIVITY_PATH[item.kind],
      source: { type: "activity" as const, item },
      preview: false,
    })),
    ...threads
      .filter((thread) => thread.unread > 0)
      .map((thread) => {
        const last = thread.messages[thread.messages.length - 1]!;
        return {
          id: `message-${thread.id}`,
          kind: "message" as const,
          at: last.at,
          unread: true,
          path: `/messages?to=${thread.id}`,
          source: { type: "message" as const, from: thread.name, role: thread.role, text: last.text },
          preview: true,
        };
      }),
  ];
  // Stage dates are days, not moments: a day sorts as its end, as on the overview.
  const moment = (at: string) => (at.length === 10 ? `${at}T23:59:59.999Z` : new Date(at).toISOString());
  return items.sort((a, b) => moment(b.at).localeCompare(moment(a.at)));
}

/** Today, yesterday or earlier, in the reader's day (India for now). */
export function dayGroup(at: string, now: string): "today" | "yesterday" | "earlier" {
  const day = (iso: string) => new Date(iso).toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  if (day(at) === day(now)) return "today";
  const yesterday = new Date(new Date(now).getTime() - 24 * 60 * 60 * 1000).toISOString();
  return day(at) === day(yesterday) ? "yesterday" : "earlier";
}
