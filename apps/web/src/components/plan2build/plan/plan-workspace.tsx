"use client";

// The floor plan workspace: the drawing, its tools and the panels beside it, around one reducer
// (HR S). Edits go to the API as typed operation batches with the revision they were made on;
// the server applies, validates and stores them, and its answer replaces the plan here. A
// rejected edit leaves the plan as it was and shows why. Editing appears only when the API says
// this person may edit and the screen is large enough (AD-12, AD-14); the server checks again.
import {
  MagnetIcon,
  MaximizeIcon,
  Redo2Icon,
  RotateCcwIcon,
  Undo2Icon,
  ZoomInIcon,
  ZoomOutIcon,
} from "lucide-react";
import { useCallback, useMemo, useReducer, useRef, useSyncExternalStore, type KeyboardEvent } from "react";

import { PlanCanvas, type PlanCanvasHandle } from "@/components/plan2build/plan/plan-canvas";
import { PlanHistory } from "@/components/plan2build/plan/plan-history";
import {
  ChangesPanel,
  OpenAreaPanel,
  OpeningPanel,
  OpeningsList,
  RoomPanel,
  SidePanel,
} from "@/components/plan2build/plan/plan-panels";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { browserApi, errorCode } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";
import { roomSides, type MoveMode } from "@/lib/plan/edit";
import {
  editorReducer,
  flaggedEntities,
  historyRequest,
  initialState,
  problemOf,
  type Direction,
  type EditorAction,
  type EditorState,
  type Units,
} from "@/lib/plan/editor";
import { issueText, rejectionText } from "@/lib/plan/messages";
import type { PlanOp, PlanState, RoomGeom, ValidationIssue } from "@/lib/plan/types";
import { formatArea, formatDims } from "@/lib/plan/units";

const t = getTranslator("Plan");

const WIDE = "(min-width: 768px)";

function subscribe(onChange: () => void) {
  const query = window.matchMedia(WIDE);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

/** Large enough to edit (tablet and desktop, AD-14). False on the server: read-only first. */
function useWideScreen(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(WIDE).matches,
    () => false,
  );
}

