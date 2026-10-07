// Server-side gate for professionals-host pages: signed in on this host, or off to sign-in. The
// API checks every call again.
import type { components } from "@p2b/contracts";
import { redirect } from "next/navigation";
import { cache } from "react";

import { serverApi } from "@/lib/api/server";

export type ProDashboard = components["schemas"]["OwnDashboardOut"];

export async function signedInProfessional(): Promise<boolean> {
  const { data, response } = await (await serverApi()).GET("/api/v1/me");
  if (data) return true;
  if (response.status === 401) return false;
  throw new Error(`session check failed with status ${response.status}`);
}

/** Where a professional finishes onboarding: the profile, until every required field is in. */
export const ONBOARDING_PATH = "/profile";

/** True while the profile still lacks a required field: the professional is onboarding. */
export function isOnboarding(profile: ProDashboard | null): boolean {
  return profile === null || profile.profile.missing.length > 0;
}

/**
 * The professional's own dashboard data, or a redirect: to sign-in when signed out, to the
 * profile while it is incomplete (onboarding happens there, with no sidebar around it).
 */
export async function loadOwnProfile(returnTo: string): Promise<ProDashboard> {
  const { data, response } = await (await serverApi()).GET("/api/v1/pro/profile");
  if (response.status === 401) redirect(`/sign-in?next=${encodeURIComponent(returnTo)}`);
  if (!data) throw new Error("the professional profile could not be loaded");
  if (isOnboarding(data) && returnTo !== ONBOARDING_PATH) redirect(ONBOARDING_PATH);
  return data;
}

/**
 * For the work pages (requests, quotes, inspections, the Build Plan): a professional who has
 * not finished their profile is sent to it. Signed-out visitors and API failures pass through;
 * each page handles those itself.
 */
export async function requireOnboarded(): Promise<void> {
  const own = await ownProfileOrNull();
  if (own && isOnboarding(own)) redirect(ONBOARDING_PATH);
}

export interface ProCounts {
  /** Connection requests waiting for the professional's reply. */
  requests: number;
  /** Requests to quote that are open for a reply or a quote. */
  quotes: number;
  /** Inspections scheduled or under way (appointed auditors only). */
  inspections: number;
}

/**
 * What is waiting for the professional, for the sidebar counts and the dashboard tiles. One read
 * per request; a list the API does not return for this person counts as nothing waiting.
 */
export const loadProCounts = cache(async (): Promise<ProCounts> => {
  const api = await serverApi();
  const [connections, invitations, inspections] = await Promise.all([
    api.GET("/api/v1/pro/connections").then((r) => r.data).catch(() => undefined),
    api.GET("/api/v1/pro/rfq-invitations").then((r) => r.data).catch(() => undefined),
    api.GET("/api/v1/pro/inspections").then((r) => r.data).catch(() => undefined),
  ]);
  return {
    requests: (connections?.items ?? []).filter((c) => c.state === "SENT").length,
    quotes: (invitations?.items ?? []).filter((i) => i.state === "SENT" || (i.state === "ACCEPTED" && i.rfq_open && !i.outcome)).length,
    inspections: (inspections?.items ?? []).filter((i) => i.state === "SCHEDULED" || i.state === "IN_PROGRESS").length,
  };
});

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
