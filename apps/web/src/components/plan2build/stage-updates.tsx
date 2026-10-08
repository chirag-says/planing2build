"use client";

// The contractor's own updates on one stage (EX-02), newest first, read when asked for: kind,
// note, materials, open problems and photos behind logged links. A photo's capture time is the
// device's claim (EX-22). Re-read when the stage's update count changes after a new post.
import type { components } from "@p2b/contracts";
import { useEffect, useState } from "react";

import { call, problem } from "@/components/plan2build/execution";
import { DownloadLink } from "@/components/plan2build/rfq";
import { LoadingState, Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

type Updates = components["schemas"]["UpdatesOut"];
type Load = { key: string } & ({ status: "error"; message: string } | { status: "done"; data: Updates });

const t = getTranslator("Execution");

export function StageUpdateHistory({ engagementId, stageId, count }: { engagementId: string; stageId: string; count: number }) {
  const base = `/api/v1/pro/engagements/${engagementId}`;
  const [open, setOpen] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<Load | null>(null);
  const panel = `updates-${stageId}`;
  // One read per (count, attempt) while open: a new post changes the count, "Try again" the attempt.
  const key = `${count}:${attempt}`;

  useEffect(() => {
    if (!open || load?.key === key) return;
    let current = true;
    void call("GET", `${base}/stages/${stageId}/updates`).then((result) => {
      if (!current) return;
      setLoad(result.ok
        ? { key, status: "done", data: result.body as Updates }
        : { key, status: "error", message: problem(result) });
    });
    return () => { current = false; };
  }, [open, key, load?.key, base, stageId]);

  const shown = load?.key === key ? load : null;
  return (
    <div className="flex flex-col gap-2">
      <Button type="button" size="sm" variant="outline" className="self-start" aria-expanded={open} aria-controls={panel}
        onClick={() => setOpen((o) => !o)}>
        {open ? t("hideOwnUpdates") : t("showOwnUpdates", { count })}
      </Button>
      {open && (
        <div id={panel} className="flex flex-col gap-2" data-testid="own-updates">
          {!shown && <LoadingState label={t("loadingUpdates")} />}
          {shown?.status === "error" && (
            <Notice tone="error" live="assertive">
              <span className="flex flex-col items-start gap-2">
                {shown.message}
                <Button type="button" size="sm" variant="outline" onClick={() => setAttempt((a) => a + 1)}>{t("retry")}</Button>
              </span>
            </Notice>
          )}
          {shown?.status === "done" && shown.data.updates.length === 0 && (
            <p className="text-sm text-muted-foreground">{t("noUpdates")}</p>
          )}
          {shown?.status === "done" && shown.data.updates.length > 0 && (
            <ol className="flex flex-col gap-2" aria-label={t("ownUpdates")}>
              {shown.data.updates.map((u) => (
                <li key={u.id} className="flex flex-col gap-1 border-l-2 border-border pl-3" data-testid="own-update">
                  <span className="font-medium">
                    {t(`kinds.${u.kind}`)} · {formatDateTime(u.posted_at)}
                    {u.entered_by_operations && ` · ${t("enteredByOps")}`}
                  </span>
                  {u.corrects_update_id && <span className="text-muted-foreground">{t("corrects")}</span>}
                  <p className="whitespace-pre-wrap">{u.note}</p>
                  {u.materials && <p>{t("materials", { text: u.materials })}</p>}
                  {u.open_problems && <p>{t("openProblems", { text: u.open_problems })}</p>}
                  {u.photos.length > 0 && (
                    <span className="flex flex-wrap gap-3">
                      {u.photos.map((p, n) => (
                        <span key={p.file_id} className="flex flex-col gap-1">
                          <DownloadLink label={t("photo", { n: n + 1 })} url={`${base}/execution/files/${p.file_id}/url`} />
                          {p.captured_at && (
                            <span className="text-xs text-muted-foreground">{t("captured", { at: formatDateTime(p.captured_at) })}</span>
                          )}
                        </span>
                      ))}
                    </span>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
