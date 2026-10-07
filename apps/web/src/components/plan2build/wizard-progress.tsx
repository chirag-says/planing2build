"use client";

// Where the family is in a multi-step form (UI_DESIGN_SYSTEM.md section 6): "Step n of m" always;
// on phones one progress bar; from sm up, one column per step on a single row, each with a bar and
// a done, current or not-started mark. Steps already reached can be reopened; later ones cannot be
// skipped to.
import { cn } from "cn";
import { CircleCheckIcon, CircleDotIcon, CircleIcon } from "lucide-react";

import { Progress } from "@/components/ui/progress";

export interface WizardLabels {
  nav: string;
  step: (current: number, total: number) => string;
  done: (title: string) => string;
  current: (title: string) => string;
  todo: (title: string) => string;
}

export function WizardProgress({
  steps,
  current,
  furthest,
  onSelect,
  labels,
}: {
  steps: string[];
  current: number;
  furthest: number;
  onSelect: (index: number) => void;
  labels: WizardLabels;
}) {
  const total = steps.length;
  const counter = labels.step(current + 1, total);
  return (
    <nav aria-label={labels.nav} className="flex flex-col gap-3">
      <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">{counter}</p>
      {/* Phones: one bar. From sm: one column per step, each with its own bar, on a single row. */}
      <Progress value={((current + 1) / total) * 100} aria-label={counter} className="sm:hidden" />
      <ol
        className="hidden gap-3 sm:grid"
        style={{ gridTemplateColumns: `repeat(${total}, minmax(0, 1fr))` }}
      >
        {steps.map((title, index) => {
          const isCurrent = index === current;
          const isDone = index < furthest && !isCurrent;
          const reachable = index <= furthest && !isCurrent;
          const Icon = isCurrent ? CircleDotIcon : isDone ? CircleCheckIcon : CircleIcon;
          const name = isCurrent
            ? labels.current(title)
            : isDone
              ? labels.done(title)
              : labels.todo(title);
          // The visible title and icon are hidden from assistive technology; the hidden text says
          // the title and its state once.
          const body = (
            <>
              <Icon
                aria-hidden="true"
                className={cn("mt-0.5 size-4 shrink-0", isDone && "text-success")}
              />
              <span aria-hidden="true">{title}</span>
              <span className="sr-only">{name}</span>
            </>
          );
          const base = "flex items-start gap-1.5 rounded-sm text-left font-mono text-xs leading-snug tracking-wider uppercase";
          return (
            <li
              key={title}
              aria-current={isCurrent ? "step" : undefined}
              className="flex min-w-0 flex-col gap-2"
            >
              <span
                aria-hidden="true"
                className={cn(
                  "h-1.5",
                  isCurrent ? "bg-brand ring-1 ring-foreground" : isDone ? "bg-foreground" : "bg-foreground/15",
                )}
              />
              {reachable ? (
                <button
                  type="button"
                  onClick={() => onSelect(index)}
                  className={cn(base, "text-foreground underline-offset-4 hover:underline")}
                >
                  {body}
                </button>
              ) : (
                <span
                  className={cn(
                    base,
                    isCurrent ? "font-semibold text-foreground" : "text-muted-foreground",
                  )}
                >
                  {body}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
