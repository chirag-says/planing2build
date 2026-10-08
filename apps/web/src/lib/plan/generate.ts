// Generating a concept floor plan from the designs page (Checkpoint 1 route, Checkpoint 4
// assistant). The server decides everything: what the requirement already answers, which
// provisional design inputs are still needed (DESIGN_INPUT_REQUIRED), whether the plan is
// supported, and the outcome of the job. This module only turns the form into the contract's
// DesignInputs, reads the server's error details back onto the form's fields, says when
// generating is locked and why, and phrases the assistant's proposal and a plan's outcome for a
// person to read. Every enum comes from the generated contract; nothing here invents a value.
import {
  DesignInputKeyValues,
  DiningArrangementValues,
  FacingValues,
  KitchenArrangementValues,
  MissingInputReasonValues,
  ParkingKindValues,
  SetbackSideValues,
  StairChoiceValues,
  UnsupportedReasonValues,
  type DesignInputKey,
  type MissingInputReason,
  type PlanGenerationState,
  type ProjectStatus,
  type SetbackSide,
  type UnsupportedReason,
} from "@p2b/contracts";
import type { components } from "@p2b/contracts";

import { getTranslator } from "@/lib/i18n";

type Schemas = components["schemas"];

export type DesignInputs = Schemas["DesignInputs-Input"];
export type ProposedInputs = Schemas["DesignInputs-Output"];
export type PlanSummary = Schemas["HousePlanSummaryOut"];
export type RequirementProposal = Schemas["AssistantRequirementOut"];
export type Infeasibility = Schemas["InfeasibilityOut"];

const t = getTranslator("Plan");

// ---------- the form ----------

export const SETBACK_SIDES = SetbackSideValues;

export type ChoiceField = "facing_override" | "parking_kind" | "dining" | "kitchen" | "stair" | "utility";
export type CountField = "bedrooms_exact" | "bathrooms_exact" | "attached_bathrooms" | "parking_spaces";
export type SetbackField = `setback_${SetbackSide}`;
export type FieldId = ChoiceField | CountField | SetbackField;

/** Every field as typed: "" is "not set" and is never sent. */
export type FormValues = Record<FieldId, string>;

/** The contract's bounds for the whole-number inputs (DesignInputs in openapi.json). */
export const COUNT_RANGE: Record<CountField, readonly [number, number]> = {
  bedrooms_exact: [5, 12],
  bathrooms_exact: [5, 12],
  attached_bathrooms: [0, 12],
  parking_spaces: [1, 4],
};
export const SETBACK_MAX_FT = 200;

export const COUNT_FIELDS = Object.keys(COUNT_RANGE) as CountField[];

/** The choices for each choice field, straight from the contract's enums. */
export const CHOICES: Record<ChoiceField, readonly string[]> = {
  facing_override: FacingValues,
  parking_kind: ParkingKindValues,
  dining: DiningArrangementValues,
  kitchen: KitchenArrangementValues,
  stair: StairChoiceValues,
  utility: ["yes", "no"],
};

export const FIELD_ORDER: FieldId[] = [
  "facing_override",
  "setback_FRONT",
  "setback_BACK",
  "setback_LEFT",
  "setback_RIGHT",
  "bedrooms_exact",
  "bathrooms_exact",
  "attached_bathrooms",
  "parking_spaces",
  "parking_kind",
  "dining",
  "kitchen",
  "stair",
  "utility",
];

export function emptyForm(): FormValues {
  return Object.fromEntries(FIELD_ORDER.map((f) => [f, ""])) as FormValues;
}

export type FieldProblem =
  | { kind: "range"; min: number; max: number }
  | { kind: "setback" }
  | { kind: "missing"; reason: MissingInputReason }
  | { kind: "conflict" }
  | { kind: "invalid"; messages: string[] };

export type FieldProblems = Partial<Record<FieldId, FieldProblem>>;

const SETBACK_TEXT = /^\d{1,3}(\.\d{1,2})?$/;

/** The form as the contract's DesignInputs: only what was set, or null when nothing was. Values
 * outside the contract's bounds are reported, not sent. */
