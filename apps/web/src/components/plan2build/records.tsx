"use client";

// Handover controls (Slice 3.7C): a functional pass, no visual polish. The owner acknowledges the
// handover with an emailed code against the statement shown, and can ask for a new code when one
// is used up; the contractor adds handover documents and warranties while the handover is open.
// Files are scanned first, so adding waits for the check and retries briefly. The API decides
// every rule.
import type { components } from "@p2b/contracts";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { call, postWhenChecked, problem, uploadEvidence } from "@/components/plan2build/execution";
import { FormField } from "@/components/plan2build/form-field";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { formatDateTime } from "@/lib/format";
import { acknowledgeNext } from "@/lib/handover";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Records");
const SELECT =
  "h-11 w-full rounded-md border border-input bg-background px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 sm:h-10";
const KINDS = ["WARRANTY", "MANUAL", "DRAWING", "CERTIFICATE", "PHOTO", "OTHER"] as const;

type Document = components["schemas"]["HandoverDocumentOut"];

type Challenge = components["schemas"]["p2b__records__schemas__ChallengeOut"];

export function AcknowledgeHandover({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // After a failure the API decides whether the same code can be typed again (lib/handover.ts).
  const [needsNewCode, setNeedsNewCode] = useState(false);
  const base = `/api/v1/projects/${projectId}/handover`;

  async function sendCode() {
    setBusy(true);
    setError(null);
    const result = await call("POST", `${base}/acknowledgement-code`);
    setBusy(false);
    if (result.ok) {
      setChallenge(result.body as Challenge);
      setCode("");
      setNeedsNewCode(false);
    } else {
      setError(problem(result));
      if (acknowledgeNext(result.status, result.body) === "refresh") router.refresh();
    }
  }
  async function acknowledge(event: FormEvent) {
    event.preventDefault();
    if (!challenge) return;
    setBusy(true);
    setError(null);
    const result = await call("POST", `${base}/acknowledge`, {
      challenge_id: challenge.challenge_id, code, statement_id: challenge.statement_id,
    }, true);
    setBusy(false);
    if (result.ok) {
      router.refresh();
      return;
    }
    setError(problem(result));
    const next = acknowledgeNext(result.status, result.body);
    if (next === "newCode") setNeedsNewCode(true);
    if (next === "refresh") router.refresh();
  }
  return (
    <div className="flex flex-col gap-3" data-testid="acknowledge">
      {!challenge && (
        <>
          <p className="text-sm text-muted-foreground">{t("acknowledgeHelp")}</p>
          <Button type="button" className="self-start" disabled={busy} onClick={() => void sendCode()}>
            {busy && <Spinner />}
            {t("sendCode")}
          </Button>
        </>
      )}
      {challenge && (
        <form onSubmit={acknowledge} className="flex flex-col gap-3">
          <p className="text-sm font-medium">{t("statementTitle", { version: challenge.statement_version })}</p>
          <blockquote className="border-l-2 border-border pl-3 text-sm whitespace-pre-wrap" data-testid="statement">
            {challenge.statement_text}
          </blockquote>
          <p role="status" className="text-sm">
            {t("codeSent", { to: challenge.sent_to })} {t("codeExpires", { when: formatDateTime(challenge.expires_at) })}
          </p>
          {!needsNewCode && (
            <>
              <FormField id="acknowledge-code" label={t("code")} required>
                {(f) => (
                  <Input {...f} inputMode="numeric" autoComplete="one-time-code" maxLength={10} value={code}
                    onChange={(e) => setCode(e.target.value.trim())} />
                )}
              </FormField>
              <Button type="submit" className="self-start" disabled={busy || code.length < 4}>
                {busy && <Spinner />}
                {t("acknowledge")}
              </Button>
            </>
          )}
          <Button type="button" variant={needsNewCode ? "default" : "outline"} className="self-start" disabled={busy}
            onClick={() => void sendCode()}>
            {t("newCode")}
          </Button>
        </form>
      )}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
    </div>
  );
}

export function HandoverDocumentForm({ engagementId }: { engagementId: string }) {
  const router = useRouter();
  const [kind, setKind] = useState<string>("MANUAL");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState(false);
  const base = `/api/v1/pro/engagements/${engagementId}/handover`;

  async function add(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setAdded(false);
    const fileId = await uploadEvidence(`${base}/uploads`, file, false);
    if (!fileId) {
      setBusy(false);
      setError(t("error"));
      return;
    }
    const result = await postWhenChecked(`${base}/documents`, { kind, title, file_id: fileId });
    setBusy(false);
    if (!result.ok) {
      setError(problem(result));
      return;
    }
    setAdded(true);
    setTitle("");
    setFile(null);
    router.refresh();
  }
  return (
    <form onSubmit={add} className="flex flex-col gap-2" data-testid="handover-document-form">
      <FormField id="handover-kind" label={t("kind")} required>
        {(f) => (
          <select {...f} className={SELECT} value={kind} onChange={(e) => setKind(e.target.value)}>
            {KINDS.map((k) => <option key={k} value={k}>{t(`kinds.${k}`)}</option>)}
          </select>
        )}
      </FormField>
      <FormField id="handover-title" label={t("title")} required>
        {(f) => <Input {...f} value={title} onChange={(e) => setTitle(e.target.value)} />}
      </FormField>
      <FormField id="handover-file" label={t("file")} required>
        {(f) => <Input {...f} type="file" accept="application/pdf,image/jpeg,image/png" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}
      </FormField>
      <Button type="submit" variant="outline" className="self-start" disabled={busy || !title.trim() || !file}>
        {busy && <Spinner />}
        {t("add")}
      </Button>
      {added && <Notice tone="success" live="polite">{t("added")}</Notice>}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
    </form>
  );
}

export function WarrantyForm({ engagementId, documents }: { engagementId: string; documents: Document[] }) {
  const router = useRouter();
  const warrantyDocs = documents.filter((d) => d.kind === "WARRANTY");
  // The document is chosen when submitting, so one added after this form rendered is offered.
  const [values, setValues] = useState({ item: "", term: "", expiry_date: "", installer: "", document_id: "" });
  const documentId = values.document_id || warrantyDocs[0]?.id || "";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (key: keyof typeof values, value: string) => setValues((v) => ({ ...v, [key]: value }));

  async function add(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const result = await call("POST", `/api/v1/pro/engagements/${engagementId}/handover/warranties`, {
      ...values, document_id: documentId || null,
    }, true);
    setBusy(false);
    if (result.ok) router.refresh();
    else setError(problem(result));
  }
  return (
    <form onSubmit={add} className="flex flex-col gap-2" data-testid="warranty-form">
      {(["item", "term", "installer"] as const).map((key) => (
        <FormField key={key} id={`warranty-${key}`} label={t(key)} required>
          {(f) => <Input {...f} value={values[key]} onChange={(e) => set(key, e.target.value)} />}
        </FormField>
      ))}
      <FormField id="warranty-expiry" label={t("expiry")} required>
        {(f) => <Input {...f} type="date" value={values.expiry_date} onChange={(e) => set("expiry_date", e.target.value)} />}
      </FormField>
      {warrantyDocs.length > 0 && (
        <FormField id="warranty-document" label={t("forDocument")}>
          {(f) => (
            <select {...f} className={SELECT} value={documentId} onChange={(e) => set("document_id", e.target.value)}>
              {warrantyDocs.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
            </select>
          )}
        </FormField>
      )}
      <Button type="submit" variant="outline" className="self-start" disabled={busy}>
        {busy && <Spinner />}
        {t("addWarranty")}
      </Button>
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
    </form>
  );
}
