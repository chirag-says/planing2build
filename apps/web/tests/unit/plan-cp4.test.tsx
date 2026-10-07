// Checkpoint 4 in the web app: the assistant's proposals are read from the server's structured
// result (never from model prose), applying is the owner's choice, and the panel is accessible.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AssistantPanel } from "@/components/plan2build/plan/plan-assistant";
import { changeLines, intentLine, outcomeLine, previewOf } from "@/lib/plan/assistant";
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
    expect(outcomeLine(proposal({ status: "UNSUPPORTED", detail: "ADD_FLOOR", ops: [], rooms: [], openings: [] }))).toMatch(
      /single storey/,
    );
    expect(outcomeLine(proposal({ status: "UNSUPPORTED", detail: "SOMETHING", ops: [] }))).toMatch(/outside what/);
    expect(outcomeLine(proposal({ status: "CLARIFY", detail: "Which room?" }))).toBe(
      "Could you say a little more? Which room?",
    );
    expect(outcomeLine(proposal({ status: "FAILED", detail: "NOTHING_VALID" }))).toBe(
      "I could not make that change without breaking the plan's current rules.",
    );
    expect(outcomeLine(proposal({ status: "FAILED", detail: "MALFORMED_ANSWER" }))).toMatch(/another way/);
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
