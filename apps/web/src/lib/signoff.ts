// Revoking a structural sign-off (BP-20), as the API decides it: only a listed engineer's sign-off
// that is still SIGNED, on a version in review (the sign-off is voided) or issued or accepted (the
// revocation is recorded and the version can no longer be accepted). A void sign-off, or one on a
// version returned, withdrawn or superseded, is answered with STATE_CONFLICT.
import type { components } from "@p2b/contracts";

type Signoff = Pick<components["schemas"]["SnapshotSignoffOut"], "state" | "signer_kind">;
type VersionState = components["schemas"]["BuildPlanState"];

const VOIDS: readonly VersionState[] = ["IN_REVIEW"];
const RECORDS: readonly VersionState[] = ["ISSUED", "ACCEPTED"];

export type RevokeEffect = "void" | "afterIssue";

/** What revoking would do, or null when the API would refuse it. */
export function revokeEffect(signoff: Signoff, versionState: VersionState): RevokeEffect | null {
  if (signoff.signer_kind !== "LISTED" || signoff.state !== "SIGNED") return null;
  if (VOIDS.includes(versionState)) return "void";
  if (RECORDS.includes(versionState)) return "afterIssue";
  return null;
}
