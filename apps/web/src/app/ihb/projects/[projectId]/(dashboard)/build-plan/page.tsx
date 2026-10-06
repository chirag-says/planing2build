import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { DesignRequestCard, DesignRequestForm } from "@/components/plan2build/build-plan";
import { SectionHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({ params }: { params: Promise<{ projectId: string }> }): Promise<Metadata> {
  return { title: await projectTitle((await params).projectId, getTranslator("BuildPlan")("title")) };
}

// Design intake and the issued Build Plan versions for the family (Slice 3.5, functional).
export default async function BuildPlanPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const { project } = await loadProject(projectId);
  if (!dashboardOpen(project.status)) redirect(`/projects/${projectId}`);
  const api = await serverApi();
  const [plan, services] = await Promise.all([
    api.GET("/api/v1/projects/{project_id}/build-plan", { params: { path: { project_id: projectId } } }),
    api.GET("/api/v1/projects/{project_id}/services", { params: { path: { project_id: projectId } } }),
  ]);
  if (!plan.data) throw new Error("the Build Plan could not be loaded");
  const t = getTranslator("BuildPlan");
  const engagements = (services.data?.categories ?? [])
    .filter((c) => c.engagement)
    .map((c) => ({
      id: c.engagement!.id,
      party: c.engagement!.party,
      label: `${c.name}: ${c.engagement!.name ?? ""}`,
    }));
  const view = plan.data;
  return (
    <section aria-labelledby="build-plan" className="flex flex-col gap-6">
      <SectionHeader id="build-plan" title={t("title")} description={t("intro")} />
      <section aria-labelledby="drawings" className="flex flex-col gap-3">
        <h3 id="drawings" className="font-heading text-base font-medium">{t("drawings")}</h3>
        {view.design_requests.length === 0 && <p className="text-sm text-muted-foreground">{t("noRequests")}</p>}
        {view.design_requests.map((request) => (
          <DesignRequestCard key={request.id} audience="family" projectId={projectId} request={request} />
        ))}
        {view.can_act && (
          <details>
            <summary className="cursor-pointer text-sm font-medium">{t("newRequest")}</summary>
            <DesignRequestForm audience="family" projectId={projectId} engagements={engagements} />
          </details>
        )}
      </section>
      <section aria-labelledby="versions" className="flex flex-col gap-3">
        <h3 id="versions" className="font-heading text-base font-medium">{t("versions")}</h3>
        {view.versions.length === 0 ? (
          <Notice tone="info">{t("noVersions")}</Notice>
        ) : (
          <ul className="flex flex-col gap-2">
            {view.versions.map((v) => (
              <li key={v.id} className="flex flex-wrap items-center gap-2">
                <Link href={`/projects/${projectId}/build-plan/${v.id}`} className="font-medium underline underline-offset-4">
                  {t("view", { number: v.version_no })}
                </Link>
                <StatusBadge kind="buildPlan" status={v.state} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}
