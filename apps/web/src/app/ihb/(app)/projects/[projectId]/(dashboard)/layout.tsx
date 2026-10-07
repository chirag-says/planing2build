import type { ReactNode } from "react";

import { projectGroups } from "@/components/plan2build/homeowner-shell";
import { PageHeader } from "@/components/plan2build/page-header";
import { ProjectBreadcrumb } from "@/components/plan2build/project-breadcrumb";
import { ProjectNav } from "@/components/plan2build/project-nav";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, loadProject } from "@/lib/project";

// The project dashboard (PD-07): one header around every project area. The sections are in the
// shell's sidebar on wide screens and in a scrolling row above the content on phones. It opens on
// submission (PD-21); a draft shows only its overview, which leads back to the requirement.
export default async function ProjectDashboardLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const detail = await loadProject(projectId);
  const { project } = detail;
  const t = getTranslator("Dashboard");
  const code = getTranslator("Projects")("code", { code: project.code });
  const open = dashboardOpen(project.status);
  const items = projectGroups(detail).flatMap((group) => group.items);

  return (
    <main
      id="main"
      className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8 lg:gap-8 lg:px-8"
    >
      <div className="flex flex-col gap-4">
        <ProjectBreadcrumb trail={[{ label: code }]} />
        <PageHeader
          size="compact"
          title={code}
          description={project.locality ?? undefined}
          actions={<StatusBadge kind="project" status={project.status} withLabel />}
        />
      </div>
      {open && (
        <div className="lg:hidden">
          <ProjectNav label={t("nav")} items={items} />
        </div>
      )}
      <div className={open ? "flex min-w-0 flex-col gap-8" : "flex max-w-3xl flex-col gap-8"}>{children}</div>
    </main>
  );
}
