"use client";

// Optional attachments (R-15; ADR-011). The browser sends each file straight to storage on a
// presigned URL bound to its type and size (XMLHttpRequest, for upload progress); the API then
// checks it (type, content, malware) before it becomes available. Limits come from the question
// set. The checks below only spare the family a wasted upload; the API and the storage signature
// enforce them.
import type { FileView, Question } from "@p2b/contracts";
import { cn } from "cn";
import { Trash2Icon, UploadIcon } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";

import { FileRow } from "@/components/plan2build/file-row";
import { FormFieldset } from "@/components/plan2build/form-field";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { browserApi } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Uploads");

const COUNTED: readonly FileView["state"][] = ["PENDING_UPLOAD", "UPLOADED", "SCANNING", "AVAILABLE"];
const IN_PROGRESS: readonly FileView["state"][] = ["UPLOADED", "SCANNING"];
const POLL_MS = 2000;
const POLL_LIMIT = 60;

interface Sending {
  id: string;
  name: string;
  mime: string;
  size: number;
  progress: number;
}

function putWithProgress(
  url: string,
  headers: Record<string, string>,
  file: File,
  onProgress: (percent: number) => void,
): Promise<boolean> {
  return new Promise((resolve) => {
    const request = new XMLHttpRequest();
    request.open("PUT", url);
    for (const [name, value] of Object.entries(headers)) request.setRequestHeader(name, value);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onload = () => resolve(request.status >= 200 && request.status < 300);
    request.onerror = () => resolve(false);
    request.send(file);
  });
}

