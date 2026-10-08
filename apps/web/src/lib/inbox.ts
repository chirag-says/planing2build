// The homeowner's notifications (decided 2026-10-08: no sample data). The API has no
// notifications or messaging yet, so this module derives notifications from what the API records:
// "action required" from the next actions (lib/journey.ts) and project updates from the dates the
// API records (ProjectOverview.activity). Nothing here is invented; there are no message threads
// until the API has messaging. When the backend gains notifications, only this module changes.
import type { NextAction } from "@/lib/journey";
import type { ActivityItem, ActivityKind, ProjectOverview } from "@/lib/project-overview";

export type NotificationKind = "action" | "update" | "quote" | "inspection";

export interface InboxNotification {
  id: string;
  kind: NotificationKind;
  at: string;
  /** Needs the family: a next action of kind "act", until it is done. Activity is history, never unread. */
  unread: boolean;
  /** Where it leads, relative to the project's base path. */
  path: string;
  /** What it says: a next action or an activity. */
  source: { type: "action"; action: NextAction } | { type: "activity"; item: ActivityItem };
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

export function buildNotifications(overview: Pick<ProjectOverview, "actions" | "activity">, now: string): InboxNotification[] {
  const items: InboxNotification[] = [
    ...overview.actions.map((action, index) => ({
      id: `action-${action.key}-${index}`,
      kind: "action" as const,
      at: now,
      // Only what the family must do counts as new; "watch" actions are listed, not counted.
      unread: action.kind === "act",
      path: action.path,
      source: { type: "action" as const, action },
    })),
    ...overview.activity.map((item) => ({
      id: `activity-${item.id}`,
      kind: ACTIVITY_KIND[item.kind],
      at: item.at,
      unread: false,
      path: ACTIVITY_PATH[item.kind],
      source: { type: "activity" as const, item },
    })),
  ];
  // Stage dates are days, not moments: a day sorts as its end, as on the overview.
  const moment = (at: string) => (at.length === 10 ? `${at}T23:59:59.999Z` : new Date(at).toISOString());
  return items.sort((a, b) => moment(b.at).localeCompare(moment(a.at)));
}

/** The bell's count: what needs the family, from real items only. */
export function unreadCount(items: InboxNotification[]): number {
  return items.filter((item) => item.unread).length;
}

/** Today, yesterday or earlier, in the reader's day (India for now). */
export function dayGroup(at: string, now: string): "today" | "yesterday" | "earlier" {
  const day = (iso: string) => new Date(iso).toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  if (day(at) === day(now)) return "today";
  const yesterday = new Date(new Date(now).getTime() - 24 * 60 * 60 * 1000).toISOString();
  return day(at) === day(yesterday) ? "yesterday" : "earlier";
}
