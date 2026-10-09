"use client";

// Build Plan workflow controls (Slice 3.5): a functional pass, no visual polish. The family asks
// for drawings, provides or reviews sets, and accepts an issued version with a one-time code; a
// professional provides sets and signs structural lines; operations record checks, draft and
// issue versions. The API decides every rule; these controls send and show its answer.
import { CSRF_HEADERS, type components } from "@p2b/contracts";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { ConfirmationDialog } from "@/components/plan2build/confirmation-dialog";
import { FormField } from "@/components/plan2build/form-field";
import { PackageLock } from "@/components/plan2build/package-lock";
import { Notice } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { SCAN_POLL_MS, shouldPollScan } from "@/lib/file-scan";
import { getTranslator } from "@/lib/i18n";

type Request = components["schemas"]["DesignRequestOut"];
type FileState = components["schemas"]["FileState"];
type Audience = "family" | "pro" | "ops";

const t = getTranslator("BuildPlan");
const SELECT =
  "h-11 w-full rounded-md border border-input bg-background px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 sm:h-10";
const CLASSES = ["SITE_PLAN", "FLOOR_PLAN", "ELEVATION", "SECTION", "STRUCTURAL", "OTHER"] as const;

type Result = { ok: boolean; status: number; body: unknown };

/** One JSON call with the CSRF header; a fresh Idempotency-Key when `once`. */
async function call(method: string, url: string, body?: unknown, once = false): Promise<Result> {
  const headers: Record<string, string> = { ...CSRF_HEADERS, "Content-Type": "application/json" };
  if (once) headers["Idempotency-Key"] = crypto.randomUUID();
  try {
    const response = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    return { ok: response.ok, status: response.status, body: text ? JSON.parse(text) : null };
  } catch {
    return { ok: false, status: 0, body: null };
  }
}

function problem(result: Result): string {
  const error = (result.body as { error?: { code?: string; message?: string; details?: Record<string, unknown> } })
    ?.error;
  if (!error) return t("error");
  const detail = error.details?.reason ?? error.details?.missing ?? error.details?.fields ?? error.code;
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
  return error ? (
    <Notice tone="error" live="assertive">
      {error}
    </Notice>
  ) : null;
}

function paths(audience: Audience, projectId: string) {
  const base = `/api/v1/projects/${projectId}`;
  return {
    upload: (requestId: string) =>
      audience === "family"
        ? `${base}/build-plan/uploads`
        : audience === "pro"
          ? `/api/v1/pro/build-plan/design-requests/${requestId}/uploads`
          : `/api/v1/ops/projects/${projectId}/build-plan/files`,
    complete: (fileId: string) =>
      audience === "family"
        ? `${base}/build-plan/uploads/${fileId}/complete`
        : audience === "pro"
          ? `/api/v1/pro/build-plan/uploads/${fileId}/complete`
          : "",
    addFile: (setId: string) =>
      audience === "family"
        ? `${base}/drawing-sets/${setId}/files`
        : audience === "pro"
          ? `/api/v1/pro/build-plan/drawing-sets/${setId}/files`
          : `/api/v1/ops/drawing-sets/${setId}/files`,
    submit: (setId: string) =>
      audience === "family"
        ? `${base}/drawing-sets/${setId}/submit`
        : audience === "pro"
          ? `/api/v1/pro/build-plan/drawing-sets/${setId}/submit`
          : `/api/v1/ops/drawing-sets/${setId}/submit`,
    newSet: (requestId: string) =>
      audience === "family"
        ? `${base}/design-requests/${requestId}/sets`
        : audience === "pro"
          ? `/api/v1/pro/build-plan/design-requests/${requestId}/sets`
          : `/api/v1/ops/design-requests/${requestId}/sets`,
    download: (fileId: string) =>
      audience === "family"
        ? `${base}/build-plan/files/${fileId}/url`
        : audience === "pro"
          ? `/api/v1/pro/build-plan/files/${fileId}/url`
          : `/api/v1/ops/files/${fileId}/url`,
  };
}

