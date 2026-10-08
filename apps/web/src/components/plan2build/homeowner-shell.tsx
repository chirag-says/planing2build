// The homeowner host's signed-in shell (UI_DESIGN_SYSTEM.md section 9). A signed-in homeowner has
// the app shell (projects, directory, billing) from the first sign-in, with or without a project:
// the requirement is asked for, never required. Only the entry steps of a requirement keep the
// website-style header until the family has a project (`entry`), as a signed-out visitor sees it.
// On a project's pages the top bar names the home (the
// project switcher) beside the notifications bell, and the sidebar carries the project's sections
// in seven groups (ProjectSectionsNav). Phones get the groups as a scrolling row in the page.
import type { ReactNode } from "react";

import { AppShell, type ShellSection } from "@/components/plan2build/app-shell";
import { HomeownerHeader } from "@/components/plan2build/homeowner-header";
import { NotificationsBell } from "@/components/plan2build/notifications-bell";
import {
  ProjectSectionsNav,
  type SectionGroup,
  type SectionIcon,
  type SectionItem,
} from "@/components/plan2build/project-sections-nav";
import { ProjectSwitcher } from "@/components/plan2build/project-switcher";
import { getTranslator } from "@/lib/i18n";
import { getInbox } from "@/lib/inbox-server";
import { dashboardOpen, hasStagesAndLines, type ProjectDetail } from "@/lib/project";
import { currentUser, initialsOf, ownProjects } from "@/lib/session";

type GroupKey = "home" | "project" | "quotes" | "construction" | "verify" | "records" | "journey";

/**
 * The project's sections in seven groups (ProjectSectionsNav). Only sections with content appear;
 * a draft has its overview, the requirement being written and the journey.
 */
export function projectGroups(detail: ProjectDetail): SectionGroup[] {
  const t = getTranslator("Dashboard");
  const o = getTranslator("Overview");
  const { project } = detail;
  const base = `/projects/${project.project_id}`;
  const g = (key: GroupKey, icon: SectionIcon, items: SectionItem[]): SectionGroup => ({
    key,
    label: t(`groups.${key}`),
    icon,
    items,
  });
  const journey = g("journey", "journey", [{ href: `${base}/journey`, label: t("areas.journey"), icon: "journey" }]);
  if (!dashboardOpen(project.status)) {
    return [
      g("home", "home", [{ href: base, label: t("areas.overview"), icon: "overview", exact: true }]),
      g("project", "project", [{ href: `${base}/requirement`, label: t("areas.requirement"), icon: "requirement" }]),
      journey,
    ];
  }
  const built = hasStagesAndLines(project.status);
  return [
    g("home", "home", [
      { href: base, label: t("areas.overview"), icon: "overview", exact: true },
      { href: `${base}/notifications`, label: t("areas.notifications"), icon: "notifications" },
      { href: `${base}/messages`, label: t("areas.messages"), icon: "messages" },
    ]),
    g("project", "project", [
      { href: `${base}/answers`, label: t("areas.requirement"), icon: "requirement" },
      { href: `${base}/estimate`, label: t("areas.estimate"), icon: "estimate" },
      { href: `${base}/designs`, label: t("areas.designs"), icon: "designs" },
      { href: `${base}/package`, label: t("areas.package"), icon: "package" },
      { href: `${base}/build-plan`, label: t("areas.buildPlan"), icon: "buildPlan" },
    ]),
    g("quotes", "quotes", [
      // Needs, requests and engagements per category (Slice 3.4); the directory is one step on.
      { href: `${base}/services`, label: t("areas.professionals"), icon: "professionals" },
      // Requests for contractor quotes on the accepted Build Plan (Slice 3.6).
      { href: `${base}/quotes`, label: t("areas.quotes"), icon: "quotes" },
    ]),
    ...(built
      ? [
          g("construction", "construction", [
            { href: `${base}/construction`, label: t("areas.construction"), icon: "construction" },
            { href: `${base}/specification`, label: t("areas.specification"), icon: "specification" },
          ]),
          g("verify", "verify", [{ href: `${base}/construction#inspections`, label: o("nav.inspections"), icon: "inspections" }]),
        ]
      : []),
    g("records", "records", [{ href: `${base}/documents`, label: t("areas.documents"), icon: "documents" }]),
    journey,
  ];
}

export async function HomeownerShell({
  project,
  entry = false,
  children,
}: {
  /** On a project's pages: the project, for the switcher and its sections. */
  project?: ProjectDetail;
  /** The first steps of a requirement: header only until the family has a project. */
  entry?: boolean;
  children: ReactNode;
}) {
  const user = await currentUser();
  // Signing in gets a homeowner the app shell at once; only the entry steps keep the header.
  const projects = user ? await ownProjects() : null;
  if (!user || (entry && !project && (projects?.length ?? 0) === 0)) {
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
  const sections: ShellSection[] = [workspace];
  let context: ReactNode;
  let headerActions: ReactNode;
  if (project) {
    const base = `/projects/${project.project.project_id}`;
    const switcher = (
      <ProjectSwitcher
        current={{ id: project.project.project_id, code: project.project.code, locality: project.project.locality ?? null }}
        status={getTranslator("Status")(`project.${project.project.status}`)}
        projects={(projects ?? [project.project]).map((p) => ({ id: p.project_id, code: p.code, locality: p.locality ?? null }))}
      />
    );
    // Which home this is sits in the top bar, always in view; the phone menu repeats it.
    context = <div className="max-w-sm">{switcher}</div>;
    sidebarTop = (
      <>
        <div className="md:hidden">{switcher}</div>
        <ProjectSectionsNav label={getTranslator("Dashboard")("nav")} groups={projectGroups(project)} />
      </>
    );
    if (dashboardOpen(project.project.status)) {
      const inbox = await getInbox(project.project.project_id);
      headerActions = <NotificationsBell href={`${base}/notifications`} count={inbox.unread} />;
    }
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
      headerActions={headerActions}
      primaryAction={project ? undefined : { href: "/start", label: shell("newProject") }}
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
