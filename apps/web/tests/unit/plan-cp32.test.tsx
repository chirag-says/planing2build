// Checkpoint 3.2 in the web app: rooms added in open space from the server's insertion slots.
// The size check and its reasons come before anything is sent; the preview is UI only; the
// operation names a position along a known side, never free coordinates. Real engine plans.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { OpenAreaPanel } from "@/components/plan2build/plan/plan-panels";
import { roomRect } from "@/lib/plan/edit";
import { editorReducer, initialState } from "@/lib/plan/editor";
import { addOutsideOp, fitProblems, previewRect, slotsFacing, smallestSize } from "@/lib/plan/insert";

import { FIXTURES, fixture } from "./plan-fixtures";

describe("insertion slots", () => {
  it.each(FIXTURES)("turns every slot of %s into a room that fits it, beside its wall", (name) => {
    const { document, editing } = fixture(name);
    for (const slot of editing.insertion_slots) {
      for (const type of editing.room_types) {
        const size = smallestSize(slot, type, editing.grid_mm);
        const problems = fitProblems(slot, type, size);
        const op = addOutsideOp(slot, type.type, size, "start");
        if (problems.length > 0) continue;
        expect(op).toMatchObject({ op: "ADD_ROOM_OUTSIDE", host_room: slot.host_room, side: slot.side });
        // the preview stands against the host's wall, outside it, within the slot
        const rect = previewRect(document, slot, size, "end");
        const host = roomRect(document, slot.host_room);
        if (!rect || !host) throw new Error("no rect");
        const touches =
          (slot.side === "LEFT" && rect.x1 === host.x0) ||
          (slot.side === "RIGHT" && rect.x0 === host.x1) ||
          (slot.side === "FRONT" && rect.y1 === host.y0) ||
          (slot.side === "BACK" && rect.y0 === host.y1);
        expect(touches).toBe(true);
        expect(Math.max(rect.x1 - rect.x0, rect.y1 - rect.y0)).toBeGreaterThan(0);
      }
    }
  });

  it("explains, with numbers, why a room does not fit", () => {
    const { editing } = fixture("3bhk_50x60_wide_two_cars");
    const slot = editing.insertion_slots[0];
    const bedroom = editing.room_types.find((t) => t.type === "BEDROOM");
    if (!slot || !bedroom) throw new Error("no slot");
    const tiny = { depth: slot.depth_allowance_mm + 1000, length: slot.length_allowance_mm + 1000 };
    const kinds = fitProblems(slot, bedroom, tiny).map((p) => p.kind);
    expect(kinds).toEqual(expect.arrayContaining(["shallow", "narrow", "small"]));
    const huge = { depth: slot.max_depth_mm + 50, length: slot.length_mm + 50 };
    expect(fitProblems(slot, bedroom, huge).map((p) => p.kind)).toEqual(expect.arrayContaining(["tooDeep", "tooLong"]));
    expect(addOutsideOp(slot, "BEDROOM", huge, "start")).toBeNull();
  });

  it("offers no slot on a plan with no open space against its walls", () => {
    expect(fixture("1bhk_30x40_no_parking").editing.insertion_slots).toEqual([]);
  });
});

describe("the open-area panel and the preview", () => {
  const plan = fixture("3bhk_50x60_wide_two_cars");
  const area = plan.geometry.floors[0].open_areas?.find((a) => slotsFacing(plan.editing, a.id).length > 0);

  it("labels every control and offers each facing wall", () => {
    if (!area) throw new Error("no area with a slot");
    const state = editorReducer(initialState(plan), { type: "select", selection: { kind: "area", id: area.id } });
    const html = renderToStaticMarkup(
      <OpenAreaPanel state={state} dispatch={() => {}} onCommit={() => {}} areaId={area.id} />,
    );
    const ids = [...html.matchAll(/ id="([^"]+)"/g)].map((m) => m[1]);
    for (const m of html.matchAll(/ for="([^"]+)"/g)) expect(ids).toContain(m[1]);
    expect(html.split('type="radio"').length - 1).toBe(slotsFacing(plan.editing, area.id).length);
    expect(html).toContain("Add room");
  });

  it("keeps the preview in the editor only, and drops it on a new selection or a stored change", () => {
    let s = initialState(plan);
    s = editorReducer(s, { type: "preview", rect: { x0: 0, y0: 0, x1: 1000, y1: 1000 } });
    expect(s.preview).not.toBeNull();
    expect(s.plan).toBe(initialState(plan).plan);
    expect(editorReducer(s, { type: "select", selection: null }).preview).toBeNull();
    const stored = editorReducer(s, {
      type: "committed",
      plan: { ...s.plan, editing: { ...s.plan.editing, revision_no: 1 } },
      batch: { ops: [], inverse: [{ op: "REVERT_TO_REVISION", revision: 0 }] },
      direction: "do",
    });
    expect(stored.preview).toBeNull();
  });
});
