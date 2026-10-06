// Server-side gate for pages that need a signed-in homeowner. The API decides; the page only
// redirects to sign-in on 401 and lets any other failure reach the error boundary.
import type { MeResponse } from "@p2b/contracts";
import { redirect } from "next/navigation";

import { serverApi } from "@/lib/api/server";

export async function requireSignedIn(returnTo: string): Promise<MeResponse> {
  const { data, response } = await (await serverApi()).GET("/api/v1/me");
  if (data) return data;
  if (response.status === 401) {
    redirect(`/sign-in?next=${encodeURIComponent(returnTo)}`);
  }
  throw new Error(`session check failed with status ${response.status}`);
}
