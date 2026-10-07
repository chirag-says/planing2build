import { ArrowLeftIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { PlanWorkspace } from "@/components/plan2build/plan/plan-workspace";
import { ProjectBreadcrumb } from "@/components/plan2build/project-breadcrumb";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string; planId: string }>;
}): Promise<Metadata> {
  return { title: await projectTitle((await params).projectId, getTranslator("Plan")("title")) };
}

// The concept floor plan workspace (PD-28; HR S): outside the dashboard layout for full width, as
// the requirement wizard is. The plan comes from the API with its derived geometry; members and
// owners both see it, and only the owner gets editing tools (the API decides, AD-12). A plan the
// validator has not passed is never shown (IC 18.7): only VALID plans carry a document.
export default async function FloorPlanPage({
  params,
}: {
  params: Promise<{ projectId: string; planId: string }>;
}) {
  const { projectId, planId } = await params;
  const { project } = await loadProject(projectId);
  if (!dashboardOpen(project.status)) redirect(`/projects/${projectId}`);
  const response = await (await serverApi()).GET("/api/v1/projects/{project_id}/house-plans/{plan_id}", {
    params: { path: { project_id: projectId, plan_id: planId } },
  });
  if (response.response.status === 404 || response.response.status === 422) notFound();
  const plan = response.data;
  if (!plan) throw new Error("the floor plan could not be loaded");

  const t = getTranslator("Plan");
  const code = getTranslator("Projects")("code", { code: project.code });
  const designs = `/projects/${projectId}/designs`;
  const title = t("planNumber", { number: plan.sequence });
  const ready =
    plan.state === "VALID" && plan.document && plan.geometry && plan.editing && plan.validation?.valid;
  return (
    <PageContainer width="full">
      <div className="flex flex-col gap-4">
        <ProjectBreadcrumb
          trail={[
            { label: code, href: `/projects/${projectId}` },
            { label: getTranslator("Dashboard")("areas.designs"), href: designs },
            { label: title },
          ]}
        />
        <PageHeader
          eyebrow={code}
          title={title}
          actions={
            <Button asChild variant="outline">
              <Link href={designs}>
                <ArrowLeftIcon aria-hidden="true" data-icon="inline-start" />
                {t("back")}
              </Link>
            </Button>
          }
        />
      </div>
      <Notice tone="warning" title={t("disclaimer")}>
        {t("disclaimerDetail")}
      </Notice>
      {(plan.ruleset_is_synthetic || plan.ruleset_status !== "PUBLISHED") && (
        <Notice tone="info" title={t("rulesUnverified")}>
          {t("rulesUnverifiedBody")}
        </Notice>
      )}
      {ready && plan.document && plan.geometry && plan.editing ? (
        <PlanWorkspace
          projectId={projectId}
          planId={planId}
          initial={{
            document: plan.document,
            geometry: plan.geometry,
            validation: plan.validation,
            editing: plan.editing,
          }}
        />
      ) : (
        <Notice tone="info" title={t(`list.state.${plan.state}`)} />
      )}
    </PageContainer>
  );
}
