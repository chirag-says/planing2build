// Generating a concept floor plan from the designs page: the form becomes the contract's
// DesignInputs and nothing else, the server's DESIGN_INPUT_REQUIRED and VALIDATION_ERROR details
// land on the right fields, generating is locked with the reason the API gives, the list is read
// again only while a plan is in flight, and the assistant's proposal and a plan's outcome read
// from the server's structured answer.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { FloorPlans } from "@/components/plan2build/plan/floor-plans";
import {
  anyInFlight,
  conflictLine,
  emptyForm,
  failureText,
  generationLock,
  infeasibilityView,
  mergePlans,
  missingProblems,
  pollDelay,
  preferenceLine,
  proposedInputLines,
  rejectedProblems,
  statusLock,
  toDesignInputs,
  unsupportedReasons,
  withProposal,
  withoutProposed,
  type PlanSummary,
} from "@/lib/plan/generate";

function summary(over: Partial<PlanSummary> = {}): PlanSummary {
  return {
    plan_id: "p1",
    sequence: 1,
    state: "QUEUED",
    validity: null,
    failure_reason: null,
    ruleset_version: 1,
    ruleset_status: "PUBLISHED",
    ruleset_is_synthetic: false,
    is_authoritative: false,
    created_at: "2026-10-08T10:00:00Z",
    completed_at: null,
    ...over,
  };
}

describe("the form as DesignInputs", () => {
  it("sends nothing when nothing is set", () => {
    expect(toDesignInputs(emptyForm())).toEqual({ inputs: null, problems: {} });
  });

  it("sends only what was set, typed as the contract wants", () => {
    const form = {
      ...emptyForm(),
      facing_override: "NE",
      setback_FRONT: "5",
      setback_LEFT: "2.5",
      attached_bathrooms: "1",
      parking_spaces: "2",
      parking_kind: "CAR",
      dining: "IN_LIVING",
      kitchen: "OPEN",
      stair: "NONE",
      utility: "no",
    };
    expect(toDesignInputs(form)).toEqual({
      inputs: {
        kind: "PROVISIONAL_DESIGN_INPUTS",
        version: 1,
        facing_override: "NE",
        setbacks_ft: { FRONT: 5, LEFT: 2.5 },
        attached_bathrooms: 1,
        parking_spaces: 2,
        parking_kind: "CAR",
        dining: "IN_LIVING",
        kitchen: "OPEN",
        stair: "NONE",
        utility: false,
      },
      problems: {},
    });
  });

  it("reports values outside the contract's bounds instead of sending them", () => {
    const form = { ...emptyForm(), bedrooms_exact: "4", parking_spaces: "1.5", setback_BACK: "250", setback_RIGHT: "2.345" };
    const { inputs, problems } = toDesignInputs(form);
    expect(inputs).toBeNull();
    expect(problems).toEqual({
      bedrooms_exact: { kind: "range", min: 5, max: 12 },
      parking_spaces: { kind: "range", min: 1, max: 4 },
      setback_BACK: { kind: "setback" },
      setback_RIGHT: { kind: "setback" },
    });
  });

  it("puts the assistant's proposal into the form without touching what it does not propose", () => {
    const typed = { ...emptyForm(), setback_FRONT: "6", kitchen: "CLOSED" };
    const next = withProposal(typed, {
      kind: "PROVISIONAL_DESIGN_INPUTS",
      version: 1,
      stair: "NONE",
      utility: true,
      attached_bathrooms: 2,
      dining: "SEPARATE",
    });
    expect(next).toMatchObject({
      setback_FRONT: "6",
      kitchen: "CLOSED",
      stair: "NONE",
      utility: "yes",
      attached_bathrooms: "2",
      dining: "SEPARATE",
      facing_override: "",
    });
  });
});

