"use client";

// "Use as design reference" and its reverse. A reference records that the family likes this
// concept, nothing more: the image stays illustrative, and adding or removing a reference
// changes no drawing, design, Build Plan, quote, approval or free-design count.
import { BookmarkIcon, BookmarkXIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { browserApi } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Designs");

export function DesignReferenceButton({
  projectId,
  designId,
  marked,
}: {
  projectId: string;
  designId: string;
  marked: boolean;
}) {
  const router = useRouter();
  const key = useRef<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const path = { project_id: projectId, design_id: designId };

  async function toggle() {
    setBusy(true);
    setFailed(false);
    try {
      let ok: boolean;
      if (marked) {
        // DELETE is idempotent by nature; no key needed.
        ok = Boolean(
          (
            await browserApi.DELETE("/api/v1/projects/{project_id}/designs/{design_id}/reference", {
              params: { path },
            })
          ).data,
        );
      } else {
        key.current ??= crypto.randomUUID();
        ok = Boolean(
          (
            await browserApi.POST("/api/v1/projects/{project_id}/designs/{design_id}/reference", {
              params: { path, header: { "Idempotency-Key": key.current } },
            })
          ).data,
        );
      }
      if (ok) {
        key.current = null;
        router.refresh();
        return;
      }
      setFailed(true);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {!marked && <p className="text-sm text-muted-foreground">{t("referenceHelp")}</p>}
      <Button
        type="button"
        variant={marked ? "outline" : "default"}
        onClick={() => void toggle()}
        disabled={busy}
        className="sm:self-start"
      >
        {busy ? (
          <Spinner />
        ) : marked ? (
          <BookmarkXIcon aria-hidden="true" />
        ) : (
          <BookmarkIcon aria-hidden="true" />
        )}
        {busy ? t("referenceWorking") : marked ? t("referenceRemove") : t("reference")}
      </Button>
      {failed && (
        <Notice tone="error" live="assertive">
          {t("referenceError")}
        </Notice>
      )}
    </div>
  );
}