export function PlanWorkspace({
  projectId,
  planId,
  initial,
}: {
  projectId: string;
  planId: string;
  initial: PlanState;
}) {
  const [state, dispatch] = useReducer(editorReducer, initial, initialState);
  const wide = useWideScreen();
  const editable = state.plan.editing.can_edit && wide;
  const canvas = useRef<PlanCanvasHandle | null>(null);
  const live = useRef<HTMLParagraphElement>(null);

  const commit = useCallback(
    async (ops: PlanOp[], direction: Direction, expected: number) => {
      dispatch({ type: "commit" });
      announce(live.current, t("saving"));
      const response = await browserApi
        .POST("/api/v1/projects/{project_id}/house-plans/{plan_id}/ops", {
          params: { path: { project_id: projectId, plan_id: planId } },
          body: { expected_revision: expected, ops },
        })
        .catch(() => null);
      const data = response?.data;
      if (data && data.document && data.geometry && data.editing) {
        dispatch({
          type: "committed",
          plan: { document: data.document, geometry: data.geometry, validation: data.validation, editing: data.editing },
          batch: { ops, inverse: data.inverse },
          direction,
        });
        announce(live.current, t("saved"));
        return;
      }
      const error = response?.error as { error?: { details?: unknown } } | undefined;
      dispatch({ type: "failed", problem: problemOf(errorCode(response?.error), error?.error?.details) });
      announce(live.current, "");
    },
    [projectId, planId],
  );

  const onCommit = useCallback(
    (ops: PlanOp[]) => void commit(ops, "do", state.plan.editing.revision_no),
    [commit, state.plan.editing.revision_no],
  );

  function history(direction: "undo" | "redo") {
    const request = historyRequest(state, direction);
    if (request && !state.busy) void commit(request.ops, direction, request.expected);
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (!editable || !(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "z") return;
    e.preventDefault();
    history(e.shiftKey ? "redo" : "undo");
  }

  const flagged = useMemo(() => {
    const issues: ValidationIssue[] =
      state.problem?.kind === "invalid"
        ? state.problem.issues
        : [...(state.plan.validation?.errors ?? []), ...(state.plan.validation?.warnings ?? [])];
    return flaggedEntities(issues);
  }, [state.problem, state.plan.validation]);

  const controls = useCallback((handle: PlanCanvasHandle) => {
    canvas.current = handle;
  }, []);

  return (
    <div className="flex flex-col gap-4" onKeyDown={onKeyDown}>
      <div role="toolbar" aria-label={t("toolbar")} className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="icon" onClick={() => canvas.current?.zoom(1.25)} aria-label={t("zoomIn")}>
          <ZoomInIcon aria-hidden="true" />
        </Button>
        <Button variant="outline" size="icon" onClick={() => canvas.current?.zoom(0.8)} aria-label={t("zoomOut")}>
          <ZoomOutIcon aria-hidden="true" />
        </Button>
        <Button variant="outline" size="icon" onClick={() => canvas.current?.fit()} aria-label={t("fit")}>
          <MaximizeIcon aria-hidden="true" />
        </Button>
        <div role="group" aria-label={t("unitsLabel")} className="flex gap-1">
          {(["m", "ft"] as const).map((u) => (
            <Button
              key={u}
              variant={state.units === u ? "secondary" : "ghost"}
              aria-pressed={state.units === u}
              onClick={() => dispatch({ type: "units", units: u })}
            >
              {u === "m" ? t("unitMetres") : t("unitFeet")}
            </Button>
          ))}
        </div>
        {editable && (
          <>
            <Button
              variant="outline"
              size="icon"
              onClick={() => history("undo")}
              disabled={state.undo.length === 0 || state.busy}
              aria-label={t("undo")}
            >
              <Undo2Icon aria-hidden="true" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() => history("redo")}
              disabled={state.redo.length === 0 || state.busy}
              aria-label={t("redo")}
            >
              <Redo2Icon aria-hidden="true" />
            </Button>
            <Button
              variant={state.snap ? "secondary" : "ghost"}
              aria-pressed={state.snap}
              title={t("snapHint")}
              onClick={() => dispatch({ type: "snap", on: !state.snap })}
            >
              <MagnetIcon aria-hidden="true" data-icon="inline-start" />
              {t("snap")}
            </Button>
            <div role="group" aria-label={t("moveMode.label")} title={t("moveMode.hint")} className="flex gap-1">
              {(["edge", "line"] as const satisfies readonly MoveMode[]).map((mode) => (
                <Button
                  key={mode}
                  variant={state.moveMode === mode ? "secondary" : "ghost"}
                  aria-pressed={state.moveMode === mode}
                  onClick={() => dispatch({ type: "moveMode", mode })}
                >
                  {t(`moveMode.${mode}`)}
                </Button>
              ))}
            </div>
          </>
        )}
      </div>

      <p ref={live} aria-live="polite" className="sr-only" />

      {state.problem && <ProblemNotice state={state} onDismiss={() => dispatch({ type: "dismiss" })} />}

      <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <div className="h-[60vh] min-h-80 lg:h-[72vh]">
          <PlanCanvas
            state={state}
            dispatch={dispatch}
            editable={editable}
            onCommit={onCommit}
            controls={controls}
            flagged={flagged}
          />
        </div>
        <aside className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            {!state.plan.editing.can_edit ? t("readOnly") : editable ? t("editHint") : t("editOnLargerScreen")}
          </p>
          <Inspector
            state={state}
            editable={editable}
            dispatch={dispatch}
            onCommit={onCommit}
            onPicked={() => canvas.current?.focus()}
          />
          <RoomList
            state={state}
            editable={editable}
            onSelect={(id) => dispatch({ type: "select", selection: { kind: "room", id } })}
            onSelectArea={(id) => dispatch({ type: "select", selection: { kind: "area", id } })}
          />
          <OpeningsList state={state} dispatch={dispatch} onCommit={onCommit} roomId={selectedRoom(state)} />
          <ChangesPanel state={state} />
          <Checks state={state} />
          <PlanHistory projectId={projectId} planId={planId} state={state} editable={editable} onCommit={onCommit} />
        </aside>
      </div>
    </div>
  );
}

function announce(el: HTMLParagraphElement | null, text: string) {
  if (el) el.textContent = text;
}

/** The room whose doors and windows are listed: the selected room, the room of a selected side,
 * or for a selected opening the list it was picked from (else the room it belongs to). */
function selectedRoom(state: EditorState): string | null {
  const sel = state.selection;
  if (sel?.kind === "room") return sel.id;
  if (sel?.kind === "side") return sel.room;
  if (sel?.kind === "opening") {
    if (sel.room) return sel.room;
    const connects = state.plan.geometry.floors[0]?.openings.find((o) => o.id === sel.id)?.connects ?? [];
    return connects.find((c) => c !== "EXTERIOR") ?? null;
  }
  return null;
}

