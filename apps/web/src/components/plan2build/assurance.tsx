"use client";

// Assurance controls (Slice 3.7B): a functional pass, no visual polish. The auditor records each
// checkpoint (with a finding where something needs correcting) and submits with an emailed code;
// the contractor submits a correction with photos; operations upload a signed report. Photos are
// scanned first, so saving waits for the check and retries briefly. The API decides every rule.
import type { components } from "@p2b/contracts";
import { CSRF_HEADERS } from "@p2b/contracts";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { call, postWhenChecked, problem, uploadEvidence } from "@/components/plan2build/execution";
import { FormField } from "@/components/plan2build/form-field";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Assurance");
const SELECT =
  "h-11 w-full rounded-md border border-input bg-background px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 sm:h-10";
const RESULTS = ["PASS", "OBSERVATION", "NON_CONFORMANCE", "NOT_APPLICABLE"] as const;
const SEVERITIES = ["MINOR", "MAJOR", "CRITICAL"] as const;

type Checkpoint = components["schemas"]["AuditorCheckpointOut"];
type Saved = components["schemas"]["ResultOut"];
type Row = {
  result: string; note: string; na_reason: string; measurement: string; room_tag: string;
  severity: string; description: string; corrective_action: string; due_date: string;
  file_ids: string[]; files: File[];
};

function initial(saved: Saved | undefined, kind: string): Row {
  return {
    result: saved?.result ?? "PASS", note: saved?.note ?? "", na_reason: saved?.na_reason ?? "",
    measurement: saved?.measurement ?? "", room_tag: saved?.room_tag ?? "",
    severity: saved?.severity ?? (kind === "INITIAL" ? "MINOR" : ""), description: saved?.description ?? "",
    corrective_action: saved?.corrective_action ?? "", due_date: saved?.due_date ?? "",
    file_ids: saved?.file_ids ?? [], files: [],
  };
}

