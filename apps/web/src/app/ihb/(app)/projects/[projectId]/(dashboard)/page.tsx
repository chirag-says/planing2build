import type { Metadata } from "next";

import {
  ActivityTimeline,
  HomeVisual,
  NextStep,
  OverviewGreeting,
  ProjectSnapshot,
  StagePanel,
  StandingPanel,
  TeamSection,
} from "@/components/plan2build/overview";
import { Notice } from "@/components/plan2build/states";
import { getTranslator } from "@/lib/i18n";
import { getInbox } from "@/lib/inbox-server";
import { dashboardOpen, loadProject, projectTitle, type ProjectDetail } from "@/lib/project";
import { getProjectOverview, type ProjectOverview } from "@/lib/project-overview";
import { currentUser } from "@/lib/session";
import { site } from "@/marketing/content/site";

export async function generateMetadata({ params }: { params: Promise<{ projectId: string }> }): Promise<Metadata> {
  return { title: await projectTitle((await params).projectId) };
}

/**
 * What Plan2Build's review says (PD-21), where it adds to the next step: its question to the
 * family, a closed project's reason, and the result of the initial review. The review itself runs
 * in the background and never blocks the dashboard.
 */
function ReviewNotice({ detail, boardSaysReview }: { detail: ProjectDetail; boardSaysReview: boolean }) {
  const t = getTranslator("Dashboard");
  const projects = getTranslator("Projects");
  const { project, review_message: message } = detail;
  if (message?.status === "NEEDS_INFO") {
    return (
      <Notice tone="warning" title={projects("needsInfoTitle")}>
        <p className="whitespace-pre-line">{message.message}</p>
      </Notice>
    );
  }
  if (message?.status === "CANCELLED") {
    return (
      <Notice tone="info" title={projects("cancelledTitle")}>
        <p className="whitespace-pre-line">{projects("reason", { reason: message.message })}</p>
      </Notice>
    );
  }
  if (project.status === "SUBMITTED" && !boardSaysReview) {
    return (
      <Notice tone="info" title={t("reviewTitle")}>
        <p>{t("reviewBody")}</p>
      </Notice>
    );
  }
  if (detail.package.availability === "ELIGIBLE" && detail.package.state === "NOT_ACTIVE") {
    return (
      <Notice tone="success" title={t("acceptedTitle")}>
        <p>{t("acceptedBody")}</p>
      </Notice>
    );
  }
  return null;
}

/** What the board says when nothing needs the family; null while the project is paused or closed. */
function waitingCopy(overview: ProjectOverview) {
  const t = getTranslator("Dashboard");
  const o = getTranslator("Overview");
  if (overview.waiting === "review") return { title: t("reviewTitle"), body: t("reviewBody") };
  if (!overview.phase) return null;
  if (overview.waiting === "quotes") {
    const invited = overview.phaseNotes.compare?.values?.count ?? 0;
    return {
      title: o("waiting.quotes.title"),
      body: o("waiting.quotes.body", { invited }),
    };
  }
  return {
    title: o(`waiting.${overview.waiting}.title`),
    body: o(`waiting.${overview.waiting}.body`),
  };
}

/**
 * The project's home (homeowner brief v3): which home and where it stands, the one next step, how
 * far it has come, who is building it, what changed. The estimate, the package, the designs and
 * the full journey have their own pages.
 */
export default async function ProjectOverviewPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const [detail, overview, user] = await Promise.all([
    loadProject(projectId),
    getProjectOverview(projectId),
    currentUser(),
  ]);
  const base = `/projects/${projectId}`;
  const open = dashboardOpen(detail.project.status);
  const waiting = waitingCopy(overview);
  const hasAct = overview.actions.some((action) => action.kind === "act");
  const boardSaysReview = !hasAct && overview.waiting === "review";
  const now = open ? (await getInbox(projectId)).now : new Date().toISOString();

  return (
    <div className="flex flex-col gap-10 lg:gap-14">
      <OverviewGreeting name={user?.display_name ?? null} />

      {/* The home beside where it stands; on phones the stage and the next step come first. */}
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-10">
        <div className="order-2 min-w-0 lg:order-1">
          <HomeVisual overview={overview} base={base} />
        </div>
        <div className="order-1 flex min-w-0 flex-col gap-6 lg:order-2">
          <StagePanel overview={overview} base={base} />
          <ReviewNotice detail={detail} boardSaysReview={boardSaysReview} />
          <NextStep overview={overview} base={base} waiting={waiting} />
        </div>
      </div>

      {open && <StandingPanel overview={overview} />}

      {open && <TeamSection overview={overview} base={base} plan2build={{ phone: site.phone }} />}

      <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-10">
        {open ? <ActivityTimeline overview={overview} base={base} now={now} /> : <div />}
        <ProjectSnapshot overview={overview} base={base} />
      </div>
    </div>
  );
}
