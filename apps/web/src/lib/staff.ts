// Server-side gate for operations pages. The API decides who is staff and whether MFA is fresh
// (`/me` on the admin host); the page only routes: sign in, set up MFA, verify MFA, or continue.
// Every operations API call is checked again by the API itself.
import type { components } from "@p2b/contracts";
import { redirect } from "next/navigation";

import { serverApi } from "@/lib/api/server";

export type StaffInfo = components["schemas"]["StaffInfo"];

export async function staffSession(): Promise<StaffInfo | null> {
  const { data, response } = await (await serverApi()).GET("/api/v1/me");
  if (data) return data.staff ?? null;
  if (response.status === 401) return null;
  throw new Error(`session check failed with status ${response.status}`);
}

/** Signed in, enrolled and verified within 8 hours; otherwise redirects to the right step. */
export async function requireVerifiedStaff(returnTo: string): Promise<StaffInfo> {
  const staff = await staffSession();
  if (!staff) redirect(`/sign-in?next=${encodeURIComponent(returnTo)}`);
  if (!staff.mfa_enrolled) redirect("/mfa/setup");
  if (!staff.mfa_verified) redirect(`/mfa?next=${encodeURIComponent(returnTo)}`);
  return staff;
}
