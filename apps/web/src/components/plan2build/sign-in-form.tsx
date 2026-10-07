"use client";

// Email OTP sign-in, which also creates the account on first use (B-03). Two steps: email, then
// code. The session arrives as an HttpOnly cookie set by the API; this component never sees it.
import { ArrowLeftIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import { FormField } from "@/components/plan2build/form-field";
import { CardStep } from "@/components/plan2build/hanging-card";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { browserApi, errorCode } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";
import { safeNextPath } from "@/lib/navigation";

const t = getTranslator("SignIn");

type ErrorKey = "OTP_INVALID" | "OTP_LOCKED" | "RATE_LIMITED" | "VALIDATION_ERROR" | "FORBIDDEN";
const KNOWN_ERRORS: readonly string[] = [
  "OTP_INVALID",
  "OTP_LOCKED",
  "RATE_LIMITED",
  "VALIDATION_ERROR",
  "FORBIDDEN",
];

function messageFor(error: unknown): string {
  const code = errorCode(error);
  return code && KNOWN_ERRORS.includes(code)
    ? t(`errors.${code as ErrorKey}`)
    : t("errors.default");
}

type Step = { kind: "email" } | { kind: "code"; challengeId: string; maskedContact: string };

/**
 * `next` is where to go after signing in; anything but a same-site path falls back to home.
 * `framed` lays the two steps out as the numbered steps of a HangingCard (homeowner and
 * professional sign-in); labels, buttons and messages are the same either way. `home` is where a
 * sign-in without `next` lands: the homeowner host sends families to their projects, because its
 * `/` is the public website.
 */
export function SignInForm({ next, framed = false, home = "/" }: { next?: string; framed?: boolean; home?: string }) {
  const router = useRouter();
  const [step, setStep] = useState<Step>({ kind: "email" });
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function requestCode(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { data, error: failure } = await browserApi.POST("/api/v1/auth/otp/start", {
        body: { email },
      });
      if (data) {
        setStep({ kind: "code", challengeId: data.challenge_id, maskedContact: data.masked_contact });
        setCode("");
      } else {
        setError(messageFor(failure));
      }
    } catch {
      setError(t("errors.default"));
    } finally {
      setBusy(false);
    }
  }

  async function verifyCode(event: FormEvent) {
    event.preventDefault();
    if (step.kind !== "code") return;
    setBusy(true);
    setError(null);
    try {
      const { data, error: failure } = await browserApi.POST("/api/v1/auth/otp/verify", {
        body: { challenge_id: step.challengeId, code },
      });
      if (data) {
        router.replace(safeNextPath(next, home));
        router.refresh();
        return;
      }
      setError(messageFor(failure));
    } catch {
      setError(t("errors.default"));
    } finally {
      setBusy(false);
    }
  }

  const framedStep = (number: number, title: string, body: ReactNode) =>
    framed ? (
      <CardStep number={number} title={title}>
        {body}
      </CardStep>
    ) : (
      body
    );

  const problem = error && (
    <Notice tone="error" live="assertive">
      {error}
    </Notice>
  );

  if (step.kind === "email") {
    return (
      <form onSubmit={requestCode} className="flex flex-col gap-6">
        {framedStep(1, t("card.stepEmail"), <FormField id="email" label={t("emailLabel")} required>
          {(control) => (
            <Input
              {...control}
              type="email"
              required
              autoComplete="email"
              inputMode="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          )}
        </FormField>)}
        {problem}
        <Button type="submit" size="lg" disabled={busy}>
          {busy && <Spinner />}
          {busy ? t("sending") : t("sendCode")}
        </Button>
      </form>
    );
  }

  return (
    <form onSubmit={verifyCode} className="flex flex-col gap-6">
      <Notice tone="info" live="polite">
        {t("codeSent", { contact: step.maskedContact })}
      </Notice>
      {framedStep(2, t("card.stepCode"), <FormField id="code" label={t("codeLabel")} required>
        {(control) => (
          <Input
            {...control}
            type="text"
            required
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            className="max-w-48 font-mono text-lg tracking-[0.4em]"
          />
        )}
      </FormField>)}
      {problem}
      <div className="flex flex-col gap-3">
        <Button type="submit" size="lg" disabled={busy || code.length !== 6}>
          {busy && <Spinner />}
          {busy ? t("verifying") : t("verify")}
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => {
            setStep({ kind: "email" });
            setError(null);
          }}
        >
          <ArrowLeftIcon aria-hidden="true" />
          {t("useAnotherEmail")}
        </Button>
      </div>
    </form>
  );
}
