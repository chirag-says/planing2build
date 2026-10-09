import { redirect } from "next/navigation";

import { landingPath, ownProjects, requireSignedIn } from "@/lib/session";

// Where a sign-in with no page to return to lands. Never renders: it reads the family's projects
// and sends them on (lib/session.ts landingPath). A deep link never comes here; sign-in returns
// to it directly.
export default async function ContinuePage() {
  await requireSignedIn("/continue");
  redirect(landingPath((await ownProjects()) ?? []));
}