export function toDesignInputs(form: FormValues): { inputs: DesignInputs | null; problems: FieldProblems } {
  // `kind` and `version` are the contract's constants for this provisional shape
  const inputs: DesignInputs = { kind: "PROVISIONAL_DESIGN_INPUTS", version: 1 };
  const problems: FieldProblems = {};
  const v = (f: FieldId) => form[f].trim();

  const facing = v("facing_override");
  if (FacingValues.includes(facing as never)) inputs.facing_override = facing as DesignInputs["facing_override"];

  const setbacks: Partial<Record<SetbackSide, number>> = {};
  for (const side of SETBACK_SIDES) {
    const text = v(`setback_${side}`).replace(",", ".");
    if (!text) continue;
    const value = Number(text);
    if (!SETBACK_TEXT.test(text) || value > SETBACK_MAX_FT) problems[`setback_${side}`] = { kind: "setback" };
    else setbacks[side] = value;
  }
  if (Object.keys(setbacks).length > 0) inputs.setbacks_ft = setbacks;

  for (const field of COUNT_FIELDS) {
    const text = v(field);
    if (!text) continue;
    const [min, max] = COUNT_RANGE[field];
    const value = Number(text);
    if (!/^\d+$/.test(text) || value < min || value > max) problems[field] = { kind: "range", min, max };
    else inputs[field] = value;
  }

  const kind = v("parking_kind");
  if (ParkingKindValues.includes(kind as never)) inputs.parking_kind = kind as DesignInputs["parking_kind"];
  const dining = v("dining");
  if (DiningArrangementValues.includes(dining as never)) inputs.dining = dining as DesignInputs["dining"];
  const kitchen = v("kitchen");
  if (KitchenArrangementValues.includes(kitchen as never)) inputs.kitchen = kitchen as DesignInputs["kitchen"];
  const stair = v("stair");
  if (StairChoiceValues.includes(stair as never)) inputs.stair = stair as DesignInputs["stair"];
  const utility = v("utility");
  if (utility === "yes" || utility === "no") inputs.utility = utility === "yes";

  return { inputs: Object.keys(inputs).length > 2 ? inputs : null, problems };
}

/** The assistant's proposed inputs written into the form. Only what it proposes changes; every
 * other field keeps what the owner typed. */
export function withProposal(form: FormValues, proposed: ProposedInputs): FormValues {
  const next = { ...form };
  if (proposed.facing_override) next.facing_override = proposed.facing_override;
  for (const side of SETBACK_SIDES) {
    const value = proposed.setbacks_ft?.[side];
    if (value != null) next[`setback_${side}`] = String(Number(value));
  }
  for (const field of COUNT_FIELDS) {
    const value = proposed[field];
    if (value != null) next[field] = String(value);
  }
  if (proposed.parking_kind) next.parking_kind = proposed.parking_kind;
  if (proposed.dining) next.dining = proposed.dining;
  if (proposed.kitchen) next.kitchen = proposed.kitchen;
  if (proposed.stair) next.stair = proposed.stair;
  if (proposed.utility != null) next.utility = proposed.utility ? "yes" : "no";
  return next;
}

/** The problems left once the proposal fills its fields. */
export function withoutProposed(problems: FieldProblems, proposed: ProposedInputs): FieldProblems {
  const filled = withProposal(emptyForm(), proposed);
  return Object.fromEntries(
    Object.entries(problems).filter(([field]) => filled[field as FieldId] === ""),
  ) as FieldProblems;
}

// ---------- the server's answers, back on the fields ----------

const KEY_FIELD: Record<DesignInputKey, FieldId> = {
  FACING: "facing_override",
  SETBACK_FRONT: "setback_FRONT",
  SETBACK_BACK: "setback_BACK",
  SETBACK_LEFT: "setback_LEFT",
  SETBACK_RIGHT: "setback_RIGHT",
  BEDROOMS_EXACT: "bedrooms_exact",
  BATHROOMS_EXACT: "bathrooms_exact",
  ATTACHED_BATHROOMS: "attached_bathrooms",
  PARKING_SPACES: "parking_spaces",
  PARKING_KIND: "parking_kind",
  DINING: "dining",
  KITCHEN: "kitchen",
  STAIR: "stair",
  UTILITY: "utility",
};

function asKey(value: unknown): DesignInputKey | undefined {
  return DesignInputKeyValues.find((k) => k === value);
}

