// Readable text for the server's validation issues, operation rejections and recorded room
// changes (Checkpoint 3.1). The server sends a code, its structured values and an English
// fallback message; the text here comes from messages/en.json (Plan.validation, Plan.rejection,
// Plan.changes) with lengths and areas in the chosen units and ids turned into room, door,
// window and fixture names. A code without a template keeps the server's message. Nothing here
// judges validity: the validator's codes are shown as they are.
import { getTranslator } from "@/lib/i18n";

import type { Units } from "./editor";
import type { Compromise, HousePlan, PlanGeometry, ValidationIssue } from "./types";
import { formatArea, formatLength } from "./units";

const t = getTranslator("Plan");

const TEMPLATED = [
  "ROOM_OVERLAP",
  "ROOM_OUTSIDE_ENVELOPE",
  "BUILDING_OUTSIDE_PLOT",
  "OPENING_OUTSIDE_HOST",
  "OPENING_OVERLAP",
  "WINDOW_ON_INTERIOR_WALL",
  "FIXTURE_NOT_ON_ROOM_WALL",
  "FIXTURE_OUTSIDE_ROOM",
  "FIXTURE_NOT_PERMITTED_IN_ROOM",
  "FIXTURE_OVERLAP",
  "FIXTURE_CLEARANCE_BLOCKED",
  "FIXTURE_BLOCKS_OPENING",
  "ENTRANCE_MISSING",
  "ROOM_UNREACHABLE",
  "PASSAGE_TOO_NARROW",
  "ROOM_BELOW_MIN_SHORT_SIDE",
  "ROOM_BELOW_MIN_AREA",
  "HABITABLE_ROOM_NO_WINDOW",
  "ROOM_COUNT_MISMATCH",
  "PARKING_MISSING",
  "PARKING_TOO_SMALL",
  "RELATION_UNMET",
] as const;

const REJECTIONS = [
  "UNKNOWN_ENTITY",
  "ENTITY_EXISTS",
  "NOT_SUPPORTED",
  "NO_MOVEMENT",
  "NOT_AXIS_ALIGNED",
  "WALL_WOULD_COLLAPSE",
  "HOSTED_ITEM_LEAVES_WALL",
  "NOT_RECTANGULAR",
  "HOSTED_ITEM_CHANGES_ROOMS",
  "DOOR_DOES_NOT_FIT",
  "ROOMS_WOULD_OVERLAP",
  "NOT_A_SLICE",
  "ROOMS_NOT_MERGEABLE",
  "ROOM_TYPE_NOT_ALLOWED",
  "REVERT_NOT_ALONE",
  "UNKNOWN_REVISION",
] as const;

const ROOM_TYPES = [
  "LIVING",
  "DINING",
  "KITCHEN",
  "BEDROOM",
  "BATH_ATTACHED",
  "BATH_COMMON",
  "WC",
  "PUJA",
  "UTILITY",
  "STORE",
  "PASSAGE",
  "FOYER",
  "STAIR_HALL",
  "PARKING",
] as const;

const FIXTURE_TYPES = [
  "WC_WESTERN",
  "WC_INDIAN",
  "WASH_BASIN",
  "SHOWER_AREA",
  "KITCHEN_COUNTER",
  "KITCHEN_SINK",
] as const;

const OPENING_KINDS = ["MAIN_ENTRANCE", "DOOR", "VOID", "WINDOW"] as const;

function member<T extends string>(list: readonly T[], value: string): T | undefined {
  return list.find((v) => v === value);
}

export function roomTypeLabel(type: string): string {
  const known = member(ROOM_TYPES, type);
  return known ? t(`roomTypes.${known}`) : type;
}

/** A fixture type as a noun inside a sentence ("western toilet"). */
function fixtureNoun(type: string): string {
  const known = member(FIXTURE_TYPES, type);
  return known ? t(`fixtureNouns.${known}`) : type;
}

/** An opening kind as a noun inside a sentence ("main entrance"). */
function openingNoun(kind: string): string {
  const known = member(OPENING_KINDS, kind.toUpperCase());
  return known ? t(`openingNouns.${known}`) : kind;
}

