import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { DesignRequestCard } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireOnboarded } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("BuildPlan")("title") };

// The professional's Build Plan work (Slice 3.5, functional): drawing requests addressed to an
// active engagement, and versions waiting for a structural sign-off.
export default async function ProBuildPlanPage() {
  await requireOnboarded();
  const api = await serverApi();
  const [requests, signoffs] = await Promise.all([
    api.GET("/api/v1/pro/build-plan/design-requests"),
    api.GET("/api/v1/pro/build-plan/signoffs"),
  ]);
  if (requests.response.status === 401) redirect("/sign-in?next=%2Fbuild-plan");
  if (requests.response.status === 404) redirect("/profile");
  const t = getTranslator("BuildPlan");
  return (
    <PageContainer>
      <PageHeader title={t("title")} />
      <section aria-labelledby="requests" className="flex flex-col gap-3">
        <SectionHeader id="requests" title={t("requests")} />
        {(requests.data?.items ?? []).length === 0 && <p className="text-sm text-muted-foreground">{t("nothing")}</p>}
        {(requests.data?.items ?? []).map((item) => (
          <div key={item.request.id} className="flex flex-col gap-1">
            <p className="text-sm font-medium">{item.project_code}</p>
            <DesignRequestCard audience="pro" projectId={item.project_id} request={item.request} />
          </div>
        ))}
      </section>
      <section aria-labelledby="to-sign" className="flex flex-col gap-3">
        <SectionHeader id="to-sign" title={t("toSign")} />
        {(signoffs.data?.items ?? []).length === 0 && <p className="text-sm text-muted-foreground">{t("nothing")}</p>}
        <ul className="flex flex-col gap-2">
          {(signoffs.data?.items ?? []).map((item) => (
            <li key={item.version_id} className="flex flex-wrap items-center gap-2">
              <Link href={`/build-plan/signoffs/${item.version_id}`} className="font-medium underline underline-offset-4">
                {item.project_code}: {t("version", { number: item.version_no })}
              </Link>
              <StatusBadge kind="buildPlan" status={item.state} />
            </li>
          ))}
        </ul>
      </section>
    </PageContainer>
  );
}
