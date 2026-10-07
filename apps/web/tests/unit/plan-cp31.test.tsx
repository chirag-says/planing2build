// Checkpoint 3.1 in the web app: local edge moves, room add/remove/rename/retype, door and window
// add/resize/move/remove, readable validation and rejection messages, the restore operations and
// the three histories. Everything runs on real engine plans (plan-fixtures).
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { lengthFromInput, OpeningsList, RoomPanel } from "@/components/plan2build/plan/plan-panels";
import {
  addOpeningOp,
  addRoomOp,
  deleteRoomOp,
  mergeTargets,
  moveRoomOps,
  moveSideOp,
  renameRoomOp,
  resizeOpeningOps,
  roomRect,
  roomSides,
  setRoomTypeOps,
  wallNormal,
} from "@/lib/plan/edit";
import { editorReducer, historyRequest, initialState, problemOf } from "@/lib/plan/editor";
import { changeText, issueText, labelOf, rejectionText } from "@/lib/plan/messages";
import type { Compromise, PlanOp, PlanState, ValidationIssue } from "@/lib/plan/types";

import { FIXTURES, fixture } from "./plan-fixtures";

describe("moving just one side (MOVE_EDGE)", () => {
  it.each(FIXTURES)("is the default for every side of every room of %s", (name) => {
    const { document } = fixture(name);
    for (const room of document.floors[0].rooms) {
      for (const side of roomSides(document, room.id) ?? []) {
        const op = moveSideOp(document, room.id, side, 149.6);
        expect(op).toEqual({ op: "MOVE_EDGE", room: room.id, side: side.side.toUpperCase(), delta_mm: 150 });
      }
    }
  });

  it("moves a room as two edge moves, the leading side first, and never sends nothing", () => {
    const { document } = fixture("3bhk_50x60_wide_two_cars");
    expect(moveRoomOps(document, "kitchen", "x", 300)).toEqual([
      { op: "MOVE_EDGE", room: "kitchen", side: "RIGHT", delta_mm: 300 },
      { op: "MOVE_EDGE", room: "kitchen", side: "LEFT", delta_mm: 300 },
    ]);
    expect(moveRoomOps(document, "kitchen", "y", -300).map((o) => (o.op === "MOVE_EDGE" ? o.side : ""))).toEqual([
      "FRONT",
      "BACK",
    ]);
    const side = roomSides(document, "kitchen")?.[0];
    if (!side) throw new Error("no side");
    expect(moveSideOp(document, "kitchen", side, 0.3)).toBeNull();
  });
});

