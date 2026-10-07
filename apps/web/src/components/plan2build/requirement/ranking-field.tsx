"use client";

// The family ranks every priority themselves (R-12): nothing starts pre-ordered, so no default
// order can stand in for their choice. Buttons, not drag and drop, so it works by keyboard and touch.
import type { Question } from "@p2b/contracts";
import { ArrowDownIcon, ArrowUpIcon, PlusIcon, XIcon } from "lucide-react";

import { FormFieldset } from "@/components/plan2build/form-field";
import { Button } from "@/components/ui/button";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Requirement");

export function RankingField({
  question,
  value,
  onChange,
  errors,
}: {
  question: Question;
  value: string[];
  onChange: (value: string[]) => void;
  errors?: string[];
}) {
  const options = question.options ?? [];
  const label = (raw: string) => options.find((option) => option.value === raw)?.label ?? raw;
  const unranked = options.filter((option) => !value.includes(option.value));

  const move = (index: number, by: -1 | 1) => {
    const next = [...value];
    [next[index], next[index + by]] = [next[index + by], next[index]];
    onChange(next);
  };

  return (
    <FormFieldset
      id={`q-${question.key}`}
      legend={question.label}
      required={question.required}
      description={t("rank.hint")}
      errors={errors}
    >
      {() => (
        <div className="flex flex-col gap-5">
          {value.length > 0 && (
            <div className="flex flex-col gap-2">
              <h4 className="font-mono text-sm tracking-widest text-muted-foreground uppercase">{t("rank.ranked")}</h4>
              <ol className="flex flex-col gap-2">
                {value.map((raw, index) => (
                  <li
                    key={raw}
                    className="flex min-h-12 items-center gap-3 rounded-md border border-foreground bg-secondary py-1 pr-1 pl-3"
                  >
                    <span
                      aria-hidden="true"
                      className="flex size-8 shrink-0 items-center justify-center rounded-sm bg-brand font-mono text-sm font-semibold text-brand-foreground tabular-nums ring-1 ring-foreground"
                    >
                      {index + 1}
                    </span>
                    <span className="sr-only">{index + 1}.</span>
                    <span className="flex-1 text-base font-semibold sm:text-lg">{label(raw)}</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      disabled={index === 0}
                      onClick={() => move(index, -1)}
                      aria-label={t("rank.up", { item: label(raw) })}
                    >
                      <ArrowUpIcon aria-hidden="true" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      disabled={index === value.length - 1}
                      onClick={() => move(index, 1)}
                      aria-label={t("rank.down", { item: label(raw) })}
                    >
                      <ArrowDownIcon aria-hidden="true" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => onChange(value.filter((item) => item !== raw))}
                      aria-label={t("rank.remove", { item: label(raw) })}
                    >
                      <XIcon aria-hidden="true" />
                    </Button>
                  </li>
                ))}
              </ol>
            </div>
          )}
          {unranked.length > 0 && (
            <div className="flex flex-col gap-2">
              <h4 className="font-mono text-sm tracking-widest text-muted-foreground uppercase">{t("rank.available")}</h4>
              <ul className="flex flex-wrap gap-2">
                {unranked.map((option) => (
                  <li key={option.value}>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => onChange([...value, option.value])}
                      aria-label={t("rank.add", { item: option.label })}
                    >
                      <PlusIcon aria-hidden="true" />
                      {option.label}
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </FormFieldset>
  );
}
