"use client";

// Downloads use a short-lived signed link requested on click; the API logs each request. `staff`
// asks the operations endpoint (admin host), otherwise the homeowner's own.
import { DownloadIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { browserApi } from "@/lib/api/browser";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Projects");
const common = getTranslator("Common");

export function DownloadButton({
  fileId,
  name,
  staff = false,
}: {
  fileId: string;
  name: string;
  staff?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  async function open() {
    setBusy(true);
    setFailed(false);
    try {
      const params = { params: { path: { file_id: fileId } } };
      const { data } = staff
        ? await browserApi.GET("/api/v1/ops/files/{file_id}/url", params)
        : await browserApi.GET("/api/v1/files/{file_id}/url", params);
      if (data) window.location.assign(data.url);
      else setFailed(true);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="flex flex-col items-end gap-1">
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={open}
        disabled={busy}
        aria-label={`${t("download")}: ${name}`}
      >
        {busy ? <Spinner /> : <DownloadIcon aria-hidden="true" />}
        {t("download")}
      </Button>
      {failed && (
        <span role="alert" className="text-xs text-destructive">
          {common("unavailable")}
        </span>
      )}
    </span>
  );
}
