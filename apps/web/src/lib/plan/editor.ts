// The editor's state, one reducer per page (HR S; IC 19.6). It holds the last server response
// (the canonical document and its derived geometry), UI state (selection, a drag preview, snap,
// units, how sides move) and the undo and redo stacks of operation batches with their
// server-computed inverses (HR O.3). The preview is drawn over the plan and never sent: a
// committed gesture becomes an operation batch, and only the server's answer changes the plan.
//
// Three histories, kept apart (Checkpoint 3.1): this session's undo and redo stacks live here and
// end with the page; the server's revisions (every stored batch) and named versions persist and
// are restored by typed operations that make a new revision, so undo and restore never rewrite
// history. A structural edit's inverse is REVERT_TO_REVISION, so undo works the same for it.
import type { Axis, MoveMode, Side } from "./edit";
import type { PlanOp, PlanState, ValidationIssue } from "./types";

export type Selection =
  | { kind: "room"; id: string }
  | { kind: "side"; room: string; side: Side }
  | { kind: "opening"; id: string; room?: string }; // room: the list it was picked from

export type Drag =
  // a room side moving along its axis: its line from `from` to `to` (world mm)
  | { kind: "side"; room: string; side: Side; axis: Axis; from: number; to: number; guide: number | null }
  // a whole room moving along one axis by `delta` (world mm)
  | { kind: "room"; room: string; axis: Axis; delta: number; guide: number | null }
  // an opening sliding along its host wall to `offset`
  | { kind: "opening"; id: string; offset: number };

export type Problem =
  | { kind: "invalid"; issues: ValidationIssue[] } // PLAN_EDIT_INVALID: the validator said no
  | { kind: "rejected"; code: string; entities: string[] } // PLAN_OPERATION_REJECTED: cannot apply
  | { kind: "conflict" } // REVISION_CONFLICT: changed elsewhere; reload
  | { kind: "history" } // PLAN_HISTORY_UNAVAILABLE: an earlier state cannot be rebuilt exactly
  | { kind: "failed" }; // anything else (network, server)

export interface Batch {
  ops: PlanOp[];
  inverse: PlanOp[];
}

export type Units = "m" | "ft";

export interface EditorState {
  plan: PlanState;
  selection: Selection | null;
  drag: Drag | null;
  busy: boolean;
  problem: Problem | null;
  undo: Batch[];
  redo: Batch[];
  snap: boolean;
  units: Units;
  moveMode: MoveMode;
}

export type Direction = "do" | "undo" | "redo";

export type EditorAction =
  | { type: "select"; selection: Selection | null }
  | { type: "drag"; drag: Drag }
  | { type: "cancel" }
  | { type: "commit" }
  | { type: "committed"; plan: PlanState; batch: Batch; direction: Direction }
  | { type: "failed"; problem: Problem }
  | { type: "dismiss" }
  | { type: "snap"; on: boolean }
  | { type: "units"; units: Units }
  | { type: "moveMode"; mode: MoveMode }
  | { type: "reload"; plan: PlanState };

export function initialState(plan: PlanState): EditorState {
  return {
    plan,
    selection: null,
    drag: null,
    busy: false,
    problem: null,
    undo: [],
    redo: [],
    snap: true,
    units: "m",
    moveMode: "edge",
  };
}

export const HISTORY_LIMIT = 100;

export function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case "select":
      return { ...state, selection: action.selection, drag: null };
    case "drag":
      return state.busy ? state : { ...state, drag: action.drag };
    case "cancel":
      // Escape: drop the gesture; the plan is untouched because nothing was sent
      return { ...state, drag: null, selection: state.drag ? state.selection : null };
    case "commit":
      return { ...state, busy: true, problem: null };
    case "committed": {
      const { batch, direction } = action;
      let undo = state.undo;
      let redo = state.redo;
      if (direction === "do") {
        undo = [...undo, batch].slice(-HISTORY_LIMIT);
        redo = [];
      } else if (direction === "undo") {
        undo = undo.slice(0, -1);
        redo = [...redo, batch];
      } else {
        redo = redo.slice(0, -1);
        undo = [...undo, batch].slice(-HISTORY_LIMIT);
      }
      return { ...state, plan: action.plan, busy: false, drag: null, problem: null, undo, redo };
    }
    case "failed":
      return { ...state, busy: false, drag: null, problem: action.problem };
    case "dismiss":
      return { ...state, problem: null };
    case "snap":
      return { ...state, snap: action.on };
    case "units":
      return { ...state, units: action.units };
    case "moveMode":
      return { ...state, moveMode: action.mode };
    case "reload":
      return { ...initialState(action.plan), snap: state.snap, units: state.units, moveMode: state.moveMode };
  }
}

/** The batch to send for undo or redo, and the expected revision; null when there is nothing. */
export function historyRequest(
  state: EditorState,
  direction: "undo" | "redo",
): { ops: PlanOp[]; expected: number } | null {
  const stack = direction === "undo" ? state.undo : state.redo;
  const top = stack[stack.length - 1];
  if (!top) return null;
  return { ops: top.inverse, expected: state.plan.editing.revision_no };
}

/** The problem for an API error envelope. */
export function problemOf(code: string | null, details: unknown): Problem {
  if (code === "PLAN_EDIT_INVALID") {
    const report = (details as { report?: { errors?: ValidationIssue[] } } | undefined)?.report;
    return { kind: "invalid", issues: report?.errors ?? [] };
  }
  if (code === "PLAN_OPERATION_REJECTED") {
    const d = details as { code?: unknown; entities?: unknown } | undefined;
    const entities = Array.isArray(d?.entities) ? d.entities.filter((e) => typeof e === "string") : [];
    return { kind: "rejected", code: typeof d?.code === "string" ? d.code : "NOT_SUPPORTED", entities };
  }
  if (code === "REVISION_CONFLICT") return { kind: "conflict" };
  if (code === "PLAN_HISTORY_UNAVAILABLE") return { kind: "history" };
  return { kind: "failed" };
}

/** Entities an issue list points at, for highlighting them in the drawing. */
export function flaggedEntities(issues: ValidationIssue[]): Set<string> {
  const out = new Set<string>();
  for (const issue of issues) for (const e of issue.entities) out.add(`${e.kind}:${e.id}`);
  return out;
}
