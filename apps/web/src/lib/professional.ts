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
  rolesOf,
  sheetOf,
  sortQueue,
  type Connection,
  type Console,
  type DesignRequest,
  type Engagement,
  type Inspection,
  type Invitation,
  type QueueItem,
  type Roles,
  type Signoff,
} from "@/lib/pro-console";
import { currentPath } from "@/lib/session";

export type ProDashboard = components["schemas"]["OwnDashboardOut"];

export async function signedInProfessional(): Promise<boolean> {
  const { data, response } = await (await serverApi()).GET("/api/v1/me");
  if (data) return true;
  if (response.status === 401) return false;
  throw new Error(`session check failed with status ${response.status}`);
}

/**
 * The professional's own dashboard data, or a redirect to sign-in when signed out (and back to
 * the page asked for afterwards). An incomplete profile does not hold anyone back: the dashboard
 * asks for the missing details, and the API refuses a listing until they are in.
 */
export async function loadOwnProfile(returnTo?: string): Promise<ProDashboard> {
  const { data, response } = await (await serverApi()).GET("/api/v1/pro/profile");
  if (response.status === 401) redirect(`/sign-in?next=${encodeURIComponent(returnTo ?? (await currentPath()))}`);
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
  /** Drawing sets to submit and versions to sign. */
  drawings: number;
  /** Whether the professional is an appointed auditor (the inspections list is theirs). */
  auditor: boolean;
  roles: Roles;
}

/** One thing waiting for the professional, as the work queue shows it. */
export type ProQueueItem = QueueItem;

export interface ProRaw {
  connections: Connection[];
  invitations: Invitation[];
  /** Null when the API does not return an inspections list for this person (not an auditor). */
  inspections: Inspection[] | null;
  drawings: DesignRequest[];
  signoffs: Signoff[];
}

/**
 * The professional's lists, read once per request for the shell, the dashboard and the queue. A
 * list the API does not return for this person counts as nothing waiting.
 */
export const loadProRaw = cache(async (): Promise<ProRaw> => {
  const api = await serverApi();
  const [connections, invitations, inspections, drawings, signoffs] = await Promise.all([
    api.GET("/api/v1/pro/connections").then((r) => r.data).catch(() => undefined),
    api.GET("/api/v1/pro/rfq-invitations").then((r) => r.data).catch(() => undefined),
    api.GET("/api/v1/pro/inspections").then((r) => r.data).catch(() => undefined),
    api.GET("/api/v1/pro/build-plan/design-requests").then((r) => r.data).catch(() => undefined),
    api.GET("/api/v1/pro/build-plan/signoffs").then((r) => r.data).catch(() => undefined),
  ]);
  return {
    connections: connections?.items ?? [],
    invitations: invitations?.items ?? [],
    inspections: inspections ? inspections.items : null,
    drawings: drawings?.items ?? [],
    signoffs: signoffs?.items ?? [],
  };
});

/**
 * Every engagement the professional holds, from the one place the API records each relationship:
 * an accepted request carries its engagement id, and a selected quote its own. Nothing is guessed
 * from page history. A few reads per engagement, so only the screens that show the work call it.
 */
export const loadEngagements = cache(async (): Promise<Engagement[]> => {
  const api = await serverApi();
  const { invitations, connections } = await loadProRaw();
  const fromQuotes = await Promise.all(
    invitations
      .filter((i) => i.outcome === "SELECTED")
      .map(async (invitation) => {
        const detail = await api
          .GET("/api/v1/pro/rfq-invitations/{invitation_id}", { params: { path: { invitation_id: invitation.id } } })
          .then((r) => r.data)
          .catch(() => undefined);
        return detail?.engagement_id ? { id: detail.engagement_id, locality: invitation.locality } : null;
      }),
  );
  const ids = new Map<string, string | null>();
  for (const c of connections) if (c.engagement_id) ids.set(c.engagement_id, c.brief.locality ?? null);
  for (const won of fromQuotes) if (won && !ids.has(won.id)) ids.set(won.id, won.locality);
  const engagements = await Promise.all(
    [...ids].map(async ([engagementId, locality]): Promise<Engagement | null> => {
      const path = { params: { path: { engagement_id: engagementId } } };
      const [engagement, execution, handover] = await Promise.all([
        api.GET("/api/v1/pro/engagements/{engagement_id}", path).then((r) => r.data).catch(() => undefined),
        api.GET("/api/v1/pro/engagements/{engagement_id}/execution", path).then((r) => r.data).catch(() => undefined),
        api.GET("/api/v1/pro/engagements/{engagement_id}/handover", path).then((r) => r.data).catch(() => undefined),
      ]);
      if (!engagement) return null;
      return {
        engagementId,
        projectCode: engagement.project_code,
        category: engagement.category_name,
        categoryCode: engagement.category,
        origin: engagement.origin === "RFQ_SELECTION" ? "rfq" : "connection",
        startedAt: engagement.started_at,
        ended: engagement.state === "ENDED",
        locality,
        family: engagement.family_contact?.name ?? null,
        stages: execution?.stages ?? [],
        handover: handover?.state ?? null,
      };
    }),
  );
  return engagements.filter((e): e is Engagement => e !== null);
});

/** The whole command center for the dashboard. */
export async function loadConsole(returnTo?: string): Promise<Console> {
  const [dashboard, raw, engagements] = await Promise.all([loadOwnProfile(returnTo), loadProRaw(), loadEngagements()]);
  return buildConsole({ dashboard, ...raw, engagements, now: new Date() });
}

export interface ProWork {
  counts: ProCounts;
  /** Most urgent first: by group (urgent, respond, review, complete), then the date due. */
  queue: ProQueueItem[];
}

/** What is waiting for the professional, for the shell's counts and the Needs attention page. */
export const loadProWork = cache(async (): Promise<ProWork> => {
  const [dashboard, raw, engagements] = await Promise.all([loadOwnProfile(), loadProRaw(), loadEngagements()]);
  const { connections, invitations, inspections, drawings, signoffs } = raw;
  const active = engagements.filter((e) => !e.ended);
  const queue = sortQueue([
    ...buildQueue(connections, invitations, inspections, new Date(), { drawings, signoffs, engagements }),
    ...findingItems(active.map(sheetOf)),
  ]);
  const count = (...kinds: ProQueueItem["kind"][]) => queue.filter((item) => kinds.includes(item.kind)).length;
  return {
    counts: {
      requests: count("connection"),
      quotes: count("quote"),
      inspections: count("inspection"),
      findings: count("finding"),
      drawings: count("drawing", "signoff"),
      projects: active.length,
      auditor: inspections !== null,
      roles: rolesOf(dashboard),
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
