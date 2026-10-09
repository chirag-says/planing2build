import { describe, expect, it } from "vitest";

import { buildQueue, groupOf, readinessOf, sortQueue, type Dashboard } from "@/lib/pro-console";
import { landingPath } from "@/lib/session";

describe("landingPath: where a sign-in with no page to return to lands", () => {
  it("sends a family with no project to the start questions", () => {
    expect(landingPath([])).toBe("/start");
  });
  it("resumes a lone draft in its requirement", () => {
    expect(landingPath([{ project_id: "p1", status: "DRAFT" }])).toBe("/projects/p1/requirement");
  });
  it("opens the overview of a lone project past its draft", () => {
    expect(landingPath([{ project_id: "p1", status: "SUBMITTED" }])).toBe("/projects/p1");
    expect(landingPath([{ project_id: "p1", status: "ACCEPTED" }])).toBe("/projects/p1");
  });
  it("lists several projects, drafts included", () => {
    expect(
      landingPath([
        { project_id: "p1", status: "DRAFT" },
        { project_id: "p2", status: "ACCEPTED" },
      ]),
    ).toBe("/projects");
  });
});

describe("the professional's work queue", () => {
  it("groups dated and assigned work first, then answers, reviews, completion", () => {
    expect(groupOf("inspection", null)).toBe("urgent");
    expect(groupOf("finding", null)).toBe("urgent");
    expect(groupOf("connection", { kind: "respond", at: "2026-10-09T00:00:00Z", soon: false })).toBe("respond");
    expect(groupOf("quote", { kind: "quotes", at: "2026-10-09T00:00:00Z", soon: true })).toBe("urgent");
    expect(groupOf("drawing", null)).toBe("review");
    expect(groupOf("signoff", null)).toBe("review");
    expect(groupOf("handover", null)).toBe("complete");
  });
  it("sorts by group, then by the date due, undated last", () => {
    const sorted = sortQueue([
      { kind: "handover", group: "complete", id: "h", href: "", title: "", place: null, due: null, brief: null },
      { kind: "connection", group: "respond", id: "c2", href: "", title: "", place: null, due: null, brief: null },
      { kind: "connection", group: "respond", id: "c1", href: "", title: "", place: null, due: { kind: "respond", at: "2026-10-10T00:00:00Z", soon: false }, brief: null },
      { kind: "inspection", group: "urgent", id: "i", href: "", title: "", place: null, due: { kind: "scheduled", at: "2026-10-12T00:00:00Z", soon: false }, brief: null },
    ]);
    expect(sorted.map((item) => item.id)).toEqual(["i", "c1", "c2", "h"]);
  });
  it("adds a sign-off and an open handover from the other domains", () => {
    const queue = buildQueue([], [], null, new Date("2026-10-08T00:00:00Z"), {
      drawings: [],
      signoffs: [
        {
          version_id: "v1",
          project_code: "P2B-1",
          version_no: 2,
          state: "IN_REVIEW",
          content_hash: null,
          verified: true,
          statement_version: null,
          statement_text: null,
          lines: [{ code: "S1", item: "Footing", criteria: "", applicability: "APPLICABLE", basis: null, value: "x", not_applicable_reason: null, signed: false }],
          drawings: [],
          my_signoffs: [],
        },
      ],
      engagements: [
        {
          engagementId: "e1",
          projectCode: "P2B-2",
          category: "Contractor",
          categoryCode: "CONTRACTOR",
          origin: "connection",
          startedAt: "2026-09-01T00:00:00Z",
          ended: false,
          locality: null,
          family: null,
          stages: [],
          handover: "OPEN",
        },
      ],
    });
    expect(queue.map((item) => [item.kind, item.group, item.href])).toEqual([
      ["signoff", "review", "/build-plan/signoffs/v1"],
      ["handover", "complete", "/engagements/e1/execution#handover"],
    ]);
  });
});

describe("the listing checklist", () => {
  const dashboard = {
    profile: { missing: [] },
    categories: [{ code: "ARCHITECT", name: "Architect", listing_state: "DRAFT", requirements: [], missing_requirements: [] }],
    portfolio: [],
  } as unknown as Dashboard;
  it("asks for portfolio photos before the verification requirements and the submission", () => {
    const { checkpoints } = readinessOf(dashboard);
    expect(checkpoints.map((c) => c.key)).toEqual(["profile", "services", "portfolio", "evidence", "listed"]);
    expect(checkpoints.find((c) => c.key === "portfolio")?.state).toBe("current");
    expect(checkpoints.find((c) => c.key === "listed")?.href).toBe("/categories/ARCHITECT");
  });
});
