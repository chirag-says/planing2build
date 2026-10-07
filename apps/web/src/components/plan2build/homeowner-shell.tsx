// The homeowner host's signed-in shell (UI_DESIGN_SYSTEM.md section 9). The workspace sidebar
// (projects, estimator, directory, billing) opens with the first project; until then a signed-in
// homeowner is onboarding (the entry questions, then the first requirement) and keeps the
// website-style header, as a signed-out visitor does. On a project's pages the project switcher
// and the project's sections sit above the workspace links.
import type { ReactNode } from "react";

import { AppShell, type ShellGroup, type ShellSection } from "@/components/plan2build/app-shell";
import { HomeownerHeader } from "@/components/plan2build/homeowner-header";
import { ProjectSwitcher } from "@/components/plan2build/project-switcher";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, hasStagesAndLines, type ProjectDetail } from "@/lib/project";
import { currentUser, initialsOf, ownProjects } from "@/lib/session";

/** The project's sections, grouped the way the build runs. Only sections with content appear. */
export function projectGroups(detail: ProjectDetail): ShellGroup[] {
  const t = getTranslator("Dashboard");
  const shell = getTranslator("Shell");
  const { project } = detail;
  const base = `/projects/${project.project_id}`;
  const overview = { href: base, label: t("areas.overview"), icon: "overview", exact: true } as const;
  // A draft has no dashboard yet: its overview and the requirement being written.
  if (!dashboardOpen(project.status)) {
    return [{ items: [overview, { href: `${base}/requirement`, label: t("areas.requirement"), icon: "requirement" }] }];
  }
  const built = hasStagesAndLines(project.status);
  return [
    {
      label: shell("groups.plan"),
      items: [
        overview,
        { href: `${base}/answers`, label: t("areas.requirement"), icon: "requirement" },
        { href: `${base}/estimate`, label: t("areas.estimate"), icon: "estimate" },
        { href: `${base}/designs`, label: t("areas.designs"), icon: "designs" },
        { href: `${base}/build-plan`, label: t("areas.buildPlan"), icon: "buildPlan" },
      ],
    },
    ...(built
      ? [
          {
            label: shell("groups.build"),
            items: [
              { href: `${base}/construction`, label: t("areas.construction"), icon: "construction" },
              { href: `${base}/specification`, label: t("areas.specification"), icon: "specification" },
            ] as ShellGroup["items"],
          },
        ]
      : []),
    {
      label: shell("groups.hire"),
      items: [
        // Needs, requests and engagements per category (Slice 3.4); the directory is one step on.
        { href: `${base}/services`, label: t("areas.professionals"), icon: "professionals" },
        // Requests for contractor quotes on the accepted Build Plan (Slice 3.6).
        { href: `${base}/quotes`, label: t("areas.quotes"), icon: "quotes" },
      ],
    },
    {
      label: shell("groups.records"),
      items: [
        { href: `${base}/documents`, label: t("areas.documents"), icon: "documents" },
        { href: `${base}/package`, label: t("areas.package"), icon: "package" },
      ],
    },
  ];
}

export async function HomeownerShell({
  project,
  children,
}: {
  /** On a project's pages: the project, for the switcher and its sections. */
  project?: ProjectDetail;
  children: ReactNode;
}) {
  const user = await currentUser();
  // On a project's pages the project itself is the proof that onboarding is done.
  const projects = user ? await ownProjects() : null;
  if (!user || (!project && (projects?.length ?? 0) === 0)) {
    return (
      <>
        <HomeownerHeader />
        {/* The website's blueprint ground under every screen. */}
        <div className="p2b-ground flex flex-1 flex-col">{children}</div>
      </>
    );
  }

  const t = getTranslator("Nav");
  const shell = getTranslator("Shell");
  const projectsT = getTranslator("Projects");
  const workspace: ShellSection = {
    navLabel: t("main"),
    groups: [
      {
        label: shell("workspace"),
        items: [
          { href: "/projects", label: t("projects"), icon: "projects", exact: Boolean(project) },
          { href: "/professionals", label: t("professionals"), icon: "search" },
          { href: "/account/billing", label: t("billing"), icon: "billing" },
        ],
      },
    ],
  };

  let sidebarTop: ReactNode;
  let sections: ShellSection[] = [workspace];
  let context: ReactNode;
  if (project) {
    const all = projects;
    const current = {
      id: project.project.project_id,
      code: projectsT("code", { code: project.project.code }),
      locality: project.project.locality ?? null,
    };
    sidebarTop = (
      <ProjectSwitcher
        current={{ ...current, code: project.project.code }}
        status={getTranslator("Status")(`project.${project.project.status}`)}
        projects={(all ?? [project.project]).map((p) => ({
          id: p.project_id,
          code: p.code,
          locality: p.locality ?? null,
        }))}
      />
    );
    sections = [{ navLabel: getTranslator("Dashboard")("nav"), groups: projectGroups(project) }, workspace];
    context = (
      <p className="flex min-w-0 items-center gap-2.5 font-mono text-sm tracking-widest text-muted-foreground uppercase">
        <span aria-hidden="true" className="size-2 shrink-0 bg-brand ring-1 ring-foreground" />
        <span className="truncate">
          {current.code}
          {current.locality && ` · ${current.locality}`}
        </span>
      </p>
    );
  } else {
    context = (
      <p className="flex min-w-0 items-center gap-2.5 font-mono text-sm tracking-widest text-muted-foreground uppercase">
        <span aria-hidden="true" className="size-2 shrink-0 bg-brand ring-1 ring-foreground" />
        <span className="truncate">
          {user.display_name ? shell("greeting", { name: user.display_name }) : shell("greetingNoName")}
        </span>
      </p>
    );
  }

  return (
    <AppShell
      brand={getTranslator("App")("name")}
      tag={t("tag")}
      homeHref="/projects"
      userName={user.display_name}
      initials={initialsOf(user.display_name)}
      accountKind={shell("homeowner")}
      sections={sections}
      sidebarTop={sidebarTop}
      helpHref="/need-help"
      context={context}
      primaryAction={{ href: "/start", label: shell("newProject") }}
      accountLinks={[
        { href: "/projects", label: t("projects"), icon: "projects" },
        { href: "/account/billing", label: t("billing"), icon: "billing" },
        { href: "/need-help", label: shell("help"), icon: "help" },
      ]}
    >
      {children}
    </AppShell>
  );
}
