"use client";

// Handover controls (Slice 3.7C): a functional pass, no visual polish. The owner acknowledges the
// handover with an emailed code against the statement shown, and can ask for a new code when one
// is used up; the contractor adds handover documents and warranties while the handover is open.
// Files are scanned first, so adding waits for the check and retries briefly. The API decides
// every rule.
import type { components } from "@p2b/contracts";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { call, postWhenChecked, problem, uploadOpsFile, uploadTo } from "@/components/plan2build/execution";
import { FormField } from "@/components/plan2build/form-field";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
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
  const base = `/api/v1/pro/engagements/${engagementId}/handover`;
  return (
    <DocumentForm
      idPrefix="handover"
      documentsUrl={`${base}/documents`}
      upload={async (file) => {
        const uploaded = await uploadTo(`${base}/uploads`, file, false);
        return uploaded.ok ? { fileId: uploaded.fileId } : { error: uploaded.result ? problem(uploaded.result) : t("error") };
      }}
    />
  );
}

/** Operations add a document received outside the portal: the raw upload, then the document. */
export function OpsHandoverDocumentForm({ projectId }: { projectId: string }) {
  return (
    <DocumentForm
      idPrefix="ops-handover"
      documentsUrl={`/api/v1/ops/projects/${projectId}/handover/documents`}
      upload={async (file) => {
        const fileId = await uploadOpsFile(`/api/v1/ops/projects/${projectId}/handover-files`, file);
        return fileId ? { fileId } : { error: t("error") };
      }}
    />
  );
}

type UploadOutcome = { fileId: string } | { error: string };

