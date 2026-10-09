"use client";

// The two capture paths (REQUIREMENT_QUESTIONS_V1 L.3; R-1, R-2): an email, plus the type of work
// for "Need help?". Each creates an enquiry for operations; nothing else follows from it.
import type { ComingSoonWork, EnquiryKind } from "@p2b/contracts";
import { ComingSoonWorkValues } from "@p2b/contracts";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { ChoiceGroup, FormField, FormFieldset } from "@/components/plan2build/form-field";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { browserApi, errorCode } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Enquiry");
const requirement = getTranslator("Requirement");

export function EnquiryForm({ kind }: { kind: EnquiryKind }) {
  const [email, setEmail] = useState("");
  const [workType, setWorkType] = useState<ComingSoonWork | null>(null);
  const [workMissing, setWorkMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const needsWork = kind === "COMING_SOON_HELP";

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (needsWork && !workType) {
      setWorkMissing(true);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const { error: failure, response } = await browserApi.POST("/api/v1/public/enquiries", {
        body: { kind, email, work_type: needsWork ? workType : null },
      });
      if (response.status === 202) {
        setSent(true);
        return;
      }
      const code = errorCode(failure);
      setError(
        code === "VALIDATION_ERROR" || code === "RATE_LIMITED"
          ? t(`errors.${code}`)
          : t("errors.default"),
      );
    } catch {
      setError(t("errors.default"));
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <div className="flex flex-col gap-4">
        <Notice tone="success" live="polite">
          {t("thanks")}
        </Notice>
        <div className="flex flex-wrap gap-3">
          <Button asChild variant="outline">
            <Link href="/">{t("backHome")}</Link>
          </Button>
          <Button asChild variant="ghost">
            <Link href="/estimate">{t("tryEstimate")}</Link>
          </Button>
        </div>
      </div>
    );
  }


  return (
    <form onSubmit={submit} className="flex flex-col gap-6">
      {needsWork && (
        <FormFieldset
          id="work-type"
          legend={t("workType")}
          required
          errors={workMissing ? [requirement("validation.required")] : undefined}
        >
          {({ legendId, invalid }) => (
            <ChoiceGroup
              id="work-type"
              labelledBy={legendId}
              required
              invalid={invalid}
              columns={3}
              value={workType ?? undefined}
              onValueChange={(next) => {
                setWorkType(next as ComingSoonWork);
                setWorkMissing(false);
              }}
              options={ComingSoonWorkValues.map((value) => ({ value, label: t(`work.${value}`) }))}
            />
          )}
        </FormFieldset>
      )}
      <FormField id="enquiry-email" label={t("email")} required>
        {(control) => (
          <Input
            {...control}
            type="email"
            required
            autoComplete="email"
            inputMode="email"
            maxLength={320}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        )}
      </FormField>
      {error && (
        <Notice tone="error" live="assertive">
          {error}
        </Notice>
      )}
      <Button type="submit" size="lg" disabled={busy} className="self-start">
        {busy && <Spinner />}
        {busy ? t("sending") : t("send")}
      </Button>
    </form>
  );
}
