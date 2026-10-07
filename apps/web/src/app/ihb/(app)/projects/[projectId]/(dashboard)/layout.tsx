import type { ReactNode } from "react";

import { PageHeader } from "@/components/plan2build/page-header";
import { JourneyRail } from "@/components/plan2build/journey-rail";
import { ProjectBreadcrumb } from "@/components/plan2build/project-breadcrumb";
import { ProjectNav } from "@/components/plan2build/project-nav";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, hasStagesAndLines, loadProject } from "@/lib/project";

// The project dashboard (PD-07): one header and a section nav around every project area. It opens
// on submission (PD-21); a draft shows only its overview, which leads back to the requirement.
// Sections appear only once they have content.
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
  const base = `/projects/${project.project_id}`;
  const open = dashboardOpen(project.status);
  const items = open
    ? [
        { href: base, label: t("areas.overview"), exact: true },
        { href: `${base}/answers`, label: t("areas.requirement") },
        { href: `${base}/estimate`, label: t("areas.estimate") },
        { href: `${base}/designs`, label: t("areas.designs") },
        ...(hasStagesAndLines(project.status)
          ? [
              { href: `${base}/construction`, label: t("areas.construction") },
              { href: `${base}/specification`, label: t("areas.specification") },
            ]
          : []),
        { href: `${base}/documents`, label: t("areas.documents") },
        { href: `${base}/package`, label: t("areas.package") },
        { href: `${base}/build-plan`, label: t("areas.buildPlan") },
        // Needs, requests and engagements per category (Slice 3.4); the directory is one step on.
        { href: `${base}/services`, label: t("areas.professionals") },
        // Requests for contractor quotes on the accepted Build Plan (Slice 3.6).
        { href: `${base}/quotes`, label: t("areas.quotes") },
      ]
    : [];

  return (
    <main
      id="main"
      className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-8 sm:px-6 sm:py-12"
    >
      <div className="flex flex-col gap-4">
        <ProjectBreadcrumb trail={[{ label: code }]} />
        <PageHeader
          title={code}
          description={project.locality ?? undefined}
          actions={<StatusBadge kind="project" status={project.status} withLabel />}
        />
      </div>
      {/* Where the project is in the journey, on every project page; the layout stays mounted
          between them, so the rail draws in once. */}
      <JourneyRail status={project.status} pkg={detail.package} />
      {open ? (
        <div className="flex flex-col gap-8 lg:grid lg:grid-cols-[12rem_minmax(0,1fr)] lg:items-start">
          <ProjectNav label={t("nav")} items={items} />
          <div className="flex min-w-0 flex-col gap-8">{children}</div>
        </div>
      ) : (
        <div className="flex max-w-3xl flex-col gap-8">{children}</div>
      )}
    </main>
  );
}