describe("the server's answers on the fields", () => {
  it("keeps the server's questions the proposal does not answer", () => {
    const problems = missingProblems({
      missing: [
        { key: "SETBACK_LEFT", reason: "NOT_SURE" },
        { key: "KITCHEN", reason: "NOT_ANSWERED" },
      ],
    });
    expect(
      withoutProposed(problems, { kind: "PROVISIONAL_DESIGN_INPUTS", version: 1, kitchen: "OPEN" }),
    ).toEqual({ setback_LEFT: { kind: "missing", reason: "NOT_SURE" } });
  });

  it("names a setback side inside a sentence", () => {
    expect(
      proposedInputLines({ kind: "PROVISIONAL_DESIGN_INPUTS", version: 1, setbacks_ft: { LEFT: "2.50" } }),
    ).toEqual(["Setback, left: 2.5 ft"]);
  });

  it("marks each missing input with its reason", () => {
    expect(
      missingProblems({
        missing: [
          { key: "SETBACK_BACK", reason: "NOT_SURE" },
          { key: "ATTACHED_BATHROOMS", reason: "OUT_OF_RANGE" },
          { key: "DINING", reason: "NOT_ANSWERED" },
          { key: "SOMETHING_NEW", reason: "NOT_ANSWERED" },
        ],
      }),
    ).toEqual({
      setback_BACK: { kind: "missing", reason: "NOT_SURE" },
      attached_bathrooms: { kind: "missing", reason: "OUT_OF_RANGE" },
      dining: { kind: "missing", reason: "NOT_ANSWERED" },
    });
    expect(missingProblems(null)).toEqual({});
  });

  it("marks inputs that contradict the requirement and values the contract refuses", () => {
    const { problems, other } = rejectedProblems({
      fields: {
        design_inputs: [
          "BEDROOMS_EXACT contradicts the submitted requirement; change the requirement instead",
          "something else",
        ],
        "design_inputs.parking_spaces": ["Input should be less than or equal to 4"],
        "design_inputs.setbacks_ft.LEFT": ["bad"],
        text: ["unrelated"],
      },
    });
    expect(problems).toEqual({
      bedrooms_exact: { kind: "conflict" },
      parking_spaces: { kind: "invalid", messages: ["Input should be less than or equal to 4"] },
      setback_LEFT: { kind: "invalid", messages: ["bad"] },
    });
    expect(other).toEqual(["something else", "unrelated"]);
  });

  it("keeps only the unsupported reasons the contract knows", () => {
    expect(unsupportedReasons({ reasons: ["PLOT_NOT_RECTANGULAR", "NEW_ONE", "FLOORS_NOT_SUPPORTED"] })).toEqual([
      "PLOT_NOT_RECTANGULAR",
      "FLOORS_NOT_SUPPORTED",
    ]);
  });
});

describe("when generating is locked", () => {
  const plans = [summary({ state: "VALID" })];

  it("follows the server's eligible project states", () => {
    expect(statusLock("SUBMITTED")).toBeNull();
    expect(statusLock("BUILDING")).toBeNull();
    expect(statusLock("COMPLETED")).toBeNull();
    expect(statusLock("DRAFT")).toBe("NOT_SUBMITTED");
    expect(statusLock("NEEDS_INFO")).toBe("NEEDS_INFO");
    expect(statusLock("ON_HOLD")).toBe("ON_HOLD");
    expect(statusLock("CANCELLED")).toBe("CLOSED");
    expect(statusLock("ARCHIVED")).toBe("CLOSED");
  });

  it("gives the most fundamental reason first", () => {
    const base = { isOwner: true, status: "SUBMITTED", plans, rulesetBlocked: false };
    expect(generationLock(base)).toBeNull();
    expect(generationLock({ ...base, isOwner: null })).toBeNull();
    expect(generationLock({ ...base, isOwner: false, status: "NEEDS_INFO" })).toBe("OWNER_ONLY");
    expect(generationLock({ ...base, status: "NEEDS_INFO", rulesetBlocked: true })).toBe("NEEDS_INFO");
    expect(generationLock({ ...base, rulesetBlocked: true, plans: [summary({ state: "RUNNING" })] })).toBe(
      "RULESET_NOT_PUBLISHED",
    );
    expect(generationLock({ ...base, plans: [summary({ state: "QUEUED" })] })).toBe("IN_PROGRESS");
  });
});

describe("reading the list again", () => {
  it("polls only while a plan is queued or running", () => {
    expect(anyInFlight([summary({ state: "QUEUED" })])).toBe(true);
    expect(anyInFlight([summary({ state: "RUNNING" }), summary({ plan_id: "p2", state: "VALID" })])).toBe(true);
    expect(anyInFlight([summary({ state: "VALID" }), summary({ state: "INFEASIBLE" }), summary({ state: "FAILED" })])).toBe(
      false,
    );
  });

  it("waits longer after the first minute", () => {
    expect(pollDelay(0)).toBe(2_500);
    expect(pollDelay(59_999)).toBe(2_500);
    expect(pollDelay(60_000)).toBe(10_000);
  });

  it("keeps a just-requested plan until a read includes it", () => {
    const fresh = [summary({ plan_id: "old", sequence: 1, state: "VALID" })];
    const requested = summary({ plan_id: "new", sequence: 2 });
    expect(mergePlans(fresh, requested).map((p) => p.plan_id)).toEqual(["new", "old"]);
    expect(mergePlans([requested, ...fresh], requested).map((p) => p.plan_id)).toEqual(["new", "old"]);
    expect(mergePlans(fresh, null)).toEqual(fresh);
  });
});

