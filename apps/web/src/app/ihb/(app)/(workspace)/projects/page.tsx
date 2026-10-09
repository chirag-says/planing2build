import type { Metadata } from "next";

import { PlusIcon } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
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
  // No project yet: there is nothing to list; the start questions are the way in.
  if (projects.length === 0) redirect("/start");
  const count = (statuses: ProjectStatus[]) => projects.filter((p) => statuses.includes(p.status)).length;
  const startNew = (
    <Button asChild variant="outline">
      <Link href="/start">
        <PlusIcon aria-hidden="true" data-icon="inline-start" />
        {t("newProject")}
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
