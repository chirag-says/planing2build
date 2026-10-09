/**
 * Links between the public site and the professionals host. The host name comes from the same
 * P2B_HOST_PRO setting the proxy uses (lib/audience.ts), so production, CI and local runs agree.
 * Local hosts (`*.localhost`) are reached through the Compose stack's Caddy on port 8080
 * (infra/local); every other host is served over HTTPS.
 */
const LOCAL_CADDY_PORT = 8080;

export function professionalsOrigin(): string {
  const host = process.env.P2B_HOST_PRO?.trim().toLowerCase();
  if (!host) return '';
  return host.endsWith('.localhost') || host === 'localhost' ? `http://${host}:${LOCAL_CADDY_PORT}` : `https://${host}`;
}

/** The homeowner site's origin (the public website and the family's sign-in), or '' when unset. */
export function homeownerOrigin(): string {
  const host = process.env.P2B_HOST_IHB?.trim().toLowerCase();
  if (!host) return '';
  return host.endsWith('.localhost') || host === 'localhost' ? `http://${host}:${LOCAL_CADDY_PORT}` : `https://${host}`;
}

/** The homeowner sign-in, for a family that landed on the professionals host. */
export function homeownerSignInUrl(): string {
  const origin = homeownerOrigin();
  return origin ? `${origin}/sign-in` : '/';
}

/** The professionals sign-in (registration starts there), or the public page when unset. */
export function professionalsSignInUrl(): string {
  const origin = professionalsOrigin();
  return origin ? `${origin}/sign-in` : '/for-professionals';
}

/** True for absolute links to one of Plan2Build's own hosts: they open in the same tab. */
export function isOwnHost(url: string): boolean {
  try {
    const { hostname } = new URL(url);
    return hostname === 'plan2build.in' || hostname.endsWith('.plan2build.in') || hostname.endsWith('.localhost');
  } catch {
    return false;
  }
}