export function AuditorResults({ inspectionId, kind, checkpoints, results }: {
  inspectionId: string; kind: string; checkpoints: Checkpoint[]; results: Saved[];
}) {
  const router = useRouter();
  const byPoint = new Map(results.map((r) => [r.checkpoint_id, r]));
  const [rows, setRows] = useState<Record<string, Row>>(
    Object.fromEntries(checkpoints.map((c) => [c.id, initial(byPoint.get(c.id), kind)])),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const base = `/api/v1/pro/inspections/${inspectionId}`;
  const set = (id: string, patch: Partial<Row>) => setRows((all) => ({ ...all, [id]: { ...all[id], ...patch } }));

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    const items = [];
    for (const c of checkpoints) {
      const row = rows[c.id];
      const ids = [...row.file_ids];
      for (const file of row.files) {
        const id = await uploadEvidence(`${base}/evidence`, file);
        if (!id) {
          setBusy(false);
          setError(t("error"));
          return;
        }
        ids.push(id);
      }
      const finding = kind === "INITIAL" && row.result === "NON_CONFORMANCE";
      items.push({
        checkpoint_id: c.id, result: row.result, note: row.note || null,
        na_reason: row.result === "NOT_APPLICABLE" ? row.na_reason || null : null,
        measurement: row.measurement || null, room_tag: row.room_tag || null, file_ids: ids,
        severity: finding ? row.severity : null, description: finding ? row.description || null : null,
        corrective_action: finding ? row.corrective_action || null : null,
        due_date: finding ? row.due_date || null : null,
      });
    }
    const result = await postWhenChecked(`${base}/results`, { results: items }, "PUT");
    setBusy(false);
    if (!result.ok) {
      setError(problem(result));
      return;
    }
    setSaved(true);
    router.refresh();
  }

  const choices = kind === "INITIAL" ? RESULTS : (["PASS", "NON_CONFORMANCE"] as const);
  return (
    <form onSubmit={save} className="flex flex-col gap-4" data-testid="results-form">
      {checkpoints.map((c) => {
        const row = rows[c.id];
        return (
          <fieldset key={c.id} className="flex flex-col gap-2 rounded-md border border-border p-3 text-sm" data-checkpoint={c.code}>
            <legend className="px-1 font-medium">{c.code} {c.text}</legend>
            {c.criteria && <p className="text-muted-foreground">{t("criteria", { text: c.criteria })}</p>}
            {c.accepted_value && <p className="text-muted-foreground">{t("acceptedValue", { text: c.accepted_value })}</p>}
            {c.expected_evidence && <p className="text-muted-foreground">{t("expected", { text: c.expected_evidence })}</p>}
            <FormField id={`result-${c.id}`} label={t("result")} required>
              {(f) => (
                <select {...f} className={SELECT} value={row.result} onChange={(e) => set(c.id, { result: e.target.value })}>
                  {choices.map((r) => <option key={r} value={r}>{t(`results.${r}`)}</option>)}
                </select>
              )}
            </FormField>
            <FormField id={`note-${c.id}`} label={t("note")}>
              {(f) => <Textarea {...f} rows={2} value={row.note} onChange={(e) => set(c.id, { note: e.target.value })} />}
            </FormField>
            {row.result === "NOT_APPLICABLE" && (
              <FormField id={`na-${c.id}`} label={t("naReason")} required>
                {(f) => <Input {...f} value={row.na_reason} onChange={(e) => set(c.id, { na_reason: e.target.value })} />}
              </FormField>
            )}
            {kind === "INITIAL" && row.result === "NON_CONFORMANCE" && (
              <>
                <FormField id={`severity-${c.id}`} label={t("severityField")} required>
                  {(f) => (
                    <select {...f} className={SELECT} value={row.severity} onChange={(e) => set(c.id, { severity: e.target.value })}>
                      {SEVERITIES.map((v) => <option key={v} value={v}>{v}</option>)}
                    </select>
                  )}
                </FormField>
                <FormField id={`description-${c.id}`} label={t("description")} required>
                  {(f) => <Textarea {...f} rows={2} value={row.description} onChange={(e) => set(c.id, { description: e.target.value })} />}
                </FormField>
                <FormField id={`action-${c.id}`} label={t("correctiveAction")} required>
                  {(f) => <Textarea {...f} rows={2} value={row.corrective_action} onChange={(e) => set(c.id, { corrective_action: e.target.value })} />}
                </FormField>
                <FormField id={`due-${c.id}`} label={t("dueDate")} required>
                  {(f) => <Input {...f} type="date" value={row.due_date} onChange={(e) => set(c.id, { due_date: e.target.value })} />}
                </FormField>
              </>
            )}
            <FormField id={`measurement-${c.id}`} label={t("measurement")}>
              {(f) => <Input {...f} value={row.measurement} onChange={(e) => set(c.id, { measurement: e.target.value })} />}
            </FormField>
            <FormField id={`room-${c.id}`} label={t("roomTag")}>
              {(f) => <Input {...f} value={row.room_tag} onChange={(e) => set(c.id, { room_tag: e.target.value })} />}
            </FormField>
            <FormField id={`photos-${c.id}`} label={t("photos")}>
              {(f) => <Input {...f} type="file" accept="image/jpeg,image/png" multiple
                onChange={(e) => set(c.id, { files: Array.from(e.target.files ?? []).slice(0, 10) })} />}
            </FormField>
          </fieldset>
        );
      })}
      <Button type="submit" className="self-start" disabled={busy}>
        {busy && <Spinner />}
        {t("save")}
      </Button>
      {saved && <Notice tone="success" live="polite">{t("saved")}</Notice>}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
    </form>
  );
}

