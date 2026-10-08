// A Build Record snapshot read for the screen: the shape the backend assembles (schema_version 1),
// read without inventing anything when a field is missing or mistyped.
import { describe, expect, it } from "vitest";

import { isNotRecorded, NOT_RECORDED, readBuildRecord } from "@/lib/build-record";

const snapshot = {
  schema_version: 1,
  identity: { project_code: "P2B-0042", locality: "Andheri" },
  plan: { build_plan_version_no: 3, content_hash: "abc", accepted_at: "2026-05-01T10:00:00+00:00" },
  drawings: [{ file_id: "f1", drawing_class: "FLOOR_PLAN", floor: 0, title: "Ground", sheet_no: "A-01", sha256: "d1" }],
  specification: [
    {
      code: "STR-01", item: "Concrete grade", accepted_value: "M25", applicability: "APPLICABLE",
      verification: [{ gate: 2, floor: 0, result: "PASS", approved_at: "2026-06-01T00:00:00+00:00" }],
      product: NOT_RECORDED, purchase: NOT_RECORDED, installation: NOT_RECORDED,
    },
    { code: "FIN-02", item: "Skirting height", accepted_value: 100, applicability: "APPLICABLE", verification: [] },
  ],
  contractors: [
    { name: "Asha Builders", party: "OUTSIDE", origin: "OUTSIDE", state: "ACTIVE", chosen_by_family: true,
      started_at: "2026-05-02T00:00:00+00:00", ended_at: null },
  ],
  execution: [
    { stage_number: 1, name: "Excavation", floor: null, state: "COMPLETED", is_gate: false, gate_status: null,
      is_payment_milestone: true, actual_start: "2026-05-03", actual_end: "2026-05-10", updates: 4 },
  ],
  assurance: {
    inspections: [
      { gate: 1, kind: "INITIAL", stage_number: 2, stage: "Footing", floor: null, approved_at: "2026-05-12T00:00:00+00:00",
        auditor_code: "AUD-7", outcome: "Passed: no item needs correction.", reports: [{ version: 1, sha256: "r1" }] },
    ],
    findings: [{ severity: "MINOR", description: "Cover blocks", state: "CLOSED", closed_at: "2026-05-20T00:00:00+00:00" }],
  },
  payment_marks: [
    { stage_number: 1, floor: null, due: true, paid: { value: "YES", marked_at: "2026-05-11T00:00:00+00:00" },
      received: { value: "YES", marked_at: "2026-05-12T00:00:00+00:00", by_operations: true } },
  ],
  handover: {
    state: "ACKNOWLEDGED",
    opened_at: "2026-09-01T00:00:00+00:00",
    documents: [{ kind: "WARRANTY", title: "Waterproofing", file_id: "f9", sha256: "w1" }],
    warranties: [{ item: "Roof", term: "10 years", expiry_date: "2036-09-01", installer: "DryCo", spec_line_code: null }],
    acknowledgement: { acknowledged_at: "2026-09-10T00:00:00+00:00", statement_text: "I received the house." },
    issued_without_acknowledgement: null,
  },
};

describe("readBuildRecord", () => {
  it("reads every section of a schema 1 snapshot", () => {
    const record = readBuildRecord(snapshot);
    expect(record.schemaVersion).toBe(1);
    expect(record.identity).toEqual({ projectCode: "P2B-0042", locality: "Andheri" });
    expect(record.plan.versionNo).toBe(3);
    expect(record.drawings[0]).toMatchObject({ drawingClass: "FLOOR_PLAN", floor: 0, sheetNo: "A-01" });
    expect(record.specification[0]?.verification).toEqual([
      { gate: 2, floor: 0, result: "PASS", approvedAt: "2026-06-01T00:00:00+00:00" },
    ]);
    expect(record.contractors[0]).toMatchObject({ name: "Asha Builders", chosenByFamily: true, endedAt: null });
    expect(record.execution[0]).toMatchObject({ stageNumber: 1, floor: null, state: "COMPLETED", updates: 4 });
    expect(record.inspections[0]?.reports).toEqual([{ version: 1, sha256: "r1" }]);
    expect(record.findings[0]).toMatchObject({ severity: "MINOR", state: "CLOSED" });
    expect(record.paymentMarks[0]?.received).toEqual({ value: "YES", markedAt: "2026-05-12T00:00:00+00:00", byOperations: true });
    expect(record.handover.acknowledgement?.statementText).toBe("I received the house.");
    expect(record.handover.issuedWithoutAcknowledgement).toBeNull();
  });

  it("spells a numeric specification value and leaves missing ones out", () => {
    const [, line] = readBuildRecord(snapshot).specification;
    expect(line?.acceptedValue).toBe("100");
    expect(line?.product).toBeNull();
    expect(isNotRecorded(line?.product ?? null)).toBe(true);
    expect(isNotRecorded(NOT_RECORDED)).toBe(true);
    expect(isNotRecorded("Brand X")).toBe(false);
  });

  it("carries no amount: payment marks keep only their yes or no", () => {
    const mark = readBuildRecord(snapshot).paymentMarks[0];
    expect(Object.keys(mark ?? {}).sort()).toEqual(["floor", "paid", "received", "stageNumber"]);
  });

  it("reads an empty or malformed snapshot as empty, inventing nothing", () => {
    for (const input of [{}, null, "x", { drawings: "no", handover: [], assurance: { inspections: [1, null] } }]) {
      const record = readBuildRecord(input);
      expect(record.schemaVersion).toBeNull();
      expect(record.drawings).toEqual([]);
      expect(record.inspections).toEqual([]);
      expect(record.handover).toEqual({
        state: null, openedAt: null, documents: [], warranties: [], acknowledgement: null, issuedWithoutAcknowledgement: null,
      });
    }
  });
});
