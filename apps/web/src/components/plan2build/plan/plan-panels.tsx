"use client";

// The editing panels beside the drawing (Checkpoint 3.1): a room's name, type, removal and a new
// room inside it; a side's new door or window; the doors and windows as a keyboard-reachable list
// with width, position and removal; and the owner's recorded changes from the requirement. Every
// control builds typed operations (`lib/plan/edit`) and hands them to `onCommit`; the server
// applies, validates and stores them, so nothing here decides what is allowed.
import { ArrowLeftIcon, ArrowRightIcon, PlusIcon, Trash2Icon } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getTranslator } from "@/lib/i18n";
import {
  SIDES,
  addOpeningOp,
  addRoomOp,
  deleteOpeningOp,
  deleteRoomOp,
  hostedOpening,
  mergeTargets,
  moveOpeningOp,
  renameRoomOp,
  resizeOpeningOps,
  setRoomTypeOps,
  type Side,
} from "@/lib/plan/edit";
import type { EditorAction, EditorState, Units } from "@/lib/plan/editor";
import { changeText, labelOf, roomTypeLabel } from "@/lib/plan/messages";
import type { PlanOp, RoomType } from "@/lib/plan/types";
import { formatLength } from "@/lib/plan/units";

const t = getTranslator("Plan");

const MM_PER = { m: 1000, ft: 304.8 } as const;

/** A length typed in the chosen units, to whole grid steps of millimetres; null when not a
 * positive number. */
export function lengthFromInput(text: string, units: Units, grid: number): number | null {
  const value = Number(text.replace(",", "."));
  if (!Number.isFinite(value) || value <= 0) return null;
  const mm = value * MM_PER[units];
  const step = grid > 0 ? grid : 1;
  return Math.max(step, Math.round(mm / step) * step);
}

function inputFromLength(mm: number, units: Units): string {
  return (mm / MM_PER[units]).toFixed(2);
}

interface PanelProps {
  state: EditorState;
  dispatch: (action: EditorAction) => void;
  onCommit: (ops: PlanOp[]) => void;
}

