import type { Metadata } from "next";
import Link from "next/link";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("nav.execution") };

// Completion requests waiting for a decision (Slice 3.7A, functional), oldest first. One waiting
// the configured number of days is an exception (EX-12); nothing is sent to anyone.
export default async function OpsExecutionPage() {
  await requireVerifiedStaff("/execution");
  const { data } = await (await serverApi()).GET("/api/v1/ops/execution");
  const t = getTranslator("Execution");
  return (
    <PageContainer width="wide">
      <PageHeader title={t("opsTitle")} description={t("opsIntro", { days: data?.exception_days ?? 0 })} />
      <ul className="flex flex-col gap-2">
        {(data?.waiting ?? []).map((w) => (
          <li key={w.stage.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm" data-testid="waiting">
            <span className="font-medium">
              {w.project_code} · {w.stage.stage_number}. {w.stage.name}
              {w.exception && <span className="ml-2 text-destructive">{t("exception")}</span>}
            </span>
            {w.stage.completion_requested_at && (
              <span>{t("requestedAt", { when: formatDate(w.stage.completion_requested_at) })}</span>
            )}
            <Link href={`/execution/${w.project_id}`} className="underline underline-offset-4">{t("openProject")}</Link>
          </li>
        ))}
      </ul>
    </PageContainer>
  );
}
