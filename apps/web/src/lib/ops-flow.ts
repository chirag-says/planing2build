// Small decisions for the operations project screens (floor plans, per-project RFQs, stage
// updates, later test results). Each reads only what the API returned; the API checks every rule
// again when an action is sent.
import type { components } from "@p2b/contracts";

type Schemas = components["schemas"];

/** The RFQ that blocks a new one: the API allows one DRAFT or ISSUED request at a time (OPEN_RFQ). */
export function openRfq(items: Schemas["OpsRfqSummaryOut"][]): Schemas["OpsRfqSummaryOut"] | null {
  return items.find((r) => r.state === "DRAFT" || r.state === "ISSUED") ?? null;
}

/** A plan the read-only drawing can show: only a VALID plan carries a document and its geometry. */
export function drawablePlan(
  plan: Pick<Schemas["OpsHousePlanDetailOut"], "state" | "document" | "geometry">,
): plan is typeof plan & { document: Schemas["HousePlan"]; geometry: Schemas["PlanGeometry"] } {
  return plan.state === "VALID" && plan.document != null && plan.geometry != null;
}

/** Later test results (cube tests) attach only to a result on an approved inspection (NOT_APPROVED). */
export function acceptsTestResults(inspection: Pick<Schemas["OpsInspectionOut"], "state">): boolean {
  return inspection.state === "APPROVED";
}

/** What the stage-updates panel shows once its request has answered. */
export type UpdatesView =
  | { kind: "error"; message: string | null }
  | { kind: "empty" }
  | { kind: "list"; updates: Schemas["UpdateOut"][] };

export function updatesView(result: { ok: boolean; body: unknown }): UpdatesView {
  if (!result.ok) {
    const message = (result.body as { error?: { message?: string } } | null)?.error?.message ?? null;
    return { kind: "error", message };
  }
  const updates = (result.body as Schemas["UpdatesOut"] | null)?.updates ?? [];
  return updates.length === 0 ? { kind: "empty" } : { kind: "list", updates };
}
