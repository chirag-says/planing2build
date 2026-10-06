/**
 * A same-site path for the post-sign-in redirect, or the fallback. Rejects absolute URLs,
 * protocol-relative `//host` and backslash tricks, so the parameter cannot send a user off-site.
 */
export function safeNextPath(next: string | null | undefined, fallback = "/projects"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || /[\\\u0000-\u001f]/.test(next)) {
    return fallback;
  }
  return next;
}
