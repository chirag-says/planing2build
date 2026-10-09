// Host-to-audience routing for the one app that serves three hosts (ADR-001; SYSTEM_ARCHITECTURE 5).
// Pure functions so the rules are unit-tested; proxy.ts applies them to every request.
import type { Audience } from "@p2b/contracts";

export type AudienceHosts = Record<Audience, string>;

/** The request header carrying the public path and query (set by proxy.ts, read by lib/session.ts). */
export const PATH_HEADER = "x-p2b-path";

const ENV_KEYS: Record<Audience, string> = {
  ihb: "P2B_HOST_IHB",
  pro: "P2B_HOST_PRO",
  ops: "P2B_HOST_OPS",
};

/** Same variables as the API, so both sides agree on which host is which. Fails fast if unset. */
export function hostsFromEnv(env: Record<string, string | undefined>): AudienceHosts {
  const hosts = {} as AudienceHosts;
  for (const [audience, key] of Object.entries(ENV_KEYS) as [Audience, string][]) {
    const value = env[key]?.trim().toLowerCase();
    if (!value) throw new Error(`${key} is not set`);
    hosts[audience] = value;
  }
  return hosts;
}

/** The audience for a Host header (port ignored), or null for a host we do not serve. */
export function audienceForHost(host: string | null, hosts: AudienceHosts): Audience | null {
  if (!host) return null;
  const bare = host.split(":", 1)[0].trim().toLowerCase();
  const match = (Object.entries(hosts) as [Audience, string][]).find(([, name]) => name === bare);
  return match ? match[0] : null;
}

/**
 * Every request is served from its audience's segment: `/x` on the homeowner host renders
 * `app/ihb/x`. A path belonging to another audience therefore cannot resolve on this host:
 * `/pro/...` on the homeowner host becomes `/ihb/pro/...`, which does not exist (404).
 */
export function internalPath(audience: Audience, pathname: string): string {
  return pathname === "/" ? `/${audience}` : `/${audience}${pathname}`;
}