/** Upload one file (presigned PUT, then complete). Returns the file id. */
async function uploadFile(
  audience: Audience,
  projectId: string,
  requestId: string,
  file: File,
  purpose: "DRAWING" | "BUILD_PLAN_EVIDENCE" = "DRAWING",
): Promise<string | null> {
  if (audience === "ops") {
    // The admin host never uploads to storage directly (R2 CORS): the bytes go through the API.
    const query = new URLSearchParams({ purpose, file_name: file.name.slice(0, 200) });
    const response = await fetch(`/api/v1/ops/projects/${projectId}/build-plan/files?${query}`, {
      method: "POST",
      headers: { ...CSRF_HEADERS, "Content-Type": file.type || "application/pdf", "Idempotency-Key": crypto.randomUUID() },
      body: file,
    }).catch(() => null);
    if (!response?.ok) return null;
    return ((await response.json()) as { file_id: string }).file_id;
  }
  const p = paths(audience, projectId);
  const ticket = await call(
    "POST",
    p.upload(requestId),
    { purpose, file_name: file.name.slice(0, 200), content_type: file.type || "application/pdf", size_bytes: file.size },
    true,
  );
  if (!ticket.ok) return null;
  const body = ticket.body as { file: { file_id: string }; upload_url: string; headers: Record<string, string> };
  const put = await fetch(body.upload_url, { method: "PUT", headers: body.headers, body: file }).then(
    (r) => r.ok,
    () => false,
  );
  if (!put) return null;
  const done = await call("POST", p.complete(body.file.file_id));
  return done.ok ? body.file.file_id : null;
}

export function DownloadButton({
  audience,
  projectId,
  fileId,
  label,
}: {
  audience: Audience;
  projectId: string;
  fileId: string;
  label: string;
}) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  async function open() {
    setBusy(true);
    const result = await call("GET", paths(audience, projectId).download(fileId));
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

// --- design requests and sets ----------------------------------------------------------------

export function DesignRequestForm({
  audience,
  projectId,
  engagements,
}: {
  audience: "family" | "ops";
  projectId: string;
  engagements: { id: string; label: string; party: string }[];
}) {
  const action = useCall();
  const kinds =
    audience === "ops"
      ? (["HOMEOWNER_PROVIDED", "OUTSIDE_PROFESSIONAL", "LISTED_PROFESSIONAL", "PLAN2BUILD_ARRANGED"] as const)
      : (["HOMEOWNER_PROVIDED", "OUTSIDE_PROFESSIONAL", "LISTED_PROFESSIONAL"] as const);
  const [kind, setKind] = useState<string>(kinds[0]);
  const [engagement, setEngagement] = useState("");
  const [scope, setScope] = useState("");
  const [provider, setProvider] = useState("");
  const [qualification, setQualification] = useState("");
  const party = kind === "LISTED_PROFESSIONAL" ? "LISTED" : kind === "OUTSIDE_PROFESSIONAL" ? "OUTSIDE" : null;
  const choices = engagements.filter((e) => e.party === party);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const url =
      audience === "family" ? `/api/v1/projects/${projectId}/design-requests` : `/api/v1/ops/projects/${projectId}/design-requests`;
    const ok = await action.run(
      "POST",
      url,
      {
        kind,
        engagement_id: party ? engagement || null : null,
        scope_note: scope,
        provider_name: provider || null,
        provider_qualification: qualification || null,
      },
      true,
    );
    if (ok) setScope("");
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-md border border-border p-3">
      <FormField id={`kind-${audience}`} label={t("kind")} required>
        {(c) => (
          <select {...c} className={SELECT} value={kind} onChange={(e) => setKind(e.target.value)}>
            {kinds.map((k) => (
              <option key={k} value={k}>{t(`kinds.${k}`)}</option>
            ))}
          </select>
        )}
      </FormField>
      {party && (
        <FormField id={`engagement-${audience}`} label={t("engagement")} required>
          {(c) => (
            <select {...c} className={SELECT} value={engagement} onChange={(e) => setEngagement(e.target.value)}>
              <option value="">{t("chooseEngagement")}</option>
              {choices.map((e) => (
                <option key={e.id} value={e.id}>{e.label}</option>
              ))}
            </select>
          )}
        </FormField>
      )}
      {kind === "PLAN2BUILD_ARRANGED" && (
        <>
          <FormField id="provider-name" label={t("ops.checkerName")} required>
            {(c) => <Input {...c} value={provider} onChange={(e) => setProvider(e.target.value)} />}
          </FormField>
          <FormField id="provider-qualification" label={t("ops.qualification")} required>
            {(c) => <Input {...c} value={qualification} onChange={(e) => setQualification(e.target.value)} />}
          </FormField>
        </>
      )}
      <FormField id={`scope-${audience}`} label={t("scopeNote")} required>
        {(c) => <Textarea {...c} rows={2} value={scope} onChange={(e) => setScope(e.target.value)} />}
      </FormField>
      <ErrorNotice error={action.error} />
      <Button type="submit" className="self-start" disabled={!scope.trim() || action.busy}>
        {action.busy && <Spinner />}
        {t("openRequest")}
      </Button>
    </form>
  );
}

