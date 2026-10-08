"use client";

// "Generate a floor plan": one request to the layout engine for the project, with the
// provisional design inputs the owner chose to give (CP1-03). Nothing is prefilled: the server
// reads the submitted requirement and answers DESIGN_INPUT_REQUIRED with the facts it still
// needs, which are marked on their fields with the server's reason. Each request keeps one
// Idempotency-Key until the server answers it, so a retry after a lost answer never asks twice.
// When generating is locked (not the owner, project state, rules not published, a plan already
// being laid out) the reason shows instead of a button that would fail.
import { ChevronDownIcon, ChevronUpIcon, MapIcon } from "lucide-react";
import { useId, useRef, useState } from "react";

import { DescribePanel } from "@/components/plan2build/plan/plan-describe";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { browserApi, errorCode } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";
import {
  CHOICES,
  COUNT_FIELDS,
  COUNT_RANGE,
  SETBACK_SIDES,
  emptyForm,
  fieldLabel,
  missingProblems,
  optionLabel,
  problemText,
  rejectedProblems,
  statusLock,
  toDesignInputs,
  unsupportedReasons,
  withProposal,
  withoutProposed,
  type ChoiceField,
  type CountField,
  type FieldId,
  type FieldProblem,
  type FieldProblems,
  type FormValues,
  type LockReason,
  type PlanSummary,
  type ProposedInputs,
} from "@/lib/plan/generate";

const t = getTranslator("Plan");

const NOT_SET = "__not_set";
const CHOICE_FIELDS: ChoiceField[] = ["facing_override", "parking_kind", "dining", "kitchen", "stair", "utility"];
const HELP: Partial<Record<ChoiceField | CountField, true>> = {
  facing_override: true,
  bedrooms_exact: true,
  bathrooms_exact: true,
  attached_bathrooms: true,
  parking_spaces: true,
  parking_kind: true,
  stair: true,
};

type Failure = { message: string; lines: string[] };

function FieldProblemText({ id, problem }: { id: string; problem: FieldProblem | undefined }) {
  if (!problem) return null;
  return (
    <p id={id} className="text-sm text-destructive" data-problem={problem.kind}>
      {problemText(problem)}
      {problem.kind === "invalid" && problem.messages.length > 0 && ` (${problem.messages.join("; ")})`}
    </p>
  );
}

