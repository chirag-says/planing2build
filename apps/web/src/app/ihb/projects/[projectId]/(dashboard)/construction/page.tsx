import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { SectionHeader } from "@/components/plan2build/page-header";
import { StagesTable } from "@/components/plan2build/workspace-view";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { hasStagesAndLines, loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  const area = getTranslator("Dashboard")("areas.construction");
  return { title: await projectTitle((await params).projectId, area) };
}

// The build stages, created when the project passed the initial review (16 stages; 5, 6 and 9 per
// floor and for a basement). "Schedule to be confirmed" until approved dates exist (ruling 2.9).
export default async function ProjectConstructionPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const { project } = await loadProject(projectId);
  if (!hasStagesAndLines(project.status)) redirect(`/projects/${projectId}`);
  const { data: workspace } = await (await serverApi()).GET(
    "/api/v1/projects/{project_id}/workspace",
    { params: { path: { project_id: projectId } } },
  );
  if (!workspace) throw new Error("the stages could not be loaded");
  const t = getTranslator("Dashboard");
  return (
    <section aria-labelledby="stages" className="flex flex-col gap-4">
      <SectionHeader
        id="stages"
        title={t("areas.construction")}
        description={t("constructionIntro")}
      />
      <StagesTable workspace={workspace} />
    </section>
  );
}
