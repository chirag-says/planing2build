// Server-side gate for professionals-host pages: signed in on this host, or off to sign-in. The
// API checks every call again.
import type { components } from "@p2b/contracts";
import { redirect } from "next/navigation";
import { cache } from "react";

import { serverApi } from "@/lib/api/server";
import {
  buildConsole,
  buildQueue,
  findingItems,
  sheetOf,
  type Connection,
  type Console,
  type Inspection,
  type Invitation,
  type QueueItem,
  type WonProject,
} from "@/lib/pro-console";

export type ProDashboard = components["schemas"]["OwnDashboardOut"];

export async function signedInProfessional(): Promise<boolean> {
  const { data, response } = await (await serverApi()).GET("/api/v1/me");
  if (data) return true;
  if (response.status === 401) return false;
  throw new Error(`session check failed with status ${response.status}`);
}

/**
 * The professional's own dashboard data, or a redirect to sign-in when signed out. An incomplete
 * profile does not hold anyone back: the dashboard asks for the missing details, and the API
 * refuses a listing until they are in.
 */
export async function loadOwnProfile(returnTo: string): Promise<ProDashboard> {
  const { data, response } = await (await serverApi()).GET("/api/v1/pro/profile");
  if (response.status === 401) redirect(`/sign-in?next=${encodeURIComponent(returnTo)}`);
  if (!data) throw new Error("the professional profile could not be loaded");
  return data;
}

export interface ProCounts {
  /** Connection requests waiting for the professional's reply. */
  requests: number;
  /** Requests to quote that are open for a reply or a quote. */
  quotes: number;
  /** Inspections scheduled or under way (appointed auditors only). */
  inspections: number;
  /** Projects on site: active engagements from requests and from selected quotes. */
  projects: number;
  /** Open inspection findings on their projects, waiting for a correction. */
  findings: number;
  /** Whether the professional is an appointed auditor (the inspections list is theirs). */
  auditor: boolean;
}

/** One thing waiting for the professional, as the work queue shows it. */
export type ProQueueItem = QueueItem;

export interface ProRaw {
  connections: Connection[];
  invitations: Invitation[];
  /** Null when the API does not return an inspections list for this person (not an auditor). */
  inspections: Inspection[] | null;
}

/**
 * The professional's lists, read once per request for the shell, the dashboard and the queue. A
 * list the API does not return for this person counts as nothing waiting.
 */
export const loadProRaw = cache(async (): Promise<ProRaw> => {
  const api = await serverApi();
  const [connections, invitations, inspections] = await Promise.all([
    api.GET("/api/v1/pro/connections").then((r) => r.data).catch(() => undefined),
    api.GET("/api/v1/pro/rfq-invitations").then((r) => r.data).catch(() => undefined),
    api.GET("/api/v1/pro/inspections").then((r) => r.data).catch(() => undefined),
  ]);
  return {
    connections: connections?.items ?? [],
    invitations: invitations?.items ?? [],
    inspections: inspections ? inspections.items : null,
  };
});

/**
 * Projects won through a request to quote: each selected quote's engagement and its stages. A few
 * reads per won project, so only the screens that show the work call it.
 */
export const loadWonProjects = cache(async (): Promise<WonProject[]> => {
  const api = await serverApi();
  const { invitations } = await loadProRaw();
  const selected = invitations.filter((i) => i.outcome === "SELECTED");
  const won = await Promise.all(
    selected.map(async (invitation): Promise<WonProject | null> => {
      const detail = await api
        .GET("/api/v1/pro/rfq-invitations/{invitation_id}", { params: { path: { invitation_id: invitation.id } } })
        .then((r) => r.data)
        .catch(() => undefined);
      const engagementId = detail?.engagement_id;
      if (!engagementId) return null;
      const path = { params: { path: { engagement_id: engagementId } } };
      const [engagement, execution] = await Promise.all([
        api.GET("/api/v1/pro/engagements/{engagement_id}", path).then((r) => r.data).catch(() => undefined),
        api.GET("/api/v1/pro/engagements/{engagement_id}/execution", path).then((r) => r.data).catch(() => undefined),
      ]);
      if (!engagement) return null;
      return {
        invitationId: invitation.id,
        engagementId,
        projectCode: engagement.project_code,
        category: engagement.category_name,
        startedAt: engagement.started_at,
        ended: engagement.state === "ENDED",
        locality: invitation.locality,
        family: engagement.family_contact?.name ?? null,
        stages: execution?.stages ?? [],
      };
    }),
  );
  return won.filter((project): project is WonProject => project !== null);
});

/** The whole command center for the dashboard. */
export async function loadConsole(returnTo: string): Promise<Console> {
  const [dashboard, raw, won] = await Promise.all([loadOwnProfile(returnTo), loadProRaw(), loadWonProjects()]);
  return buildConsole({ dashboard, ...raw, won, now: new Date() });
}

export interface ProWork {
  counts: ProCounts;
  /** Most urgent first: by the date it is due, undated last. */
  queue: ProQueueItem[];
}

/** What is waiting for the professional, for the shell's counts and the notifications page. */
export const loadProWork = cache(async (): Promise<ProWork> => {
  const [{ connections, invitations, inspections }, won] = await Promise.all([loadProRaw(), loadWonProjects()]);
  const queue = [
    ...buildQueue(connections, invitations, inspections, new Date()),
    ...findingItems(won.filter((p) => !p.ended).map(sheetOf)),
  ];
  const count = (kind: ProQueueItem["kind"]) => queue.filter((item) => item.kind === kind).length;
  return {
    counts: {
      requests: count("connection"),
      quotes: count("quote"),
      inspections: count("inspection"),
      findings: count("finding"),
      projects: won.filter((p) => !p.ended).length + connections.filter((c) => c.engagement_state === "ACTIVE").length,
      auditor: inspections !== null,
    },
    queue,
  };
});

/** The counts beside the shell's links. */
export const loadProCounts = cache(async (): Promise<ProCounts> => (await loadProWork()).counts);

/**
 * The professional's own profile for the shell (the name they gave during onboarding), or null.
 * Never redirects and never throws; one read per request.
 */
export const ownProfileOrNull = cache(async (): Promise<ProDashboard | null> => {
  try {
    const { data } = await (await serverApi()).GET("/api/v1/pro/profile");
    return data ?? null;
  } catch {
    return null;
  }
});