export function SubmitInspection({ inspectionId }: { inspectionId: string }) {
  const router = useRouter();
  const [challenge, setChallenge] = useState<{ challenge_id: string; sent_to: string } | null>(null);
  const [code, setCode] = useState("");
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = `/api/v1/pro/inspections/${inspectionId}`;

  async function sendCode() {
    setBusy(true);
    setError(null);
    const result = await call("POST", `${base}/submission-code`);
    setBusy(false);
    if (result.ok) setChallenge(result.body as { challenge_id: string; sent_to: string });
    else setError(problem(result));
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!challenge) return;
    setBusy(true);
    setError(null);
    const result = await call("POST", `${base}/submit`, {
      summary: summary || null, challenge_id: challenge.challenge_id, code,
    }, true);
    setBusy(false);
    if (result.ok) router.refresh();
    else setError(problem(result));
  }
  return (
    <div className="flex flex-col gap-3">
      {!challenge && (
        <Button type="button" variant="outline" className="self-start" disabled={busy} onClick={() => void sendCode()}>
          {busy && <Spinner />}
          {t("sendCode")}
        </Button>
      )}
      {challenge && (
        <form onSubmit={submit} className="flex flex-col gap-3">
          <p role="status" className="text-sm">{t("codeSent", { to: challenge.sent_to })}</p>
          <FormField id="submit-summary" label={t("summary")}>
            {(f) => <Textarea {...f} rows={2} value={summary} onChange={(e) => setSummary(e.target.value)} />}
          </FormField>
          <FormField id="submit-code" label={t("code")} required>
            {(f) => <Input {...f} inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />}
          </FormField>
          <Button type="submit" className="self-start" disabled={busy || !code}>
            {busy && <Spinner />}
            {t("submit")}
          </Button>
        </form>
      )}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
    </div>
  );
}

export function RectifyForm({ engagementId, ncId }: { engagementId: string; ncId: string }) {
  const router = useRouter();
  const [note, setNote] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
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
    const result = await postWhenChecked(
      `/api/v1/pro/engagements/${engagementId}/non-conformances/${ncId}/rectification`, { note, file_ids: ids },
    );
    setBusy(false);
    if (!result.ok) {
      setError(problem(result));
      return;
    }
    setDone(true);
    router.refresh();
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-2" data-testid="rectify-form">
      <FormField id={`rectify-note-${ncId}`} label={t("rectifyNote")} required>
        {(f) => <Textarea {...f} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />}
      </FormField>
      <FormField id={`rectify-photos-${ncId}`} label={t("rectifyPhotos")} required>
        {(f) => <Input {...f} type="file" accept="image/jpeg,image/png" multiple
          onChange={(e) => setFiles(Array.from(e.target.files ?? []).slice(0, 10))} />}
      </FormField>
      <Button type="submit" variant="outline" className="self-start" disabled={busy || !note.trim() || files.length === 0}>
        {busy && <Spinner />}
        {t("rectify")}
      </Button>
      {done && <Notice tone="success" live="polite">{t("rectified")}</Notice>}
      {error && <Notice tone="error" live="assertive">{error}</Notice>}
    </form>
  );
}

export function OpsFileUpload({ url, id }: { url: string; id: string }) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  async function upload(file: File) {
    setBusy(true);
    setFailed(false);
    const response = await fetch(`${url}?file_name=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { ...CSRF_HEADERS, "Content-Type": file.type, "Idempotency-Key": crypto.randomUUID() },
      body: file,
    }).catch(() => null);
    setBusy(false);
    if (response?.ok) setDone(((await response.json()) as { file_id: string }).file_id);
    else setFailed(true);
  }
  return (
    <div className="flex flex-col gap-2">
      <FormField id={id} label={t("evidence")}>
        {(c) => <Input {...c} type="file" accept="application/pdf,image/jpeg,image/png" disabled={busy}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); }} />}
      </FormField>
      {done && <p role="status" className="font-mono text-xs" data-testid="uploaded-file-id">{t("uploaded", { id: done })}</p>}
      {failed && <Notice tone="error" live="assertive">{t("error")}</Notice>}
    </div>
  );
}
