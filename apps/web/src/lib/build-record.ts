// A Build Record version's frozen snapshot (Slice 3.7C, EX-17), read for the screen. The API types
// `snapshot` as a free object; its shape is the one the backend assembles (records/service.py
// `snapshot`, schema_version 1) and prints in the PDF. This reads it defensively: a missing or
// mistyped field becomes null or an empty list, never an invented value. The snapshot carries no
// price or amount; product, purchase and installation are recorded as "NOT RECORDED" (EX-16).

type Obj = Record<string, unknown>;

export const NOT_RECORDED = "NOT RECORDED";

export interface RecordVerification {
  gate: number | null;
  floor: number | null;
  result: string | null;
  approvedAt: string | null;
}

export interface RecordSpecLine {
  code: string;
  item: string;
  acceptedValue: string | null;
  applicability: string | null;
  verification: RecordVerification[];
  /** Product, purchase and installation: the text the snapshot holds ("NOT RECORDED" today). */
  product: string | null;
  purchase: string | null;
  installation: string | null;
}

export interface RecordMark {
  value: string | null;
  markedAt: string | null;
  byOperations: boolean;
}

export interface BuildRecordContent {
  schemaVersion: number | null;
  identity: { projectCode: string | null; locality: string | null };
  plan: { versionNo: number | null; contentHash: string | null; acceptedAt: string | null };
  drawings: Array<{
    fileId: string | null;
    drawingClass: string | null;
    floor: number | null;
    title: string | null;
    sheetNo: string | null;
    sha256: string | null;
  }>;
  specification: RecordSpecLine[];
  contractors: Array<{
    name: string | null;
    party: string | null;
    state: string | null;
    chosenByFamily: boolean;
    startedAt: string | null;
    endedAt: string | null;
  }>;
  execution: Array<{
    stageNumber: number | null;
    name: string;
    floor: number | null;
    state: string | null;
    actualStart: string | null;
    actualEnd: string | null;
    updates: number;
  }>;
  inspections: Array<{
    gate: number | null;
    kind: string | null;
    stage: string | null;
    floor: number | null;
    approvedAt: string | null;
    auditorCode: string | null;
    outcome: string | null;
    reports: Array<{ version: number | null; sha256: string | null }>;
  }>;
  findings: Array<{
    severity: string | null;
    description: string;
    state: string | null;
    closedAt: string | null;
  }>;
  paymentMarks: Array<{
    stageNumber: number | null;
    floor: number | null;
    paid: RecordMark | null;
    received: RecordMark | null;
  }>;
  handover: {
    state: string | null;
    openedAt: string | null;
    documents: Array<{ kind: string | null; title: string; sha256: string | null }>;
    warranties: Array<{ item: string; term: string; expiryDate: string | null; installer: string }>;
    acknowledgement: { acknowledgedAt: string | null; statementText: string | null } | null;
    issuedWithoutAcknowledgement: { issuedAt: string | null; reason: string | null } | null;
  };
}

const isObj = (value: unknown): value is Obj => typeof value === "object" && value !== null && !Array.isArray(value);
const obj = (value: unknown): Obj => (isObj(value) ? value : {});
const list = (value: unknown): Obj[] => (Array.isArray(value) ? value.filter(isObj) : []);
const str = (value: unknown): string | null => (typeof value === "string" && value !== "" ? value : null);
const num = (value: unknown): number | null => (typeof value === "number" && Number.isFinite(value) ? value : null);

/** A specification value as text: strings as they are, numbers and booleans spelled, anything else left out. */
function valueText(value: unknown): string | null {
  if (typeof value === "string") return value === "" ? null : value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  return null;
}

function mark(value: unknown): RecordMark | null {
  if (!isObj(value)) return null;
  return { value: str(value.value), markedAt: str(value.marked_at), byOperations: value.by_operations === true };
}

