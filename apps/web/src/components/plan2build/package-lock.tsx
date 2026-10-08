// A package-gated action shown locked instead of hidden (PD-19, BP-09): the reason the API's
// package_state gives, and the way to the package page. Server and client components both use it.
import { LockIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { getTranslator } from "@/lib/i18n";

export function PackageLock({ projectId, reason }: { projectId: string; reason?: ReactNode }) {
  const t = getTranslator("Common");
  const link = (
    <Button asChild variant="outline" size="sm" className="self-start">
      <Link href={`/projects/${projectId}/package`}>
        <LockIcon aria-hidden="true" data-icon="inline-start" />
        {t("packageUnlock")}
      </Link>
    </Button>
  );
  if (!reason) return link;
  return (
    <div className="flex flex-col gap-2 rounded-md border border-dashed border-border p-3 text-sm" data-testid="package-lock">
      <p className="text-muted-foreground">{reason}</p>
      {link}
    </div>
  );
}