/** A plain name for a room, door, window or fixture id, for a person to read. */
export function labelOf(id: string, doc: HousePlan, geometry: PlanGeometry | null): string {
  const floor = doc.floors[0];
  const room = floor?.rooms.find((r) => r.id === id);
  if (room) return room.name;
  const opening = floor?.openings.find((o) => o.id === id);
  if (opening) {
    const kind = openingNoun(opening.kind);
    const connects = geometry?.floors[0]?.openings.find((o) => o.id === id)?.connects ?? [];
    const names = connects.filter((c) => c !== "EXTERIOR").map((c) => labelOf(c, doc, null));
    if (names.length === 2) return t("labels.openingBetween", { kind, a: names[0], b: names[1] });
    if (names.length === 1) return t("labels.openingOf", { kind, a: names[0] });
    return t("labels.openingOnly", { kind });
  }
  const fixture = floor?.fixtures.find((f) => f.id === id);
  if (fixture) {
    const owner = floor?.rooms.find((r) => r.id === fixture.room)?.name;
    const type = fixtureNoun(fixture.type);
    return owner ? t("labels.fixtureIn", { type, room: owner }) : t("labels.fixtureOnly", { type });
  }
  if (floor?.walls.some((w) => w.id === id)) return t("labels.aWall");
  return id;
}

function formatValue(
  key: string,
  value: unknown,
  doc: HousePlan,
  geometry: PlanGeometry | null,
  units: Units,
): string {
  if (typeof value === "number") {
    if (key.endsWith("_mm2")) return formatArea(value, units);
    if (key.endsWith("_mm")) return formatLength(value, units);
    return String(value);
  }
  if (typeof value !== "string") return Array.isArray(value) ? value.join(", ") : String(value);
  if (key === "fixture_type") return fixtureNoun(value);
  if (key === "room_type") return roomTypeLabel(value);
  if (key === "kind") return openingNoun(value);
  if (key.startsWith("fixture") || key.startsWith("opening") || key.startsWith("wall")) {
    return labelOf(value, doc, geometry);
  }
  return value;
}

/** The text for one validation issue: the template for its code with every value formatted,
 * or the server's message for a code without one. */
export function issueText(
  issue: ValidationIssue,
  doc: HousePlan,
  geometry: PlanGeometry | null,
  units: Units,
): string {
  const code = member(TEMPLATED, issue.code);
  if (!code) return issue.message;
  const values: Record<string, string> = {};
  for (const [key, value] of Object.entries(issue.params ?? {})) {
    values[key] = formatValue(key, value, doc, geometry, units);
  }
  try {
    return t(`validation.${code}`, values);
  } catch {
    return issue.message;
  }
}

/** Why an operation could not apply, naming what it concerns. */
export function rejectionText(
  code: string,
  entities: string[],
  doc: HousePlan,
  geometry: PlanGeometry | null,
): string {
  const known = member(REJECTIONS, code) ?? "NOT_SUPPORTED";
  const names = entities.map((e) => labelOf(e, doc, geometry));
  return t(`rejection.${known}`, { item: names[0] ?? t("labels.something"), other: names[1] ?? "" });
}

/** One of the owner's recorded room changes, or null for another kind of compromise. */
export function changeText(change: Compromise, doc: HousePlan): string | null {
  const p = change.params as Record<string, unknown>;
  const room = typeof p.room === "string" ? labelOf(p.room, doc, null) : "";
  if (change.change_key === "ROOM_ADDED_BY_OWNER") {
    return t("changes.added", { room, type: roomTypeLabel(String(p.room_type)) });
  }
  if (change.change_key === "ROOM_REMOVED_BY_OWNER") {
    return t("changes.removed", { type: roomTypeLabel(String(p.room_type)) });
  }
  if (change.change_key === "ROOM_TYPE_CHANGED_BY_OWNER") {
    return t("changes.retyped", {
      room,
      from: roomTypeLabel(String(p.from_type)),
      to: roomTypeLabel(String(p.to_type)),
    });
  }
  return null;
}