function ProblemNotice({ state, onDismiss }: { state: EditorState; onDismiss: () => void }) {
  const p = state.problem;
  if (!p) return null;
  const { document: doc, geometry } = state.plan;
  const action =
    p.kind === "conflict" ? (
      <Button variant="outline" onClick={() => window.location.reload()}>
        <RotateCcwIcon aria-hidden="true" data-icon="inline-start" />
        {t("problem.reload")}
      </Button>
    ) : (
      <Button variant="ghost" onClick={onDismiss}>
        {t("problem.dismiss")}
      </Button>
    );
  const title = {
    invalid: t("problem.invalidTitle"),
    rejected: t("problem.rejectedTitle"),
    conflict: t("problem.conflictTitle"),
    history: t("problem.historyTitle"),
    failed: t("problem.failedTitle"),
  }[p.kind];
  return (
    <div className="flex flex-col gap-2">
      <Notice tone="error" live="assertive" title={title}>
        {p.kind === "invalid" && (
          <>
            <p>{t("problem.invalidBody")}</p>
            <ul className="list-disc pl-5">
              {p.issues.map((issue, i) => (
                <li key={`${issue.code}-${i}`}>{issueText(issue, doc, geometry, state.units)}</li>
              ))}
            </ul>
          </>
        )}
        {p.kind === "rejected" && <p>{rejectionText(p.code, p.entities, doc, geometry)}</p>}
        {p.kind === "conflict" && <p>{t("problem.conflictBody")}</p>}
        {p.kind === "history" && <p>{t("problem.historyBody")}</p>}
        {p.kind === "failed" && <p>{t("problem.failedBody")}</p>}
      </Notice>
      <div>{action}</div>
    </div>
  );
}

function Inspector({
  state,
  editable,
  dispatch,
  onCommit,
  onPicked,
}: {
  state: EditorState;
  editable: boolean;
  dispatch: (action: EditorAction) => void;
  onCommit: (ops: PlanOp[]) => void;
  onPicked: () => void;
}) {
  const sel = state.selection;
  const floor = state.plan.geometry.floors[0];
  const rooms = floor?.rooms ?? [];
  const nameOf = (id: string) => rooms.find((r) => r.id === id)?.name ?? id;
  let body: string | null = null;
  let hint: string | null = null;
  let roomId: string | null = null;
  if (sel?.kind === "room" || sel?.kind === "side") {
    roomId = sel.kind === "room" ? sel.id : sel.room;
    const room = rooms.find((r) => r.id === roomId);
    if (room) {
      body =
        sel.kind === "room"
          ? t("selectedRoom", { name: room.name })
          : t("selectedSide", { name: room.name, side: t(`sides.${sel.side}`) });
      hint = sel.kind === "room" ? t("moveRoomHint") : t("moveSideHint");
      if (room.clear_w_mm != null && room.clear_d_mm != null) {
        body = t("joined", { a: body, b: formatDims(room.clear_w_mm, room.clear_d_mm, state.units) });
      }
    }
  } else if (sel?.kind === "opening") {
    const opening = floor?.openings.find((o) => o.id === sel.id);
    if (opening) {
      const kind = t(`openingKinds.${opening.kind}`);
      // an outside opening joins one room and the outside: name only the room
      const [a, b] = opening.connects.filter((c) => c !== "EXTERIOR");
      body = b ? t("selectedOpeningBetween", { kind, a: nameOf(a), b: nameOf(b) }) : t("selectedOpeningIn", { kind, a: nameOf(a ?? "") });
      hint = t("moveOpeningHint");
    }
  }
  const revision = state.plan.editing.revision_no;
  // keyboard access to every gesture: pick a side here, then nudge it with the arrow keys
  const sides = editable && roomId ? (roomSides(state.plan.document, roomId) ?? []) : [];
  return (
    <section aria-labelledby="plan-selection" className="flex flex-col gap-2 rounded-lg border p-3">
      <h3 id="plan-selection" className="text-sm font-medium">
        {t("selection")}
      </h3>
      <p className="text-sm">{body ?? t("nothingSelected")}</p>
      {editable && hint && <p className="text-sm text-muted-foreground">{hint}</p>}
      {roomId && sides.length > 0 && (
        <div role="group" aria-label={t("sidesLabel")} className="flex flex-wrap gap-1">
          {sides.map((side) => {
            const active = sel?.kind === "side" && sel.side === side.side;
            return (
              <Button
                key={side.side}
                size="sm"
                variant={active ? "secondary" : "outline"}
                aria-pressed={active}
                onClick={() => {
                  dispatch({ type: "select", selection: { kind: "side", room: roomId, side: side.side } });
                  onPicked();
                }}
              >
                {t(`sides.${side.side}`)}
              </Button>
            );
          })}
        </div>
      )}
      {editable && sel?.kind === "side" && (
        <SidePanel state={state} dispatch={dispatch} onCommit={onCommit} roomId={sel.room} side={sel.side} />
      )}
      {editable && sel?.kind === "room" && (
        <RoomPanel
          key={`${sel.id}-${revision}`}
          state={state}
          dispatch={dispatch}
          onCommit={onCommit}
          roomId={sel.id}
        />
      )}
      {editable && sel?.kind === "area" && (
        <OpenAreaPanel
          key={`${sel.id}-${revision}-${state.units}`}
          state={state}
          dispatch={dispatch}
          onCommit={onCommit}
          areaId={sel.id}
        />
      )}
      {editable && sel?.kind === "opening" && (
        <OpeningPanel
          key={`${sel.id}-${revision}-${state.units}`}
          state={state}
          dispatch={dispatch}
          onCommit={onCommit}
          openingId={sel.id}
        />
      )}
    </section>
  );
}

