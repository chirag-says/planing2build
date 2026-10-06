// Server-side gate for professionals-host pages: signed in on this host, or off to sign-in. The
// API checks every call again.
import type { components } from "@p2b/contracts";
import { redirect } from "next/navigation";

import { serverApi } from "@/lib/api/server";

export type ProDashboard = components["schemas"]["OwnDashboardOut"];

export async function signedInProfessional(): Promise<boolean> {
  const { data, response } = await (await serverApi()).GET("/api/v1/me");
  if (data) return true;
  if (response.status === 401) return false;
  throw new Error(`session check failed with status ${response.status}`);
}

/** The professional's own dashboard data, or a redirect to sign-in. */
export async function loadOwnProfile(returnTo: string): Promise<ProDashboard> {
  const { data, response } = await (await serverApi()).GET("/api/v1/pro/profile");
  if (response.status === 401) redirect(`/sign-in?next=${encodeURIComponent(returnTo)}`);
  if (!data) throw new Error("the professional profile could not be loaded");
  return data;
}
