"use client";

// Operations' professional review controls (Slice 3.2): record a check, decide (approve, request
// changes, reject) with the reviewer's claim, suspend or reinstate with a reason (D-10), review
// portfolio photos, and create an invited professional's account (D-04). The API enforces the
// claim, the requirements and MFA; these controls send and show what it answers.
import type { components } from "@p2b/contracts";
import { CheckIcon, PlusIcon, XIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { ChoiceGroup, FormField, FormFieldset } from "@/components/plan2build/form-field";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { browserApi } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

type Detail = components["schemas"]["ReviewDetailOut"];
type CheckKind = components["schemas"]["CheckIn"]["kind"];
type Outcome = components["schemas"]["CheckIn"]["outcome"];

const t = getTranslator("Ops");
const checks = getTranslator("Checks");
const key = () => crypto.randomUUID();

function useCall() {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function run(name: string, call: () => Promise<{ data?: unknown; error?: unknown }>) {
    setBusy(name);
    setError(null);
    try {
      const { data, error: failure } = await call();
      if (data) {
        router.refresh();
        return true;
      }
      const unmet = (failure as { error?: { details?: { unmet?: string[] } } })?.error?.details?.unmet;
      setError(unmet?.length ? t("professionals.unmetError") : t("professionals.error"));
    } catch {
      setError(t("professionals.error"));
    } finally {
      setBusy(null);
    }
    return false;
  }
  return { busy, error, run };
}

export function RecordCheckForm({ detail }: { detail: Detail }) {
  const { busy, error, run } = useCall();
  const kinds = [...new Set(detail.requirements.flatMap((r) => r.accepts))] as CheckKind[];
  const [kind, setKind] = useState<string | undefined>(undefined);
  const [outcome, setOutcome] = useState<string | undefined>("PASSED");
  const [subject, setSubject] = useState("");
  const [note, setNote] = useState("");
  async function record(event: FormEvent) {
    event.preventDefault();
    if (!kind || !outcome) return;
    const ok = await run("check", () =>
      browserApi.POST("/api/v1/ops/professional-categories/{category_id}/checks", {
        params: { path: { category_id: detail.category_id } },
        body: { kind: kind as CheckKind, outcome: outcome as Outcome, subject, note: note || null },
      }),
    );
    if (ok) {
      setSubject("");
      setNote("");
    }
  }
  return (
    <form onSubmit={record} className="flex flex-col gap-4">
      <FormFieldset id="check-kind" legend={t("professionals.checkKind")} required>
        {({ legendId }) => (
          <ChoiceGroup id="check-kind" labelledBy={legendId} value={kind} onValueChange={setKind}
            options={kinds.map((k) => ({ value: k, label: checks(`kind.${k}`) }))} />
        )}
      </FormFieldset>
      <FormField id="check-subject" label={t("professionals.subject")} required>
        {(c) => <Input {...c} maxLength={80} value={subject} onChange={(e) => setSubject(e.target.value)} />}
      </FormField>
      <FormFieldset id="check-outcome" legend={t("professionals.outcome")} required>
        {({ legendId }) => (
          <ChoiceGroup id="check-outcome" labelledBy={legendId} value={outcome} onValueChange={setOutcome} columns={3}
            options={(["PASSED", "FAILED", "NOT_APPLICABLE"] as const).map((o) => ({ value: o, label: checks(`outcome.${o}`) }))} />
        )}
      </FormFieldset>
      <FormField id="check-note" label={t("professionals.note")}>
        {(c) => <Textarea {...c} rows={2} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />}
      </FormField>
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
      <Button type="submit" variant="outline" disabled={!kind || !subject || busy !== null} className="sm:self-start">
        {busy === "check" ? <Spinner /> : <PlusIcon aria-hidden="true" />}
        {t("professionals.record")}
      </Button>
    </form>
  );
}

export function DecisionControls({ detail }: { detail: Detail }) {
  const { busy, error, run } = useCall();
  const [message, setMessage] = useState("");
  const [missing, setMissing] = useState(false);
  const path = (action: "approve" | "request-changes" | "reject") =>
    action === "approve"
      ? browserApi.POST("/api/v1/ops/professional-categories/{category_id}/approve", {
          params: { path: { category_id: detail.category_id }, header: { "Idempotency-Key": key() } },
          body: { message: message || null },
        })
      : action === "reject"
        ? browserApi.POST("/api/v1/ops/professional-categories/{category_id}/reject", {
            params: { path: { category_id: detail.category_id }, header: { "Idempotency-Key": key() } },
            body: { message },
          })
        : browserApi.POST("/api/v1/ops/professional-categories/{category_id}/request-changes", {
            params: { path: { category_id: detail.category_id }, header: { "Idempotency-Key": key() } },
            body: { message },
          });
  async function decide(action: "approve" | "request-changes" | "reject") {
    if (action !== "approve" && !message.trim()) {
      setMissing(true);
      return;
    }
    setMissing(false);
    await run(action, () => path(action));
  }
  return (
    <div className="flex flex-col gap-4">
      <FormField id="decision-message" label={t("professionals.message")}
        errors={missing ? [t("professionals.messageNeeded")] : undefined}>
        {(c) => <Textarea {...c} rows={3} maxLength={2000} value={message}
          onChange={(e) => { setMessage(e.target.value); setMissing(false); }} />}
      </FormField>
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
      <div className="flex flex-wrap gap-2">
        <Button type="button" onClick={() => decide("approve")} disabled={busy !== null}>
          {busy === "approve" ? <Spinner /> : <CheckIcon aria-hidden="true" />}
          {t("professionals.approveCategory")}
        </Button>
        <Button type="button" variant="outline" onClick={() => decide("request-changes")} disabled={busy !== null}>
          {t("professionals.requestChanges")}
        </Button>
        <Button type="button" variant="destructive" onClick={() => decide("reject")} disabled={busy !== null}>
          <XIcon aria-hidden="true" />
          {t("professionals.reject")}
        </Button>
      </div>
    </div>
  );
}

export function SuspensionControl({ detail }: { detail: Detail }) {
  const { busy, error, run } = useCall();
  const [reason, setReason] = useState("");
  const action = detail.listing_state === "SUSPENDED" ? "reinstate" : "suspend";
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!reason.trim()) return;
    const call = () =>
      action === "suspend"
        ? browserApi.POST("/api/v1/ops/professional-categories/{category_id}/suspend", {
            params: { path: { category_id: detail.category_id } }, body: { reason },
          })
        : browserApi.POST("/api/v1/ops/professional-categories/{category_id}/reinstate", {
            params: { path: { category_id: detail.category_id } }, body: { reason },
          });
    if (await run(action, call)) setReason("");
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <FormField id="suspension-reason" label={t("professionals.reason")} required>
        {(c) => <Textarea {...c} rows={2} maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} />}
      </FormField>
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
      <Button type="submit" variant={action === "suspend" ? "destructive" : "default"}
        disabled={!reason.trim() || busy !== null} className="sm:self-start">
        {busy && <Spinner />}
        {action === "suspend" ? t("professionals.suspend") : t("professionals.reinstate")}
      </Button>
    </form>
  );
}

