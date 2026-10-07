// Server-side gate for pages that need a signed-in homeowner. The API decides; the page only
// redirects to sign-in on 401 and lets any other failure reach the error boundary.
import type { MeResponse, components } from "@p2b/contracts";
import { redirect } from "next/navigation";
import { cache } from "react";

import { serverApi } from "@/lib/api/server";

type ProjectSummary = components["schemas"]["ProjectSummary"];

export async function requireSignedIn(returnTo: string): Promise<MeResponse> {
  const { data, response } = await (await serverApi()).GET("/api/v1/me");
  if (data) return data;
  if (response.status === 401) {
    redirect(`/sign-in?next=${encodeURIComponent(returnTo)}`);
  }
  throw new Error(`session check failed with status ${response.status}`);
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