function AddDrawingForm({
  audience,
  projectId,
  requestId,
  setId,
}: {
  audience: Audience;
  projectId: string;
  requestId: string;
  setId: string;
}) {
  const action = useCall();
  const [file, setFile] = useState<File | null>(null);
  const [drawingClass, setDrawingClass] = useState<string>("SITE_PLAN");
  const [floor, setFloor] = useState("");
  const [title, setTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [failed, setFailed] = useState(false);

  async function add(event: FormEvent) {
    event.preventDefault();
    if (!file || !title.trim()) return;
    setUploading(true);
    setFailed(false);
    const fileId = await uploadFile(audience, projectId, requestId, file);
    setUploading(false);
    if (!fileId) {
      setFailed(true);
      return;
    }
    const ok = await action.run("POST", paths(audience, projectId).addFile(setId), {
      file_id: fileId,
      drawing_class: drawingClass,
      floor: floor === "" ? null : Number(floor),
      title: title.trim(),
    });
    if (ok) {
      setTitle("");
      setFile(null);
    }
  }

  return (
    <form onSubmit={add} className="grid gap-3 sm:grid-cols-2">
      <FormField id={`file-${setId}`} label={t("file")} required>
        {(c) => (
          <Input {...c} type="file" accept="application/pdf,image/jpeg,image/png"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        )}
      </FormField>
      <FormField id={`class-${setId}`} label={t("class")} required>
        {(c) => (
          <select {...c} className={SELECT} value={drawingClass} onChange={(e) => setDrawingClass(e.target.value)}>
            {CLASSES.map((k) => (
              <option key={k} value={k}>{t(`classes.${k}`)}</option>
            ))}
          </select>
        )}
      </FormField>
      <FormField id={`floor-${setId}`} label={t("floor")}>
        {(c) => (
          <select {...c} className={SELECT} value={floor} onChange={(e) => setFloor(e.target.value)}>
            <option value="">{t("floorNone")}</option>
            {[-1, 0, 1, 2, 3].map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        )}
      </FormField>
      <FormField id={`title-${setId}`} label={t("drawingTitle")} required>
        {(c) => <Input {...c} maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />}
      </FormField>
      {uploading && <p role="status" className="text-sm">{t("uploading")}</p>}
      {failed && <Notice tone="error" live="assertive">{t("uploadFailed")}</Notice>}
      <ErrorNotice error={action.error} />
      <Button type="submit" variant="outline" className="self-start" disabled={!file || !title.trim() || uploading || action.busy}>
        {(uploading || action.busy) && <Spinner />}
        {t("addFile")}
      </Button>
    </form>
  );
}

/** A drawing the family uploaded, still being checked: its state, read again until the check settles
 * (GET build-plan/files/{id}, the owner's own uploads only), then its download once AVAILABLE.
 * Only this row changes: refreshing the page from each file raced the owner's own actions (a
 * refresh started before "Submit the set" could land after it and show the set as a draft again). */
function FamilyFileState({ projectId, fileId, initial, downloadLabel }: {
  projectId: string;
  fileId: string;
  initial: FileState;
  downloadLabel: string;
}) {
  const [state, setState] = useState<FileState>(initial);
  useEffect(() => {
    let attempt = 0;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function read() {
      const result = await call("GET", `/api/v1/projects/${projectId}/build-plan/files/${fileId}`);
      attempt += 1;
      if (cancelled || !result.ok) return;
      const next = (result.body as components["schemas"]["FileOut"]).state;
      setState(next);
      if (shouldPollScan(next, attempt)) timer = setTimeout(() => void read(), SCAN_POLL_MS);
    }
    if (shouldPollScan(initial, 0)) timer = setTimeout(() => void read(), SCAN_POLL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [projectId, fileId, initial]);
  return (
    <>
      <StatusBadge kind="file" status={state} />
      {state === "AVAILABLE" && <DownloadButton audience="family" projectId={projectId} fileId={fileId} label={downloadLabel} />}
    </>
  );
}

/** Remove a drawing from the family's own DRAFT set, after a confirmation (no package needed). */
function RemoveDrawingFile({ projectId, setId, drawingFileId, title }: {
  projectId: string;
  setId: string;
  drawingFileId: string;
  title: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function remove() {
    setOpen(false);
    setBusy(true);
    setError(null);
    const result = await call("DELETE", `/api/v1/projects/${projectId}/drawing-sets/${setId}/files/${drawingFileId}`);
    setBusy(false);
    if (result.ok) {
      router.refresh();
      return;
    }
    setError(problem(result));
    // The set moved on or the drawing is already gone: show the current state.
    if (result.status === 404 || result.status === 409) router.refresh();
  }
  return (
    <>
      <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => setOpen(true)}
        aria-label={t("removeDrawingName", { title })}>
        {busy && <Spinner />}
        {t("removeDrawing")}
      </Button>
      <ConfirmationDialog
        open={open}
        onOpenChange={setOpen}
        title={t("removeDrawingTitle")}
        description={t("removeDrawingBody", { title })}
        confirmLabel={t("removeDrawing")}
        cancelLabel={t("keepDrawing")}
        onConfirm={() => void remove()}
      />
      {error && <span role="alert" className="basis-full text-xs text-destructive">{error}</span>}
    </>
  );
}

function FamilyDecision({ projectId, setId }: { projectId: string; setId: string }) {
  const action = useCall();
  const [note, setNote] = useState("");
  const url = `/api/v1/projects/${projectId}/drawing-sets/${setId}/decision`;
  return (
    <div className="flex flex-col gap-2">
      <FormField id={`note-${setId}`} label={t("changesNote")}>
        {(c) => <Textarea {...c} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />}
      </FormField>
      <ErrorNotice error={action.error} />
      <div className="flex flex-wrap gap-2">
        <Button type="button" onClick={() => void action.run("POST", url, { approve: true }, true)} disabled={action.busy}>
          {t("approveSet")}
        </Button>
        <Button type="button" variant="outline" disabled={!note.trim() || action.busy}
          onClick={() => void action.run("POST", url, { approve: false, note }, true)}>
          {t("changesSet")}
        </Button>
      </div>
    </div>
  );
}

function CheckForm({
  projectId,
  requestId,
  setId,
  checkers,
}: {
  projectId: string;
  requestId: string;
  setId: string;
  checkers: { id: string; name: string }[];
}) {
  const action = useCall();
  const [checker, setChecker] = useState(checkers[0]?.id ?? "");
  const [note, setNote] = useState("");
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  async function attach(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    setEvidenceId(await uploadFile("ops", projectId, requestId, file, "BUILD_PLAN_EVIDENCE"));
    setUploading(false);
  }
  async function decide(approve: boolean) {
    await action.run(
      "POST",
      `/api/v1/ops/drawing-sets/${setId}/check`,
      { appointment_id: checker, approve, note, evidence_file_id: evidenceId },
      true,
    );
  }
  return (
    <div className="flex flex-col gap-2 rounded-md border border-border p-3">
      <FormField id={`checker-${setId}`} label={t("ops.checker")} required>
        {(c) => (
          <select {...c} className={SELECT} value={checker} onChange={(e) => setChecker(e.target.value)}>
            {checkers.map((k) => (
              <option key={k.id} value={k.id}>{k.name}</option>
            ))}
          </select>
        )}
      </FormField>
      <FormField id={`check-note-${setId}`} label={t("ops.checkNote")} required>
        {(c) => <Textarea {...c} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />}
      </FormField>
      <FormField id={`evidence-${setId}`} label={t("ops.evidence")}>
        {(c) => <Input {...c} type="file" accept="application/pdf,image/jpeg,image/png" onChange={(e) => void attach(e.target.files?.[0])} />}
      </FormField>
      {uploading && <p role="status" className="text-sm">{t("uploading")}</p>}
      <ErrorNotice error={action.error} />
      <div className="flex flex-wrap gap-2">
        <Button type="button" disabled={!checker || !note.trim() || uploading || action.busy} onClick={() => void decide(true)}>
          {t("ops.approve")}
        </Button>
        <Button type="button" variant="outline" disabled={!checker || !note.trim() || action.busy} onClick={() => void decide(false)}>
          {t("ops.reject")}
        </Button>
      </div>
    </div>
  );
}

export function DesignRequestCard({
  audience,
  projectId,
  request,
  checkers = [],
  locked = false,
}: {
  audience: Audience;
  projectId: string;
  request: Request;
  checkers?: { id: string; name: string }[];
  /** The family's package is not active: its set actions show locked (BP-09), the page says why. */
  locked?: boolean;
}) {
  const action = useCall();
  const familyLocked = locked && audience === "family";
  // The family's own drawings, while the set is still a draft: the API lets the owner remove them.
  const familyDraft = (state: string) => audience === "family" && request.can_provide && state === "DRAFT";
  const open = request.sets.find((s) => ["DRAFT", "SUBMITTED", "IN_CHECK"].includes(s.state));
  return (
    <article aria-label={t(`kinds.${request.kind}`)} className="flex flex-col gap-3 rounded-md border border-border p-3">
      <header className="flex flex-col gap-1">
        <h3 className="font-medium">{t(`kinds.${request.kind}`)}{request.provider_name ? `: ${request.provider_name}` : ""}</h3>
        <p className="text-sm text-muted-foreground">{request.scope_note}</p>
      </header>
      {request.sets.map((set) => (
        <section key={set.id} aria-label={t("set", { number: set.set_no })} className="flex flex-col gap-2 border-t border-border pt-2"
          data-set-state={set.state}>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-sm font-medium">{t("set", { number: set.set_no })}</h4>
            <StatusBadge kind="drawingSet" status={set.state} />
            {set.checker_name && <span className="text-xs text-muted-foreground">{t("checkedBy", { name: set.checker_name })}</span>}
          </div>
          <ul className="flex flex-col gap-1 text-sm">
            {set.files.map((f) => (
              <li key={f.id} className="flex flex-wrap items-center gap-2">
                <span>{t(`classes.${f.drawing_class}`)}{f.floor !== null ? ` (${t("floor")} ${f.floor})` : ""}: {f.title}</span>
                {familyDraft(set.state) ? (
                  <FamilyFileState key={f.file_state} projectId={projectId} fileId={f.file_id} initial={f.file_state}
                    downloadLabel={t("download")} />
                ) : (
                  <>
                    <StatusBadge kind="file" status={f.file_state} />
                    {f.file_state === "AVAILABLE" && (
                      <DownloadButton audience={audience} projectId={projectId} fileId={f.file_id} label={t("download")} />
                    )}
                  </>
                )}
                {familyDraft(set.state) && (
                  <RemoveDrawingFile projectId={projectId} setId={set.id} drawingFileId={f.id} title={f.title} />
                )}
              </li>
            ))}
          </ul>
          {familyLocked && (set.state === "SUBMITTED" || (set.state === "DRAFT" && request.can_provide)) && (
            <PackageLock projectId={projectId} />
          )}
          {set.state === "DRAFT" && request.can_provide && !familyLocked && (
            <>
              <AddDrawingForm audience={audience} projectId={projectId} requestId={request.id} setId={set.id} />
              <Button type="button" className="self-start" disabled={set.files.length === 0 || action.busy}
                onClick={() => void action.run("POST", paths(audience, projectId).submit(set.id), undefined, true)}>
                {t("submitSet")}
              </Button>
            </>
          )}
          {set.state === "SUBMITTED" && audience === "family" && !familyLocked && <FamilyDecision projectId={projectId} setId={set.id} />}
          {set.state === "IN_CHECK" && audience === "ops" && (
            <CheckForm projectId={projectId} requestId={request.id} setId={set.id} checkers={checkers} />
          )}
        </section>
      ))}
      <ErrorNotice error={action.error} />
      {!open && request.can_provide && !familyLocked && (
        <Button type="button" variant="outline" className="self-start" disabled={action.busy}
          onClick={() => void action.run("POST", paths(audience, projectId).newSet(request.id), undefined, true)}>
          {t("newSet")}
        </Button>
      )}
    </article>
  );
}

// --- acceptance ------------------------------------------------------------------------------

export function AcceptPanel({ projectId, versionId }: { projectId: string; versionId: string }) {
  const action = useCall();
  const [challenge, setChallenge] = useState<{ challenge_id: string; sent_to: string } | null>(null);
  const [code, setCode] = useState("");
  const [reason, setReason] = useState("");
  const base = `/api/v1/projects/${projectId}/build-plan/versions/${versionId}`;

  async function send() {
    const result = await action.run("POST", `${base}/acceptance-code`);
    if (result) setChallenge(result.body as { challenge_id: string; sent_to: string });
  }
  async function confirm(event: FormEvent) {
    event.preventDefault();
    if (!challenge) return;
    await action.run("POST", `${base}/accept`, { challenge_id: challenge.challenge_id, code }, true);
  }
  return (
    <div className="flex flex-col gap-4">
      <section aria-labelledby="accept" className="flex flex-col gap-2 rounded-md border border-border p-3">
        <h3 id="accept" className="font-medium">{t("accept")}</h3>
        <p className="text-sm text-muted-foreground">{t("acceptHelp")}</p>
        {challenge ? (
          <form onSubmit={confirm} className="flex flex-col gap-2">
            <p role="status" className="text-sm">{t("codeSent", { email: challenge.sent_to })}</p>
            <FormField id="accept-code" label={t("code")} required>
              {(c) => <Input {...c} inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} />}
            </FormField>
            <Button type="submit" className="self-start" disabled={code.length !== 6 || action.busy}>
              {action.busy && <Spinner />}
              {t("confirmAccept")}
            </Button>
          </form>
        ) : (
          <Button type="button" className="self-start" onClick={() => void send()} disabled={action.busy}>
            {t("sendCode")}
          </Button>
        )}
      </section>
      <section aria-labelledby="changes" className="flex flex-col gap-2 rounded-md border border-border p-3">
        <h3 id="changes" className="font-medium">{t("requestChanges")}</h3>
        <FormField id="changes-reason" label={t("changesReason")} required>
          {(c) => <Textarea {...c} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />}
        </FormField>
        <Button type="button" variant="outline" className="self-start" disabled={!reason.trim() || action.busy}
          onClick={() => void action.run("POST", `${base}/request-changes`, { reason }, true)}>
          {t("sendChanges")}
        </Button>
      </section>
      <ErrorNotice error={action.error} />
    </div>
  );
}

// --- professional sign-off -------------------------------------------------------------------

export function SignPanel({ versionId, codes }: { versionId: string; codes: string[] }) {
  const action = useCall();
  const [chosen, setChosen] = useState<string[]>(codes);
  const [challenge, setChallenge] = useState<{ challenge_id: string; sent_to: string } | null>(null);
  const [code, setCode] = useState("");
  const base = `/api/v1/pro/build-plan/signoffs/${versionId}`;
  async function send() {
    const result = await action.run("POST", `${base}/code`, { line_codes: chosen });
    if (result) setChallenge(result.body as { challenge_id: string; sent_to: string });
  }
  async function sign(event: FormEvent) {
    event.preventDefault();
    if (!challenge) return;
    const done = await action.run("POST", `${base}/sign`, { line_codes: chosen, challenge_id: challenge.challenge_id, code }, true);
    if (done) setChallenge(null);
  }
  return (
    <div className="flex flex-col gap-3">
      <fieldset className="flex flex-col gap-1">
        <legend className="text-sm font-medium">{t("chooseLines")}</legend>
        {codes.map((c) => (
          <label key={c} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={chosen.includes(c)}
              onChange={(e) => setChosen(e.target.checked ? [...chosen, c] : chosen.filter((x) => x !== c))} />
            {c}
          </label>
        ))}
      </fieldset>
      {challenge ? (
        <form onSubmit={sign} className="flex flex-col gap-2">
          <p role="status" className="text-sm">{t("codeSent", { email: challenge.sent_to })}</p>
          <FormField id="sign-code" label={t("code")} required>
            {(c) => <Input {...c} inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} />}
          </FormField>
          <Button type="submit" className="self-start" disabled={code.length !== 6 || action.busy}>{t("sign")}</Button>
        </form>
      ) : (
        <Button type="button" className="self-start" disabled={chosen.length === 0 || action.busy} onClick={() => void send()}>
          {t("sendCode")}
        </Button>
      )}
      <ErrorNotice error={action.error} />
    </div>
  );
}

/** Revoke one of your structural sign-offs with a reason (BP-20), confirmed first. In review the
 * sign-off is voided; after issue the revocation is recorded and blocks acceptance. */
export function RevokeSignoff({ signoffId, lineCode, afterIssue }: { signoffId: string; lineCode: string; afterIssue: boolean }) {
  const action = useCall();
  const [editing, setEditing] = useState(false);
  const [reason, setReason] = useState("");
  const [confirming, setConfirming] = useState(false);
  const id = `revoke-${signoffId.slice(-8)}`;
  async function revoke() {
    const done = await action.run("POST", `/api/v1/pro/build-plan/signoffs/${signoffId}/revoke`, { reason: reason.trim() }, true);
    if (done) {
      setEditing(false);
      setReason("");
    }
  }
  if (!editing) {
    return (
      <Button type="button" variant="outline" size="sm" className="self-start" onClick={() => setEditing(true)}>
        {t("revoke.open")}
      </Button>
    );
  }
  return (
    <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); if (reason.trim()) setConfirming(true); }}>
      <FormField id={id} label={t("revoke.reason")} required>
        {(c) => <Textarea {...c} rows={2} maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} />}
      </FormField>
      <span className="flex flex-wrap gap-2">
        <Button type="submit" variant="destructive" size="sm" disabled={!reason.trim() || action.busy}>
          {action.busy && <Spinner />}
          {t("revoke.submit")}
        </Button>
        <Button type="button" variant="ghost" size="sm" disabled={action.busy} onClick={() => { setEditing(false); setReason(""); }}>
          {t("revoke.cancel")}
        </Button>
      </span>
      <ErrorNotice error={action.error} />
      <ConfirmationDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t("revoke.title", { line: lineCode })}
        description={afterIssue ? t("revoke.bodyAfterIssue") : t("revoke.bodyInReview")}
        confirmLabel={t("revoke.submit")}
        cancelLabel={t("revoke.keep")}
        onConfirm={() => void revoke()}
      />
    </form>
  );
}

