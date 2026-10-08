"use client";

// RFQ workflow controls (Slice 3.6): a functional pass, no visual polish. The homeowner requests
// quotes and selects one with a one-time code; a contractor answers an invitation, quotes every
// line and asks questions; operations upload a quote document received outside the portal. The
// API decides every rule; these controls send and show its answer.
import { CSRF_HEADERS } from "@p2b/contracts";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { FormField } from "@/components/plan2build/form-field";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Rfq");
const SELECT =
  "h-11 w-full rounded-md border border-input bg-background px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 sm:h-10";
const DECLINE_REASONS = [
  "UNAVAILABLE", "OUTSIDE_SERVICE_AREA", "SCOPE_MISMATCH", "SCHEDULE_MISMATCH", "COMPLIANCE",
  "ALREADY_ENGAGED", "OTHER",
] as const;

type Result = { ok: boolean; status: number; body: unknown };

async function call(method: string, url: string, body?: unknown, once = false): Promise<Result> {
  const headers: Record<string, string> = { ...CSRF_HEADERS, "Content-Type": "application/json" };
  if (once) headers["Idempotency-Key"] = crypto.randomUUID();
  try {
    const response = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    const text = await response.text();
    return { ok: response.ok, status: response.status, body: text ? JSON.parse(text) : null };
  } catch {
    return { ok: false, status: 0, body: null };
  }
}

function problem(result: Result): string {
  const error = (result.body as { error?: { message?: string; details?: Record<string, unknown>; code?: string } })?.error;
  if (!error) return t("error");
  const detail = error.details?.reason ?? error.details?.fields ?? error.code;
  return t("errorReason", { reason: `${error.message ?? ""} ${JSON.stringify(detail)}`.trim() });
}

function useCall() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run(method: string, url: string, body?: unknown, once = false): Promise<Result | null> {
    setBusy(true);
    setError(null);
    const result = await call(method, url, body, once);
    setBusy(false);
    if (!result.ok) {
      setError(problem(result));
      return null;
    }
    router.refresh();
    return result;
  }
  return { busy, error, run };
}

function ErrorNotice({ error }: { error: string | null }) {
  return error ? <Notice tone="error" live="assertive">{error}</Notice> : null;
}

// --- the homeowner -----------------------------------------------------------------------------

export function RequestQuotes({
  projectId,
  candidates,
  max,
  engaged,
}: {
  projectId: string;
  candidates: { id: string; name: string }[];
  max: number;
  engaged: boolean;
}) {
  const action = useCall();
  const [chosen, setChosen] = useState<string[]>([]);
  async function send(event: FormEvent) {
    event.preventDefault();
    await action.run("POST", `/api/v1/projects/${projectId}/rfqs`, { profile_ids: chosen }, true);
  }
  return (
    <form onSubmit={send} className="flex flex-col gap-3 rounded-md border border-border p-3">
      {!engaged && (
        <fieldset className="flex flex-col gap-1">
          <legend className="text-sm font-medium">{t("choose", { max })}</legend>
          {candidates.length === 0 && <p className="text-sm text-muted-foreground">{t("noCandidates")}</p>}
          {candidates.map((c) => (
            <label key={c.id} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={chosen.includes(c.id)}
                onChange={(e) => setChosen(e.target.checked ? [...chosen, c.id] : chosen.filter((x) => x !== c.id))} />
              {c.name}
            </label>
          ))}
        </fieldset>
      )}
      <ErrorNotice error={action.error} />
      <Button type="submit" className="self-start" disabled={action.busy || (!engaged && chosen.length === 0)}>
        {action.busy && <Spinner />}
        {t("request")}
      </Button>
    </form>
  );
}

