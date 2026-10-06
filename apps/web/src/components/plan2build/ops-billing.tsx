"use client";

// Operations and ADMIN billing controls (Slice 3.3; SLICE3_3_READINESS E, I, K): refund requests
// and decisions with a reason, package cancellation (ADMIN), payment exceptions, staff invoice
// links, reconciliation and the versioned configuration. The API enforces roles, MFA, amounts
// and states; these controls send and show what it answers.
import type { components } from "@p2b/contracts";
import { CheckIcon, DownloadIcon, RefreshCwIcon, RotateCcwIcon, XIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { FormField } from "@/components/plan2build/form-field";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { browserApi } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Ops");
const key = () => crypto.randomUUID();
type Request = components["schemas"]["StaffRefundRequestOut"];
type ConfigKind = "pricing-rules" | "instalment-plans" | "tax-configurations" | "offerings";

function message(failure: unknown): string {
  const body = failure as { error?: { message?: string; details?: unknown } } | undefined;
  const detail = body?.error?.details ? ` ${JSON.stringify(body.error.details)}` : "";
  return `${body?.error?.message ?? ""}${detail}`.trim();
}

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
        return data;
      }
      setError(message(failure) || t("billing.error"));
    } catch {
      setError(t("billing.error"));
    } finally {
      setBusy(null);
    }
    return null;
  }
  return { busy, error, run };
}

export function StaffInvoiceLink({ invoiceId, code }: { invoiceId: string; code: string }) {
  const [busy, setBusy] = useState(false);
  async function open() {
    setBusy(true);
    const { data } = await browserApi.GET("/api/v1/ops/billing/invoices/{invoice_id}/document", {
      params: { path: { invoice_id: invoiceId } },
    });
    setBusy(false);
    if (data) window.location.assign(data.url);
  }
  return (
    <Button type="button" size="sm" variant="outline" onClick={() => void open()} disabled={busy}>
      {busy ? <Spinner /> : <DownloadIcon aria-hidden="true" />}
      {t("billing.download", { code })}
    </Button>
  );
}

export function StaffRefundForm({ orderId }: { orderId: string }) {
  const { busy, error, run } = useCall();
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!reason.trim()) return;
    const ok = await run("refund", () =>
      browserApi.POST("/api/v1/ops/billing/orders/{order_id}/refund-requests", {
        params: { path: { order_id: orderId }, header: { "Idempotency-Key": key() } },
        body: { amount: amount.trim() || null, reason: reason.trim() },
      }),
    );
    if (ok) {
      setAmount("");
      setReason("");
    }
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <FormField id="staff-refund-amount" label={t("billing.amountOptional")}>
        {(c) => <Input {...c} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />}
      </FormField>
      <FormField id="staff-refund-reason" label={t("billing.reason")} required>
        {(c) => <Textarea {...c} rows={2} maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} />}
      </FormField>
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
      <Button type="submit" variant="outline" className="sm:self-start" disabled={!reason.trim() || busy !== null}>
        {busy && <Spinner />}
        {t("billing.send")}
      </Button>
    </form>
  );
}

export function CancelPackageForm({ projectId }: { projectId: string }) {
  const { busy, error, run } = useCall();
  const [reason, setReason] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!reason.trim()) return;
    await run("cancel", () =>
      browserApi.POST("/api/v1/ops/billing/packages/{project_id}/cancel", {
        params: { path: { project_id: projectId }, header: { "Idempotency-Key": key() } },
        body: { reason: reason.trim() },
      }),
    );
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">{t("billing.cancelPackageHelp")}</p>
      <FormField id="cancel-package-reason" label={t("billing.reason")} required>
        {(c) => <Textarea {...c} rows={2} maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} />}
      </FormField>
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
      <Button type="submit" variant="destructive" className="sm:self-start" disabled={!reason.trim() || busy !== null}>
        {busy && <Spinner />}
        {t("billing.cancelPackage")}
      </Button>
    </form>
  );
}