// --- operations ------------------------------------------------------------------------------

export function JsonForm({
  id,
  label,
  method,
  url,
  initial,
  wrap,
  submitLabel,
  once = false,
}: {
  id: string;
  label: string;
  method: "PUT" | "POST";
  url: string;
  initial: string;
  wrap?: string;
  submitLabel: string;
  once?: boolean;
}) {
  const action = useCall();
  const [value, setValue] = useState(initial);
  const [parseError, setParseError] = useState(false);
  async function save(event: FormEvent) {
    event.preventDefault();
    let parsed: unknown;
    try {
      parsed = JSON.parse(value);
      setParseError(false);
    } catch {
      setParseError(true);
      return;
    }
    await action.run(method, url, wrap ? { [wrap]: parsed } : parsed, once);
  }
  return (
    <form onSubmit={save} className="flex flex-col gap-2">
      <FormField id={id} label={label} required>
        {(c) => <Textarea {...c} rows={8} className="font-mono text-xs" value={value} onChange={(e) => setValue(e.target.value)} />}
      </FormField>
      {parseError && <Notice tone="error" live="assertive">JSON</Notice>}
      <ErrorNotice error={action.error} />
      <Button type="submit" variant="outline" className="self-start" disabled={action.busy}>
        {action.busy && <Spinner />}
        {submitLabel}
      </Button>
    </form>
  );
}

