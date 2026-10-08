// What the operations and ADMIN screens offer for a given API state. The API enforces every rule;
// these only decide which controls to show so staff are not offered an action it will refuse.
import type { components } from "@p2b/contracts";

type BuildPlanState = components["schemas"]["BuildPlanState"];
type RateCardStatus = components["schemas"]["RateCardStatus"];
type HandoverState = components["schemas"]["HandoverState"];
type MfaStatus = components["schemas"]["MfaStatusResponse"];

/** A published card can be retired by ADMIN (catalog.retire_item_rate_card); nothing else can. */
export function canRetireCard(status: RateCardStatus, admin: boolean): boolean {
  return admin && status === "PUBLISHED";
}

/** A SIGNED sign-off can be revoked while the version is in review (voided) or after issue
 * (recorded as a revocation that blocks acceptance, BP-20). */
export function canRevokeSignoff(versionState: BuildPlanState, signoffState: string): boolean {
  return signoffState === "SIGNED" && ["IN_REVIEW", "ISSUED", "ACCEPTED"].includes(versionState);
}

/** Criteria are refreshed from the current specification master only on a DRAFT (BP-19). */
export function canRefreshCriteria(versionState: BuildPlanState): boolean {
  return versionState === "DRAFT";
}

export interface HandoverControls {
  open: boolean;
  editDocuments: boolean;
  confirmReady: boolean;
  reopenOrIssue: boolean;
  assemble: boolean;
}

/** The handover's controls: open when none exists; documents and warranties change only while
 * OPEN; a READY handover is reopened or issued without the owner; a Build Record is assembled
 * once the handover is acknowledged or issued by operations. */
export function handoverControls(state: HandoverState | null): HandoverControls {
  return {
    open: state === null,
    editDocuments: state === "OPEN",
    confirmReady: state === "OPEN",
    reopenOrIssue: state === "READY",
    assemble: state === "ACKNOWLEDGED" || state === "ISSUED_BY_OPERATIONS",
  };
}

/** A warranty that names a document blocks removing it (409 HAS_WARRANTY). */
export function documentHasWarranty(
  documentId: string,
  warranties: { document_id?: string | null }[],
): boolean {
  return warranties.some((w) => w.document_id === documentId);
}

export type MfaSummary = "notEnrolled" | "noRecoveryCodes" | "verified" | "notVerified";

/** The one line shown above the verify form, from GET /auth/mfa. */
export function mfaSummary(status: MfaStatus): MfaSummary {
  if (!status.enrolled) return "notEnrolled";
  if (status.recovery_codes_left === 0) return "noRecoveryCodes";
  return status.verified ? "verified" : "notVerified";
}

export type AssembleMode = "first" | "reassemble" | "correction";

/** How the next assemble behaves (records.service.assemble): the DRAFT is re-assembled when one
 * exists; otherwise a new version, which needs a correction reason once any version exists. */
export function assembleMode(versions: { state: string }[]): AssembleMode {
  if (versions.some((v) => v.state === "DRAFT")) return "reassemble";
  return versions.length === 0 ? "first" : "correction";
}

type Tone = "neutral" | "info" | "success" | "warning";

/** Badge tones for the handover and Build Record states shown to operations. */
export const HANDOVER_TONE: Record<HandoverState, Tone> = {
  OPEN: "info",
  READY: "warning",
  ACKNOWLEDGED: "success",
  ISSUED_BY_OPERATIONS: "success",
};

export const BUILD_RECORD_TONE: Record<components["schemas"]["BuildRecordState"], Tone> = {
  DRAFT: "neutral",
  ISSUED: "success",
  SUPERSEDED: "neutral",
};
