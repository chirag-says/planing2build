"use client";

// Buying the package or an AI credit, and following an order (Slice 3.3; SLICE3_3_READINESS J).
// Every amount on these screens is the server's: the page sends versions and choices, never a
// price. Payment opens the provider's checkout (Razorpay), or in local development the fake
// gateway's test panel. Its callback is only a hint: the page tells the server, which verifies
// with the provider, and the page waits for the order to change.
import type { components } from "@p2b/contracts";
import { CreditCardIcon, DownloadIcon, ReceiptIcon, RotateCcwIcon, XIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { ConfirmationDialog } from "@/components/plan2build/confirmation-dialog";
import { ChoiceGroup, FormField, FormFieldset } from "@/components/plan2build/form-field";
import { Notice } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { browserApi, errorCode } from "@/lib/api/browser";
import { formatDate, formatRupees } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

type Offer = components["schemas"]["OfferOut"];
type Order = components["schemas"]["OrderOut"];
type Due = components["schemas"]["DueOut"];
type Mode = components["schemas"]["PaymentMode"];

const t = getTranslator("Billing");
const POLL_MS = 2000;
const POLL_LIMIT = 60;

const SELECT =
  "h-11 w-full rounded-md border border-input bg-background px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 sm:h-10";

function money(amount: string): string {
  return t("money", { amount: formatRupees(amount) });
}

/** The server's price for one payment mode, with tax lines and the instalments. */
export function PriceBreakdown({ offer, mode }: { offer: Offer; mode: Mode }) {
  const dues = offer.dues[mode] ?? [];
  const inputs = Object.entries(offer.pricing_inputs)
    .map(([name, value]) =>
      t(`package.inputs.${name as "floors"}`, { value: String(value) }),
    )
    .join(", ");
  return (
    <div className="flex flex-col gap-3">
      {offer.is_test && <Notice tone="warning">{t("testValues")}</Notice>}
      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
        <dt>{t("package.taxable")}</dt>
        <dd className="text-right tabular-nums">{money(offer.taxable_total)}</dd>
        {offer.tax.map((line) => (
          <div key={line.component} className="contents">
            <dt>{t("package.tax", { component: line.component, rate: line.rate })}</dt>
            <dd className="text-right tabular-nums">{money(line.amount)}</dd>
          </div>
        ))}
        <dt className="font-semibold">{t("package.total")}</dt>
        <dd className="text-right font-semibold tabular-nums">{money(offer.total)}</dd>
      </dl>
      {inputs && <p className="text-xs text-muted-foreground">{t("package.basedOn", { inputs })}</p>}
      {dues.length > 1 && (
        <ul className="flex flex-col gap-1 text-sm">
          {dues.map((due) => (
            <li key={due.sequence}>
              {t("package.instalment", { sequence: due.sequence, amount: formatRupees(due.amount) })}
              {", "}
              {due.due_days
                ? t("package.dueAfter", { days: due.due_days })
                : t("package.dueOnOrder")}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

type Buyer = { name: string; address: string; state_code: string; gstin: string };

function BuyerFields({
  buyer,
  onChange,
  states,
}: {
  buyer: Buyer;
  onChange: (buyer: Buyer) => void;
  states: Record<string, string>;
}) {
  return (
    <fieldset className="flex flex-col gap-4">
      <legend className="mb-2 font-heading text-base font-medium">{t("package.buyer")}</legend>
      <FormField id="buyer-name" label={t("package.name")} required>
        {(c) => (
          <Input {...c} autoComplete="name" maxLength={120} value={buyer.name}
            onChange={(e) => onChange({ ...buyer, name: e.target.value })} />
        )}
      </FormField>
      <FormField id="buyer-address" label={t("package.address")} required>
        {(c) => (
          <Textarea {...c} rows={2} autoComplete="street-address" maxLength={500} value={buyer.address}
            onChange={(e) => onChange({ ...buyer, address: e.target.value })} />
        )}
      </FormField>
      <FormField id="buyer-state" label={t("package.state")} required>
        {(c) => (
          <select {...c} className={SELECT} value={buyer.state_code}
            onChange={(e) => onChange({ ...buyer, state_code: e.target.value })}>
            <option value="">{t("package.chooseState")}</option>
            {Object.entries(states).map(([code, name]) => (
              <option key={code} value={code}>{name}</option>
            ))}
          </select>
        )}
      </FormField>
      <FormField id="buyer-gstin" label={t("package.gstin")}>
        {(c) => (
          <Input {...c} maxLength={15} value={buyer.gstin}
            onChange={(e) => onChange({ ...buyer, gstin: e.target.value.toUpperCase() })} />
        )}
      </FormField>
    </fieldset>
  );
}

function useOrderForm() {
  const [buyer, setBuyer] = useState<Buyer>({ name: "", address: "", state_code: "", gstin: "" });
  const [terms, setTerms] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = useRef(crypto.randomUUID());
  const complete = buyer.name.trim() && buyer.address.trim() && buyer.state_code && terms;
  /** The key for this submission; a failed one gets a fresh key, a retry of the same reuses it. */
  const currentKey = () => key.current;
  const renewKey = () => {
    key.current = crypto.randomUUID();
  };
  return { buyer, setBuyer, terms, setTerms, busy, setBusy, error, setError, currentKey, renewKey, complete };
}

function orderError(failure: unknown): string {
  const code = errorCode(failure);
  const details = (failure as { error?: { details?: Record<string, unknown> } })?.error?.details;
  if (code === "STATE_CONFLICT" && details?.offering_version) return t("package.errors.changed");
  if (code === "STATE_CONFLICT" && details?.open_order_id) return t("package.errors.open");
  return t("package.errors.default");
}

function TermsField({
  version,
  checked,
  onChange,
}: {
  version: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-start gap-3">
      <Checkbox id="accept-terms" checked={checked} onCheckedChange={(v) => onChange(v === true)} />
      <Label htmlFor="accept-terms" className="font-normal leading-snug">
        {t("package.terms", { version })}
      </Label>
    </div>
  );
}

export function PackagePurchase({
  projectId,
  offer,
  states,
}: {
  projectId: string;
  offer: Offer;
  states: Record<string, string>;
}) {
  const router = useRouter();
  const form = useOrderForm();
  const [mode, setMode] = useState<Mode>(offer.payment_modes[0] ?? "FULL");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.complete) return;
    form.setBusy(true);
    form.setError(null);
    try {
      const { data, error } = await browserApi.POST("/api/v1/projects/{project_id}/package/orders", {
        params: { path: { project_id: projectId }, header: { "Idempotency-Key": form.currentKey() } },
        body: {
          offering_version_id: offer.offering_version_id,
          payment_mode: mode,
          buyer: form.buyer,
          accept_terms_version: offer.terms_version,
        },
      });
      if (data) {
        router.push(`/projects/${projectId}/package/orders/${data.order_id}`);
        return;
      }
      form.renewKey();
      form.setError(orderError(error));
      if (errorCode(error) === "STATE_CONFLICT") router.refresh();
    } catch {
      form.setError(t("package.errors.default"));
    } finally {
      form.setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-6">
      {offer.payment_modes.length > 1 && (
        <FormFieldset id="payment-mode" legend={t("package.mode")} required>
          {({ legendId }) => (
            <ChoiceGroup
              id="payment-mode"
              labelledBy={legendId}
              value={mode}
              onValueChange={(value) => setMode(value as Mode)}
              options={offer.payment_modes.map((m) => ({ value: m, label: t(`package.modes.${m}`) }))}
            />
          )}
        </FormFieldset>
      )}
      <PriceBreakdown offer={offer} mode={mode} />
      <BuyerFields buyer={form.buyer} onChange={form.setBuyer} states={states} />
      <TermsField version={offer.terms_version} checked={form.terms} onChange={form.setTerms} />
      {form.error && <Notice tone="error" live="assertive">{form.error}</Notice>}
      <Button type="submit" size="lg" className="sm:self-start" disabled={!form.complete || form.busy}>
        {form.busy ? <Spinner /> : <CreditCardIcon aria-hidden="true" />}
        {form.busy ? t("package.working") : t("package.continue")}
      </Button>
    </form>
  );
}

export function CreditPurchase({
  offer,
  states,
  projectId,
}: {
  offer: Offer;
  states: Record<string, string>;
  projectId: string | null;
}) {
  const router = useRouter();
  const form = useOrderForm();

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.complete) return;
    form.setBusy(true);
    form.setError(null);
    try {
      const { data, error } = await browserApi.POST("/api/v1/ai-credits/orders", {
        params: { header: { "Idempotency-Key": form.currentKey() } },
        body: {
          offering_version_id: offer.offering_version_id,
          buyer: form.buyer,
          accept_terms_version: offer.terms_version,
        },
      });
      if (data) {
        const back = projectId ? `?project=${projectId}` : "";
        router.push(`/account/orders/${data.order_id}${back}`);
        return;
      }
      form.renewKey();
      form.setError(orderError(error));
    } catch {
      form.setError(t("package.errors.default"));
    } finally {
      form.setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-6">
      <PriceBreakdown offer={offer} mode="FULL" />
      <BuyerFields buyer={form.buyer} onChange={form.setBuyer} states={states} />
      <TermsField version={offer.terms_version} checked={form.terms} onChange={form.setTerms} />
      {form.error && <Notice tone="error" live="assertive">{form.error}</Notice>}
      <Button type="submit" size="lg" className="sm:self-start" disabled={!form.complete || form.busy}>
        {form.busy ? <Spinner /> : <CreditCardIcon aria-hidden="true" />}
        {form.busy ? t("package.working") : t("credits.buy")}
      </Button>
    </form>
  );
}

// --- checkout ----------------------------------------------------------------------------

type Ticket = components["schemas"]["CheckoutOut"];

type RazorpayResponse = {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
};

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

function loadRazorpay(): Promise<boolean> {
  if (window.Razorpay) return Promise.resolve(true);
  return new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

async function returned(attemptId: string, ids: RazorpayResponse): Promise<boolean> {
  const { data } = await browserApi.POST("/api/v1/payment-attempts/{attempt_id}/confirm", {
    params: { path: { attempt_id: attemptId } },
    body: {
      provider_order_id: ids.razorpay_order_id,
      provider_payment_id: ids.razorpay_payment_id,
      signature: ids.razorpay_signature,
    },
  });
  return Boolean(data);
}

function FakeCheckout({
  ticket,
  onClose,
  onReturned,
}: {
  ticket: Ticket;
  onClose: () => void;
  onReturned: () => void;
}) {
  const [busy, setBusy] = useState(false);
  async function act(outcome: "capture" | "fail") {
    setBusy(true);
    try {
      const { data } = await browserApi.POST("/api/v1/dev/fake-gateway/attempts/{attempt_id}/pay", {
        params: { path: { attempt_id: ticket.attempt_id } },
        body: { outcome },
      });
      if (data?.signature) {
        await returned(ticket.attempt_id, {
          razorpay_order_id: data.provider_order_id,
          razorpay_payment_id: data.provider_payment_id,
          razorpay_signature: data.signature,
        });
      }
      onReturned();
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{t("fake.title")}</DialogTitle>
          <DialogDescription>{t("fake.body")}</DialogDescription>
        </DialogHeader>
        <p className="text-sm font-medium tabular-nums">
          {money(String(ticket.amount_paise / 100))} · {ticket.order_code}
        </p>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            {t("fake.close")}
          </Button>
          <Button type="button" variant="destructive" onClick={() => void act("fail")} disabled={busy}>
            {t("fake.fail")}
          </Button>
          <Button type="button" onClick={() => void act("capture")} disabled={busy}>
            {busy && <Spinner />}
            {t("fake.pay")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PayButton({ due, onStarted }: { due: Due; onStarted: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fake, setFake] = useState<Ticket | null>(null);
  const o = (key: "errors.default" | "errors.provider" | "errors.rate") => t(`order.${key}`);

  async function pay() {
    setBusy(true);
    setError(null);
    try {
      const { data: ticket, error: failure } = await browserApi.POST(
        "/api/v1/payment-dues/{due_id}/checkout",
        { params: { path: { due_id: due.due_id } } },
      );
      if (!ticket) {
        const code = errorCode(failure);
        setError(
          code === "PROVIDER_UNAVAILABLE"
            ? o("errors.provider")
            : code === "RATE_LIMITED"
              ? o("errors.rate")
              : o("errors.default"),
        );
        return;
      }
      if (ticket.provider === "fake") {
        setFake(ticket);
        return;
      }
      if (!(await loadRazorpay()) || !window.Razorpay) {
        setError(o("errors.provider"));
        return;
      }
      new window.Razorpay({
        key: ticket.key_id,
        amount: ticket.amount_paise,
        currency: ticket.currency,
        name: "Plan2Build",
        description: ticket.description,
        order_id: ticket.provider_order_id,
        handler: (response: RazorpayResponse) => {
          void returned(ticket.attempt_id, response).then(onStarted);
        },
      }).open();
    } catch {
      setError(o("errors.default"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <Button type="button" onClick={() => void pay()} disabled={busy} className="sm:self-start">
        {busy ? <Spinner /> : <CreditCardIcon aria-hidden="true" />}
        {busy ? t("order.paying") : t("order.pay", { amount: formatRupees(due.amount) })}
      </Button>
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
      {fake && (
        <FakeCheckout
          ticket={fake}
          onClose={() => setFake(null)}
          onReturned={() => {
            setFake(null);
            onStarted();
          }}
        />
      )}
    </div>
  );
}

// --- the order ---------------------------------------------------------------------------

type Started = { paid: number; attemptId: string | null };

/** The wait after paying ends when the order shows one more paid due, or a newer attempt than
 * the one shown when paying started has failed or expired. */
function settled(order: Order, started: Started): boolean {
  const paid = order.dues.filter((d) => d.state === "PAID").length;
  const latest = order.attempts[0];
  const newer = latest && latest.attempt_id !== started.attemptId;
  return paid > started.paid || Boolean(newer && (latest.state === "FAILED" || latest.state === "EXPIRED"));
}

export function OrderView({ order }: { order: Order }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState<Started | null>(null);
  const [polls, setPolls] = useState(0);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [refundOpen, setRefundOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pendingDocuments = order.invoices.some((i) => !i.document_ready);
  // Derived, not stored: the wait ends when the order shows a new payment or a failed attempt.
  const isConfirming = confirming !== null && !settled(order, confirming);
  const waiting = isConfirming || pendingDocuments;

  useEffect(() => {
    if (!waiting || polls >= POLL_LIMIT) return;
    const timer = setTimeout(() => {
      router.refresh();
      setPolls((count) => count + 1);
    }, POLL_MS);
    return () => clearTimeout(timer);
  }, [waiting, polls, router]);

  async function act(name: string, call: () => Promise<{ data?: unknown }>): Promise<boolean> {
    setBusy(name);
    setError(null);
    try {
      const { data } = await call();
      if (data) {
        router.refresh();
        return true;
      }
      setError(t("order.errors.default"));
    } catch {
      setError(t("order.errors.default"));
    } finally {
      setBusy(null);
    }
    return false;
  }

  async function download(invoiceId: string) {
    const { data } = await browserApi.GET("/api/v1/invoices/{invoice_id}/document", {
      params: { path: { invoice_id: invoiceId } },
    });
    if (data) window.location.assign(data.url);
    else setError(t("order.errors.default"));
  }

  const lastAttempt = order.attempts[0];
  const paidCount = order.dues.filter((d) => d.state === "PAID").length;

  return (
    <div className="flex flex-col gap-6">
      {order.is_test && <Notice tone="warning">{t("testValues")}</Notice>}
      {isConfirming && (
        <Notice tone="info" live="polite">
          <span className="flex items-center gap-2">
            <Spinner />
            {t("order.confirming")}
          </span>
        </Notice>
      )}
      {!isConfirming && lastAttempt?.state === "FAILED" && order.state === "AWAITING_PAYMENT" && (
        <Notice tone="warning">{t("order.failed")}</Notice>
      )}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}

      <Card size="sm">
        <CardHeader>
          <CardTitle className="text-base"><h2>{t("order.summary")}</h2></CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm">
          <p className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{order.offering_name}</span>
            <StatusBadge kind="order" status={order.state} withLabel />
          </p>
          <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
            <dt>{t("package.taxable")}</dt>
            <dd className="text-right tabular-nums">{money(order.taxable_total)}</dd>
            {order.tax.map((line) => (
              <div key={line.component} className="contents">
                <dt>{t("package.tax", { component: line.component, rate: line.rate })}</dt>
                <dd className="text-right tabular-nums">{money(line.amount)}</dd>
              </div>
            ))}
            <dt className="font-semibold">{t("package.total")}</dt>
            <dd className="text-right font-semibold tabular-nums">{money(order.total)}</dd>
          </dl>
        </CardContent>
      </Card>

      <section aria-labelledby="dues" className="flex flex-col gap-3">
        <h2 id="dues" className="font-heading text-lg font-medium">{t("order.dues")}</h2>
        <ul className="flex flex-col gap-3">
          {order.dues.map((due) => (
            <li key={due.due_id} className="flex flex-col gap-2 rounded-md border border-border p-3">
              <span className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">
                  {t("order.due", { sequence: due.sequence })}: {money(due.amount)}
                </span>
                <StatusBadge kind="due" status={due.state} />
              </span>
              <span className="text-sm text-muted-foreground">
                {due.state === "PAID" && due.paid_at
                  ? t("order.paidNote", { date: formatDate(due.paid_at) })
                  : due.due_at
                    ? t("order.dueWhen", { date: formatDate(due.due_at) })
                    : due.due_days
                      ? t("order.dueLater", { days: due.due_days })
                      : null}
              </span>
              {due.payable && !isConfirming && (
                <PayButton
                  due={due}
                  onStarted={() => {
                    setPolls(0);
                    setConfirming({ paid: paidCount, attemptId: lastAttempt?.attempt_id ?? null });
                  }}
                />
              )}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="invoices" className="flex flex-col gap-3">
        <h2 id="invoices" className="font-heading text-lg font-medium">{t("order.invoices")}</h2>
        {order.invoices.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("order.noInvoices")}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {order.invoices.map((invoice) => (
              <li key={invoice.invoice_id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="flex items-center gap-2">
                  <ReceiptIcon aria-hidden="true" className="size-4 text-muted-foreground" />
                  {t(`order.invoiceKinds.${invoice.kind}`)} {invoice.code} · {money(invoice.total)}
                </span>
                {invoice.document_ready ? (
                  <Button type="button" size="sm" variant="outline"
                    onClick={() => void download(invoice.invoice_id)}>
                    <DownloadIcon aria-hidden="true" />
                    {t("order.download", { code: invoice.code })}
                  </Button>
                ) : (
                  <span className="flex items-center gap-2 text-muted-foreground">
                    <Spinner />
                    {t("order.preparing", { code: invoice.code })}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {order.refund_requests.length > 0 && (
        <section aria-labelledby="refunds" className="flex flex-col gap-3">
          <h2 id="refunds" className="font-heading text-lg font-medium">{t("order.refunds")}</h2>
          <ul className="flex flex-col gap-2 text-sm">
            {order.refund_requests.map((request) => (
              <li key={request.request_id} className="flex flex-col gap-1 rounded-md border border-border p-3">
                <span className="flex flex-wrap items-center gap-2">
                  <StatusBadge kind="refund" status={request.state} />
                  <span className="text-muted-foreground">{formatDate(request.created_at)}</span>
                </span>
                <span>{request.reason}</span>
                {request.decision?.amount && (
                  <span>{t("order.refundAmount", { amount: formatRupees(request.decision.amount) })}</span>
                )}
                {request.decision && (
                  <span className="text-muted-foreground">
                    {t("order.refundDecision", { reason: request.decision.reason })}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="flex flex-wrap gap-2">
        {order.can_cancel && !isConfirming && (
          <Button type="button" variant="outline" onClick={() => setCancelOpen(true)} disabled={busy !== null}>
            <XIcon aria-hidden="true" />
            {t("order.cancel")}
          </Button>
        )}
        {order.can_request_refund && (
          <Button type="button" variant="outline" onClick={() => setRefundOpen(true)} disabled={busy !== null}>
            <RotateCcwIcon aria-hidden="true" />
            {t("order.refund")}
          </Button>
        )}
      </div>

      <ConfirmationDialog
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        title={t("order.cancelTitle")}
        description={t("order.cancelBody")}
        confirmLabel={t("order.cancel")}
        cancelLabel={t("order.keep")}
        onConfirm={() =>
          void act("cancel", () =>
            browserApi.POST("/api/v1/orders/{order_id}/cancel", {
              params: { path: { order_id: order.order_id }, header: { "Idempotency-Key": crypto.randomUUID() } },
            }),
          )
        }
      />
      <Dialog open={refundOpen} onOpenChange={setRefundOpen}>
        <DialogContent showCloseButton={false}>
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (!reason.trim()) return;
              void act("refund", () =>
                browserApi.POST("/api/v1/orders/{order_id}/refund-requests", {
                  params: { path: { order_id: order.order_id }, header: { "Idempotency-Key": crypto.randomUUID() } },
                  body: { reason: reason.trim() },
                }),
              ).then((ok) => {
                if (ok) {
                  setRefundOpen(false);
                  setReason("");
                }
              });
            }}
          >
            <DialogHeader>
              <DialogTitle>{t("order.refundTitle")}</DialogTitle>
              <DialogDescription>{t("order.refundHelp")}</DialogDescription>
            </DialogHeader>
            <FormField id="refund-reason" label={t("order.refundReason")} required>
              {(c) => (
                <Textarea {...c} rows={3} maxLength={2000} value={reason}
                  onChange={(e) => setReason(e.target.value)} />
              )}
            </FormField>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setRefundOpen(false)}>
                {t("order.back")}
              </Button>
              <Button type="submit" disabled={!reason.trim() || busy !== null}>
                {busy === "refund" && <Spinner />}
                {t("order.refundSend")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function OrderBadge({ kind }: { kind: "PACKAGE" | "AI_CREDIT" }) {
  return <Badge variant="neutral">{t(`account.kinds.${kind}`)}</Badge>;
}

export function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className="text-sm font-medium underline underline-offset-4">
      {label}
    </Link>
  );
}