export function ActionButton({
  label,
  method = "POST",
  url,
  body,
  once = true,
  variant = "default",
}: {
  label: string;
  method?: "POST" | "PUT";
  url: string;
  body?: unknown;
  once?: boolean;
  variant?: "default" | "outline" | "destructive";
}) {
  const action = useCall();
  return (
    <span className="flex flex-col gap-1">
      <Button type="button" variant={variant} className="self-start" disabled={action.busy}
        onClick={() => void action.run(method, url, body, once)}>
        {action.busy && <Spinner />}
        {label}
      </Button>
      <ErrorNotice error={action.error} />
    </span>
  );
}

export function ReasonAction({ label, url }: { label: string; url: string }) {
  const action = useCall();
  const [reason, setReason] = useState("");
  return (
    <div className="flex flex-col gap-2">
      <FormField id={`reason-${label}`} label={`${label}: ${t("ops.reason")}`} required>
        {(c) => <Input {...c} value={reason} onChange={(e) => setReason(e.target.value)} />}
      </FormField>
      <Button type="button" variant="outline" className="self-start" disabled={!reason.trim() || action.busy}
        onClick={() => void action.run("POST", url, { reason }, true)}>
        {label}
      </Button>
      <ErrorNotice error={action.error} />
    </div>
  );
}

