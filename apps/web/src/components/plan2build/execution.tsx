"use client";

// Execution controls (Slice 3.7A): a functional pass, no visual polish. The contractor posts an
// update in the standard format with photos; operations upload a photo an outside contractor
// sent. Photos are scanned before use, so posting waits for the check and retries briefly. The
// API decides every rule; these controls send and show its answer.
import { CSRF_HEADERS } from "@p2b/contracts";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { FormField } from "@/components/plan2build/form-field";
import { DownloadLink } from "@/components/plan2build/rfq";
import { LoadingState, Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { formatDate } from "@/lib/format";
import { FILE_FIELDS, filesStillChecking } from "@/lib/file-check";
import { getTranslator } from "@/lib/i18n";
import { updatesView, type UpdatesView } from "@/lib/ops-flow";

const t = getTranslator("Execution");
const SELECT =
  "h-11 w-full rounded-md border border-input bg-background px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 sm:h-10";
const CHECK_TRIES = 20;
const CHECK_WAIT_MS = 1500;

export type Result = { ok: boolean; status: number; body: unknown };

export async function call(method: string, url: string, body?: unknown, once = false): Promise<Result> {
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

export function problem(result: Result): string {
  const error = (result.body as { error?: { message?: string; details?: Record<string, unknown>; code?: string } })?.error;
  if (!error) return t("error");
  const detail = error.details?.reason ?? error.details?.fields ?? error.code;
  return t("errorReason", { reason: `${error.message ?? ""} ${JSON.stringify(detail)}`.trim() });
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Post once the files have passed the scan: a 422 only on a file field (`file_ids`, `file_id`, or
 * the ones given) means "not checked yet", so the same request is retried with the same key, up
 * to `tries` times `waitMs` apart (fewer where each attempt counts against a rate limit). */
export async function postWhenChecked(
  url: string, body: unknown, method = "POST",
  { fileFields = FILE_FIELDS, tries = CHECK_TRIES, waitMs = CHECK_WAIT_MS }: { fileFields?: readonly string[]; tries?: number; waitMs?: number } = {},
): Promise<Result> {
  const key = crypto.randomUUID();
  let result: Result = { ok: false, status: 0, body: null };
  for (let attempt = 0; attempt < tries; attempt += 1) {
    try {
      const response = await fetch(url, {
        method,
        headers: { ...CSRF_HEADERS, "Content-Type": "application/json", "Idempotency-Key": key },
        body: JSON.stringify(body),
      });
      const text = await response.text();
      result = { ok: response.ok, status: response.status, body: text ? JSON.parse(text) : null };
    } catch {
      result = { ok: false, status: 0, body: null };
    }
    if (!filesStillChecking(result, fileFields) || attempt === tries - 1) return result;
    await wait(waitMs);
  }
  return result;
}

export type Uploaded = { ok: true; fileId: string; state: string } | { ok: false; result: Result | null };

/** Upload one file through an upload route (`base`, then `base/{id}/complete`), keeping the API's
 * answer when a step is refused. Photos carry the device's capture time as a claim (EX-22);
 * documents do not. */
export async function uploadTo(base: string, file: File, withCaptureClaim = true): Promise<Uploaded> {
  const claim = withCaptureClaim ? { captured_at: new Date(file.lastModified).toISOString() } : {};
  const ticket = await call("POST", base, {
    file_name: file.name.slice(0, 200), content_type: file.type, size_bytes: file.size, ...claim,
  });
  if (!ticket.ok) return { ok: false, result: ticket };
  const { file: info, upload_url, headers } = ticket.body as { file: { file_id: string }; upload_url: string; headers: Record<string, string> };
  const put = await fetch(upload_url, { method: "PUT", headers, body: file }).then((r) => r.ok, () => false);
  if (!put) return { ok: false, result: null };
  const done = await call("POST", `${base}/${info.file_id}/complete`);
  if (!done.ok) return { ok: false, result: done };
  return { ok: true, fileId: info.file_id, state: (done.body as { state?: string } | null)?.state ?? "UPLOADED" };
}

/** {@link uploadTo}, reduced to the file id (null when any step fails). */
export async function uploadEvidence(base: string, file: File, withCaptureClaim = true): Promise<string | null> {
  const uploaded = await uploadTo(base, file, withCaptureClaim);
  return uploaded.ok ? uploaded.fileId : null;
}

/** Upload one file from the admin host: the raw body to an operations route with `?file_name=`
 * (the admin host never writes to storage directly). Returns the file id. */
export async function uploadOpsFile(url: string, file: File): Promise<string | null> {
  const response = await fetch(`${url}?file_name=${encodeURIComponent(file.name.slice(0, 200))}`, {
    method: "POST",
    headers: { ...CSRF_HEADERS, "Content-Type": file.type, "Idempotency-Key": crypto.randomUUID() },
    body: file,
  }).catch(() => null);
  if (!response?.ok) return null;
  return ((await response.json()) as { file_id: string }).file_id;
}

type StageOption = { id: string; label: string };

export function UpdateForm({ engagementId, stages }: { engagementId: string; stages: StageOption[] }) {
  const router = useRouter();
  const [stageId, setStageId] = useState(stages[0]?.id ?? "");
  const [kind, setKind] = useState("PROGRESS");
  const [note, setNote] = useState("");
  const [materials, setMaterials] = useState("");
  const [problems, setProblems] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [posted, setPosted] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setPosted(false);
    const ids: string[] = [];
    for (const file of files) {
      const id = await uploadEvidence(`/api/v1/pro/engagements/${engagementId}/evidence`, file);
      if (!id) {
        setBusy(false);
        setError(t("error"));
        return;
      }
      ids.push(id);
    }
    const result = await postWhenChecked(`/api/v1/pro/engagements/${engagementId}/stages/${stageId}/updates`, {
      kind, note, materials: materials || null, open_problems: problems || null, file_ids: ids,
    });
    setBusy(false);
    if (!result.ok) {
      setError(problem(result));
      return;
    }
    setPosted(true);
    setNote("");
    setMaterials("");
    setProblems("");
    setFiles([]);
    router.refresh();
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3" data-testid="update-form">
      <FormField id="update-stage" label={t("stageField")} required>
        {(c) => (
          <select {...c} className={SELECT} value={stageId} onChange={(e) => setStageId(e.target.value)}>
            {stages.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        )}
      </FormField>
      <FormField id="update-kind" label={t("kindField")} required>
        {(c) => (
          <select {...c} className={SELECT} value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="PROGRESS">{t("kinds.PROGRESS")}</option>
            <option value="COMPLETION_REQUEST">{t("kinds.COMPLETION_REQUEST")}</option>
          </select>
        )}
      </FormField>
      <FormField id="update-note" label={t("note")} required>
        {(c) => <Textarea {...c} rows={3} value={note} onChange={(e) => setNote(e.target.value)} />}
      </FormField>
      <FormField id="update-materials" label={t("materialsField")}>
        {(c) => <Textarea {...c} rows={2} value={materials} onChange={(e) => setMaterials(e.target.value)} />}
      </FormField>
      <FormField id="update-problems" label={t("problemsField")}>
        {(c) => <Textarea {...c} rows={2} value={problems} onChange={(e) => setProblems(e.target.value)} />}
      </FormField>
      <FormField id="update-photos" label={t("photosField")} required>
        {(c) => (
          <Input {...c} type="file" accept="image/jpeg,image/png" multiple
            onChange={(e) => setFiles(Array.from(e.target.files ?? []).slice(0, 10))} />
        )}
      </FormField>
      <Button type="submit" className="self-start" disabled={busy || !note.trim() || files.length === 0 || !stageId}>
        {busy && <Spinner />}
        {t("post")}
      </Button>
      {busy && <p role="status" className="text-sm text-muted-foreground">{t("waiting")}</p>}
      {posted && <Notice tone="success" live="polite">{t("posted")}</Notice>}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
    </form>
  );
}

export function OpsEvidenceUpload({ projectId }: { projectId: string }) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  async function upload(file: File) {
    setBusy(true);
    setFailed(false);
    const fileId = await uploadOpsFile(`/api/v1/ops/projects/${projectId}/stage-evidence`, file);
    setBusy(false);
    if (fileId) setDone(fileId);
    else setFailed(true);
  }
  return (
    <div className="flex flex-col gap-2">
      <FormField id="stage-evidence" label={t("evidence")}>
        {(c) => <Input {...c} type="file" accept="image/jpeg,image/png" disabled={busy}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); }} />}
      </FormField>
      {done && <p role="status" className="font-mono text-xs" data-testid="uploaded-photo">{t("uploaded", { id: done })}</p>}
      {failed && <Notice tone="error" live="assertive">{t("error")}</Notice>}
    </div>
  );
}

