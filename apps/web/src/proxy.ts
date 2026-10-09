import { NextResponse, type NextRequest } from "next/server";

import { PATH_HEADER, audienceForHost, hostsFromEnv, internalPath, type AudienceHosts } from "@/lib/audience";

let hosts: AudienceHosts | undefined;

export function proxy(request: NextRequest) {
  hosts ??= hostsFromEnv(process.env);
  const audience = audienceForHost(request.headers.get("host"), hosts);
  if (audience === null) {
    return new NextResponse(null, { status: 400 });
  }
  const url = request.nextUrl.clone();
  // The public path (before the audience rewrite) travels with the request: server code reads it
  // to send a signed-out visitor back to the page they asked for and to guard a project's pages.
  const headers = new Headers(request.headers);
  headers.set(PATH_HEADER, `${url.pathname}${url.search}`);
  url.pathname = internalPath(audience, url.pathname);
  return NextResponse.rewrite(url, { request: { headers } });
}

export const config = {
  // Framework assets and the container health check are host-independent.
  matcher: ["/((?!_next/|api/health$|favicon.ico$).*)"],
};
