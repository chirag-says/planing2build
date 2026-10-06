import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { SectionHeader } from "@/components/plan2build/page-header";
import { SpecificationGroups } from "@/components/plan2build/workspace-view";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { hasStagesAndLines, loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  const area = getTranslator("Dashboard")("areas.specification");
  return { title: await projectTitle((await params).projectId, area) };
}

// The 67 specification lines in groups A, B and C (groupings and timing only, never products,
// PD-09). Criteria appear when the API sends them (open point F-09).
export default async function ProjectSpecificationPage({
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
  if (!workspace) throw new Error("the specification could not be loaded");
  const t = getTranslator("Dashboard");
  return (
    <section aria-labelledby="specification" className="flex flex-col gap-4">
      <SectionHeader
        id="specification"
        title={t("areas.specification")}
        description={t("specificationIntro")}
      />
      <SpecificationGroups workspace={workspace} />
    </section>
  );
}
