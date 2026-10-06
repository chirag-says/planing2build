// API access from server components: loopback to FastAPI with the user's cookie and host
// forwarded, so the API applies the same audience and session rules as for the browser
// (SYSTEM_ARCHITECTURE 4.1; ADR-016). fetch cannot set Host, so the host travels as
// X-Forwarded-Host, as it does from Caddy. Never import this from a client component.
import { createApiClient, type ApiClient } from "@p2b/contracts";
import { headers } from "next/headers";

const FORWARDED_HEADERS = ["cookie", "x-request-id"] as const;

export async function serverApi(): Promise<ApiClient> {
  const baseUrl = process.env.P2B_API_INTERNAL_URL;
  if (!baseUrl) throw new Error("P2B_API_INTERNAL_URL is not set");
  const incoming = await headers();
  const forwarded: Record<string, string> = {};
  const host = incoming.get("x-forwarded-host") ?? incoming.get("host");
  if (host) forwarded["x-forwarded-host"] = host;
  for (const name of FORWARDED_HEADERS) {
    const value = incoming.get(name);
    if (value) forwarded[name] = value;
  }
  return createApiClient({ baseUrl, headers: forwarded });
}
