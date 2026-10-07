"use client";

// The AI assistant in the plan editor (Checkpoint 4): one sentence in, one proposal out. The
// proposal is the server's: typed operations it compiled from the model's structured intent and
// already checked against the plan's rules, with the before and after of each room. It is shown
// and drawn as a preview; nothing is stored until the owner chooses Apply, which sends the same
// operations through the operations route (validated again, logged, undoable). Cancel drops it.
import { SparklesIcon } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { browserApi, errorCode } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";
import { changeLines, intentLine, outcomeLine, previewOf } from "@/lib/plan/assistant";
import type { EditorAction, EditorState } from "@/lib/plan/editor";
import type { AssistantEdit, PlanOp } from "@/lib/plan/types";

const t = getTranslator("Plan");

type Phase =
  | { kind: "idle" }
  | { kind: "asking" }
  | { kind: "answer"; edit: AssistantEdit }
  | { kind: "error"; message: string };

export function AssistantPanel({
  projectId,
  planId,
  state,
  dispatch,
  onApply,
}: {
  projectId: string;
  planId: string;
  state: EditorState;
  dispatch: (action: EditorAction) => void;
  onApply: (ops: PlanOp[], expected: number) => void;
}) {
  const ids = useId();
  const [text, setText] = useState("");
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const doc = state.plan.document;
  const revision = state.plan.editing.revision_no;

  async function ask() {
    const words = text.trim();
    if (!words) return;
    setPhase({ kind: "asking" });
    dispatch({ type: "preview", rect: null });
    const response = await browserApi
      .POST("/api/v1/projects/{project_id}/house-plans/{plan_id}/assistant/edit", {
        params: { path: { project_id: projectId, plan_id: planId } },
        body: { text: words, expected_revision: revision },
      })
      .catch(() => null);
    const data = response?.data;
    if (data) {
      setPhase({ kind: "answer", edit: data });
      if (data.status === "PROPOSED") dispatch({ type: "preview", rect: previewOf(data) });
      return;
    }
    const code = errorCode(response?.error);
    const message =
      code === "REVISION_CONFLICT"
        ? t("assistant.errorConflict")
        : code === "PROVIDER_UNAVAILABLE"
          ? t("assistant.errorUnavailable")
          : code === "RATE_LIMITED"
            ? t("assistant.errorBusy")
            : t("assistant.errorFailed");
    setPhase({ kind: "error", message });
  }

  function cancel() {
    setPhase({ kind: "idle" });
    dispatch({ type: "preview", rect: null });
  }

  const answer = phase.kind === "answer" ? phase.edit : null;
  const stale = answer !== null && answer.expected_revision !== revision;

  return (
    <section aria-labelledby={`${ids}-title`} className="flex flex-col gap-2 rounded-lg border p-3">
      <h3 id={`${ids}-title`} className="flex items-center gap-2 text-sm font-medium">
        <SparklesIcon aria-hidden="true" className="size-4" />
        {t("assistant.title")}
      </h3>
      <p className="text-xs text-muted-foreground">{t("assistant.note")}</p>
      <form
        className="flex flex-col gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void ask();
        }}
      >
        <Label htmlFor={`${ids}-text`}>{t("assistant.label")}</Label>
        <Textarea
          id={`${ids}-text`}
          value={text}
          maxLength={400}
          rows={2}
          placeholder={t("assistant.placeholder")}
          onChange={(e) => setText(e.target.value)}
        />
        <Button type="submit" variant="outline" disabled={!text.trim() || phase.kind === "asking" || state.busy}>
          {phase.kind === "asking" ? t("assistant.asking") : t("assistant.ask")}
        </Button>
      </form>
      <div aria-live="polite" className="flex flex-col gap-2 text-sm">
        {phase.kind === "error" && <p className="text-destructive">{phase.message}</p>}
        {answer && answer.status === "PROPOSED" && (
          <div className="flex flex-col gap-2 rounded-md bg-muted p-2">
            <p className="font-medium">{t("assistant.proposal")}</p>
            <p>{intentLine(answer, doc)}</p>
            <ul className="list-disc pl-5">
              {changeLines(answer, doc, state.units).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            {stale && <p className="text-destructive">{t("assistant.stale")}</p>}
            <div className="flex gap-2">
              <Button
                disabled={stale || state.busy}
                onClick={() => {
                  onApply(answer.ops, answer.expected_revision);
                  setPhase({ kind: "idle" });
                  setText("");
                }}
              >
                {t("assistant.apply")}
              </Button>
              <Button variant="ghost" onClick={cancel}>
                {t("assistant.cancel")}
              </Button>
            </div>
          </div>
        )}
        {answer && answer.status !== "PROPOSED" && (
          <div className="flex flex-col gap-2">
            <p>{outcomeLine(answer)}</p>
            <div>
              <Button variant="ghost" onClick={cancel}>
                {t("assistant.dismiss")}
              </Button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
