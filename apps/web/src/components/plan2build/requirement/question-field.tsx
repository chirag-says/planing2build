"use client";

// One question, rendered from its definition with the form system (UI_DESIGN_SYSTEM.md section 7).
// Location, ranking and files have their own components; every other engine type is here
// (REQUIREMENT_QUESTIONS_V1 section L.2).
import type { Question } from "@p2b/contracts";
import { XIcon } from "lucide-react";
import type { ReactNode } from "react";

import {
  CheckboxGroup,
  ChoiceGroup,
  FormField,
  FormFieldset,
  type ChoiceOption,
} from "@/components/plan2build/form-field";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { getTranslator } from "@/lib/i18n";
import { NOT_SURE } from "@/lib/questions";

const t = getTranslator("Requirement");
const common = getTranslator("Common");

export interface FieldProps {
  question: Question;
  value: unknown;
  onChange: (value: unknown) => void;
  errors?: string[];
  /** Replaces the question's help text (for example while the locality is being looked up). */
  description?: ReactNode;
}

const toNumber = (raw: string): number | undefined => (raw === "" ? undefined : Number(raw));
const bound = (raw: string | null | undefined) => (raw == null ? undefined : Number(raw));

/** Columns for choice cards from the longest label, so short answers sit side by side. */
function columnsFor(options: ChoiceOption[]): 2 | 3 | 4 | 5 {
  const longest = Math.max(...options.map((option) => String(option.label).length));
  if (longest <= 4) return options.length > 4 ? 5 : 4;
  if (longest <= 14) return 3;
  return 2;
}

function NumberInput({
  question,
  value,
  onChange,
  ...rest
}: {
  question: Question;
  value: unknown;
  onChange: (value: number | undefined) => void;
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
  "aria-required"?: true;
  "aria-label"?: string;
}) {
  return (
    <Input
      {...rest}
      type="number"
      inputMode="decimal"
      step="any"
      min={bound(question.min)}
      max={bound(question.max)}
      value={typeof value === "number" ? value : ""}
      onChange={(e) => onChange(toNumber(e.target.value))}
      className="max-w-48 tabular-nums"
    />
  );
}