export function UploadsField({
  question,
  projectId,
  initialFiles,
}: {
  question: Question;
  projectId: string;
  initialFiles: FileView[];
}) {
  const [files, setFiles] = useState(initialFiles);
  const [sending, setSending] = useState<Sending[]>([]);
  const [problems, setProblems] = useState<string[]>([]);
  const [polls, setPolls] = useState(0);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const accept = question.accept ?? [];
  const maxBytes = question.max_bytes ?? 0;
  const maxFiles = question.max_files ?? 0;
  const maxMb = Math.round(maxBytes / (1024 * 1024));
  const checking = files.some((file) => IN_PROGRESS.includes(file.state));
  const busy = sending.length > 0;

  useEffect(() => {
    if (!checking || polls >= POLL_LIMIT) return;
    const timer = setTimeout(async () => {
      const { data } = await browserApi.GET("/api/v1/projects/{project_id}/files", {
        params: { path: { project_id: projectId } },
      });
      if (data) setFiles(data);
      setPolls((count) => count + 1);
    }, POLL_MS);
    return () => clearTimeout(timer);
  }, [checking, polls, projectId]);

  async function uploadOne(file: File, id: string): Promise<FileView | null> {
    const { data: ticket } = await browserApi.POST("/api/v1/uploads", {
      body: {
        project_id: projectId,
        file_name: file.name.slice(0, 200),
        content_type: file.type,
        size_bytes: file.size,
      },
      params: { header: { "Idempotency-Key": crypto.randomUUID() } },
    });
    if (!ticket) return null;
    const stored = await putWithProgress(ticket.upload_url, ticket.headers, file, (progress) =>
      setSending((current) => current.map((item) => (item.id === id ? { ...item, progress } : item))),
    );
    if (!stored) return ticket.file;
    const { data: completed } = await browserApi.POST("/api/v1/uploads/{file_id}/complete", {
      params: { path: { file_id: ticket.file.file_id } },
    });
    return completed ?? ticket.file;
  }

  async function add(chosen: File[]) {
    const found: string[] = [];
    let room = maxFiles - files.filter((file) => COUNTED.includes(file.state)).length;
    const accepted: File[] = [];
    for (const file of chosen) {
      if (!accept.includes(file.type)) found.push(t("wrongType", { name: file.name }));
      else if (file.size > maxBytes) found.push(t("tooBig", { name: file.name, size: maxMb }));
      else if (room <= 0) found.push(t("tooMany", { count: maxFiles }));
      else {
        accepted.push(file);
        room -= 1;
      }
    }
    setProblems([...new Set(found)]);
    if (accepted.length === 0) return;
    const queue = accepted.map((file) => ({
      file,
      item: { id: crypto.randomUUID(), name: file.name, mime: file.type, size: file.size, progress: 0 },
    }));
    setSending(queue.map(({ item }) => item));
    for (const { file, item } of queue) {
      let view: FileView | null = null;
      try {
        view = await uploadOne(file, item.id);
      } catch {
        view = null;
      }
      setSending((current) => current.filter((entry) => entry.id !== item.id));
      if (view) setFiles((current) => [...current, view]);
      if (!view || view.state === "PENDING_UPLOAD" || view.state === "FAILED") {
        setProblems((current) => [...current, t("failed", { name: file.name })]);
      }
    }
    setPolls(0);
  }

  function chosen(event: ChangeEvent<HTMLInputElement>) {
    const list = Array.from(event.target.files ?? []);
    event.target.value = "";
    void add(list);
  }

  function dropped(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!busy) void add(Array.from(event.dataTransfer.files));
  }

  async function remove(file: FileView) {
    const { response } = await browserApi.DELETE("/api/v1/files/{file_id}", {
      params: { path: { file_id: file.file_id } },
    });
    if (response.ok) setFiles((current) => current.filter((item) => item.file_id !== file.file_id));
  }

  return (
    <FormFieldset
      id={`q-${question.key}`}
      legend={question.label}
      required={question.required}
      description={t("hint", { size: maxMb, count: maxFiles })}
    >
      {({ describedBy }) => (
        <div className="flex flex-col gap-4">
          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={dropped}
            className={cn(
              "flex flex-col items-center justify-center gap-3 rounded-md border-2 border-dashed border-input px-4 py-8 text-center transition-colors",
              dragging && "border-primary bg-accent",
            )}
          >
            <UploadIcon aria-hidden="true" className="size-6 text-muted-foreground" />
            <p className="hidden text-base text-muted-foreground sm:block">{t("dropHere")}</p>
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => input.current?.click()}
              aria-describedby={describedBy}
            >
              {t("choose")}
            </Button>
            <input
              ref={input}
              type="file"
              multiple
              accept={accept.join(",")}
              onChange={chosen}
              hidden
            />
          </div>

          {problems.length > 0 && (
            <Notice tone="error" live="assertive">
              <ul className="list-disc pl-4">
                {problems.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            </Notice>
          )}

          {(sending.length > 0 || files.length > 0) && (
            <ul aria-label={t("listLabel")} aria-live="polite" className="divide-y divide-border rounded-md border border-border px-3">
              {sending.map((item) => (
                <li key={item.id}>
                  <FileRow
                    name={item.name}
                    mime={item.mime}
                    size={item.size}
                    progress={
                      <div className="flex items-center gap-2">
                        <Progress
                          value={item.progress}
                          aria-label={t("progress", { name: item.name })}
                          className="max-w-48"
                        />
                        <span className="text-xs text-muted-foreground tabular-nums">
                          {item.progress}%
                        </span>
                      </div>
                    }
                    actions={<span className="text-xs text-muted-foreground">{t("uploading")}</span>}
                  />
                </li>
              ))}
              {files.map((file) => (
                <li key={file.file_id}>
                  <FileRow
                    name={file.file_name}
                    mime={file.content_type}
                    size={file.size_bytes}
                    state={file.state}
                    actions={
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => remove(file)}
                        aria-label={t("remove", { name: file.file_name })}
                      >
                        <Trash2Icon aria-hidden="true" />
                      </Button>
                    }
                  />
                </li>
              ))}
            </ul>
          )}
          {checking && polls >= POLL_LIMIT && <Notice tone="info">{t("stillChecking")}</Notice>}
        </div>
      )}
    </FormFieldset>
  );
}