describe("words for a person", () => {
  it("lists the proposed inputs with their labels", () => {
    expect(
      proposedInputLines({
        kind: "PROVISIONAL_DESIGN_INPUTS",
        version: 1,
        stair: "NONE",
        utility: false,
        kitchen: "OPEN",
        parking_kind: "TWO_WHEELER",
        parking_spaces: 1,
      }),
    ).toEqual([
      "Parking spaces: 1",
      "Parking for: Two-wheelers",
      "Kitchen: Open kitchen",
      "Stair: No stair",
      "Utility room: No",
    ]);
    expect(proposedInputLines(null)).toEqual([]);
  });

  it("states where the words differ from the requirement", () => {
    expect(conflictLine({ key: "bedrooms", requirement: "3", said: "5_PLUS" })).toBe(
      "Bedrooms: the requirement says 3, you said 5 or more",
    );
    expect(conflictLine({ key: "facing", requirement: "N", said: "SE" })).toBe(
      "Facing: the requirement says North, you said South-east",
    );
    expect(conflictLine({ key: "car_parking", requirement: true, said: false })).toBe(
      "Parking: the requirement says Yes, you said No",
    );
    expect(conflictLine({ key: "plot_width_ft", requirement: 30, said: 40.5 })).toBe(
      "Plot width: the requirement says 30 ft, you said 40.5 ft",
    );
  });

  it("reads the kept preferences and drops ones it cannot read", () => {
    expect(preferenceLine("living_size:LARGE")).toBe("A large living room");
    expect(preferenceLine("adjacent:KITCHEN-DINING:REQUIRED")).toBe("Kitchen next to Dining (a must)");
    expect(preferenceLine("adjacent:MASTER_BEDROOM-BATHROOM:PREFERRED")).toBe("Main bedroom next to Bathroom");
    expect(preferenceLine("private:STUDY")).toBe("Study kept private");
    expect(preferenceLine("entrance:SIDE")).toBe("Entrance at the side");
    expect(preferenceLine("something:else")).toBeNull();
  });

  it("explains an infeasible plan without calling a supported-layout miss impossible", () => {
    const view = infeasibilityView({
      reasons: [{ code: "AREA_BUDGET", params: {}, message_key: "houseplans.infeasible.area_budget" }],
      classification: "NO_SUPPORTED_LAYOUT",
      message_key: "houseplans.infeasible.no_supported_layout",
      message: "server text",
      explanation: "In the closest one, Kitchen would have 4.00 m²; the rules need 5.00 m².",
      constraints: [],
    });
    expect(view.headline).toMatch(/does not mean it cannot be designed/);
    expect(view.headline).not.toMatch(/impossible/i);
    expect(view.reasons).toEqual(["The rooms need more floor area than the buildable area has."]);
    expect(view.explanation).toMatch(/Kitchen/);
    expect(infeasibilityView(null).reasons).toEqual([]);
  });

  it("says what went wrong with a failed plan", () => {
    expect(failureText("ENGINE_TIMEOUT")).toMatch(/too long/);
    expect(failureText(null)).toBe("The floor plan could not be made.");
  });
});

describe("the floor plans section", () => {
  const props = { projectId: "proj", status: "SUBMITTED" as const, assistant: null };

  it("offers generating to the owner, with the assistant while it is not known to be off", () => {
    const html = renderToStaticMarkup(<FloorPlans {...props} initial={[]} isOwner={true} />);
    expect(html).toContain("Generate floor plan");
    expect(html).toContain("Describe it in words");
    expect(html).toContain("No floor plan yet.");
  });

  it("hides the assistant when the API says it is off", () => {
    const html = renderToStaticMarkup(<FloorPlans {...props} assistant={false} initial={[]} isOwner={true} />);
    expect(html).toContain("Generate floor plan");
    expect(html).not.toContain("Describe it in words");
  });

  it("is read only for a member who is not the owner", () => {
    const html = renderToStaticMarkup(
      <FloorPlans {...props} initial={[summary({ state: "VALID" })]} isOwner={false} />,
    );
    expect(html).toContain("Only the project owner can generate floor plans");
    expect(html).not.toContain("Generate floor plan<");
    expect(html).toContain("Open floor plan");
  });

  it("locks generating while a plan is being laid out, and says so on the plan", () => {
    const html = renderToStaticMarkup(<FloorPlans {...props} initial={[summary({ state: "RUNNING" })]} isOwner={true} />);
    expect(html).toContain("A floor plan is being laid out");
    expect(html).toContain("This list updates by itself");
    expect(html).toMatch(/<button[^>]*type="submit"[^>]*disabled/);
  });

  it("locks generating while the requirement is being updated", () => {
    const html = renderToStaticMarkup(
      <FloorPlans {...props} status="NEEDS_INFO" initial={[]} isOwner={true} />,
    );
    expect(html).toContain("Your requirement is being updated");
    expect(html).not.toContain("Describe it in words");
  });

  it("says why a plan failed", () => {
    const html = renderToStaticMarkup(
      <FloorPlans
        {...props}
        initial={[summary({ state: "FAILED", failure_reason: "STALE" })]}
        isOwner={true}
      />,
    );
    expect(html).toContain("The request was not picked up in time.");
    expect(html).toContain("Could not be made");
  });
});