/** Every update on one stage for operations, loaded when the panel is first opened, with its
 * photos openable through the staff file route (logged by the API). */
export function OpsStageUpdates({ stageId }: { stageId: string }) {
  const [view, setView] = useState<UpdatesView | null>(null);
  const [loading, setLoading] = useState(false);
  async function load() {
    setLoading(true);
    setView(updatesView(await call("GET", `/api/v1/ops/stages/${stageId}/updates`)));
    setLoading(false);
  }
  return (
    <details
      onToggle={(e) => { if ((e.currentTarget as HTMLDetailsElement).open && !view && !loading) void load(); }}
      data-testid={`ops-stage-updates-${stageId}`}
    >
      <summary className="cursor-pointer">{t("viewUpdates")}</summary>
      <div className="mt-2 flex flex-col gap-2">
        {loading && <LoadingState label={t("loadingUpdates")} />}
        {view?.kind === "error" && (
          <Notice tone="error" live="assertive">
            {view.message ? t("errorReason", { reason: view.message }) : t("error")}
            <Button type="button" size="sm" variant="outline" className="mt-2 block" onClick={() => void load()}>{t("retry")}</Button>
          </Notice>
        )}
        {view?.kind === "empty" && <p className="text-muted-foreground">{t("noUpdates")}</p>}
        {view?.kind === "list" && (
          <ol className="flex flex-col gap-2">
            {view.updates.map((u) => (
              <li key={u.id} className="flex flex-col gap-1 rounded-md border border-border p-2">
                <span className="font-medium">
                  {t(`kinds.${u.kind}`)} · {formatDate(u.posted_at)}
                  {u.contractor_name && ` · ${u.contractor_name}`}
                  {u.entered_by_operations && ` · ${t("enteredByOps")}`}
                  {u.corrects_update_id && ` · ${t("corrects")}`}
                </span>
                <p className="whitespace-pre-line">{u.note}</p>
                {u.materials && <p>{t("materials", { text: u.materials })}</p>}
                {u.open_problems && <p>{t("openProblems", { text: u.open_problems })}</p>}
                {u.photos.length > 0 && (
                  <span className="flex flex-wrap gap-2">
                    {u.photos.map((p, n) => (
                      <DownloadLink key={p.file_id} url={`/api/v1/ops/stage-files/${p.file_id}/url`}
                        label={`${t("photo", { n: n + 1 })}: ${p.file_name}`} />
                    ))}
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </details>
  );
}