/** DESIGN_INPUT_REQUIRED: `details.missing` [{key, reason}] as a problem on each field. */
export function missingProblems(details: unknown): FieldProblems {
  const missing = (details as { missing?: unknown } | null)?.missing;
  const problems: FieldProblems = {};
  if (!Array.isArray(missing)) return problems;
  for (const item of missing as { key?: unknown; reason?: unknown }[]) {
    const key = asKey(item?.key);
    const reason = MissingInputReasonValues.find((r) => r === item?.reason) ?? "NOT_ANSWERED";
    if (key) problems[KEY_FIELD[key]] = { kind: "missing", reason };
  }
  return problems;
}

const CONTRADICTS = /^([A-Z_]+) contradicts the submitted requirement/;

/** VALIDATION_ERROR: an input that contradicts the requirement (`fields.design_inputs`, one
 * message per key) or a value the contract refuses (`fields["design_inputs.<field>"]`). Messages
 * that name no field are returned as they are. */
export function rejectedProblems(details: unknown): { problems: FieldProblems; other: string[] } {
  const fields = (details as { fields?: Record<string, unknown> } | null)?.fields ?? {};
  const problems: FieldProblems = {};
  const other: string[] = [];
  for (const [path, value] of Object.entries(fields)) {
    const messages = Array.isArray(value) ? value.map(String) : [String(value)];
    if (path === "design_inputs") {
      for (const message of messages) {
        const key = asKey(CONTRADICTS.exec(message)?.[1]);
        if (key) problems[KEY_FIELD[key]] = { kind: "conflict" };
        else other.push(message);
      }
      continue;
    }
    const parts = path.split(".");
    const field =
      parts[0] === "design_inputs" && parts[1] === "setbacks_ft"
        ? SETBACK_SIDES.find((s) => s === parts[2]) && (`setback_${parts[2]}` as FieldId)
        : parts[0] === "design_inputs"
          ? FIELD_ORDER.find((f) => f === parts[1])
          : undefined;
    if (field) problems[field] = { kind: "invalid", messages };
    else other.push(...messages);
  }
  return { problems, other };
}

/** PLAN_UNSUPPORTED: `details.reasons`, the known ones only. */
export function unsupportedReasons(details: unknown): UnsupportedReason[] {
  const reasons = (details as { reasons?: unknown } | null)?.reasons;
  if (!Array.isArray(reasons)) return [];
  return UnsupportedReasonValues.filter((r) => reasons.includes(r));
}

// ---------- when generating is locked ----------

export type LockReason =
  | "OWNER_ONLY"
  | "NOT_SUBMITTED"
  | "NEEDS_INFO"
  | "ON_HOLD"
  | "CLOSED"
  | "RULESET_NOT_PUBLISHED"
  | "IN_PROGRESS";

/** The project states the server generates in (ELIGIBLE_STATUSES in houseplans/service.py: the
 * requirement as submitted, never a draft or one being revised, never a closed project). The
 * server checks again and answers STATE_CONFLICT; this only explains the lock before asking. */
export function statusLock(status: ProjectStatus | string): LockReason | null {
  switch (status) {
    case "DRAFT":
      return "NOT_SUBMITTED";
    case "NEEDS_INFO":
      return "NEEDS_INFO";
    case "ON_HOLD":
      return "ON_HOLD";
    case "ARCHIVED":
    case "CANCELLED":
      return "CLOSED";
    default:
      return null;
  }
}

export function inFlight(state: PlanGenerationState): boolean {
  return state === "QUEUED" || state === "RUNNING";
}

export function anyInFlight(plans: readonly Pick<PlanSummary, "state">[]): boolean {
  return plans.some((p) => inFlight(p.state));
}

/** Why the owner cannot ask for a plan now, most fundamental first; null when they can.
 * `isOwner` null: the API did not say, so the server decides (403) when asked. */
export function generationLock(input: {
  isOwner: boolean | null;
  status: ProjectStatus | string;
  plans: readonly Pick<PlanSummary, "state">[];
  rulesetBlocked: boolean;
}): LockReason | null {
  if (input.isOwner === false) return "OWNER_ONLY";
  const byStatus = statusLock(input.status);
  if (byStatus) return byStatus;
  if (input.rulesetBlocked) return "RULESET_NOT_PUBLISHED";
  if (anyInFlight(input.plans)) return "IN_PROGRESS";
  return null;
}

/** How long to wait before asking for the list again while a plan is being laid out: every
 * 2.5 s for the first minute, then every 10 s until it finishes (the server fails a lost job). */
