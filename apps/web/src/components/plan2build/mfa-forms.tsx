"use client";

// Second factor for operations staff (SECURITY 3.3). Setup: show the secret as a QR code and a
// typed key, confirm one code, then show the recovery codes once. Verify: an authenticator code or
// a recovery code. The API rotates the session cookie on success; this component never sees it.
import { ArrowRightIcon, KeyRoundIcon, ShieldCheckIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { FormField } from "@/components/plan2build/form-field";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { browserApi, errorCode } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";
import { safeNextPath } from "@/lib/navigation";

const t = getTranslator("Ops");

type ErrorKey = "MFA_INVALID" | "MFA_ALREADY_ENROLLED" | "RATE_LIMITED";
const KNOWN: readonly string[] = ["MFA_INVALID", "MFA_ALREADY_ENROLLED", "RATE_LIMITED"];

function messageFor(error: unknown): string {
  const code = errorCode(error);
  return code && KNOWN.includes(code) ? t(`mfa.errors.${code as ErrorKey}`) : t("mfa.errors.default");
}

/** The setup key in groups of four, easier to type into an app by hand. */
function grouped(secret: string): string {
  return secret.replace(/(.{4})/g, "$1 ").trim();
}

type Setup =
  | { step: "intro" }
  | { step: "scan"; secret: string; qr: string }
  | { step: "codes"; codes: string[] };

export function MfaSetupForm() {
  const router = useRouter();
  const [state, setState] = useState<Setup>({ step: "intro" });
  const [code, setCode] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const { data, error: failure } = await browserApi.POST("/api/v1/auth/mfa/enrolment");
      if (data) setState({ step: "scan", secret: data.secret, qr: data.qr_svg_data_uri });
      else setError(messageFor(failure));
    } catch {
      setError(t("mfa.errors.default"));
    } finally {
      setBusy(false);
    }
  }

  async function confirm(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { data, error: failure } = await browserApi.POST("/api/v1/auth/mfa/enrolment/confirm", {
        body: { code },
      });
      if (data) setState({ step: "codes", codes: data.recovery_codes });
      else setError(messageFor(failure));
    } catch {
      setError(t("mfa.errors.default"));
    } finally {
      setBusy(false);
    }
  }

  const problem = error && (
    <Notice tone="error" live="assertive">
      {error}
    </Notice>
  );

  if (state.step === "intro") {
    return (
      <div className="flex flex-col gap-6">
        {problem}
        <Button type="button" size="lg" onClick={start} disabled={busy} className="sm:self-start">
          {busy ? <Spinner /> : <KeyRoundIcon aria-hidden="true" />}
          {busy ? t("mfa.starting") : t("mfa.start")}
        </Button>
      </div>
    );
  }

  if (state.step === "scan") {
    return (
      <form onSubmit={confirm} className="flex flex-col gap-6">
        <p className="text-base">{t("mfa.scan")}</p>
        {/* A data: URI from the API; no script and no third-party request. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={state.qr}
          alt={t("mfa.qrAlt")}
          width={200}
          height={200}
          className="rounded-md border border-border bg-background p-2"
        />
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium">{t("mfa.key")}</p>
          <code
            data-testid="mfa-secret"
            className="w-fit rounded-md bg-muted px-3 py-2 font-mono text-base tracking-wider"
          >
            {grouped(state.secret)}
          </code>
        </div>
        <FormField id="mfa-code" label={t("mfa.codeLabel")} required>
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
        </FormField>
        {problem}
        <Button type="submit" size="lg" disabled={busy || code.length !== 6} className="sm:self-start">
          {busy && <Spinner />}
          {busy ? t("mfa.confirming") : t("mfa.confirm")}
        </Button>
      </form>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <Notice tone="warning" title={t("mfa.codesTitle")} live="polite">
        {t("mfa.codesIntro")}
      </Notice>
      <ol
        aria-label={t("mfa.codesTitle")}
        className="grid grid-cols-2 gap-2 font-mono text-base sm:grid-cols-5"
      >
        {state.codes.map((recovery) => (
          <li key={recovery} className="rounded-md border border-border px-3 py-2 text-center">
            {recovery}
          </li>
        ))}
      </ol>
      <div className="flex min-h-11 items-center gap-3">
        <Checkbox id="codes-saved" checked={saved} onCheckedChange={(next) => setSaved(next === true)} />
        <Label htmlFor="codes-saved" className="text-base font-normal">
          {t("mfa.codesSaved")}
        </Label>
      </div>
      <Button
        type="button"
        size="lg"
        disabled={!saved}
        onClick={() => {
          router.replace("/queue");
          router.refresh();
        }}
        className="sm:self-start"
      >
        {t("mfa.continue")}
        <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
      </Button>
    </div>
  );
}

export function MfaVerifyForm({ next }: { next?: string }) {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function verify(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { data, error: failure } = await browserApi.POST("/api/v1/auth/mfa/verify", {
        body: { code },
      });
      if (data) {
        router.replace(safeNextPath(next, "/queue"));
        router.refresh();
        return;
      }
      setError(messageFor(failure));
    } catch {
      setError(t("mfa.errors.default"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={verify} className="flex flex-col gap-6">
      <FormField id="mfa-verify" label={t("mfa.verifyLabel")} required>
        {(control) => (
          <Input
            {...control}
            type="text"
            required
            autoComplete="one-time-code"
            maxLength={32}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="max-w-64 font-mono text-lg tracking-wider"
          />
        )}
      </FormField>
      {error && (
        <Notice tone="error" live="assertive">
          {error}
        </Notice>
      )}
      <Button type="submit" size="lg" disabled={busy || code.trim().length < 6} className="sm:self-start">
        {busy ? <Spinner /> : <ShieldCheckIcon aria-hidden="true" />}
        {busy ? t("mfa.verifying") : t("mfa.verify")}
      </Button>
    </form>
  );
}
