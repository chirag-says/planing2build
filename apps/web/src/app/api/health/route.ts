// Container health check (CLOUD_AND_HOSTING 2.1). Host-independent; excluded from the proxy.
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ status: "ok" });
}
