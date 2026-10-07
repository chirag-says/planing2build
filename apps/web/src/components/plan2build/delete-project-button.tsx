"use client";

// Deletes a draft project after confirmation (UI_DESIGN_SYSTEM.md section 7.4). Only drafts
// offer it: once submitted, a project is with Plan2Build and operations cancel it. The list
// refreshes from the server afterwards, so the card simply disappears.
import { Trash2Icon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ConfirmationDialog } from "@/components/plan2build/confirmation-dialog";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { browserApi } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Projects");

export function DeleteProjectButton({ projectId, code }: { projectId: string; code: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  async function remove() {
    setBusy(true);
    setFailed(false);
    try {
      const { response } = await browserApi.DELETE("/api/v1/projects/{project_id}", {
        params: { path: { project_id: projectId } },
      });
      if (response.ok) {
        router.refresh();
        return;
      }
      setFailed(true);
    } catch {
      setFailed(true);
    }
    setBusy(false);
  }

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => setOpen(true)}
        disabled={busy}
        aria-label={`${t("delete")}: ${code}`}
        className="text-muted-foreground hover:text-destructive"
      >
        {busy ? <Spinner /> : <Trash2Icon aria-hidden="true" />}
        {busy ? t("deleting") : t("delete")}
      </Button>
      {failed && (
        <Notice tone="error" live="assertive" className="basis-full">
          {t("deleteError")}
        </Notice>
      )}
      <ConfirmationDialog
        open={open}
        onOpenChange={setOpen}
        title={t("deleteTitle")}
        description={t("deleteBody", { code })}
        confirmLabel={t("delete")}
        cancelLabel={t("deleteCancel")}
        onConfirm={() => void remove()}
      />
    </>
  );
}
