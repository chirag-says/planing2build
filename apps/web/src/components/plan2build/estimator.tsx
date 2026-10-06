"use client";

// The public cost estimate (S05 F2; API section 3). The API picks the rate card and says whether it
// is a demonstration card; `EstimateFigures` marks demonstration figures.
import type { EstimateResponse, FinishLevel } from "@p2b/contracts";
import { FinishLevelValues } from "@p2b/contracts";
import { ArrowRightIcon, CalculatorIcon } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { EstimateFigures } from "@/components/plan2build/estimate-figures";
import { ChoiceGroup, FormField, FormFieldset } from "@/components/plan2build/form-field";
import { EmptyState, Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { browserApi, errorCode } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Estimate");
const FLOORS = ["1", "2", "3", "4"] as const;
type Floors = (typeof FLOORS)[number];

type Outcome =
  | { kind: "none" }
  | { kind: "result"; estimate: EstimateResponse }
  | { kind: "unavailable" }
  | { kind: "error"; message: string };

function hasCityError(error: unknown): boolean {
  const fields = (error as { error?: { details?: { fields?: Record<string, unknown> } } })?.error
    ?.details?.fields;
  return Boolean(fields && "city" in fields);
}

export function Estimator() {
  const [area, setArea] = useState("");
  const [floors, setFloors] = useState<Floors>("2");
  const [tier, setTier] = useState<FinishLevel>("STANDARD");
  const [outcome, setOutcome] = useState<Outcome>({ kind: "none" });
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const { data, error } = await browserApi.POST("/api/v1/public/estimate", {
        body: {
          city: "Raipur",
          built_up_area_sqft: Number(area),
          floors: Number(floors),
          finish_level: tier,
        },
      });
      if (data) {
        setOutcome({ kind: "result", estimate: data });
      } else if (hasCityError(error)) {
        setOutcome({ kind: "unavailable" });
      } else {
        const code = errorCode(error);
        const message =
          code === "VALIDATION_ERROR" || code === "RATE_LIMITED"
            ? t(`errors.${code}`)
            : t("errors.default");
        setOutcome({ kind: "error", message });
      }
    } catch {
      setOutcome({ kind: "error", message: t("errors.default") });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t("inputsTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="flex flex-col gap-6">
            <FormField id="area" label={t("area")} required>
              {(control) => (
                <Input
                  {...control}
                  type="number"
                  inputMode="numeric"
                  required
                  min={300}
                  max={12000}
                  value={area}
                  onChange={(e) => setArea(e.target.value)}
                  className="max-w-48 tabular-nums"
                />
              )}
            </FormField>
            <FormField id="floors" label={t("floors")} required>
              {(control) => (
                <Select value={floors} onValueChange={(value) => setFloors(value as Floors)}>
                  <SelectTrigger {...control} className="w-full max-w-48">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {FLOORS.map((value) => (
                      <SelectItem key={value} value={value}>
                        {t(`floorOptions.${value}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </FormField>
            <FormFieldset id="tier" legend={t("tier")} description={t("tierHelp")} required>
              {({ legendId }) => (
                <ChoiceGroup
                  id="tier"
                  labelledBy={legendId}
                  required
                  columns={3}
                  value={tier}
                  onValueChange={(value) => setTier(value as FinishLevel)}
                  options={FinishLevelValues.map((value) => ({ value, label: t(`tiers.${value}`) }))}
                />
              )}
            </FormFieldset>
            <Button type="submit" size="lg" disabled={busy} className="sm:self-start">
              {busy ? <Spinner /> : <CalculatorIcon aria-hidden="true" />}
              {busy ? t("working") : t("submit")}
            </Button>
          </form>
        </CardContent>
      </Card>

      <section aria-live="polite" aria-label={t("resultTitle")}>
        {outcome.kind === "none" && (
          <div className="hidden lg:block">
            <EmptyState icon={CalculatorIcon} title={t("resultTitle")} description={t("intro")} />
          </div>
        )}
        {outcome.kind === "unavailable" && <Notice tone="info">{t("notAvailable")}</Notice>}
        {outcome.kind === "error" && (
          <Notice tone="error" live="assertive">
            {outcome.message}
          </Notice>
        )}
        {outcome.kind === "result" && <EstimateResult estimate={outcome.estimate} />}
      </section>
    </div>
  );
}

function EstimateResult({ estimate }: { estimate: EstimateResponse }) {
  return (
    <EstimateFigures
      figures={estimate}
      title={t("range")}
      footer={
        <Button asChild size="lg">
          <Link href="/start">
            {t("next")}
            <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
          </Link>
        </Button>
      }
    />
  );
}
