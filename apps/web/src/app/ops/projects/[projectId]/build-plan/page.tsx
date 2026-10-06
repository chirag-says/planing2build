import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ActionButton, DesignRequestCard, DesignRequestForm, ManifestButton } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("BuildPlan")("title") };

// A project's design intake and Build Plan versions for operations (Slice 3.5, functional).
export default async function OpsProjectBuildPlanPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  await requireVerifiedStaff(`/projects/${projectId}/build-plan`);
  const api = await serverApi();
  const [plan, checkers] = await Promise.all([
    api.GET("/api/v1/ops/projects/{project_id}/build-plan", { params: { path: { project_id: projectId } } }),
    api.GET("/api/v1/ops/drawing-checkers"),
  ]);
  if (plan.response.status === 404 || !plan.data) notFound();
  const t = getTranslator("BuildPlan");
  const view = plan.data;
  return (
    <PageContainer width="wide">
      <PageHeader title={t("ops.projectTitle", { code: view.project_code })} />
      <section aria-labelledby="drawings" className="flex flex-col gap-3">
        <SectionHeader id="drawings" title={t("drawings")} />
        {view.design_requests.map((request) => (
          <DesignRequestCard key={request.id} audience="ops" projectId={projectId} request={request}
            checkers={(checkers.data ?? []).map((c) => ({ id: c.id, name: c.name }))} />
        ))}
        <details>
          <summary className="cursor-pointer text-sm font-medium">{t("newRequest")}</summary>
          <DesignRequestForm audience="ops" projectId={projectId} engagements={[]} />
        </details>
      </section>
      <section aria-labelledby="versions" className="flex flex-col gap-3">
        <SectionHeader id="versions" title={t("versions")} />
        <ul className="flex flex-col gap-2">
          {view.versions.map((v) => (
            <li key={v.id} className="flex flex-wrap items-center gap-2">
              <Link href={`/build-plan/versions/${v.id}`} className="font-medium underline underline-offset-4">
                {t("ops.openVersion", { number: v.version_no })}
              </Link>
              <StatusBadge kind="buildPlan" status={v.state} />
            </li>
          ))}
        </ul>
        <ActionButton label={t("ops.newVersion")} url={`/api/v1/ops/projects/${projectId}/build-plan/versions`} />
      </section>
      <section aria-labelledby="manifest" className="flex flex-col gap-3">
        <SectionHeader id="manifest" title={t("ops.manifest")} />
        <ManifestButton projectId={projectId} />
      </section>
    </PageContainer>
  );
}