export function ScopeForm({ versionId, scope }: { versionId: string; scope: components["schemas"]["SnapshotScopeOut"] }) {
  const action = useCall();
  const [inclusions, setInclusions] = useState(scope.inclusions.join("\n"));
  const [exclusions, setExclusions] = useState(scope.exclusions.join("\n"));
  const [assumptions, setAssumptions] = useState(scope.assumptions.join("\n"));
  const lines = (v: string) => v.split("\n").map((x) => x.trim()).filter(Boolean);
  async function save(event: FormEvent) {
    event.preventDefault();
    await action.run("PUT", `/api/v1/ops/build-plan-versions/${versionId}/scope`, {
      inclusions: lines(inclusions),
      exclusions: lines(exclusions),
      assumptions: lines(assumptions),
    });
  }
  return (
    <form onSubmit={save} className="grid gap-2 sm:grid-cols-3">
      <FormField id="inclusions" label={t("ops.scopeInclusions")} required>
        {(c) => <Textarea {...c} rows={3} value={inclusions} onChange={(e) => setInclusions(e.target.value)} />}
      </FormField>
      <FormField id="exclusions" label={t("ops.scopeExclusions")} required>
        {(c) => <Textarea {...c} rows={3} value={exclusions} onChange={(e) => setExclusions(e.target.value)} />}
      </FormField>
      <FormField id="assumptions" label={t("ops.scopeAssumptions")} required>
        {(c) => <Textarea {...c} rows={3} value={assumptions} onChange={(e) => setAssumptions(e.target.value)} />}
      </FormField>
      <ErrorNotice error={action.error} />
      <Button type="submit" variant="outline" className="self-start" disabled={action.busy}>{t("ops.save")}</Button>
    </form>
  );
}

