"use client";

// Creates the project (API section 4). One idempotency key per page view, so a double click or a
// retry after a lost response replays the same creation instead of making a second project.
import { ArrowRightIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { browserApi, errorCode } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Projects");

export function CreateProjectButton() {
  const router = useRouter();
  const key = useRef<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    key.current ??= crypto.randomUUID();
    setBusy(true);
    setError(null);
    try {
      const { data, error: failure } = await browserApi.POST("/api/v1/projects", {
        body: { city: "Raipur", project_type: "NEW_HOME" },
        params: { header: { "Idempotency-Key": key.current } },
      });
      if (data) {
        router.push(`/projects/${data.project.project_id}/requirement`);
        return;
      }
      const code = errorCode(failure);
      setError(
        code === "VALIDATION_ERROR" || code === "RATE_LIMITED"
          ? t(`errors.${code}`)
          : t("errors.default"),
      );
    } catch {
      setError(t("errors.default"));
    }
    setBusy(false);
  }

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <Notice tone="error" live="assertive">
          {error}
        </Notice>
      )}
      <Button type="button" size="lg" onClick={create} disabled={busy} className="sm:self-start">
        {busy && <Spinner />}
        {busy ? t("creating") : t("create")}
        {!busy && <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />}
      </Button>
    </div>
  );
}