export function readBuildRecord(snapshot: unknown): BuildRecordContent {
  const root = obj(snapshot);
  const identity = obj(root.identity);
  const plan = obj(root.plan);
  const assurance = obj(root.assurance);
  const handover = obj(root.handover);
  const acknowledgement = isObj(handover.acknowledgement) ? handover.acknowledgement : null;
  const forced = isObj(handover.issued_without_acknowledgement) ? handover.issued_without_acknowledgement : null;
  return {
    schemaVersion: num(root.schema_version),
    identity: { projectCode: str(identity.project_code), locality: str(identity.locality) },
    plan: {
      versionNo: num(plan.build_plan_version_no),
      contentHash: str(plan.content_hash),
      acceptedAt: str(plan.accepted_at),
    },
    drawings: list(root.drawings).map((d) => ({
      fileId: str(d.file_id),
      drawingClass: str(d.drawing_class),
      floor: num(d.floor),
      title: str(d.title),
      sheetNo: str(d.sheet_no),
      sha256: str(d.sha256),
    })),
    specification: list(root.specification).map((s) => ({
      code: str(s.code) ?? "",
      item: str(s.item) ?? "",
      acceptedValue: valueText(s.accepted_value),
      applicability: str(s.applicability),
      verification: list(s.verification).map((v) => ({
        gate: num(v.gate),
        floor: num(v.floor),
        result: str(v.result),
        approvedAt: str(v.approved_at),
      })),
      product: str(s.product),
      purchase: str(s.purchase),
      installation: str(s.installation),
    })),
    contractors: list(root.contractors).map((c) => ({
      name: str(c.name),
      party: str(c.party),
      state: str(c.state),
      chosenByFamily: c.chosen_by_family === true,
      startedAt: str(c.started_at),
      endedAt: str(c.ended_at),
    })),
    execution: list(root.execution).map((s) => ({
      stageNumber: num(s.stage_number),
      name: str(s.name) ?? "",
      floor: num(s.floor),
      state: str(s.state),
      actualStart: str(s.actual_start),
      actualEnd: str(s.actual_end),
      updates: num(s.updates) ?? 0,
    })),
    inspections: list(assurance.inspections).map((i) => ({
      gate: num(i.gate),
      kind: str(i.kind),
      stage: str(i.stage),
      floor: num(i.floor),
      approvedAt: str(i.approved_at),
      auditorCode: str(i.auditor_code),
      outcome: str(i.outcome),
      reports: list(i.reports).map((r) => ({ version: num(r.version), sha256: str(r.sha256) })),
    })),
    findings: list(assurance.findings).map((f) => ({
      severity: str(f.severity),
      description: str(f.description) ?? "",
      state: str(f.state),
      closedAt: str(f.closed_at),
    })),
    paymentMarks: list(root.payment_marks).map((m) => ({
      stageNumber: num(m.stage_number),
      floor: num(m.floor),
      paid: mark(m.paid),
      received: mark(m.received),
    })),
    handover: {
      state: str(handover.state),
      openedAt: str(handover.opened_at),
      documents: list(handover.documents).map((d) => ({
        kind: str(d.kind),
        title: str(d.title) ?? "",
        sha256: str(d.sha256),
      })),
      warranties: list(handover.warranties).map((w) => ({
        item: str(w.item) ?? "",
        term: str(w.term) ?? "",
        expiryDate: str(w.expiry_date),
        installer: str(w.installer) ?? "",
      })),
      acknowledgement: acknowledgement
        ? { acknowledgedAt: str(acknowledgement.acknowledged_at), statementText: str(acknowledgement.statement_text) }
        : null,
      issuedWithoutAcknowledgement: forced ? { issuedAt: str(forced.issued_at), reason: str(forced.reason) } : null,
    },
  };
}

/** Whether a snapshot field holds the "not recorded" marker rather than a recorded fact. */
export function isNotRecorded(value: string | null): boolean {
  return value === null || value === NOT_RECORDED;
}