export function SignDocumentForm({ projectId, versionId, codes }: { projectId: string; versionId: string; codes: string[] }) {
  const action = useCall();
  const [lineCodes, setLineCodes] = useState(codes.join(", "));
  const [name, setName] = useState("");
  const [number, setNumber] = useState("");
  const [issuer, setIssuer] = useState("");
  const [attestation, setAttestation] = useState("");
  const [certificateId, setCertificateId] = useState<string | null>(null);
  const [signedId, setSignedId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [failed, setFailed] = useState(false);
  async function attach(file: File | undefined, set: (id: string | null) => void) {
    if (!file) return;
    setUploading(true);
    setFailed(false);
    const id = await uploadFile("ops", projectId, "", file, "BUILD_PLAN_EVIDENCE");
    setUploading(false);
    if (!id) setFailed(true);
    set(id);
  }
  async function record(event: FormEvent) {
    event.preventDefault();
    if (!certificateId || !signedId) return;
    await action.run(
      "POST",
      `/api/v1/ops/build-plan-versions/${versionId}/signoffs`,
      {
        line_codes: lineCodes.split(",").map((c) => c.trim()).filter(Boolean),
        engineer_name: name,
        registration_number: number,
        registration_issuer: issuer,
        credential_file_id: certificateId,
        evidence_file_id: signedId,
        attestation,
      },
      true,
    );
  }
  return (
    <form onSubmit={record} className="grid gap-2 sm:grid-cols-2">
      <FormField id="sd-lines" label={t("ops.lineCodes")} required>
        {(c) => <Input {...c} value={lineCodes} onChange={(e) => setLineCodes(e.target.value)} />}
      </FormField>
      <FormField id="sd-name" label={t("ops.engineerName")} required>
        {(c) => <Input {...c} value={name} onChange={(e) => setName(e.target.value)} />}
      </FormField>
      <FormField id="sd-number" label={t("ops.registrationNumber")} required>
        {(c) => <Input {...c} value={number} onChange={(e) => setNumber(e.target.value)} />}
      </FormField>
      <FormField id="sd-issuer" label={t("ops.registrationIssuer")} required>
        {(c) => <Input {...c} value={issuer} onChange={(e) => setIssuer(e.target.value)} />}
      </FormField>
      <FormField id="sd-certificate" label={t("ops.certificate")} required>
        {(c) => <Input {...c} type="file" accept="application/pdf,image/jpeg,image/png" onChange={(e) => void attach(e.target.files?.[0], setCertificateId)} />}
      </FormField>
      <FormField id="sd-signed" label={t("ops.signedDocument")} required>
        {(c) => <Input {...c} type="file" accept="application/pdf,image/jpeg,image/png" onChange={(e) => void attach(e.target.files?.[0], setSignedId)} />}
      </FormField>
      <FormField id="sd-attestation" label={t("ops.attestation")} required>
        {(c) => <Input {...c} value={attestation} onChange={(e) => setAttestation(e.target.value)} />}
      </FormField>
      {uploading && <p role="status" className="text-sm">{t("uploading")}</p>}
      {failed && <Notice tone="error" live="assertive">{t("uploadFailed")}</Notice>}
      <ErrorNotice error={action.error} />
      <Button type="submit" variant="outline" className="self-start"
        disabled={!certificateId || !signedId || uploading || !name.trim() || !number.trim() || !issuer.trim() || !attestation.trim() || action.busy}>
        {t("ops.record")}
      </Button>
    </form>
  );
}

export function ManifestButton({ projectId }: { projectId: string }) {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function load() {
    const result = await call("GET", `/api/v1/ops/projects/${projectId}/build-plan/rfq-manifest`);
    if (result.ok) setText(JSON.stringify(result.body, null, 2));
    else setError(problem(result));
  }
  return (
    <div className="flex flex-col gap-2">
      <Button type="button" variant="outline" className="self-start" onClick={() => void load()}>{t("ops.showManifest")}</Button>
      <ErrorNotice error={error} />
      {text && <pre tabIndex={0} data-testid="rfq-manifest" className="max-h-96 overflow-auto rounded-md bg-muted p-2 text-xs">{text}</pre>}
    </div>
  );
}

// --- operations: confirmed actions -------------------------------------------------------------

/** An action that cannot be undone from this screen: optionally a reason first, then a
 * confirmation dialog, then one call. Shows the API's answer (error or `done`). */
export function ConfirmAction({
  id,
  label,
  title,
  description,
  url,
  once = true,
  reason = false,
  done,
  variant = "outline",
}: {
  id: string;
  label: string;
  title: string;
  description: string;
  url: string;
  once?: boolean;
  /** Ask for a reason and send it as `{reason}`. */
  reason?: boolean;
  done?: string;
  variant?: "default" | "outline" | "destructive";
}) {
  const action = useCall();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [finished, setFinished] = useState(false);
  async function confirm() {
    setOpen(false);
    setFinished(false);
    const result = await action.run("POST", url, reason ? { reason: text.trim() } : undefined, once);
    if (result) {
      setFinished(true);
      setText("");
    }
  }
  return (
    <div className="flex flex-col gap-2">
      {reason && (
        <FormField id={id} label={`${label}: ${t("ops.reason")}`} required>
          {(c) => <Input {...c} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} />}
        </FormField>
      )}
      <Button type="button" variant={variant} size="sm" className="self-start"
        disabled={action.busy || (reason && !text.trim())} onClick={() => setOpen(true)}>
        {action.busy && <Spinner />}
        {label}
      </Button>
      <ConfirmationDialog open={open} onOpenChange={setOpen} title={title} description={description}
        confirmLabel={label} cancelLabel={t("ops.cancel")} onConfirm={() => void confirm()} />
      <ErrorNotice error={action.error} />
      {finished && done && <Notice tone="success" live="polite">{done}</Notice>}
    </div>
  );
}