export function GeneratePanel({
  projectId,
  lock,
  assistant,
  onRequested,
  onInProgress,
  onLock,
}: {
  projectId: string;
  lock: LockReason | null;
  assistant: boolean | null;
  onRequested: (plan: PlanSummary) => void;
  onInProgress: () => void;
  onLock: (reason: LockReason, currentState?: string) => void;
}) {
  const ids = useId();
  const [form, setForm] = useState<FormValues>(emptyForm);
  const [problems, setProblems] = useState<FieldProblems>({});
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [requested, setRequested] = useState<number | null>(null);
  const [assistantOn, setAssistantOn] = useState(assistant !== false);
  const [used, setUsed] = useState(false);
  const key = useRef<{ body: string; key: string } | null>(null);
  const submitRef = useRef<HTMLButtonElement>(null);

  const fieldId = (field: FieldId) => `${ids}-${field}`;

  function focusField(field: FieldId | undefined) {
    if (!field) return;
    requestAnimationFrame(() => document.getElementById(fieldId(field))?.focus());
  }

  function set(field: FieldId, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
    setProblems((p) => {
      if (!p[field]) return p;
      const next = { ...p };
      delete next[field];
      return next;
    });
  }

  function applyProposal(proposed: ProposedInputs) {
    setForm((f) => withProposal(f, proposed));
    // a field the proposal fills is answered; the server's other questions still stand
    setProblems((p) => withoutProposed(p, proposed));
    setOpen(true);
    setUsed(true);
    requestAnimationFrame(() => submitRef.current?.focus());
  }

  async function generate() {
    if (lock) return;
    const { inputs, problems: local } = toDesignInputs(form);
    const order = Object.keys(local) as FieldId[];
    if (order.length > 0) {
      setProblems(local);
      setOpen(true);
      setFailure({ message: t("generate.fixFirst"), lines: [] });
      focusField(order[0]);
      return;
    }
    const body = inputs ? { design_inputs: inputs } : {};
    const fingerprint = JSON.stringify(body);
    if (!key.current || key.current.body !== fingerprint) {
      key.current = { body: fingerprint, key: crypto.randomUUID() };
    }
    setBusy(true);
    setFailure(null);
    setRequested(null);
    setUsed(false);
    try {
      const { data, error, response } = await browserApi.POST("/api/v1/projects/{project_id}/house-plans", {
        params: { path: { project_id: projectId }, header: { "Idempotency-Key": key.current.key } },
        body,
      });
      if (data) {
        key.current = null;
        setProblems({});
        setRequested(data.sequence);
        onRequested(data);
        return;
      }
      // the server answered: a new attempt is a new action with a new key
      if (response.status < 500) key.current = null;
      const code = errorCode(error);
      const details = (error as { error?: { details?: unknown } } | undefined)?.error?.details;
      const message = (error as { error?: { message?: string } } | undefined)?.error?.message;
      switch (code) {
        case "DESIGN_INPUT_REQUIRED": {
          const missing = missingProblems(details);
          setProblems(missing);
          setOpen(true);
          setFailure({ message: t("generate.errors.DESIGN_INPUT_REQUIRED"), lines: [] });
          focusField((Object.keys(missing) as FieldId[])[0]);
          return;
        }
        case "VALIDATION_ERROR": {
          const rejected = rejectedProblems(details);
          setProblems(rejected.problems);
          setOpen(true);
          setFailure({ message: t("generate.errors.VALIDATION_ERROR"), lines: rejected.other });
          focusField((Object.keys(rejected.problems) as FieldId[])[0]);
          return;
        }
        case "PLAN_UNSUPPORTED":
          setFailure({
            message: t("generate.errors.PLAN_UNSUPPORTED"),
            lines: unsupportedReasons(details).map((r) => t(`generate.unsupported.${r}`)),
          });
          return;
        case "GENERATION_IN_PROGRESS":
          setFailure({ message: t("generate.errors.GENERATION_IN_PROGRESS"), lines: [] });
          onInProgress();
          return;
        case "RULESET_NOT_PUBLISHED":
          onLock("RULESET_NOT_PUBLISHED");
          return;
        case "FORBIDDEN":
          onLock("OWNER_ONLY");
          return;
        case "STATE_CONFLICT": {
          const state = (details as { current_state?: unknown } | undefined)?.current_state;
          if (typeof state === "string" && statusLock(state)) onLock(statusLock(state) ?? "CLOSED", state);
          else setFailure({ message: message ?? t("generate.errors.default"), lines: [] });
          return;
        }
        case "RATE_LIMITED":
          setFailure({ message: t("generate.errors.RATE_LIMITED"), lines: [] });
          return;
        default:
          setFailure({ message: message ?? t("generate.errors.default"), lines: [] });
      }
    } catch {
      setFailure({ message: t("generate.errors.default"), lines: [] });
    } finally {
      setBusy(false);
    }
  }

  if (lock === "OWNER_ONLY") {
    return <Notice tone="info">{t("generate.locks.OWNER_ONLY")}</Notice>;
  }

  const formOpen = lock === null || lock === "IN_PROGRESS";
  const problemFor = (field: FieldId) => problems[field];

  function describedBy(field: FieldId, help: boolean) {
    return [help ? `${fieldId(field)}-help` : null, problemFor(field) ? `${fieldId(field)}-error` : null]
      .filter(Boolean)
      .join(" ") || undefined;
  }

  return (
    <Card size="sm">
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <h3 className="flex items-center gap-2 font-medium">
            <MapIcon aria-hidden="true" className="size-4" />
            {t("generate.title")}
          </h3>
          <p className="text-sm text-muted-foreground">{t("generate.intro")}</p>
        </div>

        {lock && (
          <Notice tone="info" title={t("generate.locks.title")}>
            {t(`generate.locks.${lock}`)}
          </Notice>
        )}

        {formOpen && assistantOn && (
          <DescribePanel
            projectId={projectId}
            onUse={applyProposal}
            onOff={() => setAssistantOn(false)}
            onOwnerOnly={() => onLock("OWNER_ONLY")}
          />
        )}

        {formOpen && (
          <form
            noValidate
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              void generate();
            }}
          >
            <div>
              <Button
                type="button"
                variant="ghost"
                aria-expanded={open}
                aria-controls={`${ids}-details`}
                onClick={() => setOpen((o) => !o)}
              >
                {open ? <ChevronUpIcon aria-hidden="true" /> : <ChevronDownIcon aria-hidden="true" />}
                {open ? t("generate.hideDetails") : t("generate.showDetails")}
              </Button>
            </div>

            <div id={`${ids}-details`} hidden={!open} className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">{t("generate.detailsIntro")}</p>

              <fieldset className="flex flex-col gap-2" aria-describedby={`${ids}-setbacks-help`}>
                <legend className="text-sm font-medium">{t("generate.setbacksLegend")}</legend>
                <p id={`${ids}-setbacks-help`} className="text-xs text-muted-foreground">
                  {t("generate.setbacksHelp")}
                </p>
                <div className="grid gap-3 sm:grid-cols-4">
                  {SETBACK_SIDES.map((side) => {
                    const field: FieldId = `setback_${side}`;
                    return (
                      <div key={side} className="flex flex-col gap-1">
                        <Label htmlFor={fieldId(field)}>{t(`generate.setbackSides.${side}`)}</Label>
                        <Input
                          id={fieldId(field)}
                          inputMode="decimal"
                          autoComplete="off"
                          value={form[field]}
                          aria-invalid={problemFor(field) ? true : undefined}
                          aria-describedby={describedBy(field, false)}
                          onChange={(e) => set(field, e.target.value)}
                        />
                        <FieldProblemText id={`${fieldId(field)}-error`} problem={problemFor(field)} />
                      </div>
                    );
                  })}
                </div>
              </fieldset>

              <div className="grid gap-4 sm:grid-cols-2">
                {COUNT_FIELDS.map((field) => (
                  <div key={field} className="flex flex-col gap-1">
                    <Label htmlFor={fieldId(field)}>{fieldLabel(field)}</Label>
                    {HELP[field] && (
                      <p id={`${fieldId(field)}-help`} className="text-xs text-muted-foreground">
                        {t(`generate.fields.${field as "bedrooms_exact"}.help`)}
                      </p>
                    )}
                    <Input
                      id={fieldId(field)}
                      inputMode="numeric"
                      autoComplete="off"
                      placeholder={`${COUNT_RANGE[field][0]}–${COUNT_RANGE[field][1]}`}
                      value={form[field]}
                      aria-invalid={problemFor(field) ? true : undefined}
                      aria-describedby={describedBy(field, Boolean(HELP[field]))}
                      onChange={(e) => set(field, e.target.value)}
                    />
                    <FieldProblemText id={`${fieldId(field)}-error`} problem={problemFor(field)} />
                  </div>
                ))}

                {CHOICE_FIELDS.map((field) => (
                  <div key={field} className="flex flex-col gap-1">
                    <Label htmlFor={fieldId(field)}>{fieldLabel(field)}</Label>
                    {HELP[field] && (
                      <p id={`${fieldId(field)}-help`} className="text-xs text-muted-foreground">
                        {t(`generate.fields.${field as "stair"}.help`)}
                      </p>
                    )}
                    <Select
                      value={form[field] || NOT_SET}
                      onValueChange={(value) => set(field, value === NOT_SET ? "" : value)}
                    >
                      <SelectTrigger
                        id={fieldId(field)}
                        className="w-full"
                        aria-invalid={problemFor(field) ? true : undefined}
                        aria-describedby={describedBy(field, Boolean(HELP[field]))}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={NOT_SET}>{t("generate.notSet")}</SelectItem>
                        {CHOICES[field].map((value) => (
                          <SelectItem key={value} value={value}>
                            {optionLabel(field, value)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FieldProblemText id={`${fieldId(field)}-error`} problem={problemFor(field)} />
                  </div>
                ))}
              </div>
            </div>

            <div aria-live="polite" className="flex flex-col gap-2">
              {used && <p className="text-sm">{t("generate.words.used")}</p>}
              {requested !== null && (
                <Notice tone="success">{t("generate.requested", { number: requested })}</Notice>
              )}
            </div>
            {failure && (
              <Notice tone="error" live="assertive" title={failure.message}>
                {failure.lines.length > 0 && (
                  <ul className="list-disc pl-5">
                    {failure.lines.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                )}
              </Notice>
            )}

            <Button ref={submitRef} type="submit" size="lg" className="sm:self-start" disabled={busy || lock !== null}>
              {busy ? <Spinner /> : <MapIcon aria-hidden="true" />}
              {busy ? t("generate.requesting") : t("generate.submit")}
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