describe("rooms", () => {
  it.each(FIXTURES)("offers only neighbours sharing a whole side as merge targets in %s", (name) => {
    const { document } = fixture(name);
    for (const room of document.floors[0].rooms) {
      const a = roomRect(document, room.id);
      if (!a) throw new Error("no rect");
      for (const id of mergeTargets(document, room.id)) {
        const b = roomRect(document, id);
        if (!b) throw new Error("no rect");
        const rows = a.y0 === b.y0 && a.y1 === b.y1 && (a.x1 === b.x0 || b.x1 === a.x0);
        const cols = a.x0 === b.x0 && a.x1 === b.x1 && (a.y1 === b.y0 || b.y1 === a.y0);
        expect(rows || cols).toBe(true);
        expect(mergeTargets(document, id)).toContain(room.id); // symmetric
      }
    }
  });

  it("builds add, remove, rename and retype as typed operations", () => {
    const plan = fixture("2bhk_40x80_west_two_cars");
    const { document, editing } = plan;
    expect(addRoomOp("living", "UTILITY", "back", 1499.7)).toEqual({
      op: "ADD_ROOM",
      host_room: "living",
      type: "UTILITY",
      side: "BACK",
      depth_mm: 1500,
    });
    expect(addRoomOp("living", "UTILITY", "back", 0)).toBeNull();
    expect(deleteRoomOp("dining", "living")).toEqual({ op: "DELETE_ROOM", room: "dining", merge_into: "living" });
    expect(renameRoomOp(document, "bedroom_1", "  Guest room ")).toEqual({
      op: "RENAME_ROOM",
      room: "bedroom_1",
      name: "Guest room",
    });
    expect(renameRoomOp(document, "bedroom_1", "   ")).toBeNull();
    // a room with its type's default name is renamed with the type; a renamed one keeps its name
    expect(setRoomTypeOps(document, editing, "bedroom_1", "DINING")).toEqual([
      { op: "SET_ROOM_TYPE", room: "bedroom_1", type: "DINING" },
      { op: "RENAME_ROOM", room: "bedroom_1", name: "Dining 1" },
    ]);
    const renamed = structuredClone(document);
    const room = renamed.floors[0].rooms.find((r) => r.id === "bedroom_1");
    if (!room) throw new Error("no bedroom_1");
    room.name = "Grandparents";
    expect(setRoomTypeOps(renamed, editing, "bedroom_1", "DINING")).toEqual([
      { op: "SET_ROOM_TYPE", room: "bedroom_1", type: "DINING" },
    ]);
    expect(setRoomTypeOps(document, editing, "bedroom_1", "BEDROOM")).toEqual([]);
  });

  it("renders the room panel with every control labelled", () => {
    const state = initialState(fixture("3bhk_45x70_two_cars_puja"));
    const doc = state.plan.document;
    const room = doc.floors[0].rooms.find((r) => mergeTargets(doc, r.id).length > 0);
    if (!room) throw new Error("no mergeable room");
    const html = renderToStaticMarkup(
      <RoomPanel state={state} dispatch={() => {}} onCommit={() => {}} roomId={room.id} />,
    );
    const ids = [...html.matchAll(/ id="([^"]+)"/g)].map((m) => m[1]);
    const labelled = [...html.matchAll(/ for="([^"]+)"/g)].map((m) => m[1]);
    expect(labelled.length).toBeGreaterThanOrEqual(5);
    for (const id of labelled) expect(ids).toContain(id);
    expect(html).toContain("Add room");
    expect(html).toContain("Remove room");
  });
});

describe("doors and windows", () => {
  it.each(FIXTURES)("adds a door that opens into the room on the longest wall of a side in %s", (name) => {
    const { document, editing } = fixture(name);
    for (const room of document.floors[0].rooms) {
      for (const side of roomSides(document, room.id) ?? []) {
        const op = addOpeningOp(document, editing, room.id, side.side, "DOOR");
        if (!op || op.op !== "ADD_OPENING") throw new Error("no door");
        const o = op.opening;
        expect(side.walls).toContain(o.wall);
        expect(document.floors[0].openings.map((x) => x.id)).not.toContain(o.id);
        expect(o.width_mm).toBe(editing.openings?.door_width_mm);
        // the room's centre lies on the side the door opens to
        const n = wallNormal(document, o.wall);
        const rect = roomRect(document, room.id);
        const wall = document.floors[0].walls.find((w) => w.id === o.wall);
        const a = document.floors[0].nodes.find((p) => p.id === wall?.a);
        if (!n || !rect || !a) throw new Error("no frame");
        const dot = ((rect.x0 + rect.x1) / 2 - a.x) * n.x + ((rect.y0 + rect.y1) / 2 - a.y) * n.y;
        expect(o.door?.opens_to).toBe(dot > 0 ? "LEFT" : "RIGHT");
        const win = addOpeningOp(document, editing, room.id, side.side, "WINDOW");
        if (!win || win.op !== "ADD_OPENING") throw new Error("no window");
        expect(win.opening.door).toBeNull();
        expect(win.opening.sill_mm).toBe(editing.openings?.window_sill_mm);
      }
    }
  });

  it.each(FIXTURES)("resizes every opening of %s about its centre", (name) => {
    const { document } = fixture(name);
    for (const o of document.floors[0].openings) {
      const ops = resizeOpeningOps(document, o.id, o.width_mm - 100);
      expect(ops[0]).toMatchObject({ op: "SET_OPENING", opening: o.id, width_mm: o.width_mm - 100, sill_mm: o.sill_mm });
      const move = ops.find((x): x is Extract<PlanOp, { op: "MOVE_OPENING" }> => x.op === "MOVE_OPENING");
      const offset = move ? move.offset_mm : o.offset_mm;
      expect(Math.abs(offset + (o.width_mm - 100) / 2 - (o.offset_mm + o.width_mm / 2))).toBeLessThanOrEqual(1);
      expect(resizeOpeningOps(document, o.id, o.width_mm)).toEqual([]);
    }
  });

  it("lists every door and window of a room as a button a keyboard can reach", () => {
    const plan = fixture("3bhk_45x70_two_cars_puja");
    const state = editorReducer(initialState(plan), {
      type: "select",
      selection: { kind: "opening", id: plan.geometry.floors[0].openings[0].id },
    });
    const html = renderToStaticMarkup(
      <OpeningsList state={state} dispatch={() => {}} onCommit={() => {}} roomId="living" />,
    );
    const ofLiving = plan.geometry.floors[0].openings.filter((o) => o.connects.includes("living"));
    expect(ofLiving.length).toBeGreaterThan(0);
    expect(html.split("<button").length - 1).toBe(ofLiving.length);
    expect(html).toContain('aria-label="Doors and windows of Living room"');
    for (const o of ofLiving) expect(html).toContain(labelOf(o.id, plan.document, plan.geometry));
  });
});