export function pollDelay(elapsedMs: number): number {
  return elapsedMs < 60_000 ? 2_500 : 10_000;
}

/** The plans after a fresh read, keeping a just-requested plan the read does not have yet. */
export function mergePlans(fresh: readonly PlanSummary[], pending: PlanSummary | null): PlanSummary[] {
  if (!pending || fresh.some((p) => p.plan_id === pending.plan_id)) return [...fresh];
  return [pending, ...fresh];
}

// ---------- words for a person ----------

function choiceLabel(field: ChoiceField, value: string): string {
  switch (field) {
    case "facing_override":
      return FacingValues.includes(value as never) ? t(`generate.facing.${value as (typeof FacingValues)[number]}`) : value;
    case "parking_kind":
      return ParkingKindValues.includes(value as never)
        ? t(`generate.parkingKind.${value as (typeof ParkingKindValues)[number]}`)
        : value;
    case "dining":
      return DiningArrangementValues.includes(value as never)
        ? t(`generate.dining.${value as (typeof DiningArrangementValues)[number]}`)
        : value;
    case "kitchen":
      return KitchenArrangementValues.includes(value as never)
        ? t(`generate.kitchen.${value as (typeof KitchenArrangementValues)[number]}`)
        : value;
    case "stair":
      return StairChoiceValues.includes(value as never)
        ? t(`generate.stair.${value as (typeof StairChoiceValues)[number]}`)
        : value;
    case "utility":
      return value === "yes" ? t("generate.yes") : value === "no" ? t("generate.no") : value;
  }
}

export function optionLabel(field: ChoiceField, value: string): string {
  return choiceLabel(field, value);
}

export function fieldLabel(field: FieldId): string {
  if (field.startsWith("setback_")) {
    const side = field.slice("setback_".length) as SetbackSide;
    return t("generate.setbackLine", { side: t(`generate.setbackSideNouns.${side}`) });
  }
  return t(`generate.fields.${field as ChoiceField | CountField}.label`);
}

/** The proposal's design inputs, one "label: value" line each, in the form's order. */
export function proposedInputLines(proposed: ProposedInputs | null): string[] {
  if (!proposed) return [];
  const form = withProposal(emptyForm(), proposed);
  return FIELD_ORDER.filter((f) => form[f] !== "").map((f) => {
    const value = form[f];
    const shown =
      f in CHOICES
        ? choiceLabel(f as ChoiceField, value)
        : f.startsWith("setback_")
          ? t("generate.feet", { value })
          : value;
    return t("generate.line", { label: fieldLabel(f), value: shown });
  });
}

const BRIDGE_FACTS = [
  "plot_size",
  "facing",
  "setbacks",
  "bedrooms",
  "bathrooms",
  "attached_bathrooms",
  "dining",
  "kitchen",
  "parking",
  "pooja_room",
  "utility",
] as const;

/** A fact the description did not give (`missing`) or took as not wanted (`assumed`). */
export function factLabel(key: string): string {
  const known = BRIDGE_FACTS.find((k) => k === key);
  return known ? t(`generate.words.facts.${known}`) : key;
}

const TOPICS = [
  "ADD_FLOOR",
  "FREE_SHAPE",
  "STRUCTURAL_ENGINEERING",
  "PERMIT_COMPLIANCE",
  "VASTU_CERTIFICATION",
  "PRIVACY_REDESIGN",
  "UNSUPPORTED_ROOM_TYPE",
  "IMAGES_OR_3D",
  "CONSTRUCTION_DRAWINGS",
] as const;

export function unsupportedTopic(topic: string): string {
  const known = TOPICS.find((x) => x === topic);
  return known ? t(`generate.words.unsupported.${known}`) : t("generate.words.unsupported.OTHER");
}

const CONFLICT_KEYS = [
  "plot_width_ft",
  "plot_depth_ft",
  "facing",
  "bedrooms",
  "bathrooms",
  "car_parking",
  "pooja_room",
] as const;

function answerText(key: string, value: unknown): string {
  if (value === true) return t("generate.yes");
  if (value === false) return t("generate.no");
  if (value === "5_PLUS") return t("generate.words.fivePlus");
  if (key === "facing" && typeof value === "string") return choiceLabel("facing_override", value);
  if ((key === "plot_width_ft" || key === "plot_depth_ft") && value != null) {
    return t("generate.feet", { value: String(Number(value)) });
  }
  return value == null ? "" : String(value);
}