export function RoomPanel({ state, onCommit, roomId }: PanelProps & { roomId: string }) {
  const doc = state.plan.document;
  const editing = state.plan.editing;
  const room = doc.floors[0]?.rooms.find((r) => r.id === roomId);
  const ids = useId();
  const [name, setName] = useState(room?.name ?? "");
  const [type, setType] = useState<string>(room?.type ?? "");
  const targets = mergeTargets(doc, roomId);
  const [target, setTarget] = useState(targets[0] ?? "");
  const firstType = editing.room_types[0]?.type ?? "";
  const [newType, setNewType] = useState<string>(firstType);
  const [side, setSide] = useState<Side>("back");
  const [depth, setDepth] = useState(() => {
    const min = editing.room_types.find((r) => r.type === firstType)?.min_short_mm ?? 1500;
    return inputFromLength(min + (editing.interior_wall_mm ?? 0), state.units);
  });
  if (!room) return null;
  const busy = state.busy;
  const unit = t(`unitSymbol.${state.units}`);
  const typeOptions = editing.room_types.map((r) => r.type);
  const canRetype = room.enclosed && typeOptions.includes(room.type);

  const rename = renameRoomOp(doc, roomId, name);
  const retype = canRetype && type ? setRoomTypeOps(doc, editing, roomId, type as RoomType) : [];
  const remove = target ? deleteRoomOp(roomId, target) : null;
  const depthMm = lengthFromInput(depth, state.units, editing.grid_mm);
  const add = depthMm && newType ? addRoomOp(roomId, newType as RoomType, side, depthMm) : null;

  return (
    <div className="flex flex-col gap-4">
      <form
        className="flex flex-col gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (rename) onCommit([rename]);
        }}
      >
        <Label htmlFor={`${ids}-name`}>{t("room.name")}</Label>
        <div className="flex gap-2">
          <Input id={`${ids}-name`} value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
          <Button type="submit" variant="outline" disabled={!rename || busy}>
            {t("room.rename")}
          </Button>
        </div>
      </form>

      {canRetype && (
        <div className="flex flex-col gap-2">
          <Label htmlFor={`${ids}-type`}>{t("room.type")}</Label>
          <div className="flex gap-2">
            <Select value={type} onValueChange={setType}>
              <SelectTrigger id={`${ids}-type`} className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {typeOptions.map((value) => (
                  <SelectItem key={value} value={value}>
                    {roomTypeLabel(value)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" disabled={retype.length === 0 || busy} onClick={() => onCommit(retype)}>
              {t("room.changeType")}
            </Button>
          </div>
        </div>
      )}

      <fieldset className="flex flex-col gap-2 rounded-md border p-2">
        <legend className="px-1 text-sm font-medium">{t("room.add")}</legend>
        <p className="text-sm text-muted-foreground">{t("room.addHelp")}</p>
        <Label htmlFor={`${ids}-new-type`}>{t("room.addType")}</Label>
        <Select value={newType} onValueChange={setNewType}>
          <SelectTrigger id={`${ids}-new-type`} className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {typeOptions.map((value) => (
              <SelectItem key={value} value={value}>
                {roomTypeLabel(value)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Label htmlFor={`${ids}-side`}>{t("room.addSide")}</Label>
        <Select value={side} onValueChange={(value) => setSide(value as Side)}>
          <SelectTrigger id={`${ids}-side`} className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SIDES.map((value) => (
              <SelectItem key={value} value={value}>
                {t(`sides.${value}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Label htmlFor={`${ids}-depth`}>{t("room.addDepth", { unit })}</Label>
        <Input
          id={`${ids}-depth`}
          inputMode="decimal"
          value={depth}
          onChange={(e) => setDepth(e.target.value)}
          className="tabular-nums"
        />
        <Button variant="outline" disabled={!add || busy} onClick={() => add && onCommit([add])}>
          <PlusIcon aria-hidden="true" data-icon="inline-start" />
          {t("room.addConfirm")}
        </Button>
      </fieldset>

      <fieldset className="flex flex-col gap-2 rounded-md border p-2">
        <legend className="px-1 text-sm font-medium">{t("room.remove")}</legend>
        {targets.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("room.removeNone")}</p>
        ) : (
          <>
            <Label htmlFor={`${ids}-into`}>{t("room.removeInto")}</Label>
            <Select value={target} onValueChange={setTarget}>
              <SelectTrigger id={`${ids}-into`} className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {targets.map((id) => (
                  <SelectItem key={id} value={id}>
                    {labelOf(id, doc, null)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" disabled={!remove || busy} onClick={() => remove && onCommit([remove])}>
              <Trash2Icon aria-hidden="true" data-icon="inline-start" />
              {t("room.removeConfirm")}
            </Button>
          </>
        )}
      </fieldset>
    </div>
  );
}

export function SidePanel({ state, onCommit, roomId, side }: PanelProps & { roomId: string; side: Side }) {
  const doc = state.plan.document;
  const door = addOpeningOp(doc, state.plan.editing, roomId, side, "DOOR");
  const windowOp = addOpeningOp(doc, state.plan.editing, roomId, side, "WINDOW");
  return (
    <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="outline" disabled={!door || state.busy} onClick={() => door && onCommit([door])}>
        <PlusIcon aria-hidden="true" data-icon="inline-start" />
        {t("openings.addDoor")}
      </Button>
      <Button size="sm" variant="outline" disabled={!windowOp || state.busy} onClick={() => windowOp && onCommit([windowOp])}>
        <PlusIcon aria-hidden="true" data-icon="inline-start" />
        {t("openings.addWindow")}
      </Button>
    </div>
  );
}

export function OpeningPanel({ state, onCommit, openingId }: PanelProps & { openingId: string }) {
  const doc = state.plan.document;
  const opening = doc.floors[0]?.openings.find((o) => o.id === openingId);
  const ids = useId();
  const [width, setWidth] = useState(() => (opening ? inputFromLength(opening.width_mm, state.units) : ""));
  if (!opening) return null;
  const grid = state.plan.editing.grid_mm;
  const unit = t(`unitSymbol.${state.units}`);
  const widthMm = lengthFromInput(width, state.units, grid);
  const resize = widthMm ? resizeOpeningOps(doc, openingId, widthMm) : [];
  const host = hostedOpening(doc, openingId);
  const step = (sign: number) => {
    if (!host) return null;
    return moveOpeningOp(host, Math.max(0, host.offset + sign * grid));
  };
  const back = step(-1);
  const on = step(1);
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-muted-foreground">
        {t("openings.size", { width: formatLength(opening.width_mm, state.units) })}
      </p>
      <form
        className="flex flex-col gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (resize.length > 0) onCommit(resize);
        }}
      >
        <Label htmlFor={`${ids}-width`}>{t("openings.width", { unit })}</Label>
        <div className="flex gap-2">
          <Input
            id={`${ids}-width`}
            inputMode="decimal"
            value={width}
            onChange={(e) => setWidth(e.target.value)}
            className="tabular-nums"
          />
          <Button type="submit" variant="outline" disabled={resize.length === 0 || state.busy}>
            {t("openings.resize")}
          </Button>
        </div>
      </form>
      <div className="flex flex-wrap gap-2">
        <Button
          size="icon"
          variant="outline"
          aria-label={t("openings.moveBack")}
          disabled={!back || state.busy}
          onClick={() => back && onCommit([back])}
        >
          <ArrowLeftIcon aria-hidden="true" />
        </Button>
        <Button
          size="icon"
          variant="outline"
          aria-label={t("openings.moveOn")}
          disabled={!on || state.busy}
          onClick={() => on && onCommit([on])}
        >
          <ArrowRightIcon aria-hidden="true" />
        </Button>
        <Button variant="outline" disabled={state.busy} onClick={() => onCommit([deleteOpeningOp(openingId)])}>
          <Trash2Icon aria-hidden="true" data-icon="inline-start" />
          {t("openings.delete")}
        </Button>
      </div>
    </div>
  );
}

/** Every door and window of the selected room (or of the plan), as buttons that select it: the
 * keyboard route to what the drawing shows (WCAG 2.1.1). */
export function OpeningsList({ state, dispatch, roomId }: PanelProps & { roomId: string | null }) {
  const doc = state.plan.document;
  const geometry = state.plan.geometry;
  const openings = (geometry.floors[0]?.openings ?? []).filter((o) => !roomId || o.connects.includes(roomId));
  const selected = state.selection?.kind === "opening" ? state.selection.id : null;
  const widthOf = (id: string) => doc.floors[0]?.openings.find((o) => o.id === id)?.width_mm ?? 0;
  const label = roomId ? t("openings.listLabel", { room: labelOf(roomId, doc, null) }) : t("openings.allLabel");
  return (
    <section aria-labelledby="plan-openings" className="flex flex-col gap-2 rounded-lg border p-3">
      <h3 id="plan-openings" className="text-sm font-medium">
        {t("openings.title")}
      </h3>
      {openings.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("openings.none")}</p>
      ) : (
        <ul aria-label={label} className="flex flex-col">
          {openings.map((o) => (
            <li key={o.id}>
              <button
                type="button"
                aria-pressed={selected === o.id}
                onClick={() =>
                  dispatch({ type: "select", selection: { kind: "opening", id: o.id, room: roomId ?? undefined } })
                }
                className="flex min-h-11 w-full flex-col justify-center rounded-md px-2 py-1 text-left text-sm hover:bg-accent aria-pressed:bg-accent"
              >
                <span>{labelOf(o.id, doc, geometry)}</span>
                <span className="text-xs text-muted-foreground">
                  {t("openings.size", { width: formatLength(widthOf(o.id), state.units) })}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function ChangesPanel({ state }: { state: EditorState }) {
  const doc = state.plan.document;
  const lines = doc.compromises.map((c) => changeText(c, doc)).filter((line) => line !== null);
  if (lines.length === 0) return null;
  return (
    <section aria-labelledby="plan-changes" className="flex flex-col gap-2 rounded-lg border p-3">
      <h3 id="plan-changes" className="text-sm font-medium">
        {t("changes.title")}
      </h3>
      <p className="text-sm text-muted-foreground">{t("changes.intro")}</p>
      <ul className="list-disc pl-5 text-sm">
        {lines.map((line, i) => (
          <li key={`${i}-${line}`}>{line}</li>
        ))}
      </ul>
    </section>
  );
}
