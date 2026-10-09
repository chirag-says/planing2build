import type { Metadata } from "next";

import { PageHeader } from "@/components/plan2build/page-header";
import { TeamDirectory } from "@/components/plan2build/team-directory";
import { getTranslator } from "@/lib/i18n";
import { projectTitle } from "@/lib/project";
import { getProjectOverview } from "@/lib/project-overview";
import { site } from "@/marketing/content/site";

export async function generateMetadata({ params }: { params: Promise<{ projectId: string }> }): Promise<Metadata> {
  return { title: await projectTitle((await params).projectId, getTranslator("Overview")("teamPage.title")) };
}

// Meet your team: the contractor, architect and engineer engaged on this project, each with their
// phone and email, then Plan2Build and the independent auditor.
export default async function TeamPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const o = getTranslator("Overview");
  const overview = await getProjectOverview(projectId);
  return (
    <>
      <PageHeader size="compact" title={o("teamPage.title")} description={o("teamPage.intro")} />
      <TeamDirectory overview={overview} base={`/projects/${projectId}`} plan2build={{ phone: site.phone }} />
    </>
  );
}