export function SelectQuote({ projectId, rfqId, quoteVersionId }: { projectId: string; rfqId: string; quoteVersionId: string }) {
  const action = useCall();
  const [challenge, setChallenge] = useState<{ challenge_id: string; sent_to: string; statement_id: string; statement_text: string } | null>(null);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const base = `/api/v1/projects/${projectId}/rfqs/${rfqId}`;
  async function send() {
    const result = await action.run("POST", `${base}/selection-code`, { quote_version_id: quoteVersionId });
    if (result) setChallenge(result.body as typeof challenge);
  }
  async function confirm(event: FormEvent) {
    event.preventDefault();
    if (!challenge) return;
    await action.run("POST", `${base}/select`, {
      quote_version_id: quoteVersionId, challenge_id: challenge.challenge_id, code,
      statement_id: challenge.statement_id, contact_name: name, contact_phone: phone,
    }, true);
  }
  const id = quoteVersionId.slice(-8);
  return (
    <div className="flex flex-col gap-2">
      {challenge ? (
        <form onSubmit={confirm} className="flex flex-col gap-2">
          <p className="text-sm font-medium">{t("statement")}</p>
          <p className="text-sm">{challenge.statement_text}</p>
          <p role="status" className="text-sm">{t("codeSent", { email: challenge.sent_to })}</p>
          <FormField id={`name-${id}`} label={t("contactName")} required>
            {(c) => <Input {...c} value={name} onChange={(e) => setName(e.target.value)} />}
          </FormField>
          <FormField id={`phone-${id}`} label={t("contactPhone")} required>
            {(c) => <Input {...c} type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />}
          </FormField>
          <FormField id={`code-${id}`} label={t("code")} required>
            {(c) => <Input {...c} inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} />}
          </FormField>
          <Button type="submit" className="self-start" disabled={code.length !== 6 || !name.trim() || !phone.trim() || action.busy}>
            {action.busy && <Spinner />}
            {t("confirm")}
          </Button>
        </form>
      ) : (
        <Button type="button" variant="outline" className="self-start" onClick={() => void send()} disabled={action.busy}>
          {t("select")}
        </Button>
      )}
      <ErrorNotice error={action.error} />
    </div>
  );
}

export function DownloadLink({ url, label }: { url: string; label: string }) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  async function open() {
    setBusy(true);
    const result = await call("GET", url);
    setBusy(false);
    if (result.ok) window.location.assign((result.body as { url: string }).url);
    else setFailed(true);
  }
  return (
    <span className="inline-flex items-center gap-2">
      <Button type="button" size="sm" variant="outline" onClick={() => void open()} disabled={busy}>
        {busy && <Spinner />}
        {label}
      </Button>
      {failed && <span role="alert" className="text-xs text-destructive">{t("error")}</span>}
    </span>
  );
}

// --- the contractor ----------------------------------------------------------------------------

export function RespondToInvitation({ invitationId }: { invitationId: string }) {
  const action = useCall();
  const [phone, setPhone] = useState("");
  const [reason, setReason] = useState<string>("UNAVAILABLE");
  const [note, setNote] = useState("");
  const base = `/api/v1/pro/rfq-invitations/${invitationId}`;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 rounded-md border border-border p-3">
        <FormField id="accept-phone" label={t("phone")}>
          {(c) => <Input {...c} type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />}
        </FormField>
        <Button type="button" className="self-start" disabled={action.busy}
          onClick={() => void action.run("POST", `${base}/accept`, phone.trim() ? { phone } : {}, true)}>
          {t("accept")}
        </Button>
      </div>
      <div className="flex flex-col gap-2 rounded-md border border-border p-3">
        <FormField id="decline-reason" label={t("declineReason")} required>
          {(c) => (
            <select {...c} className={SELECT} value={reason} onChange={(e) => setReason(e.target.value)}>
              {DECLINE_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          )}
        </FormField>
        <FormField id="decline-note" label={t("note")}>
          {(c) => <Textarea {...c} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />}
        </FormField>
        <Button type="button" variant="outline" className="self-start" disabled={action.busy}
          onClick={() => void action.run("POST", `${base}/decline`, note.trim() ? { reason, note } : { reason }, true)}>
          {t("decline")}
        </Button>
      </div>
      <ErrorNotice error={action.error} />
    </div>
  );
}

type Line = { line_no: number; description: string; unit: string; quantity: string };

