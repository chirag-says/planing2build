"use client";

// "Describe it in words" (Checkpoint 4): the owner's description of the home, read by the AI
// assistant into provisional design inputs, with what it could not find, what it left out, where
// the words differ from the submitted requirement and what is outside these floor plans. The
// route stores nothing. Every line here is built from the server's structured answer; the only
// model text shown is its own questions back, labelled as such. "Use these details" puts the
// proposed inputs into the generate form, where the owner checks them and generates; the
// submitted requirement stays the authority. The panel hides itself when the API answers 404
// (assistant off) and hands a 403 (not the owner) to the page's lock.
import { SparklesIcon } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { browserApi, errorCode } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";
import {
  conflictLine,
  factLabel,
  preferenceLine,
  proposedInputLines,
  unsupportedTopic,
  type ProposedInputs,
  type RequirementProposal,
} from "@/lib/plan/generate";

const t = getTranslator("Plan");

type Phase =
  | { kind: "idle" }
  | { kind: "asking" }
  | { kind: "answer"; proposal: RequirementProposal }
  | { kind: "error"; message: string }
  | { kind: "off" };

function Section({ title, note, lines }: { title: string; note?: string; lines: string[] }) {
  if (lines.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <p className="font-medium">{title}</p>
      {note && <p className="text-xs text-muted-foreground">{note}</p>}
      <ul className="list-disc pl-5">
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </div>
  );
}

export function DescribePanel({
  projectId,
  onUse,
  onOff,
  onOwnerOnly,
}: {
  projectId: string;
  onUse: (inputs: ProposedInputs) => void;
  onOff: () => void;
  onOwnerOnly: () => void;
}) {
  const ids = useId();
  const [text, setText] = useState("");
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });

  async function ask() {
    const words = text.trim();
    if (!words) return;
    setPhase({ kind: "asking" });
    const response = await browserApi
      .POST("/api/v1/projects/{project_id}/house-plans/assistant/requirement", {
        params: { path: { project_id: projectId } },
        body: { text: words },
      })
      .catch(() => null);
    const data = response?.data;
    if (data) {
      setPhase({ kind: "answer", proposal: data });
      return;
    }
    if (response?.response.status === 404) {
      setPhase({ kind: "off" });
      return;
    }
    const code = errorCode(response?.error);
    if (code === "FORBIDDEN") {
      onOwnerOnly();
      return;
    }
    setPhase({
      kind: "error",
      message:
        code === "PROVIDER_UNAVAILABLE"
          ? t("generate.words.errorUnavailable")
          : code === "RATE_LIMITED"
            ? t("generate.words.errorBusy")
            : t("generate.words.errorFailed"),
    });
  }

  if (phase.kind === "off") {
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <p>{t("generate.words.off")}</p>
        <Button type="button" variant="ghost" size="sm" onClick={onOff}>
          {t("generate.words.dismiss")}
        </Button>
      </div>
    );
  }

  const proposal = phase.kind === "answer" ? phase.proposal : null;
  const inputs = proposal ? proposedInputLines(proposal.design_inputs) : [];
  const preferences = proposal
    ? proposal.preferences.map(preferenceLine).filter((line): line is string => line !== null)
    : [];

  return (
    <section aria-labelledby={`${ids}-title`} className="flex flex-col gap-2 rounded-lg border p-3">
      <h4 id={`${ids}-title`} className="flex items-center gap-2 text-sm font-medium">
        <SparklesIcon aria-hidden="true" className="size-4" />
        {t("generate.words.title")}
      </h4>
      <p className="text-xs text-muted-foreground">{t("generate.words.note")}</p>
      <form
        className="flex flex-col gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void ask();
        }}
      >
        <Label htmlFor={`${ids}-text`}>{t("generate.words.label")}</Label>
        <Textarea
          id={`${ids}-text`}
          value={text}
          maxLength={400}
          rows={3}
          placeholder={t("generate.words.placeholder")}
          onChange={(e) => setText(e.target.value)}
        />
        <Button
          type="submit"
          variant="outline"
          className="sm:self-start"
          disabled={!text.trim() || phase.kind === "asking"}
        >
          {phase.kind === "asking" ? t("generate.words.asking") : t("generate.words.ask")}
        </Button>
      </form>
      <div aria-live="polite" className="flex flex-col gap-2 text-sm">
        {phase.kind === "error" && <p className="text-destructive">{phase.message}</p>}
        {proposal?.status === "FAILED" && (
          <div data-status="FAILED" className="flex flex-col gap-2">
            <p>{t("generate.words.failed")}</p>
            <div>
              <Button type="button" variant="ghost" onClick={() => setPhase({ kind: "idle" })}>
                {t("generate.words.dismiss")}
              </Button>
            </div>
          </div>
        )}
        {proposal?.status === "INTERPRETED" && (
          <div data-status="INTERPRETED" className="flex flex-col gap-3 rounded-md bg-muted p-2">
            {inputs.length > 0 ? (
              <Section title={t("generate.words.proposal")} lines={inputs} />
            ) : (
              <p>{t("generate.words.noInputs")}</p>
            )}
            <Section
              title={t("generate.words.conflictsTitle")}
              note={t("generate.words.conflictsNote")}
              lines={proposal.conflicts.map(conflictLine)}
            />
            <Section
              title={t("generate.words.missingTitle")}
              note={t("generate.words.missingNote")}
              lines={proposal.missing.map(factLabel)}
            />
            <Section title={t("generate.words.assumedTitle")} lines={proposal.assumed.map(factLabel)} />
            <Section
              title={t("generate.words.unsupportedTitle")}
              lines={[...new Set(proposal.unsupported.map(unsupportedTopic))]}
            />
            <Section title={t("generate.words.clarificationsTitle")} lines={proposal.clarifications} />
            <Section
              title={t("generate.words.preferencesTitle")}
              note={t("generate.words.preferencesNote")}
              lines={preferences}
            />
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={!proposal.design_inputs || inputs.length === 0}
                onClick={() => {
                  if (proposal.design_inputs) onUse(proposal.design_inputs);
                  setPhase({ kind: "idle" });
                }}
              >
                {t("generate.words.use")}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setPhase({ kind: "idle" })}>
                {t("generate.words.dismiss")}
              </Button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