export function RefundDecision({ request }: { request: Request }) {
  const { busy, error, run } = useCall();
  const [amount, setAmount] = useState(request.refundable);
  const [ends, setEnds] = useState(false);
  const [revoke, setRevoke] = useState(false);
  const [reason, setReason] = useState("");
  const path = { request_id: request.request_id };

  if (request.state === "FAILED") {
    return (
      <div className="flex flex-col gap-3">
        {error && <Notice tone="error" live="assertive">{error}</Notice>}
        <Button type="button" variant="outline" className="sm:self-start" disabled={busy !== null}
          onClick={() => void run("retry", () =>
            browserApi.POST("/api/v1/ops/billing/refund-requests/{request_id}/retry", {
              params: { path, header: { "Idempotency-Key": key() } },
            }))}>
          {busy ? <Spinner /> : <RotateCcwIcon aria-hidden="true" />}
          {t("billing.retry")}
        </Button>
      </div>
    );
  }
  if (request.state !== "REQUESTED") return null;
  return (
    <div className="flex flex-col gap-4">
      <FormField id="refund-amount" label={t("billing.amount")} required>
        {(c) => <Input {...c} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />}
      </FormField>
      {request.kind === "PACKAGE" && (
        <div className="flex items-center gap-3">
          <Checkbox id="ends-package" checked={ends} onCheckedChange={(v) => setEnds(v === true)} />
          <Label htmlFor="ends-package">{t("billing.endsPackage")}</Label>
        </div>
      )}
      {request.kind === "AI_CREDIT" && (
        <div className="flex items-center gap-3">
          <Checkbox id="revoke-credit" checked={revoke} onCheckedChange={(v) => setRevoke(v === true)} />
          <Label htmlFor="revoke-credit">{t("billing.revokeCredit")}</Label>
        </div>
      )}
      <FormField id="refund-reason" label={t("billing.decisionReason")} required>
        {(c) => <Textarea {...c} rows={3} maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} />}
      </FormField>
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
      <div className="flex flex-wrap gap-2">
        <Button type="button" disabled={!reason.trim() || !amount.trim() || busy !== null}
          onClick={() => void run("approve", () =>
            browserApi.POST("/api/v1/ops/billing/refund-requests/{request_id}/approve", {
              params: { path, header: { "Idempotency-Key": key() } },
              body: { amount: amount.trim(), ends_package: ends, credits_revoked: revoke ? 1 : 0,
                      reason: reason.trim() },
            }))}>
          {busy === "approve" ? <Spinner /> : <CheckIcon aria-hidden="true" />}
          {t("billing.approve")}
        </Button>
        <Button type="button" variant="outline" disabled={!reason.trim() || busy !== null}
          onClick={() => void run("decline", () =>
            browserApi.POST("/api/v1/ops/billing/refund-requests/{request_id}/decline", {
              params: { path, header: { "Idempotency-Key": key() } },
              body: { reason: reason.trim() },
            }))}>
          <XIcon aria-hidden="true" />
          {t("billing.decline")}
        </Button>
      </div>
    </div>
  );
}

export function ResolveException({ exceptionId }: { exceptionId: string }) {
  const { busy, error, run } = useCall();
  const [resolution, setResolution] = useState("");
  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (!resolution.trim()) return;
        void run("resolve", () =>
          browserApi.POST("/api/v1/ops/billing/exceptions/{exception_id}/resolve", {
            params: { path: { exception_id: exceptionId } },
            body: { resolution: resolution.trim() },
          }),
        );
      }}
    >
      <FormField id={`resolution-${exceptionId}`} label={t("billing.resolution")} required>
        {(c) => <Input {...c} maxLength={2000} value={resolution} onChange={(e) => setResolution(e.target.value)} />}
      </FormField>
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
      <Button type="submit" size="sm" variant="outline" className="sm:self-start" disabled={!resolution.trim() || busy !== null}>
        {t("billing.resolve")}
      </Button>
    </form>
  );
}

export function ReconcileButton() {
  const { busy, error, run } = useCall();
  const [result, setResult] = useState<string | null>(null);
  return (
    <div className="flex flex-col gap-2">
      <Button type="button" variant="outline" className="sm:self-start" disabled={busy !== null}
        onClick={() => void run("reconcile", () => browserApi.POST("/api/v1/admin/billing/reconcile"))
          .then((data) => data && setResult(JSON.stringify((data as { counts: unknown }).counts)))}>
        {busy ? <Spinner /> : <RefreshCwIcon aria-hidden="true" />}
        {t("configuration.reconcile")}
      </Button>
      {result && <Notice tone="success" live="polite">{t("configuration.reconciled", { counts: result })}</Notice>}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
    </div>
  );
}

