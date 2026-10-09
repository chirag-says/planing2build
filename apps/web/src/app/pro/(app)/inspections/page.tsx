import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

export const metadata: Metadata = { title: getTranslator("Assurance")("proTitle") };

// The appointed auditor's inspections (Slice 3.7B, functional; EX-09). Someone without an active
// appointment sees that nothing is assigned.
export default async function AuditorInspectionsPage() {
  const { data, response } = await (await serverApi()).GET("/api/v1/pro/inspections");
  if (response.status === 401) redirect("/sign-in?next=%2Finspections");
  const t = getTranslator("Assurance");
  return (
    <PageContainer>
      <PageHeader title={t("proTitle")} description={data ? t("proIntro", { code: data.auditor_code }) : t("proNone")} />
      <ul className="flex flex-col gap-2">
        {(data?.items ?? []).map((i) => (
          <li key={i.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm" data-testid="assigned">
            <span className="font-medium">
              {i.project_code} · {t(`kinds.${i.kind}`)} · {t("inspection", { gate: i.gate, stage: i.stage_name })}
              {i.floor !== null && i.floor !== undefined ? ` (${i.floor})` : ""}
            </span>
            <span>{t(`states.${i.state}`)} · {formatDate(i.scheduled_at)}</span>
            <Link href={`/inspections/${i.id}`} className="font-medium underline underline-offset-4">{t("open")}</Link>
          </li>
        ))}
      </ul>
    </PageContainer>
  );
}