describe("messages", () => {
  const plan = fixture("3bhk_45x70_two_cars_puja");
  const { document, geometry } = plan;

  function issue(code: string, params: Record<string, unknown>, message = "server text"): ValidationIssue {
    return {
      code,
      category: "SIZES",
      severity: "ERROR",
      entities: [],
      params,
      message,
      message_key: `houseplans.validation.${code.toLowerCase()}`,
      repair: "USER",
    } as unknown as ValidationIssue;
  }

  it("formats lengths and areas in the chosen units", () => {
    const area = issue("ROOM_BELOW_MIN_AREA", { room: "Bedroom 3", area_mm2: 2_800_000, min_mm2: 9_000_000 });
    expect(issueText(area, document, geometry, "m")).toBe("Bedroom 3 is 2.80 m²; it needs at least 9.00 m².");
    const short = issue("ROOM_BELOW_MIN_SHORT_SIDE", { room: "Bedroom 3", short_mm: 2750, min_mm: 3000 });
    expect(issueText(short, document, geometry, "m")).toBe("Bedroom 3 is 2.75 m across; it needs at least 3.00 m.");
    expect(issueText(short, document, geometry, "ft")).toBe("Bedroom 3 is 9′ 0″ across; it needs at least 9′ 10″.");
  });

  it("names fixtures and openings instead of showing ids, and keeps unknown codes as sent", () => {
    const fixtureId = document.floors[0].fixtures[0].id;
    const door = document.floors[0].openings.find((o) => o.kind === "DOOR");
    if (!door) throw new Error("no door");
    const text = issueText(issue("FIXTURE_BLOCKS_OPENING", { fixture: fixtureId, opening: door.id }), document, geometry, "m");
    expect(text).not.toContain(fixtureId);
    expect(text).not.toContain(door.id);
    expect(issueText(issue("SOMETHING_NEW", {}, "As the server says."), document, geometry, "m")).toBe("As the server says.");
  });

  it("says why an operation was refused, naming what it concerns", () => {
    const door = document.floors[0].openings.find((o) => o.kind === "DOOR");
    if (!door) throw new Error("no door");
    const text = rejectionText("HOSTED_ITEM_CHANGES_ROOMS", [door.id], document, geometry);
    expect(text).toContain(labelOf(door.id, document, geometry));
    expect(text).not.toContain(door.id);
    expect(rejectionText("ROOMS_WOULD_OVERLAP", ["living", "kitchen"], document, geometry)).toBe(
      `${labelOf("living", document, null)} would overlap ${labelOf("kitchen", document, null)}.`,
    );
    expect(rejectionText("SOMETHING_NEW", [], document, geometry)).toBe("This kind of change is not available.");
  });

  it("lists the owner's room changes and nothing else", () => {
    const base = { id: "owner_change_1", constraint: "c1", accepted_by_user: true };
    const added = { ...base, change_key: "ROOM_ADDED_BY_OWNER", params: { room: "living", room_type: "UTILITY" } };
    const retyped = {
      ...base,
      change_key: "ROOM_TYPE_CHANGED_BY_OWNER",
      params: { room: "living", from_type: "BEDROOM", to_type: "DINING" },
    };
    const removed = { ...base, change_key: "ROOM_REMOVED_BY_OWNER", params: { room: "gone", room_type: "PUJA" } };
    const other = { ...base, change_key: "AREA_REDUCED", params: {} };
    expect(changeText(added as Compromise, document)).toBe("You added Living room (Utility).");
    expect(changeText(retyped as Compromise, document)).toBe("You changed Living room from Bedroom to Dining.");
    expect(changeText(removed as Compromise, document)).toBe("You removed a room of type Puja.");
    expect(changeText(other as Compromise, document)).toBeNull();
  });
});

