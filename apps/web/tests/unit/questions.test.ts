// Client helpers over the served question set, checked against the real seeded set so a change to
// the locked questions is caught here as well as in the API tests.
import type { QuestionSet } from "@p2b/contracts";
import { describe, expect, it } from "vitest";

import seed from "../../../api/migrations/data/requirement_questions_v1.json";
import { safeNextPath } from "@/lib/navigation";
import {
  firstSectionWithError,
  formatAnswer,
  isVisible,
  keptAnswers,
  onlyUnanswered,
  questionsByKey,
  validateSection,
  type ValidationMessages,
} from "@/lib/questions";

const set = seed as unknown as QuestionSet;
const byKey = questionsByKey(set);
const question = (key: string) => {
  const found = byKey.get(key);
  if (!found) throw new Error(`no question ${key}`);
  return found;
};
const labels = { yes: "Yes", no: "No", notSure: "Not sure" };

describe("visibility", () => {
  it("shows the Other description only for Other", () => {
    expect(isVisible(question("property_type_other"), { property_type: "OTHER" })).toBe(true);
    expect(isVisible(question("property_type_other"), { property_type: "VILLA" })).toBe(false);
  });

  it("asks for sides or area depending on the plot shape", () => {
    expect(isVisible(question("plot_width_ft"), { plot_is_rectangular: true })).toBe(true);
    expect(isVisible(question("plot_area_sqft"), { plot_is_rectangular: true })).toBe(false);
    expect(isVisible(question("plot_area_sqft"), { plot_is_rectangular: false })).toBe(true);
  });
});

describe("keptAnswers", () => {
  it("drops answers to hidden questions, as the API does", () => {
    const kept = keptAnswers(set, {
      property_type: "VILLA",
      property_type_other: "a temple",
      plot_is_rectangular: false,
      plot_width_ft: 40,
      plot_area_sqft: 2400,
    });
    expect(kept).toEqual({ property_type: "VILLA", plot_is_rectangular: false, plot_area_sqft: 2400 });
  });
});

describe("formatAnswer", () => {
  it("uses option labels and ranks in order", () => {
    expect(formatAnswer(question("budget_band"), "40L_60L", labels)).toBe("₹40L to ₹60L");
    expect(
      formatAnswer(question("priorities"), ["ON_TIME", "QUALITY", "WITHIN_BUDGET", "SIMILAR_HOMES"], labels),
    ).toBe(
      "1. Finishing on time; 2. Quality of work; 3. Staying within budget; 4. Experience with similar homes",
    );
  });

  it("renders yes/no, not sure and setbacks", () => {
    expect(formatAnswer(question("basement"), false, labels)).toBe("No");
    expect(formatAnswer(question("built_up_area_sqft"), "NOT_SURE", labels)).toBe("Not sure yet");
    expect(
      formatAnswer(question("setbacks"), { FRONT: 10, BACK: 5, LEFT: "NOT_SURE", RIGHT: 3.5 }, labels),
    ).toBe("Front: 10, Back: 5, Left: Not sure, Right: 3.5");
  });

  it("leaves unanswered questions empty", () => {
    expect(formatAnswer(question("notes"), undefined, labels)).toBe("");
    expect(formatAnswer(question("notes"), "  ", labels)).toBe("");
  });
});

describe("firstSectionWithError", () => {
  it("finds the step to reopen", () => {
    expect(firstSectionWithError(set, { budget_band: ["This answer is required."] })).toBe(2);
    expect(firstSectionWithError(set, {})).toBeNull();
  });
});

describe("safeNextPath", () => {
  it.each([
    ["/projects/abc/requirement", "/projects/abc/requirement"],
    ["https://evil.test/", "/projects"],
    ["//evil.test/x", "/projects"],
    ["/\\evil.test", "/projects"],
    ["javascript:alert(1)", "/projects"],
    [undefined, "/projects"],
  ])("%s -> %s", (input, expected) => {
    expect(safeNextPath(input)).toBe(expected);
  });
});

const messages: ValidationMessages = {
  required: "required",
  number: "number",
  min: (min) => `min ${min}`,
  max: (max) => `max ${max}`,
  maxLength: (max) => `maxLength ${max}`,
  allSides: "allSides",
  rankAll: (count) => `rankAll ${count}`,
};
const PLOT = 0;
const MORE = 4;

describe("validateSection (rules come from the question set)", () => {
  it("asks for every required, visible answer and nothing hidden or optional", () => {
    const errors = validateSection(set, PLOT, { plot_is_rectangular: true }, messages);
    expect(Object.keys(errors).sort()).toEqual(
      ["facing", "locality", "location", "plot_depth_ft", "plot_width_ft", "property_type", "setbacks"].sort(),
    );
    expect(errors.plot_area_sqft).toBeUndefined(); // hidden for a rectangle
    expect(onlyUnanswered(errors, messages)).toBe(true);
  });

  it("checks ranges, every setback side and the length of notes", () => {
    const errors = validateSection(
      set,
      PLOT,
      { plot_is_rectangular: true, plot_width_ft: 2, plot_depth_ft: 2000, setbacks: { FRONT: 10 } },
      messages,
    );
    expect(errors.plot_width_ft).toEqual(["min 5"]);
    expect(errors.plot_depth_ft).toEqual(["max 1000"]);
    expect(errors.setbacks).toEqual(["allSides"]);
    expect(onlyUnanswered(errors, messages)).toBe(false);
    expect(validateSection(set, MORE, { notes: "x".repeat(501) }, messages).notes).toEqual([
      "maxLength 500",
    ]);
  });

  it("requires the whole ranking", () => {
    const errors = validateSection(set, 3, { priorities: ["QUALITY"] }, messages);
    expect(errors.priorities).toEqual(["rankAll 4"]);
  });

  it("accepts not sure where the set allows it", () => {
    const setbacks = { FRONT: "NOT_SURE", BACK: 0, LEFT: 3, RIGHT: "NOT_SURE" };
    const errors = validateSection(set, PLOT, { setbacks }, messages);
    expect(errors.setbacks).toBeUndefined();
    expect(validateSection(set, 1, { built_up_area_sqft: "NOT_SURE" }, messages).built_up_area_sqft).toBeUndefined();
  });
});