export function QuoteForm({ invitationId, lines }: { invitationId: string; lines: Line[] }) {
  const action = useCall();
  const today = new Date().toISOString().slice(0, 10);
  const [rates, setRates] = useState<Record<number, string>>({});
  const [excluded, setExcluded] = useState<Record<number, string | null>>({});
  const [validFrom, setValidFrom] = useState(today);
  const [validTo, setValidTo] = useState("");
  const [tax, setTax] = useState("EXCLUSIVE");
  const [duration, setDuration] = useState("");
  const [terms, setTerms] = useState("");
  const [warranty, setWarranty] = useState("");
  const [materials, setMaterials] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    const body = {
      lines: lines.map((l) =>
        excluded[l.line_no] != null
          ? { line_no: l.line_no, excluded: true, exclusion_reason: excluded[l.line_no] || "" }
          : { line_no: l.line_no, rate: rates[l.line_no] || null },
      ),
      valid_from: validFrom, valid_to: validTo, tax_treatment: tax, duration_days: Number(duration) || 0,
      ...(terms.trim() ? { payment_terms: terms } : {}),
      ...(warranty.trim() ? { warranty } : {}),
      ...(materials.trim() ? { materials } : {}),
    };
    await action.run("POST", `/api/v1/pro/rfq-invitations/${invitationId}/quotes`, body, true);
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-md border border-border p-3">
      <fieldset className="flex flex-col gap-3">
        <legend className="text-sm font-medium">{t("quantities")}</legend>
        {lines.map((l) => (
          <div key={l.line_no} className="flex flex-col gap-1 border-b border-border pb-2" data-line={l.line_no}>
            <p className="text-sm">{l.line_no}. {l.description} ({l.quantity} {l.unit})</p>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={excluded[l.line_no] != null}
                onChange={(e) => setExcluded({ ...excluded, [l.line_no]: e.target.checked ? "" : null })} />
              {t("exclude")}
            </label>
            {excluded[l.line_no] != null ? (
              <FormField id={`reason-${l.line_no}`} label={t("exclusionReason")} required>
                {(c) => <Input {...c} value={excluded[l.line_no] ?? ""} onChange={(e) => setExcluded({ ...excluded, [l.line_no]: e.target.value })} />}
              </FormField>
            ) : (
              <FormField id={`rate-${l.line_no}`} label={t("rate")} required>
                {(c) => <Input {...c} inputMode="decimal" value={rates[l.line_no] ?? ""} onChange={(e) => setRates({ ...rates, [l.line_no]: e.target.value })} />}
              </FormField>
            )}
          </div>
        ))}
      </fieldset>
      <FormField id="valid-from" label={t("validFrom")} required>
        {(c) => <Input {...c} type="date" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />}
      </FormField>
      <FormField id="valid-to" label={t("validTo")} required>
        {(c) => <Input {...c} type="date" value={validTo} onChange={(e) => setValidTo(e.target.value)} />}
      </FormField>
      <FormField id="tax" label={t("taxTreatment")} required>
        {(c) => (
          <select {...c} className={SELECT} value={tax} onChange={(e) => setTax(e.target.value)}>
            <option value="EXCLUSIVE">{t("exclusive")}</option>
            <option value="INCLUSIVE">{t("inclusive")}</option>
          </select>
        )}
      </FormField>
      <FormField id="duration" label={t("durationDays")} required>
        {(c) => <Input {...c} inputMode="numeric" value={duration} onChange={(e) => setDuration(e.target.value)} />}
      </FormField>
      <FormField id="terms" label={t("paymentTerms")}>
        {(c) => <Textarea {...c} rows={2} value={terms} onChange={(e) => setTerms(e.target.value)} />}
      </FormField>
      <FormField id="warranty" label={t("warranty")}>
        {(c) => <Textarea {...c} rows={2} value={warranty} onChange={(e) => setWarranty(e.target.value)} />}
      </FormField>
      <FormField id="materials" label={t("materials")}>
        {(c) => <Textarea {...c} rows={2} value={materials} onChange={(e) => setMaterials(e.target.value)} />}
      </FormField>
      <ErrorNotice error={action.error} />
      <Button type="submit" className="self-start" disabled={action.busy}>
        {action.busy && <Spinner />}
        {t("submit")}
      </Button>
    </form>
  );
}

