// The AI assistant's proposals, for a person to read (Checkpoint 4). Every line is built from
// the server's structured result (the compiled intent and the before and after of each room
// and opening, measured by the engine), never from free text the model wrote. Nothing here
// changes the plan: applying a proposal sends its typed operations through the operations route.
import { getTranslator } from "@/lib/i18n";

import type { Rect } from "./edit";
import type { Units } from "./editor";
import { labelOf, roomTypeLabel } from "./messages";
import type { AssistantEdit, HousePlan, PlanGeometry } from "./types";
import { formatArea, formatLength } from "./units";

const t = getTranslator("Plan");

export type { AssistantEdit };

function nameOf(id: string, doc: HousePlan, preview: PlanGeometry | null): string {
  const after = preview?.floors[0]?.rooms.find((r) => r.id === id)?.name;
  return after ?? labelOf(id, doc, null);
}

/** One sentence for what the assistant understood. */
export function intentLine(edit: AssistantEdit, doc: HousePlan): string | null {
  const i = edit.intent as Record<string, string> | null;
  if (!i) return null;
  const room = i.room ? labelOf(i.room, doc, null) : "";
  switch (i.action) {
    case "RESIZE_ROOM":
      return t(i.change === "LARGER" ? "assistant.intent.larger" : "assistant.intent.smaller", { room });
    case "MOVE_ROOM_TOWARD":
      return t("assistant.intent.toward", { room, target: labelOf(i.target ?? "", doc, null) });
    case "ADD_ROOM":
      return t("assistant.intent.add", { type: roomTypeLabel(i.room_type ?? "") });
    case "CHANGE_ROOM_TYPE":
      return t("assistant.intent.retype", { room, type: roomTypeLabel(i.room_type ?? "") });
    case "REMOVE_ROOM":
      return t("assistant.intent.remove", { room });
    case "RENAME_ROOM":
      return t("assistant.intent.rename", { room, name: i.name ?? "" });
    case "MOVE_OPENING":
      return t(i.opening === "DOOR" ? "assistant.intent.moveDoor" : "assistant.intent.moveWindow", { room });
    case "RESIZE_OPENING":
      return t(i.change === "WIDER" ? "assistant.intent.wider" : "assistant.intent.narrower", {
        room,
        opening: i.opening === "DOOR" ? t("openingNouns.DOOR") : t("openingNouns.WINDOW"),
      });
    default:
      return null;
  }
}

/** What the proposal changes, room by room and opening by opening, with the engine's numbers. */
export function changeLines(edit: AssistantEdit, doc: HousePlan, units: Units): string[] {
  const preview = edit.preview ?? null;
  const area = (mm2: number | null | undefined) => (mm2 == null ? "" : formatArea(mm2, units));
  const lines: string[] = [];
  for (const r of edit.rooms) {
    const name = nameOf(r.room, doc, preview);
    if (r.kind === "ADDED") lines.push(t("assistant.change.added", { room: name, area: area(r.area_after_mm2) }));
    else if (r.kind === "REMOVED") lines.push(t("assistant.change.removed", { room: name }));
    else if (r.kind === "RETYPED")
      lines.push(t("assistant.change.retyped", { room: name, type: roomTypeLabel(r.type_after ?? "") }));
    else if (r.kind === "RENAMED") lines.push(t("assistant.change.renamed", { room: name }));
    else lines.push(t("assistant.change.area", { room: name, before: area(r.area_before_mm2), after: area(r.area_after_mm2) }));
  }
  for (const o of edit.openings) {
    const name = labelOf(o.opening, doc, preview);
    if (o.kind === "RESIZED") {
      lines.push(
        t("assistant.change.resized", {
          opening: name,
          before: formatLength(o.width_before_mm, units),
          after: formatLength(o.width_after_mm, units),
        }),
      );
    } else lines.push(t("assistant.change.moved", { opening: name }));
  }
  return lines;
}

/** Why there is no proposal, from the status and its detail code. */
export function outcomeLine(edit: AssistantEdit): string {
  if (edit.status === "UNSUPPORTED") {
    const topics = [
      "ADD_FLOOR",
      "FREE_SHAPE",
      "STRUCTURAL_ENGINEERING",
      "PERMIT_COMPLIANCE",
      "VASTU_CERTIFICATION",
      "PRIVACY_REDESIGN",
      "UNSUPPORTED_ROOM_TYPE",
      "IMAGES_OR_3D",
    ] as const;
    const known = topics.find((x) => x === edit.detail);
    return known ? t(`assistant.unsupported.${known}`) : t("assistant.unsupported.OTHER");
  }
  if (edit.status === "CLARIFY") return t("assistant.clarify", { question: edit.detail ?? "" });
  return edit.detail === "MALFORMED_ANSWER" ? t("assistant.failedUnclear") : t("assistant.failed");
}

/** The rectangle of the room the proposal changes most visibly, for the preview overlay. */
export function previewOf(edit: AssistantEdit): Rect | null {
  const changed = edit.rooms.find((r) => r.kind !== "REMOVED");
  const room = changed ? edit.preview?.floors[0]?.rooms.find((r) => r.id === changed.room) : undefined;
  if (!room || room.polygon.length === 0) return null;
  const xs = room.polygon.map((p) => p.x);
  const ys = room.polygon.map((p) => p.y);
  return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) };
}
