import { redirect } from "next/navigation";

import { requireVerifiedStaff } from "@/lib/staff";

// The operations entry point routes to the next step: sign in, set up MFA, verify, or the queue.
export default async function OpsHome() {
  await requireVerifiedStaff("/queue");
  redirect("/queue");
}
