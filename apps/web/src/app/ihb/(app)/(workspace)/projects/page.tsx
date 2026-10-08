import type { Metadata } from "next";

import { ArrowRightIcon, PlusIcon } from "lucide-react";
import Link from "next/link";

import { Eyebrow, PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { ProjectSummaryCard } from "@/components/plan2build/project-summary-card";
import { Button } from "@/components/ui/button";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import type { ProjectStatus } from "@/lib/project";
import { requireSignedIn } from "@/lib/session";

const REVIEW: ProjectStatus[] = ["SUBMITTED", "NEEDS_INFO"];
const ACTIVE: ProjectStatus[] = [
  "ACCEPTED",
  "PLANNING",
  "PLAN_ISSUED",
  "SOURCING",
  "CONTRACTED",
  "BUILDING",
  "HANDOVER_PENDING",
  "ON_HOLD",
];

// The page title names the page (WCAG 2.4.2); the layout adds "| Plan2Build".
export const metadata: Metadata = { title: getTranslator("Projects")("title") };

export default async function ProjectsPage() {
  await requireSignedIn("/projects");
  const t = getTranslator("Projects");
  const { data: projects } = await (await serverApi()).GET("/api/v1/projects");
  if (!projects) throw new Error("projects could not be loaded");
  // No project yet: the dashboard asks for the requirement (signing up never waits on it).
  if (projects.length === 0) {
    return (
      <PageContainer width="wide">
        <PageHeader size="compact" title={t("title")} />
        <section
          aria-labelledby="get-started"
          className="surface-dark flex flex-col gap-4 rounded-xl bg-background p-6 text-foreground ring-1 ring-foreground sm:p-8"
        >
          <Eyebrow>{t("getStarted.eyebrow")}</Eyebrow>
          <span aria-hidden="true" className="p2b-beam" />
          <h2 id="get-started" className="font-heading text-3xl leading-none sm:text-4xl">
            {t("getStarted.title")}
          </h2>
          <p className="max-w-prose text-lg text-pretty text-muted-foreground">{t("getStarted.body")}</p>
          <Button asChild size="lg" className="mt-2 bg-brand text-brand-foreground sm:self-start">
            <Link href="/start">
              {t("getStarted.cta")}
              <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
            </Link>
          </Button>
        </section>
      </PageContainer>
    );
  }
  const count = (statuses: ProjectStatus[]) => projects.filter((p) => statuses.includes(p.status)).length;
  const startNew = (
    <Button asChild variant="outline">
      <Link href="/start">
        <PlusIcon aria-hidden="true" data-icon="inline-start" />
        {t("startNew")}
      </Link>
    </Button>
  );
  return (
    <PageContainer width="wide">
      <PageHeader
        size="compact"
        title={t("title")}
        description={t("summary", {
          total: projects.length,
          review: count(REVIEW),
          active: count(ACTIVE),
          drafts: count(["DRAFT"]),
        })}
        actions={startNew}
      />
      <ul className="grid gap-4 md:grid-cols-2">
        {projects.map((project) => (
          <li key={project.project_id} className="min-w-0">
            <ProjectSummaryCard project={project} />
          </li>
        ))}
      </ul>
    </PageContainer>
  );
}
