import { NextResponse, type NextRequest } from "next/server";

import { audienceForHost, hostsFromEnv, internalPath, type AudienceHosts } from "@/lib/audience";

let hosts: AudienceHosts | undefined;

export function proxy(request: NextRequest) {
  hosts ??= hostsFromEnv(process.env);
  const audience = audienceForHost(request.headers.get("host"), hosts);
  if (audience === null) {
    return new NextResponse(null, { status: 400 });
  }
  const url = request.nextUrl.clone();
  url.pathname = internalPath(audience, url.pathname);
  return NextResponse.rewrite(url);
}

export const config = {
  // Framework assets and the container health check are host-independent.
  matcher: ["/((?!_next/|api/health$|favicon.ico$).*)"],
};
