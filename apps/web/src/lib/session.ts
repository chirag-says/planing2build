// Server-side gate for pages that need a signed-in homeowner. The API decides; the page only
// redirects to sign-in on 401 and lets any other failure reach the error boundary.
import type { MeResponse, components } from "@p2b/contracts";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { serverApi } from "@/lib/api/server";
import { PATH_HEADER } from "@/lib/audience";

type ProjectSummary = components["schemas"]["ProjectSummary"];

/** The public path and query of this request (proxy.ts), or "/" outside a request. */
export async function currentPath(): Promise<string> {
  try {
    return (await headers()).get(PATH_HEADER) || "/";
  } catch {
    return "/";
  }
}

/**
 * Signed out: off to sign-in, and back to `returnTo` afterwards. By default that is the page being
 * asked for, so a deep link (a quote, an order, a drawing) survives the code.
 */
export async function requireSignedIn(returnTo?: string): Promise<MeResponse> {
  const { data, response } = await (await serverApi()).GET("/api/v1/me");
  if (data) return data;
  if (response.status === 401) {
    redirect(`/sign-in?next=${encodeURIComponent(returnTo ?? (await currentPath()))}`);
  }
  throw new Error(`session check failed with status ${response.status}`);
}

/**
 * Where a sign-in with no page to return to lands (decided 2026-10-08): no project yet, the start
 * questions; one project still being written, straight back into its requirement; one project
 * past that, its overview; more than one, the list. Only this routing resumes a draft: "New
 * project" always creates one.
 */
export function landingPath(projects: Pick<ProjectSummary, "project_id" | "status">[]): string {
  if (projects.length === 0) return "/start";
  if (projects.length > 1) return "/projects";
  const [only] = projects;
  return only.status === "DRAFT" ? `/projects/${only.project_id}/requirement` : `/projects/${only.project_id}`;
}

/**
 * The signed-in person for the app shell (name on the avatar), or null when signed out. Never
 * redirects and never throws: the shell must render even when the API is unreachable. One read
 * per request, shared by the layouts and the pages.
 */
export const currentUser = cache(async (): Promise<MeResponse | null> => {
  try {
    const { data } = await (await serverApi()).GET("/api/v1/me");
    return data ?? null;
  } catch {
    return null;
  }
});

/**
 * The homeowner's projects, for the shell's onboarding gate and the project switcher, or null when
 * signed out or the API is unreachable. Never redirects and never throws; one read per request.
 */
export const ownProjects = cache(async (): Promise<ProjectSummary[] | null> => {
  try {
    const { data } = await (await serverApi()).GET("/api/v1/projects");
    return data ?? null;
  } catch {
    return null;
  }
});

/** Up to two initials for the avatar, from the display name. */
export function initialsOf(name: string | null | undefined): string | null {
  const words = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return null;
  const letters = words.length === 1 ? words[0].slice(0, 2) : `${words[0][0]}${words[words.length - 1][0]}`;
  return letters.toUpperCase();
}
