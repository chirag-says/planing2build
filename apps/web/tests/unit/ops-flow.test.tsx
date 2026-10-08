import type { components } from "@p2b/contracts";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PlanViewer } from "@/components/plan2build/plan/plan-viewer";
import { acceptsTestResults, drawablePlan, openRfq, updatesView } from "@/lib/ops-flow";

import { fixture } from "./plan-fixtures";

type Rfq = components["schemas"]["OpsRfqSummaryOut"];
type Update = components["schemas"]["UpdateOut"];

function rfq(id: string, state: Rfq["state"]): Rfq {
  return {
    id, project_id: "p", project_code: "P2B-1", state, created_at: "2026-10-01T00:00:00Z",
    quotes_due_at: null, invitations: 0, quotes: 0, pending_reviews: 0,
  };
}

describe("openRfq", () => {
  it("finds the DRAFT or ISSUED request that blocks a new one", () => {
    expect(openRfq([rfq("a", "CLOSED"), rfq("b", "ISSUED")])?.id).toBe("b");
    expect(openRfq([rfq("a", "DRAFT")])?.id).toBe("a");
  });
  it("allows a new request when every earlier one has ended", () => {
    expect(openRfq([])).toBeNull();
    expect(openRfq([rfq("a", "CLOSED"), rfq("b", "CANCELLED")])).toBeNull();
  });
});

describe("drawablePlan", () => {
  const { document, geometry } = fixture("1bhk_25x40_south_small");
  it("draws only a VALID plan that carries its document and geometry", () => {
    expect(drawablePlan({ state: "VALID", document, geometry })).toBe(true);
    expect(drawablePlan({ state: "VALID", document: null, geometry })).toBe(false);
    expect(drawablePlan({ state: "VALID", document, geometry: null })).toBe(false);
    expect(drawablePlan({ state: "INFEASIBLE", document, geometry })).toBe(false);
    expect(drawablePlan({ state: "RUNNING", document: null, geometry: null })).toBe(false);
  });
});

describe("acceptsTestResults", () => {
  it("is open only on an approved inspection", () => {
    expect(acceptsTestResults({ state: "APPROVED" })).toBe(true);
    for (const state of ["SCHEDULED", "IN_PROGRESS", "SUBMITTED", "RETURNED", "CANCELLED"] as const) {
      expect(acceptsTestResults({ state })).toBe(false);
    }
  });
});

describe("updatesView", () => {
  const update: Update = {
    id: "u", kind: "PROGRESS", note: "Slab cast", materials: null, open_problems: null, photos: [],
    corrects_update_id: null, entered_by_operations: false, contractor_name: "A", posted_at: "2026-10-01T00:00:00Z",
  };
  it("shows the API's error message", () => {
    expect(updatesView({ ok: false, body: { error: { code: "NOT_FOUND", message: "Not found." } } }))
      .toEqual({ kind: "error", message: "Not found." });
    expect(updatesView({ ok: false, body: null })).toEqual({ kind: "error", message: null });
  });
  it("tells an empty stage from one with updates", () => {
    expect(updatesView({ ok: true, body: { stage: {}, updates: [] } })).toEqual({ kind: "empty" });
    expect(updatesView({ ok: true, body: { stage: {}, updates: [update] } })).toEqual({ kind: "list", updates: [update] });
  });
});

describe("PlanViewer", () => {
  it("draws the plan with no selection targets and no editing tools", () => {
    const { document, geometry, validation } = fixture("2bhk_30x50_north_twowheeler_open");
    const html = renderToStaticMarkup(<PlanViewer document={document} geometry={geometry} validation={validation} />);
    expect(html).toContain("data-plan-drawing");
    expect(html).not.toContain("data-hit");
    expect(html).not.toContain("data-plan-canvas");
    for (const tool of ["Undo", "Redo", "Snap"]) expect(html).not.toContain(`>${tool}<`);
  });
});
