import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { DesignGallery } from "@/components/plan2build/design-gallery";
import { SectionHeader } from "@/components/plan2build/page-header";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  const area = getTranslator("Dashboard")("areas.designs");
  return { title: await projectTitle((await params).projectId, area) };
}

// Generate My Design and the gallery (Slice 3.1). Illustrative concepts only.
export default async function ProjectDesignsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const { project } = await loadProject(projectId);
  if (!dashboardOpen(project.status)) redirect(`/projects/${projectId}`);
  const { data } = await (await serverApi()).GET("/api/v1/projects/{project_id}/designs", {
    params: { path: { project_id: projectId } },
  });
  if (!data) throw new Error("the designs could not be loaded");
  const t = getTranslator("Designs");
  return (
    <section aria-labelledby="designs" className="flex flex-col gap-4">
      <SectionHeader id="designs" title={t("title")} description={t("intro")} />
      <DesignGallery projectId={project.project_id} initial={data} />
    </section>
  );
}