export function PortfolioReview({ itemId }: { itemId: string }) {
  const { busy, run } = useCall();
  const review = (verdict: "approve" | "reject") =>
    run(verdict, () =>
      browserApi.POST("/api/v1/ops/portfolio-items/{item_id}/{verdict}", {
        params: { path: { item_id: itemId, verdict } },
      }),
    );
  return (
    <span className="flex gap-1">
      <Button type="button" size="sm" variant="outline" disabled={busy !== null} onClick={() => review("approve")}>
        {t("professionals.approve")}
      </Button>
      <Button type="button" size="sm" variant="ghost" disabled={busy !== null} onClick={() => review("reject")}>
        {t("professionals.rejectItem")}
      </Button>
    </span>
  );
}

export function CreateProfessionalForm() {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "created" | "exists" | "error">("idle");
  async function create(event: FormEvent) {
    event.preventDefault();
    setState("busy");
    try {
      const { data } = await browserApi.POST("/api/v1/ops/professionals", {
        params: { header: { "Idempotency-Key": key() } },
        body: { email, display_name: name },
      });
      if (data) {
        setState(data.created ? "created" : "exists");
        setEmail("");
        setName("");
      } else {
        setState("error");
      }
    } catch {
      setState("error");
    }
  }
  return (
    <form onSubmit={create} className="flex flex-col gap-4">
      <FormField id="pro-email" label={t("professionals.email")} required>
        {(c) => <Input {...c} type="email" autoComplete="off" value={email} onChange={(e) => setEmail(e.target.value)} />}
      </FormField>
      <FormField id="pro-name" label={t("professionals.name")}>
        {(c) => <Input {...c} value={name} onChange={(e) => setName(e.target.value)} />}
      </FormField>
      <div aria-live="polite">
        {state === "created" && <Notice tone="success">{t("professionals.created")}</Notice>}
        {state === "exists" && <Notice tone="info">{t("professionals.exists")}</Notice>}
        {state === "error" && <Notice tone="error">{t("professionals.createError")}</Notice>}
      </div>
      <Button type="submit" disabled={!email || state === "busy"} className="sm:self-start">
        {state === "busy" && <Spinner />}
        {t("professionals.createButton")}
      </Button>
    </form>
  );
}
