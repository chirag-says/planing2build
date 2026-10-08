// Checkpoint 4 in the web app: the assistant's proposals are read from the server's structured
// result (never from model prose), applying is the owner's choice, and the panel is accessible.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AssistantPanel } from "@/components/plan2build/plan/plan-assistant";
import { changeLines, intentLine, outcomeLine, previewOf, refusalDetails } from "@/lib/plan/assistant";
import { initialState } from "@/lib/plan/editor";
import type { AssistantEdit } from "@/lib/plan/types";

import { fixture } from "./plan-fixtures";

const plan = fixture("3bhk_45x70_two_cars_puja");
const call = {
  provider: "mock",
  model: "mock-rules-v1",
  request_id: "r",
  duration_ms: 5,
  model_calls: 1,
  input_tokens: 0,
  output_tokens: 0,
};

function proposal(over: Partial<AssistantEdit> = {}): AssistantEdit {
  return {
    status: "PROPOSED",
    intent: { action: "RESIZE_ROOM", room: "living", change: "LARGER", amount: "MODERATE" },
    ops: [{ op: "MOVE_EDGE", room: "living", side: "LEFT", delta_mm: -600 }],
    expected_revision: 0,
    preview: plan.geometry,
    rooms: [
      {
        room: "living",
        name: "Living room",
        kind: "CHANGED",
        area_before_mm2: 20_858_600,
        area_after_mm2: 23_100_000,
        type_before: "LIVING",
        type_after: "LIVING",
      },
    ],
    openings: [{ opening: "window_living", kind: "RESIZED", width_before_mm: 1200, width_after_mm: 1500 }],
    detail: null,
    refusal: null,
    call,
    ...over,
  };
}

describe("reading a proposal", () => {
  it("states the understood intent and every change with the engine's numbers", () => {
    const edit = proposal();
    expect(intentLine(edit, plan.document)).toBe("Make Living room larger.");
    expect(changeLines(edit, plan.document, "m")).toEqual([
      "Living room: 20.86 m² to 23.10 m²",
      `${changeLines(edit, plan.document, "m")[1].split(":")[0]}: 1.20 m to 1.50 m wide`,
    ]);
    expect(changeLines(edit, plan.document, "m")[1]).toMatch(/window of Living room/);
    expect(previewOf(edit)).not.toBeNull();
  });

  it("explains unsupported, unclear and failed requests without inventing anything", () => {
    const doc = plan.document;
    expect(
      outcomeLine(proposal({ status: "UNSUPPORTED", detail: "ADD_FLOOR", ops: [], rooms: [], openings: [] }), doc),
    ).toMatch(/single storey/);
    expect(outcomeLine(proposal({ status: "UNSUPPORTED", detail: "SOMETHING", ops: [] }), doc)).toMatch(/outside what/);
    expect(outcomeLine(proposal({ status: "CLARIFY", detail: "Which room?" }), doc)).toBe(
      "Could you say a little more? Which room?",
    );
    // FAILED without the engine's refusal: the model's answers could not be read as a change
    expect(outcomeLine(proposal({ status: "FAILED", detail: "MALFORMED_ANSWER", refusal: null }), doc)).toMatch(
      /another way/,
    );
  });
});

// Checkpoint 4.1: when the engine refuses, the owner reads the engine's reason, in the same
// words the editor uses for a manual edit, whatever the model said on a repair.
describe("the engine's refusal", () => {
  const doc = plan.document;
  const failed = (over: Partial<AssistantEdit>) =>
    proposal({ status: "FAILED", ops: [], preview: null, rooms: [], openings: [], ...over });

  it("names the protected function, as a manual edit would", () => {
    const kitchen = failed({
      intent: { action: "REMOVE_ROOM", room: "kitchen" },
      detail: "LAST_KITCHEN_REQUIRED",
      refusal: {
        reason: "LAST_KITCHEN_REQUIRED",
        rejections: [{ op: "DELETE_ROOM", code: "LAST_KITCHEN_REQUIRED", entities: ["kitchen"] }],
        issues: [],
      },
    });
    expect(intentLine(kitchen, doc)).toBe("Remove Kitchen.");
    expect(outcomeLine(kitchen, doc)).toBe(
      "Kitchen is the only kitchen. A home needs one, so it cannot be removed or changed to another type.",
    );
    const bath = failed({
      intent: { action: "CHANGE_ROOM_TYPE", room: "bath_common_1", room_type: "PUJA" },
      detail: "LAST_BATHROOM_REQUIRED",
      refusal: {
        reason: "LAST_BATHROOM_REQUIRED",
        rejections: [{ op: "SET_ROOM_TYPE", code: "LAST_BATHROOM_REQUIRED", entities: ["bath_common_1"] }],
        issues: [],
      },
    });
    expect(outcomeLine(bath, doc)).toMatch(/is the only bathroom or toilet\. A home needs one/);
    expect(refusalDetails(bath, doc, "m")).toEqual([]);
  });

  it("says where a new room does not fit, and lists what stopped every candidate", () => {
    const court = failed({
      intent: { action: "ADD_ROOM", room_type: "BEDROOM", area: "COURT" },
      refusal: { reason: "NO_PLACE_FOR_ROOM", rejections: [], issues: [] },
    });
    expect(outcomeLine(court, doc)).toBe(
      "The open area (Open court) has no space for this room (Bedroom) at its smallest allowed size.",
    );
    const rules = failed({
      intent: { action: "RESIZE_ROOM", room: "bedroom_1", change: "LARGER", amount: "MODERATE" },
      refusal: {
        reason: "RULES_NOT_MET",
        rejections: [{ op: "MOVE_EDGE", code: "HOSTED_ITEM_LEAVES_WALL", entities: [] }],
        issues: [],
      },
    });
    expect(outcomeLine(rules, doc)).toMatch(/^No version of this change keeps the plan within its rules/);
    expect(refusalDetails(rules, doc, "m")).toHaveLength(1);
  });

  it("declines permits, drawings, structure and Vastu certification without claiming any", () => {
    for (const topic of [
      "PERMIT_COMPLIANCE",
      "CONSTRUCTION_DRAWINGS",
      "STRUCTURAL_ENGINEERING",
      "VASTU_CERTIFICATION",
    ]) {
      const line = outcomeLine(failed({ status: "UNSUPPORTED", detail: topic }), doc);
      expect(line).not.toMatch(/outside what/); // each has its own sentence
      expect(line).not.toMatch(/\b(is|are) (approved|compliant|certified)\b/i);
    }
    expect(outcomeLine(failed({ status: "UNSUPPORTED", detail: "CONSTRUCTION_DRAWINGS" }), doc)).toMatch(
      /not a construction, structural or approval drawing/,
    );
  });
});

describe("the assistant panel", () => {
  it("is labelled, says what it is, and offers nothing to apply before a proposal", () => {
    const html = renderToStaticMarkup(
      <AssistantPanel projectId="p" planId="q" state={initialState(plan)} dispatch={() => {}} onApply={() => {}} />,
    );
    const ids = [...html.matchAll(/ id="([^"]+)"/g)].map((m) => m[1]);
    for (const m of html.matchAll(/ for="([^"]+)"/g)) expect(ids).toContain(m[1]);
    expect(html).toContain("AI-assisted design interpretation");
    expect(html).not.toContain(">Apply<");
    expect(html).not.toMatch(/architect|engineer-approved|certif/i);
  });
});