export function TextAction({ id, label, field, url, extra }: { id: string; label: string; field: string; url: string; extra?: Record<string, unknown> }) {
  const action = useCall();
  const [value, setValue] = useState("");
  return (
    <div className="flex flex-col gap-2">
      <FormField id={id} label={label} required>
        {(c) => <Textarea {...c} rows={2} value={value} onChange={(e) => setValue(e.target.value)} />}
      </FormField>
      <Button type="button" variant="outline" className="self-start" disabled={!value.trim() || action.busy}
        onClick={async () => { if (await action.run("POST", url, { [field]: value, ...extra }, true)) setValue(""); }}>
        {t("send")}
      </Button>
      <ErrorNotice error={action.error} />
    </div>
  );
}

// --- operations --------------------------------------------------------------------------------

export function OpsUpload({ projectId }: { projectId: string }) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  async function upload(file: File) {
    setBusy(true);
    setFailed(false);
    const response = await fetch(
      `/api/v1/ops/projects/${projectId}/rfq-files?file_name=${encodeURIComponent(file.name)}`,
      { method: "POST", headers: { ...CSRF_HEADERS, "Content-Type": file.type, "Idempotency-Key": crypto.randomUUID() }, body: file },
    ).catch(() => null);
    setBusy(false);
    if (response?.ok) setDone(((await response.json()) as { file_id: string }).file_id);
    else setFailed(true);
  }
  return (
    <div className="flex flex-col gap-2">
      <FormField id="rfq-upload" label={t("upload")}>
        {(c) => <Input {...c} type="file" accept="application/pdf,image/jpeg,image/png" disabled={busy}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); }} />}
      </FormField>
      {done && <p role="status" className="font-mono text-xs" data-testid="uploaded-file">{t("uploaded", { id: done })}</p>}
      {failed && <Notice tone="error" live="assertive">{t("error")}</Notice>}
    </div>
  );
}

/** Operations create a DRAFT request for a project at the owner's direction (QD-03), nominating
 * listed contractors or none (they can be introduced on the RFQ afterwards). The API decides every
 * rule (OPEN_RFQ, NO_ACCEPTED_VERSION, NOT_NEEDED, ENGAGED, PACKAGE_REQUIRED) and says why. */
export function OpsRequestQuotes({ projectId, candidates }: { projectId: string; candidates: { id: string; name: string }[] }) {
  const router = useRouter();
  const action = useCall();
  const [chosen, setChosen] = useState<string[]>([]);
  async function send(event: FormEvent) {
    event.preventDefault();
    const result = await action.run("POST", `/api/v1/ops/projects/${projectId}/rfqs`, { profile_ids: chosen }, true);
    const id = (result?.body as { id?: string } | null)?.id;
    if (id) router.push(`/rfqs/${id}`);
  }
  return (
    <form onSubmit={send} className="flex flex-col gap-3 rounded-md border border-border p-3" data-testid="ops-request-quotes">
      <fieldset className="flex flex-col gap-1">
        <legend className="text-sm font-medium">{t("opsChoose")}</legend>
        {candidates.length === 0 && <p className="text-sm text-muted-foreground">{t("noCandidates")}</p>}
        {candidates.map((c) => (
          <label key={c.id} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={chosen.includes(c.id)}
              onChange={(e) => setChosen(e.target.checked ? [...chosen, c.id] : chosen.filter((x) => x !== c.id))} />
            {c.name}
          </label>
        ))}
      </fieldset>
      <p className="text-sm text-muted-foreground">{t("opsChooseHint")}</p>
      <ErrorNotice error={action.error} />
      <Button type="submit" className="self-start" disabled={action.busy}>
        {action.busy && <Spinner />}
        {t("opsCreate")}
      </Button>
    </form>
  );
}
