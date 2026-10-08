import type { Metadata } from "next";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { ActiveWork } from "@/components/plan2build/pro-console";
import { getTranslator } from "@/lib/i18n";
import { loadConsole } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Console")("projectsPage.title") };

// The professional's projects: won through a request to quote (with the build's stages) and the
// services families engaged them for. Each sheet opens the project's own screen.
export default async function ProProjectsPage() {
  const c = await loadConsole("/projects");
  const t = getTranslator("Console");
  return (
    <PageContainer width="wide" className="max-w-6xl">
      <PageHeader size="compact" title={t("projectsPage.title")} description={t("projectsPage.intro")} />
      <ActiveWork console={c} heading={false} />
    </PageContainer>
  );
}