/** Where the description differs from the submitted requirement (which stays the authority). */
export function conflictLine(conflict: RequirementProposal["conflicts"][number]): string {
  const known = CONFLICT_KEYS.find((k) => k === conflict.key);
  return t("generate.words.conflict", {
    field: known ? t(`generate.words.conflictKeys.${known}`) : conflict.key,
    requirement: answerText(conflict.key, conflict.requirement),
    said: answerText(conflict.key, conflict.said),
  });
}

const ROOM_KINDS = [
  "LIVING",
  "DINING",
  "KITCHEN",
  "BEDROOM",
  "MASTER_BEDROOM",
  "BATHROOM",
  "PUJA",
  "UTILITY",
  "STUDY",
  "STORE",
  "PARKING",
] as const;

function roomKind(value: string | undefined): string | null {
  const known = ROOM_KINDS.find((k) => k === value);
  return known ? t(`generate.words.rooms.${known}`) : null;
}

/** A preference the assistant kept ("living_size:LARGE", "adjacent:KITCHEN-DINING:REQUIRED",
 * "private:BEDROOM", "circulation:COMPACT", "entrance:FRONT"); null when not one of these. */
export function preferenceLine(preference: string): string | null {
  const [kind, value = "", strength] = preference.split(":");
  switch (kind) {
    case "living_size":
      return value === "LARGE" || value === "STANDARD" || value === "COMPACT"
        ? t(`generate.words.preference.living.${value}`)
        : null;
    case "adjacent": {
      const [a, b] = value.split("-");
      const ra = roomKind(a);
      const rb = roomKind(b);
      if (!ra || !rb) return null;
      return t(strength === "REQUIRED" ? "generate.words.preference.nextToRequired" : "generate.words.preference.nextTo", {
        a: ra,
        b: rb,
      });
    }
    case "private": {
      const room = roomKind(value);
      return room ? t("generate.words.preference.private", { room }) : null;
    }
    case "circulation":
      return value === "COMPACT" || value === "GENEROUS" ? t(`generate.words.preference.circulation.${value}`) : null;
    case "entrance":
      return value === "FRONT" || value === "SIDE" ? t(`generate.words.preference.entrance.${value}`) : null;
    default:
      return null;
  }
}

const INFEASIBLE_REASONS = [
  "ENVELOPE_EMPTY",
  "AREA_BUDGET",
  "WIDTH_TOO_NARROW",
  "DEPTH_EXCEEDED",
  "PARKING_TOO_WIDE",
  "ACCESS_SPAN",
  "FIXTURE_FIT",
  "OPENING_FIT",
  "RULESET_INCOMPLETE",
] as const;

/** Why no plan was made, in plain words: the classification's headline (never "impossible" for
 * NO_SUPPORTED_LAYOUT), each reason code, and the engine's own measured explanation. */
export function infeasibilityView(infeasibility: Infeasibility | null | undefined): {
  headline: string;
  reasons: string[];
  explanation: string | null;
} {
  const headline = infeasibility?.classification
    ? t(`list.infeasible.${infeasibility.classification}`)
    : t("list.infeasible.default");
  const reasons = [
    ...new Set(
      (infeasibility?.reasons ?? []).map((r) => {
        const known = INFEASIBLE_REASONS.find((x) => x === r.code);
        return known ? t(`list.infeasible.reasons.${known}`) : t("list.infeasible.reasons.other");
      }),
    ),
  ];
  return { headline, reasons, explanation: infeasibility?.explanation ?? null };
}

const FAILURES = ["ENGINE_ERROR", "ENGINE_INVALID_OUTPUT", "ENGINE_TIMEOUT", "STALE"] as const;

export function failureText(reason: string | null | undefined): string {
  const known = FAILURES.find((f) => f === reason);
  return known ? t(`list.failure.${known}`) : t("list.failure.default");
}

export function problemText(problem: FieldProblem): string {
  switch (problem.kind) {
    case "range":
      return t("generate.problem.range", { min: problem.min, max: problem.max });
    case "setback":
      return t("generate.problem.setback", { max: SETBACK_MAX_FT });
    case "missing":
      return t(`generate.missing.${problem.reason}`);
    case "conflict":
      return t("generate.problem.conflict");
    case "invalid":
      return t("generate.problem.invalid");
  }
}
