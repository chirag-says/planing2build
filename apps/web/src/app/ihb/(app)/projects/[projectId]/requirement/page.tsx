import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { ProjectBreadcrumb } from "@/components/plan2build/project-breadcrumb";
import { Notice } from "@/components/plan2build/states";
import { RequirementWizard } from "@/components/plan2build/requirement/wizard";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { mapTiles } from "@/lib/map";
import { requireSignedIn } from "@/lib/session";


export const metadata: Metadata = { title: getTranslator("Requirement")("title") };

export default async function RequirementPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  await requireSignedIn(`/projects/${projectId}/requirement`);
  const api = await serverApi();
  const path = { params: { path: { project_id: projectId } } };
  const [detail, questions, files] = await Promise.all([
    api.GET("/api/v1/projects/{project_id}", path),
    api.GET("/api/v1/public/requirement-questions"),
    api.GET("/api/v1/projects/{project_id}/files", path),
  ]);
  if (detail.response.status === 404 || detail.response.status === 422) notFound();
  if (!detail.data || !questions.data || !files.data) {
    throw new Error("the requirement could not be loaded");
  }
  // Editable while drafting and after Plan2Build asks for more information (ruling 2.7).
  const status = detail.data.project.status;
  if (status !== "DRAFT" && status !== "NEEDS_INFO") redirect(`/projects/${projectId}`);
  const message = detail.data.review_message;
  if (questions.data.version !== detail.data.requirement.question_set_version) {
    // A project keeps the question set it started with; serving older sets is not built yet.
    throw new Error("the project uses a question set version that is no longer active");
  }

  const t = getTranslator("Requirement");
  const projects = getTranslator("Projects");
  const code = projects("code", { code: detail.data.project.code });
  return (
    <PageContainer>
      <div className="flex flex-col gap-4">
        <ProjectBreadcrumb
          trail={[{ label: code, href: `/projects/${projectId}` }, { label: t("title") }]}
        />
        <PageHeader eyebrow={code} title={t("title")} />
      </div>
      {message?.status === "NEEDS_INFO" && (
        <Notice tone="warning" title={t("needsInfoTitle")}>
          <p className="whitespace-pre-line">{message.message}</p>
        </Notice>
      )}
      <RequirementWizard
        projectId={projectId}
        set={questions.data}
        initialAnswers={detail.data.requirement.answers}
        initialVersion={detail.data.requirement.version}
        files={files.data}
        tiles={mapTiles()}
      />
    </PageContainer>
  );
}
