"use client";

// The one form pattern (UI_DESIGN_SYSTEM.md section 7): label, then help, then the control, then the
// error. Optional answers say so; required ones carry aria-required. Errors are tied to the control
// with aria-describedby and aria-invalid; the form's error summary is the live announcement, so
// field errors are not live regions themselves.
import { cn } from "cn";
import type { ReactNode } from "react";

import { Checkbox } from "@/components/ui/checkbox";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { getTranslator } from "@/lib/i18n";

const common = getTranslator("Common");

export interface ControlProps {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
  "aria-required"?: true;
}

function ids(id: string, description: ReactNode, errors?: string[]) {
  const descriptionId = description ? `${id}-description` : undefined;
  const errorId = errors && errors.length > 0 ? `${id}-error` : undefined;
  const describedBy = [descriptionId, errorId].filter(Boolean).join(" ") || undefined;
  return { descriptionId, errorId, describedBy, invalid: Boolean(errorId) };
}

export function OptionalMark() {
  return <span className="font-sans text-base font-normal tracking-normal text-muted-foreground normal-case"> {common("optional")}</span>;
}

function Errors({ id, errors }: { id?: string; errors?: string[] }) {
  if (!id || !errors) return null;
  return (
    <FieldError id={id} role={undefined}>
      {errors.length === 1 ? (
        errors[0]
      ) : (
        <ul className="ml-4 list-disc">
          {errors.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      )}
    </FieldError>
  );
}

/** A single control with its own label. */
export function FormField({
  id,
  label,
  required = false,
  description,
  errors,
  children,
}: {
  id: string;
  label: ReactNode;
  required?: boolean;
  description?: ReactNode;
  errors?: string[];
  children: (control: ControlProps) => ReactNode;
}) {
  const { descriptionId, errorId, describedBy, invalid } = ids(id, description, errors);
  return (
    <Field className="gap-2">
      {/* Onboarding type scale: 18px labels, 16px help (UI_DESIGN_SYSTEM.md 3.2). */}
      <FieldLabel htmlFor={id} className="text-lg leading-snug font-semibold">
        {label}
        {!required && <OptionalMark />}
      </FieldLabel>
      {description && <FieldDescription id={descriptionId} className="text-base">{description}</FieldDescription>}
      {children({
        id,
        "aria-describedby": describedBy,
        "aria-invalid": invalid ? true : undefined,
        "aria-required": required ? true : undefined,
      })}
      <Errors id={errorId} errors={errors} />
    </Field>
  );
}

/** Several controls under one question (a fieldset named by its legend). */
export function FormFieldset({
  id,
  legend,
  required = false,
  description,
  errors,
  legendSize = "question",
  children,
}: {
  id: string;
  legend: ReactNode;
  required?: boolean;
  /** "label" when a section heading already asks the question: the legend becomes a mono caption. */
  legendSize?: "question" | "label";
  description?: ReactNode;
  errors?: string[];
  children: (group: { legendId: string; describedBy?: string; invalid: boolean }) => ReactNode;
}) {
  const { descriptionId, errorId, describedBy, invalid } = ids(id, description, errors);
  const legendId = `${id}-legend`;
  return (
    <FieldSet
      id={id}
      aria-describedby={describedBy}
      data-invalid={invalid || undefined}
      className="gap-4"
    >
      {/* The question: display caps at 24px, 30px from sm, as on the website's request card. */}
      <FieldLegend
        id={legendId}
        className={
          legendSize === "label"
            ? "mb-0 font-mono tracking-widest text-muted-foreground uppercase data-[variant=legend]:text-xs"
            : "mb-0 font-heading leading-[1.05] data-[variant=legend]:text-2xl sm:data-[variant=legend]:text-3xl"
        }
      >
        {legend}
        {!required && <OptionalMark />}
      </FieldLegend>
      {description && <FieldDescription id={descriptionId} className="text-base">{description}</FieldDescription>}
      {children({ legendId, describedBy, invalid })}
      <Errors id={errorId} errors={errors} />
    </FieldSet>
  );
}

export interface ChoiceOption {
  value: string;
  label: ReactNode;
}

// The answer chip of the website's request card: white with an ink edge, lifting on hover, brass
// once chosen.
const CARD =
  "p2b-lift flex min-h-12 cursor-pointer items-center gap-3 rounded-md border border-foreground bg-secondary px-4 py-3 text-base leading-snug font-semibold sm:text-lg has-data-checked:bg-brand has-data-checked:text-brand-foreground has-data-checked:ring-1 has-data-checked:ring-foreground has-[[aria-invalid=true]]:border-destructive";

// Columns follow the width of the form, not the screen (container queries), so the same group
// fits a narrow card and a full-width step.
const COLUMNS = {
  1: "grid-cols-1",
  2: "grid-cols-1 @md:grid-cols-2",
  3: "grid-cols-2 @lg:grid-cols-3",
  4: "grid-cols-2 @lg:grid-cols-4",
  5: "grid-cols-3 @md:grid-cols-5",
} as const;

/** One answer from a list, as full-width choice cards (large touch targets, Radix keyboard model). */
export function ChoiceGroup({
  id,
  options,
  value,
  onValueChange,
  columns = 2,
  labelledBy,
  invalid,
  required,
}: {
  id: string;
  options: ChoiceOption[];
  value: string | undefined;
  onValueChange: (value: string) => void;
  columns?: keyof typeof COLUMNS;
  labelledBy: string;
  invalid?: boolean;
  required?: boolean;
}) {
  return (
    <div className="@container">
      <RadioGroup
        value={value ?? ""}
        onValueChange={onValueChange}
        aria-labelledby={labelledBy}
        aria-required={required || undefined}
        className={cn("grid gap-2", COLUMNS[columns])}
      >
        {options.map((option) => {
          const itemId = `${id}-${option.value}`;
          return (
            <label key={option.value} htmlFor={itemId} className={CARD}>
              <RadioGroupItem
                id={itemId}
                value={option.value}
                aria-invalid={invalid || undefined}
              />
              <span>{option.label}</span>
            </label>
          );
        })}
      </RadioGroup>
    </div>
  );
}

/** Any number of answers from a list, as checkbox cards. */
export function CheckboxGroup({
  id,
  options,
  value,
  onValueChange,
  columns = 2,
  invalid,
}: {
  id: string;
  options: ChoiceOption[];
  value: string[];
  onValueChange: (value: string[]) => void;
  columns?: keyof typeof COLUMNS;
  invalid?: boolean;
}) {
  return (
    <div className="@container">
      <div className={cn("grid gap-2", COLUMNS[columns])}>
        {options.map((option) => {
          const itemId = `${id}-${option.value}`;
          const checked = value.includes(option.value);
          return (
            <label key={option.value} htmlFor={itemId} className={CARD}>
              <Checkbox
                id={itemId}
                checked={checked}
                aria-invalid={invalid || undefined}
                onCheckedChange={(next) =>
                  onValueChange(
                    next === true
                      ? [...value, option.value]
                      : value.filter((item) => item !== option.value),
                  )
                }
              />
              <span>{option.label}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