function DocumentForm({
  idPrefix,
  documentsUrl,
  upload,
}: {
  idPrefix: string;
  documentsUrl: string;
  upload: (file: File) => Promise<UploadOutcome>;
}) {
  const router = useRouter();
  const [kind, setKind] = useState<string>("MANUAL");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState(false);
  // A new key clears the file input after a document is added.
  const [inputKey, setInputKey] = useState(0);

  async function add(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setAdded(false);
    const uploaded = await upload(file);
    if ("error" in uploaded) {
      setBusy(false);
      setError(uploaded.error);
      return;
    }
    const result = await postWhenChecked(documentsUrl, { kind, title: title.trim(), file_id: uploaded.fileId });
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
    <form onSubmit={add} className="flex flex-col gap-2" data-testid={`${idPrefix}-document-form`}>
      <FormField id={`${idPrefix}-kind`} label={t("kind")} required>
        {(f) => (
          <select {...f} className={SELECT} value={kind} onChange={(e) => setKind(e.target.value)}>
            {KINDS.map((k) => <option key={k} value={k}>{t(`kinds.${k}`)}</option>)}
          </select>
        )}
      </FormField>
      <FormField id={`${idPrefix}-title`} label={t("title")} required>
        {(f) => <Input {...f} maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />}
      </FormField>
      <FormField id={`${idPrefix}-file`} label={t("file")} required>
        {(f) => (
          <Input key={inputKey} {...f} type="file" accept="application/pdf,image/jpeg,image/png"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        )}
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
  return (
    <WarrantyFields idPrefix="warranty" url={`/api/v1/pro/engagements/${engagementId}/handover/warranties`} documents={documents} />
  );
}

export function OpsWarrantyForm({ projectId, documents }: { projectId: string; documents: Document[] }) {
  return (
    <WarrantyFields idPrefix="ops-warranty" url={`/api/v1/ops/projects/${projectId}/handover/warranties`} documents={documents} />
  );
}

function WarrantyFields({ idPrefix, url, documents }: { idPrefix: string; url: string; documents: Document[] }) {
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
    const result = await call("POST", url, {
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
    <form onSubmit={add} className="flex flex-col gap-2" data-testid={`${idPrefix}-form`}>
      {(["item", "term", "installer"] as const).map((key) => (
        <FormField key={key} id={`${idPrefix}-${key}`} label={t(key)} required>
          {(f) => <Input {...f} maxLength={WARRANTY_MAX[key]} value={values[key]} onChange={(e) => set(key, e.target.value)} />}
        </FormField>
      ))}
      <FormField id={`${idPrefix}-expiry`} label={t("expiry")} required>
        {(f) => <Input {...f} type="date" value={values.expiry_date} onChange={(e) => set("expiry_date", e.target.value)} />}
      </FormField>
      {warrantyDocs.length > 0 && (
        <FormField id={`${idPrefix}-document`} label={t("forDocument")}>
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

// --- operations --------------------------------------------------------------------------------

/** Assemble the Build Record draft from the records. A new version after an issued one corrects
 * it, so the reason is asked for then (409 REASON_REQUIRED otherwise). */
export function AssembleBuildRecord({ projectId, mode }: { projectId: string; mode: "first" | "reassemble" | "correction" }) {
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const correction = mode === "correction";

  async function assemble(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setDone(false);
    const result = await call("POST", `/api/v1/ops/projects/${projectId}/build-record/assemble`, {
      reason: correction ? reason.trim() : null,
    }, true);
    setBusy(false);
    if (!result.ok) {
      setError(problem(result));
      return;
    }
    setDone(true);
    setReason("");
    router.refresh();
  }
  return (
    <form onSubmit={assemble} className="flex flex-col gap-2" data-testid="assemble-build-record">
      <p className="text-sm text-muted-foreground">{t(`ops.assembleModes.${mode}`)}</p>
      {correction && (
        <FormField id="assemble-reason" label={t("ops.correctionReason")} required>
          {(f) => <Input {...f} maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} />}
        </FormField>
      )}
      <Button type="submit" variant="outline" className="self-start" disabled={busy || (correction && !reason.trim())}>
        {busy && <Spinner />}
        {mode === "reassemble" ? t("ops.reassemble") : t("ops.assemble")}
      </Button>
      {done && <Notice tone="success" live="polite">{t("ops.assembled")}</Notice>}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
    </form>
  );
}

type RecordSnapshot = components["schemas"]["BuildRecordSnapshotOut"];

/** One Build Record version as recorded (GET /ops/build-records/{id}): hashes and the snapshot. */
export function BuildRecordSnapshot({ recordId }: { recordId: string }) {
  const [record, setRecord] = useState<RecordSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (record) {
      setRecord(null);
      return;
    }
    setBusy(true);
    setError(null);
    const result = await call("GET", `/api/v1/ops/build-records/${recordId}`);
    setBusy(false);
    if (result.ok) setRecord(result.body as RecordSnapshot);
    else setError(problem(result));
  }
  return (
    <div className="flex flex-col gap-2">
      <Button type="button" variant="ghost" size="sm" className="self-start" disabled={busy} aria-expanded={Boolean(record)}
        onClick={() => void load()}>
        {busy && <Spinner />}
        {record ? t("ops.hideSnapshot") : t("ops.showSnapshot")}
      </Button>
      {busy && <p role="status" className="text-sm text-muted-foreground">{t("ops.loading")}</p>}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
      {record && (
        <div className="flex flex-col gap-1 text-xs" data-testid="build-record-snapshot">
          {record.json_sha256 && <span className="font-mono break-all">{t("ops.jsonHash", { hash: record.json_sha256 })}</span>}
          {record.pdf_sha256 && <span className="font-mono break-all">{t("ops.pdfHash", { hash: record.pdf_sha256 })}</span>}
          <pre tabIndex={0} aria-label={t("ops.snapshot")} className="max-h-96 overflow-auto rounded-md bg-muted p-2">
            {JSON.stringify(record.snapshot, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

/** ADMIN drafts a new acknowledgement statement version; activating it is a separate step. */
export function AcknowledgementStatementForm() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const short = text.trim().length < 20;

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    const result = await call("POST", "/api/v1/admin/acknowledgement-statements", { text: text.trim(), note: note.trim() }, true);
    setBusy(false);
    if (!result.ok) {
      setError(problem(result));
      return;
    }
    setSaved(true);
    setText("");
    setNote("");
    router.refresh();
  }
  return (
    <form onSubmit={save} className="flex flex-col gap-3" data-testid="acknowledgement-statement-form">
      <FormField id="statement-text" label={t("ops.statementText")} description={t("ops.statementTextHelp")} required>
        {(f) => <Textarea {...f} rows={6} maxLength={4000} value={text} onChange={(e) => setText(e.target.value)} />}
      </FormField>
      <FormField id="statement-note" label={t("ops.statementNote")} required>
        {(f) => <Input {...f} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />}
      </FormField>
      <Button type="submit" variant="outline" className="self-start" disabled={busy || short || !note.trim()}>
        {busy && <Spinner />}
        {t("ops.createDraft")}
      </Button>
      {saved && <Notice tone="success" live="polite">{t("ops.draftSaved")}</Notice>}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
    </form>
  );
}
