"use client";

// The two entry questions before the requirement (REQUIREMENT_QUESTIONS_V1 L.1): a "No" leads to
// the matching capture path (L.3); two "Yes" answers lead to the project. Choosing an answer only
// reveals the next step; the family follows a link to move on (no change of page on input,
// WCAG 3.2.2).
import { ArrowRightIcon } from "lucide-react";
import Link from "next/link";
import { useState, type CSSProperties, type ReactNode } from "react";

import { ChoiceGroup, FormFieldset } from "@/components/plan2build/form-field";
import { Button } from "@/components/ui/button";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Start");
const common = getTranslator("Common");

function YesNo({
  id,
  legend,
  value,
  onChange,
}: {
  id: string;
  legend: string;
  value: boolean | null;
  onChange: (value: boolean) => void;
}) {
  return (
    <FormFieldset id={id} legend={legend} required>
      {({ legendId }) => (
        <ChoiceGroup
          id={id}
          labelledBy={legendId}
          required
          columns={4}
          value={value === null ? undefined : value ? "yes" : "no"}
          onValueChange={(next) => onChange(next === "yes")}
          options={[
            { value: "yes", label: common("yes") },
            { value: "no", label: common("no") },
          ]}
        />
      )}
    </FormFieldset>
  );
}

/** On the hanging card each question carries its step number, as on the website's card. */
function Step({ number, framed, children }: { number: number; framed: boolean; children: ReactNode }) {
  if (!framed) return children;
  return (
    <div className="bid-step hc-step hc-q" style={{ "--i": number } as CSSProperties}>
      <span className="hc-qnum font-mono" aria-hidden="true">
        {String(number).padStart(2, "0")}
      </span>
      {children}
    </div>
  );
}

function Next({ href, label }: { href: string; label: string }) {
  return (
    <Button asChild size="lg" className="self-start">
      <Link href={href}>
        {label}
        <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
      </Link>
    </Button>
  );
}

export function EntryQuestions({ framed = false }: { framed?: boolean }) {
  const [newHome, setNewHome] = useState<boolean | null>(null);
  const [inRaipur, setInRaipur] = useState<boolean | null>(null);

  return (
    <div className="flex flex-col gap-8">
      <Step number={1} framed={framed}>
        <YesNo id="new-home" legend={t("newHome")} value={newHome} onChange={setNewHome} />
      </Step>
      <div aria-live="polite" className="flex flex-col gap-8">
        {newHome === false && <Next href="/need-help" label={t("continue")} />}
        {newHome && (
          <Step number={2} framed={framed}>
            <YesNo id="in-raipur" legend={t("inRaipur")} value={inRaipur} onChange={setInRaipur} />
          </Step>
        )}
        {newHome && inRaipur === false && <Next href="/other-city" label={t("continue")} />}
        {newHome && inRaipur && (
          <div className="flex flex-col gap-4">
            <p className="text-base">{t("ready")}</p>
            <Next href="/projects/new" label={t("begin")} />
          </div>
        )}
      </div>
    </div>
  );
}
