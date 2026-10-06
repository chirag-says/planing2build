// One attached file: type icon, name, type and size, state, and actions. Used by the upload list
// and the project page so a file looks the same everywhere.
import type { FileView } from "@p2b/contracts";
import { FileIcon, FileImageIcon, FileTextIcon } from "lucide-react";
import type { ReactNode } from "react";

import { StatusBadge } from "@/components/plan2build/status-badge";
import { formatBytes } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

const ICONS: Record<string, typeof FileIcon> = {
  "image/jpeg": FileImageIcon,
  "image/png": FileImageIcon,
  "application/pdf": FileTextIcon,
};

type TypeKey = "image/jpeg" | "image/png" | "application/pdf";

export function typeLabel(mime: string): string {
  const t = getTranslator("Uploads");
  return mime in ICONS ? t(`type.${mime as TypeKey}`) : mime;
}

export function FileRow({
  name,
  mime,
  size,
  state,
  progress,
  actions,
}: {
  name: string;
  mime: string;
  size: number;
  state?: FileView["state"];
  progress?: ReactNode;
  actions?: ReactNode;
}) {
  const Icon = ICONS[mime] ?? FileIcon;
  return (
    <div className="flex items-start gap-3 py-3">
      <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <p className="text-sm font-medium break-all">{name}</p>
        <p className="text-xs text-muted-foreground">
          {typeLabel(mime)} · {formatBytes(size)}
        </p>
        {progress}
      </div>
      <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
        {state && <StatusBadge kind="file" status={state} />}
        {actions}
      </div>
    </div>
  );
}