describe("history", () => {
  function next(plan: PlanState, revision: number): PlanState {
    return { ...plan, editing: { ...plan.editing, revision_no: revision } };
  }

  it("undoes a structural edit by restoring the revision, and redoes it the same way", () => {
    let s = initialState(fixture("2bhk_30x50_north_twowheeler_open"));
    const edge: PlanOp = { op: "MOVE_EDGE", room: "living", side: "BACK", delta_mm: 300 };
    s = editorReducer(s, {
      type: "committed",
      plan: next(s.plan, 1),
      batch: { ops: [edge], inverse: [{ op: "REVERT_TO_REVISION", revision: 0 }] },
      direction: "do",
    });
    expect(historyRequest(s, "undo")).toEqual({ ops: [{ op: "REVERT_TO_REVISION", revision: 0 }], expected: 1 });
    s = editorReducer(s, {
      type: "committed",
      plan: next(s.plan, 2),
      batch: { ops: [{ op: "REVERT_TO_REVISION", revision: 0 }], inverse: [{ op: "REVERT_TO_REVISION", revision: 1 }] },
      direction: "undo",
    });
    expect(historyRequest(s, "redo")).toEqual({ ops: [{ op: "REVERT_TO_REVISION", revision: 1 }], expected: 2 });
  });

  it("restores a named version as a new, undoable change", () => {
    let s = initialState(next(fixture("2bhk_30x50_north_twowheeler_open"), 4));
    s = editorReducer(s, {
      type: "committed",
      plan: next(s.plan, 5),
      batch: { ops: [{ op: "REVERT_TO_VERSION", version: 2 }], inverse: [{ op: "REVERT_TO_REVISION", revision: 4 }] },
      direction: "do",
    });
    expect(s.undo).toHaveLength(1);
    expect(historyRequest(s, "undo")?.ops).toEqual([{ op: "REVERT_TO_REVISION", revision: 4 }]);
  });

  it("starts a reloaded page from the server's head and revision, with an empty undo stack", () => {
    const reloaded = initialState(next(fixture("2bhk_30x50_north_twowheeler_open"), 7));
    expect(reloaded.plan.editing.revision_no).toBe(7);
    expect(reloaded.undo).toEqual([]);
    expect(reloaded.moveMode).toBe("edge");
    const kept = editorReducer(editorReducer(reloaded, { type: "moveMode", mode: "line" }), {
      type: "reload",
      plan: next(reloaded.plan, 8),
    });
    expect(kept.moveMode).toBe("line");
    expect(kept.plan.editing.revision_no).toBe(8);
  });

  it("reads the new API errors", () => {
    expect(problemOf("PLAN_HISTORY_UNAVAILABLE", { revision_no: 3 })).toEqual({ kind: "history" });
    expect(
      problemOf("PLAN_OPERATION_REJECTED", { index: 0, op: "ADD_ROOM", code: "NOT_A_SLICE", entities: ["living", 4] }),
    ).toEqual({ kind: "rejected", code: "NOT_A_SLICE", entities: ["living"] });
  });
});

describe("typed lengths", () => {
  it("reads metres and feet to whole grid steps", () => {
    expect(lengthFromInput("3", "m", 50)).toBe(3000);
    expect(lengthFromInput("1,234", "m", 50)).toBe(1250);
    expect(lengthFromInput("10", "ft", 50)).toBe(3050);
    expect(lengthFromInput("0", "m", 50)).toBeNull();
    expect(lengthFromInput("abc", "m", 50)).toBeNull();
  });
});
