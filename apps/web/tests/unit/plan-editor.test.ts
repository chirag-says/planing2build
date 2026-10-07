import { describe, expect, it } from "vitest";

import {
  editorReducer,
  flaggedEntities,
  historyRequest,
  initialState,
  problemOf,
  type EditorState,
} from "@/lib/plan/editor";
import type { PlanOp, PlanState } from "@/lib/plan/types";

import { fixture } from "./plan-fixtures";

const move: PlanOp = { op: "MOVE_WALL", wall: "w5", delta_mm: 100 };
const back: PlanOp = { op: "MOVE_WALL", wall: "w5", delta_mm: -100 };

function next(plan: PlanState, revision: number): PlanState {
  return { ...plan, editing: { ...plan.editing, revision_no: revision } };
}

function start(): EditorState {
  return initialState(fixture("2bhk_30x50_north_twowheeler_open"));
}

describe("editor state", () => {
  it("selects, previews and cancels without touching the plan", () => {
    const s0 = start();
    const s1 = editorReducer(s0, { type: "select", selection: { kind: "room", id: "living" } });
    const s2 = editorReducer(s1, {
      type: "drag",
      drag: { kind: "room", room: "living", axis: "x", delta: 300, guide: null },
    });
    expect(s2.drag).not.toBeNull();
    expect(s2.plan).toBe(s0.plan);
    const s3 = editorReducer(s2, { type: "cancel" });
    expect(s3.drag).toBeNull();
    expect(s3.selection).toEqual({ kind: "room", id: "living" }); // Escape drops the gesture first
    expect(editorReducer(s3, { type: "cancel" }).selection).toBeNull(); // then the selection
    expect(s3.plan).toBe(s0.plan);
  });

  it("changes the plan only with the server's answer, and records the batch for undo", () => {
    const s0 = start();
    const busy = editorReducer(s0, { type: "commit" });
    expect(busy.busy).toBe(true);
    expect(editorReducer(busy, { type: "drag", drag: { kind: "opening", id: "x", offset: 1 } }).drag).toBeNull();
    const after = next(s0.plan, 1);
    const done = editorReducer(busy, {
      type: "committed",
      plan: after,
      batch: { ops: [move], inverse: [back] },
      direction: "do",
    });
    expect(done.plan).toBe(after);
    expect(done.busy).toBe(false);
    expect(done.undo).toEqual([{ ops: [move], inverse: [back] }]);
    expect(historyRequest(done, "undo")).toEqual({ ops: [back], expected: 1 });
  });

  it("keeps the plan when the server refuses, and says why", () => {
    const s0 = start();
    const busy = editorReducer(s0, { type: "commit" });
    const issues = [
      {
        code: "ROOM_BELOW_MIN_SHORT_SIDE" as const,
        category: "GEOMETRY" as const,
        severity: "ERROR" as const,
        entities: [{ kind: "ROOM" as const, id: "bedroom_1" }],
        message_key: "k",
        params: {},
        message: "Bedroom 1 is narrower than its minimum.",
        repair: "NONE" as const,
      },
    ];
    const failed = editorReducer(busy, {
      type: "failed",
      problem: problemOf("PLAN_EDIT_INVALID", { report: { errors: issues } }),
    });
    expect(failed.plan).toBe(s0.plan);
    expect(failed.busy).toBe(false);
    expect(failed.problem).toEqual({ kind: "invalid", issues });
    expect(failed.undo).toEqual([]);
    expect(flaggedEntities(issues)).toEqual(new Set(["ROOM:bedroom_1"]));
  });

  it("reads every rejection the API can send", () => {
    expect(problemOf("PLAN_OPERATION_REJECTED", { index: 0, op: "MOVE_WALL", code: "WALL_WOULD_COLLAPSE" })).toEqual({
      kind: "rejected",
      code: "WALL_WOULD_COLLAPSE",
    });
    expect(problemOf("REVISION_CONFLICT", { current_revision: 4 })).toEqual({ kind: "conflict" });
    expect(problemOf(null, undefined)).toEqual({ kind: "failed" });
  });

  it("undoes and redoes as new batches, in order", () => {
    let s = start();
    s = editorReducer(s, {
      type: "committed",
      plan: next(s.plan, 1),
      batch: { ops: [move], inverse: [back] },
      direction: "do",
    });
    // undo sends the inverse; the server's inverse of that becomes the redo batch's inverse
    const undo = historyRequest(s, "undo");
    expect(undo).toEqual({ ops: [back], expected: 1 });
    s = editorReducer(s, {
      type: "committed",
      plan: next(s.plan, 2),
      batch: { ops: [back], inverse: [move] },
      direction: "undo",
    });
    expect(s.undo).toEqual([]);
    expect(historyRequest(s, "redo")).toEqual({ ops: [move], expected: 2 });
    s = editorReducer(s, {
      type: "committed",
      plan: next(s.plan, 3),
      batch: { ops: [move], inverse: [back] },
      direction: "redo",
    });
    expect(s.redo).toEqual([]);
    expect(s.undo).toHaveLength(1);
    // a new edit clears redo
    s = editorReducer(s, {
      type: "committed",
      plan: next(s.plan, 4),
      batch: { ops: [back], inverse: [move] },
      direction: "do",
    });
    expect(s.redo).toEqual([]);
    expect(s.undo).toHaveLength(2);
  });
});
