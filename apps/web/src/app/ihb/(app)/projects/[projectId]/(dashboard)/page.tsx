import type { Metadata } from "next";
import type { ReactNode } from "react";

import { ArrowRightIcon } from "lucide-react";
import Link from "next/link";

import { ActivityTimeline, HomeVisual, NextStep, OverviewGreeting, ProjectSnapshot } from "@/components/plan2build/overview";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Notice } from "@/components/plan2build/states";
import { getTranslator } from "@/lib/i18n";
import { getInbox } from "@/lib/inbox-server";
import { dashboardOpen, loadProject, projectTitle, type ProjectDetail } from "@/lib/project";
import { getProjectOverview, type ProjectOverview } from "@/lib/project-overview";
import { currentUser } from "@/lib/session";

export async function generateMetadata({ params }: { params: Promise<{ projectId: string }> }): Promise<Metadata> {
  return { title: await projectTitle((await params).projectId) };
}

/**
 * What Plan2Build's review says (PD-21), where it adds to the next step: its question to the
 * family, a closed project's reason, and the result of the initial review. The review itself runs
 * in the background and never blocks the dashboard.
 */
function reviewNotice(detail: ProjectDetail, boardSaysReview: boolean): ReactNode {
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
 * The project's home: where the project stands (its status, the journey), the house as it stands
 * (the contractor's site photo), the next step with everything else waiting under it, what changed
 * lately, and the project's standing (code, package, requirement, estimate). The team, the designs
 * and the full journey have their own pages and sidebar entries. Phones stack it and scroll.
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
  const notice = reviewNotice(detail, boardSaysReview);
  const now = open ? (await getInbox(projectId)).now : new Date().toISOString();
  const o = getTranslator("Overview");

  return (
    // On wide screens the page is as tall as the window under the top bar, so nothing scrolls.
    <div className="ov-single flex flex-col gap-6 lg:gap-5">
      <OverviewGreeting name={user?.display_name ?? null} />
      <div className="ov-single-grid grid gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-8">
        {/* Phones put the next step first; the house follows. */}
        <div className="ov-single-col order-2 min-w-0 lg:order-1">
          <HomeVisual overview={overview} base={base} fill />
        </div>
        <div className="ov-single-col order-1 flex min-w-0 flex-col gap-4 lg:order-2">
          {/* Where the project stands: the backend's own status, and the way to the whole journey. */}
          <div className="flex shrink-0 flex-wrap items-center justify-between gap-3">
            <StatusBadge kind="project" status={detail.project.status} withLabel />
            <Link href={`${base}/journey`} className="ov-link">
              {o("stage.viewJourney")}
              <ArrowRightIcon aria-hidden="true" />
            </Link>
          </div>
          {notice && <div className="shrink-0">{notice}</div>}
          <div className="shrink-0">
            <NextStep overview={overview} base={base} waiting={waiting} />
          </div>
          {open && <ActivityTimeline overview={overview} base={base} now={now} compact rows={2} />}
          {open && <ProjectSnapshot overview={overview} base={base} />}
        </div>
      </div>
    </div>
  );
}