function RoomList({
  state,
  editable,
  onSelect,
  onSelectArea,
}: {
  state: EditorState;
  editable: boolean;
  onSelect: (id: string) => void;
  onSelectArea: (id: string) => void;
}) {
  const floor = state.plan.geometry.floors[0];
  const rooms = floor?.rooms ?? [];
  const open = floor?.open_areas ?? [];
  const selected = state.selection?.kind === "room" ? state.selection.id : null;
  return (
    <section aria-labelledby="plan-rooms" className="flex flex-col gap-2 rounded-lg border p-3">
      <h3 id="plan-rooms" className="text-sm font-medium">
        {t("rooms")}
      </h3>
      {rooms.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("roomsEmpty")}</p>
      ) : (
        <ul className="flex flex-col">
          {rooms.map((room) => (
            <li key={room.id}>
              <button
                type="button"
                onClick={() => onSelect(room.id)}
                aria-pressed={selected === room.id}
                className="flex min-h-11 w-full flex-col justify-center rounded-md px-2 py-1 text-left text-sm hover:bg-accent aria-pressed:bg-accent"
              >
                <span>{room.name}</span>
                <span className="text-xs text-muted-foreground">{roomSize(room, state.units)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {open.length > 0 && (
        <>
          <h4 className="pt-2 text-sm font-medium">{t("openAreas")}</h4>
          <ul className="flex flex-col gap-1 text-sm">
            {open.map((a) => {
              const slots = state.plan.editing.insertion_slots.filter((s) => s.open_area === a.id).length;
              const pressed = state.selection?.kind === "area" && state.selection.id === a.id;
              const content = (
                <>
                  <span className="flex flex-col">
                    <span>{t(`openArea.${a.kind}`)}</span>
                    {editable && (
                      <span className="text-xs text-muted-foreground">
                        {slots > 0 ? t("insert.canAdd") : t("insert.cannotAdd")}
                      </span>
                    )}
                  </span>
                  <span className="text-muted-foreground">{formatArea(a.area_mm2, state.units)}</span>
                </>
              );
              return (
                <li key={a.id}>
                  {editable ? (
                    <button
                      type="button"
                      aria-pressed={pressed}
                      onClick={() => onSelectArea(a.id)}
                      className="flex min-h-11 w-full justify-between gap-2 rounded-md px-2 py-1 text-left hover:bg-accent aria-pressed:bg-accent"
                    >
                      {content}
                    </button>
                  ) : (
                    <div className="flex justify-between gap-2 px-2">{content}</div>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}

function roomSize(room: RoomGeom, units: Units): string | null {
  const dims =
    room.clear_w_mm != null && room.clear_d_mm != null
      ? formatDims(room.clear_w_mm, room.clear_d_mm, units)
      : null;
  const area = room.carpet_area_mm2 != null ? formatArea(room.carpet_area_mm2, units) : null;
  return dims && area ? t("joined", { a: dims, b: area }) : (dims ?? area);
}

function Checks({ state }: { state: EditorState }) {
  const { document: doc, geometry, validation } = state.plan;
  const issues: ValidationIssue[] = [...(validation?.errors ?? []), ...(validation?.warnings ?? [])];
  return (
    <section aria-labelledby="plan-checks" className="flex flex-col gap-2 rounded-lg border p-3">
      <h3 id="plan-checks" className="text-sm font-medium">
        {t("issues")}
      </h3>
      {issues.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("issuesNone")}</p>
      ) : (
        <ul className="list-disc pl-5 text-sm">
          {issues.map((issue, i) => (
            <li key={`${issue.code}-${i}`}>{issueText(issue, doc, geometry, state.units)}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
