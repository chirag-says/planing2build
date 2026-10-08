"use client";

// Handover controls (Slice 3.7C): a functional pass, no visual polish. The owner acknowledges the
// handover with an emailed code against the statement shown; the contractor adds handover
// documents and warranties while the handover is open. Files are scanned first, so adding waits
// for the check and retries briefly. The API decides every rule.
import type { components } from "@p2b/contracts";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { call, postWhenChecked, problem, uploadTo } from "@/components/plan2build/execution";
import { FormField } from "@/components/plan2build/form-field";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Records");
const SELECT =
  "h-11 w-full rounded-md border border-input bg-background px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 sm:h-10";
const KINDS = ["WARRANTY", "MANUAL", "DRAWING", "CERTIFICATE", "PHOTO", "OTHER"] as const;

type Document = components["schemas"]["HandoverDocumentOut"];

export function AcknowledgeHandover({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [challenge, setChallenge] = useState<{ challenge_id: string; sent_to: string; statement_id: string; statement_text: string } | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = `/api/v1/projects/${projectId}/handover`;

  async function sendCode() {
    setBusy(true);
    setError(null);
    const result = await call("POST", `${base}/acknowledgement-code`, undefined, true);
    setBusy(false);
    if (result.ok) setChallenge(result.body as typeof challenge);
    else setError(problem(result));
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
    if (result.ok) router.refresh();
    else setError(problem(result));
  }
  return (
    <div className="flex flex-col gap-3" data-testid="acknowledge">
      {!challenge && (
        <Button type="button" className="self-start" disabled={busy} onClick={() => void sendCode()}>
          {busy && <Spinner />}
          {t("sendCode")}
        </Button>
      )}
      {challenge && (
        <form onSubmit={acknowledge} className="flex flex-col gap-3">
          <blockquote className="border-l-2 border-border pl-3 text-sm" data-testid="statement">{challenge.statement_text}</blockquote>
          <p role="status" className="text-sm">{t("codeSent", { to: challenge.sent_to })}</p>
          <FormField id="acknowledge-code" label={t("code")} required>
            {(f) => <Input {...f} inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />}
          </FormField>
          <Button type="submit" className="self-start" disabled={busy || !code}>
            {busy && <Spinner />}
            {t("acknowledge")}
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
  // A new key clears the file input after a document is added.
  const [inputKey, setInputKey] = useState(0);
  const base = `/api/v1/pro/engagements/${engagementId}/handover`;

  async function add(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setAdded(false);
    const uploaded = await uploadTo(`${base}/uploads`, file, false);
    if (!uploaded.ok) {
      setBusy(false);
      setError(uploaded.result ? problem(uploaded.result) : t("error"));
      return;
    }
    const result = await postWhenChecked(`${base}/documents`, { kind, title: title.trim(), file_id: uploaded.fileId });
    setBusy(false);
    if (!result.ok) {
      setError(problem(result));
      return;
    }
    setAdded(true);
    setTitle("");
    setFile(null);
    setInputKey((k) => k + 1);
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
        {(f) => <Input {...f} maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />}
      </FormField>
      <FormField id="handover-file" label={t("file")} required>
        {(f) => <Input key={inputKey} {...f} type="file" accept="application/pdf,image/jpeg,image/png" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}
      </FormField>
      <Button type="submit" variant="outline" className="self-start" disabled={busy || !title.trim() || !file}>
        {busy && <Spinner />}
        {t("add")}
      </Button>
      {busy && <p role="status" className="text-sm text-muted-foreground">{t("checking")}</p>}
      {added && <Notice tone="success" live="polite">{t("added")}</Notice>}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
    </form>
  );
}

const NO_DOCUMENT = "none";
const EMPTY_WARRANTY = { item: "", term: "", expiry_date: "", installer: "", document_id: "" };
const WARRANTY_MAX = { item: 200, term: 120, installer: 200 } as const;

export function WarrantyForm({ engagementId, documents }: { engagementId: string; documents: Document[] }) {
  const router = useRouter();
  const warrantyDocs = documents.filter((d) => d.kind === "WARRANTY");
  // The document is chosen when submitting, so one added after this form rendered is offered.
  const [values, setValues] = useState(EMPTY_WARRANTY);
  const documentId = values.document_id || warrantyDocs[0]?.id || "";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState(false);
  const set = (key: keyof typeof values, value: string) => setValues((v) => ({ ...v, [key]: value }));
  const complete = Boolean(values.item.trim() && values.term.trim() && values.installer.trim() && values.expiry_date);

  async function add(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setAdded(false);
    const result = await call("POST", `/api/v1/pro/engagements/${engagementId}/handover/warranties`, {
      item: values.item.trim(), term: values.term.trim(), installer: values.installer.trim(),
      expiry_date: values.expiry_date, document_id: documentId && documentId !== NO_DOCUMENT ? documentId : null,
    }, true);
    setBusy(false);
    if (!result.ok) {
      setError(problem(result));
      return;
    }
    setAdded(true);
    setValues(EMPTY_WARRANTY);
    router.refresh();
  }
  return (
    <form onSubmit={add} className="flex flex-col gap-2" data-testid="warranty-form">
      {(["item", "term", "installer"] as const).map((key) => (
        <FormField key={key} id={`warranty-${key}`} label={t(key)} required>
          {(f) => <Input {...f} maxLength={WARRANTY_MAX[key]} value={values[key]} onChange={(e) => set(key, e.target.value)} />}
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
              <option value={NO_DOCUMENT}>{t("noDocumentLink")}</option>
            </select>
          )}
        </FormField>
      )}
      <Button type="submit" variant="outline" className="self-start" disabled={busy || !complete}>
        {busy && <Spinner />}
        {t("addWarranty")}
      </Button>
      {added && <Notice tone="success" live="polite">{t("warrantyAdded")}</Notice>}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
    </form>
  );
}