export function PublishButton({ kind, versionId }: { kind: ConfigKind | "eligibility"; versionId: string }) {
  const { busy, error, run } = useCall();
  return (
    <span className="flex flex-col gap-1">
      <Button type="button" size="sm" disabled={busy !== null}
        onClick={() => void run("publish", () =>
          kind === "eligibility"
            ? browserApi.POST("/api/v1/admin/eligibility-checklists/{version_id}/publish", {
                params: { path: { version_id: versionId } },
              })
            : browserApi.POST("/api/v1/admin/billing/{kind}/{version_id}/publish", {
                params: { path: { kind, version_id: versionId } },
              }))}>
        {busy && <Spinner />}
        {t("configuration.publish")}
      </Button>
      {error && <span role="alert" className="text-xs text-destructive">{t("configuration.error", { message: error })}</span>}
    </span>
  );
}

function parse(text: string): { ok: true; value: unknown } | { ok: false } {
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch {
    return { ok: false };
  }
}

/** A new draft version of one kind. Structured values are JSON, validated by the API. */
export function ConfigDraftForm({
  kind,
  template,
  label,
}: {
  kind: ConfigKind | "eligibility";
  template: string;
  label: string;
}) {
  const { busy, error, run } = useCall();
  const [json, setJson] = useState(template);
  const [isTest, setIsTest] = useState(true);
  const [note, setNote] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [saved, setSaved] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    const parsed = parse(json);
    setInvalid(!parsed.ok);
    setSaved(false);
    if (!parsed.ok) return;
    const body = { ...(parsed.value as Record<string, unknown>), note };
    const result =
      kind === "eligibility"
        ? await run("save", () => browserApi.POST("/api/v1/admin/eligibility-checklists", { body: body as never }))
        : await run("save", () =>
            browserApi.POST(`/api/v1/admin/billing/${kind}` as "/api/v1/admin/billing/pricing-rules", {
              body: { ...body, is_test: isTest } as never,
            }),
          );
    setSaved(Boolean(result));
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <FormField id={`${kind}-json`} label={label} errors={invalid ? [t("configuration.invalidJson")] : undefined}>
        {(c) => <Textarea {...c} rows={8} className="font-mono text-xs" value={json} onChange={(e) => setJson(e.target.value)} />}
      </FormField>
      {kind !== "eligibility" && (
        <div className="flex items-center gap-3">
          <Checkbox id={`${kind}-test`} checked={isTest} onCheckedChange={(v) => setIsTest(v === true)} />
          <Label htmlFor={`${kind}-test`}>{t("configuration.isTest")}</Label>
        </div>
      )}
      <FormField id={`${kind}-note`} label={t("configuration.note")}>
        {(c) => <Input {...c} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />}
      </FormField>
      {error && <Notice tone="error" live="assertive">{t("configuration.error", { message: error })}</Notice>}
      {saved && <Notice tone="success" live="polite">{t("configuration.saved")}</Notice>}
      <Button type="submit" variant="outline" className="sm:self-start" disabled={busy !== null}>
        {busy && <Spinner />}
        {t("configuration.save")}
      </Button>
    </form>
  );
}

export function PricePreview({ versionId }: { versionId: string }) {
  const { busy, error, run } = useCall();
  const [json, setJson] = useState('{"built_up_area_sqft": 2000, "quality_tier": "STANDARD"}');
  const [price, setPrice] = useState<string | null>(null);
  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        const parsed = parse(json);
        if (!parsed.ok) return;
        void run("preview", () =>
          browserApi.POST("/api/v1/admin/billing/pricing-rules/{version_id}/preview", {
            params: { path: { version_id: versionId } },
            body: { characteristics: parsed.value as Record<string, unknown> },
          }),
        ).then((data) => setPrice(data ? (data as { price: string }).price : null));
      }}
    >
      <FormField id={`preview-${versionId}`} label={t("configuration.characteristics")}>
        {(c) => <Input {...c} className="font-mono text-xs" value={json} onChange={(e) => setJson(e.target.value)} />}
      </FormField>
      <Button type="submit" size="sm" variant="ghost" className="sm:self-start" disabled={busy !== null}>
        {t("configuration.preview")}
      </Button>
      {price && <span className="text-sm">{t("configuration.previewResult", { price })}</span>}
      {error && <span role="alert" className="text-xs text-destructive">{error}</span>}
    </form>
  );
}
