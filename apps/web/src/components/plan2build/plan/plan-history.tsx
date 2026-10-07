"use client";

// The plan's persistent history (Checkpoint 3.1): named versions and the server's revisions. A
// version is saved from the head the editor shows; restoring a version or an earlier revision is
// a typed operation (REVERT_TO_VERSION, REVERT_TO_REVISION) sent through the editor like any
// edit, so it becomes a new revision, is undoable, and leaves the history as it was. The lists
// are read from the API again whenever the plan's revision changes.
import { HistoryIcon, SaveIcon } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { browserApi } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";
import type { EditorState } from "@/lib/plan/editor";
import type { PlanOp, PlanRevision, PlanVersion } from "@/lib/plan/types";

const t = getTranslator("Plan");

interface Lists {
  versions: PlanVersion[];
  revisions: PlanRevision[];
}

type Load = { status: "loading" } | { status: "failed" } | ({ status: "ready" } & Lists);

async function loadHistory(projectId: string, planId: string): Promise<Load> {
  const path = { project_id: projectId, plan_id: planId };
  const [versions, revisions] = await Promise.all([
    browserApi.GET("/api/v1/projects/{project_id}/house-plans/{plan_id}/versions", { params: { path } }).catch(() => null),
    browserApi
      .GET("/api/v1/projects/{project_id}/house-plans/{plan_id}/revisions", { params: { path, query: { limit: 20 } } })
      .catch(() => null),
  ]);
  if (!versions?.data || !revisions?.data) return { status: "failed" };
  return { status: "ready", versions: versions.data.items, revisions: revisions.data.items };
}

function revisionText(r: PlanRevision): string {
  if (r.restored_version != null) return t("history.restoredVersion", { version: r.restored_version });
  if (r.restored_revision != null) {
    return r.restored_revision === 0
      ? t("history.generated")
      : t("history.restoredRevision", { revision: r.restored_revision });
  }
  return t(`history.reason${r.reason}`);
}

export function PlanHistory({
  projectId,
  planId,
  state,
  editable,
  onCommit,
}: {
  projectId: string;
  planId: string;
  state: EditorState;
  editable: boolean;
  onCommit: (ops: PlanOp[]) => void;
}) {
  const revision = state.plan.editing.revision_no;
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [name, setName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const ids = useId();

  const [saves, setSaves] = useState(0); // a saved version is read back with the lists

  useEffect(() => {
    // the lists follow the plan: read them again after every stored change
    let active = true;
    void loadHistory(projectId, planId).then((next) => {
      if (active) setLoad(next);
    });
    return () => {
      active = false;
    };
  }, [projectId, planId, revision, saves]);

  async function save() {
    const trimmed = name.trim();
    if (!trimmed) return;
    const response = await browserApi
      .POST("/api/v1/projects/{project_id}/house-plans/{plan_id}/versions", {
        params: { path: { project_id: projectId, plan_id: planId }, header: { "Idempotency-Key": crypto.randomUUID() } },
        body: { name: trimmed, expected_revision: revision },
      })
      .catch(() => null);
    if (response?.data) {
      setName("");
      setMessage(t("history.saved"));
      setSaves((n) => n + 1);
    } else {
      setMessage(t("history.saveFailed"));
    }
  }

  return (
    <section aria-labelledby="plan-history" className="flex flex-col gap-3 rounded-lg border p-3">
      <h3 id="plan-history" className="text-sm font-medium">
        {t("history.title")}
      </h3>
      <p className="text-sm text-muted-foreground">{t("history.note")}</p>
      {load.status === "failed" && <p className="text-sm text-destructive">{t("history.loadFailed")}</p>}

      <h4 className="text-sm font-medium">{t("history.versions")}</h4>
      {load.status === "ready" && (
        <ul className="flex flex-col gap-1 text-sm">
          {load.versions.map((v) => (
            <li key={v.version_no} className="flex items-center justify-between gap-2">
              <span>
                {v.name}
                <span className="text-muted-foreground">
                  {" · "}
                  {v.revision_no === 0
                    ? t("history.generatedVersion")
                    : t("history.savedAt", { revision: v.revision_no })}
                </span>
              </span>
              {editable && (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={state.busy}
                  aria-label={t("history.restoreVersion", { name: v.name })}
                  onClick={() => onCommit([{ op: "REVERT_TO_VERSION", version: v.version_no }])}
                >
                  <HistoryIcon aria-hidden="true" data-icon="inline-start" />
                  {t("history.restore")}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {editable && (
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <Label htmlFor={`${ids}-name`}>{t("history.saveName")}</Label>
          <div className="flex gap-2">
            <Input id={`${ids}-name`} value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
            <Button type="submit" variant="outline" disabled={!name.trim() || state.busy}>
              <SaveIcon aria-hidden="true" data-icon="inline-start" />
              {t("history.save")}
            </Button>
          </div>
          {message && (
            <p role="status" className="text-sm text-muted-foreground">
              {message}
            </p>
          )}
        </form>
      )}

      <h4 className="text-sm font-medium">{t("history.changes")}</h4>
      {load.status === "ready" &&
        (load.revisions.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("history.changesEmpty")}</p>
        ) : (
          <ol className="flex flex-col gap-1 text-sm">
            {load.revisions.map((r) => (
              <li key={r.revision_no} className="flex items-center justify-between gap-2">
                <span>
                  {t("history.change", { revision: r.revision_no })}
                  <span className="text-muted-foreground"> · {revisionText(r)}</span>
                </span>
                {r.revision_no === revision ? (
                  <span className="text-xs text-muted-foreground">{t("history.current")}</span>
                ) : (
                  editable && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={state.busy}
                      aria-label={t("history.restoreRevision", { revision: r.revision_no })}
                      onClick={() => onCommit([{ op: "REVERT_TO_REVISION", revision: r.revision_no }])}
                    >
                      <HistoryIcon aria-hidden="true" data-icon="inline-start" />
                      {t("history.restore")}
                    </Button>
                  )
                )}
              </li>
            ))}
          </ol>
        ))}
    </section>
  );
}