export function QuestionField({ question, value, onChange, errors, description }: FieldProps) {
  const id = `q-${question.key}`;
  const help = description ?? question.help ?? undefined;
  const options = (question.options ?? []).map((option) => ({
    value: option.value,
    label: option.label,
  }));

  switch (question.type) {
    case "text": {
      const text = typeof value === "string" ? value : "";
      const max = question.max_length ?? undefined;
      const counter = question.multiline && max ? t("chars", { count: text.length, max }) : null;
      return (
        <FormField
          id={id}
          label={question.label}
          required={question.required}
          description={help ?? counter}
          errors={errors}
        >
          {(control) => {
            const props = {
              ...control,
              value: text,
              maxLength: max,
              onChange: (e: { target: { value: string } }) =>
                onChange(e.target.value === "" ? undefined : e.target.value),
            };
            return question.multiline ? (
              <>
                <Textarea {...props} rows={4} />
                {help && counter && <p className="text-sm text-muted-foreground">{counter}</p>}
              </>
            ) : (
              <Input {...props} type="text" />
            );
          }}
        </FormField>
      );
    }

    case "number":
      return (
        <FormField
          id={id}
          label={question.label}
          required={question.required}
          description={help}
          errors={errors}
        >
          {(control) => <NumberInput {...control} question={question} value={value} onChange={onChange} />}
        </FormField>
      );

    case "number_or_not_sure":
      return (
        <FormFieldset
          id={id}
          legend={question.label}
          required={question.required}
          description={help}
          errors={errors}
        >
          {({ describedBy, invalid }) => (
            <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
              <NumberInput
                id={`${id}-value`}
                question={question}
                value={value}
                onChange={onChange}
                aria-label={question.label}
                aria-describedby={describedBy}
                aria-invalid={invalid ? true : undefined}
              />
              <div className="flex min-h-11 items-center gap-3">
                <Checkbox
                  id={`${id}-not-sure`}
                  checked={value === NOT_SURE}
                  onCheckedChange={(checked) => onChange(checked === true ? NOT_SURE : undefined)}
                />
                <Label htmlFor={`${id}-not-sure`} className="text-base font-normal">
                  {question.not_sure_label ?? common("notSure")}
                </Label>
              </div>
            </div>
          )}
        </FormFieldset>
      );

    case "yes_no":
      return (
        <FormFieldset
          id={id}
          legend={question.label}
          required={question.required}
          description={help}
          errors={errors}
        >
          {({ legendId, invalid }) => (
            <ChoiceGroup
              id={id}
              labelledBy={legendId}
              required={question.required}
              invalid={invalid}
              columns={4}
              value={value === true ? "yes" : value === false ? "no" : undefined}
              onValueChange={(next) => onChange(next === "yes")}
              options={[
                { value: "yes", label: common("yes") },
                { value: "no", label: common("no") },
              ]}
            />
          )}
        </FormFieldset>
      );

    case "single_choice":
      return (
        <FormFieldset
          id={id}
          legend={question.label}
          required={question.required}
          description={help}
          errors={errors}
        >
          {({ legendId, invalid }) => (
            <>
              <ChoiceGroup
                id={id}
                labelledBy={legendId}
                required={question.required}
                invalid={invalid}
                columns={columnsFor(options)}
                value={typeof value === "string" ? value : undefined}
                onValueChange={onChange}
                options={options}
              />
              {!question.required && value !== undefined && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => onChange(undefined)}
                  className="self-start"
                >
                  <XIcon aria-hidden="true" />
                  {t("clearChoice")}
                </Button>
              )}
            </>
          )}
        </FormFieldset>
      );

    case "multi_choice":
      return (
        <FormFieldset
          id={id}
          legend={question.label}
          required={question.required}
          description={help}
          errors={errors}
        >
          {({ invalid }) => (
            <CheckboxGroup
              id={id}
              invalid={invalid}
              value={Array.isArray(value) ? (value as string[]) : []}
              onValueChange={(next) => onChange(next.length > 0 ? next : undefined)}
              options={options}
            />
          )}
        </FormFieldset>
      );

    case "setbacks": {
      const sides = (value && typeof value === "object" ? value : {}) as Record<string, unknown>;
      const update = (side: string, next: unknown) => {
        const merged = { ...sides, [side]: next };
        if (next === undefined) delete merged[side];
        onChange(Object.keys(merged).length > 0 ? merged : undefined);
      };
      return (
        <FormFieldset
          id={id}
          legend={question.label}
          required={question.required}
          description={help}
          errors={errors}
        >
          {({ invalid }) => (
            <div className="grid gap-4 sm:grid-cols-2">
              {(question.sides ?? []).map((side) => {
                const sideId = `${id}-${side.value}`;
                return (
                  <div key={side.value} className="flex flex-col gap-2">
                    <Label htmlFor={sideId} className="text-sm">
                      {side.label}
                    </Label>
                    <div className="flex items-center gap-4">
                      <NumberInput
                        id={sideId}
                        question={question}
                        value={sides[side.value]}
                        onChange={(next) => update(side.value, next)}
                        aria-invalid={invalid ? true : undefined}
                      />
                      <div className="flex min-h-11 items-center gap-2">
                        <Checkbox
                          id={`${sideId}-not-sure`}
                          checked={sides[side.value] === NOT_SURE}
                          onCheckedChange={(checked) =>
                            update(side.value, checked === true ? NOT_SURE : undefined)
                          }
                          aria-label={`${side.label}: ${t("notSureYet")}`}
                        />
                        <Label
                          htmlFor={`${sideId}-not-sure`}
                          aria-hidden="true"
                          className="text-sm font-normal"
                        >
                          {t("notSureYet")}
                        </Label>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </FormFieldset>
      );
    }

    default:
      return null;
  }
}
