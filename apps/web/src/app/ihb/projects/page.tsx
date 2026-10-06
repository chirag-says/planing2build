import type { Metadata } from "next";

import { FolderOpenIcon, PlusIcon } from "lucide-react";
import Link from "next/link";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { ProjectSummaryCard } from "@/components/plan2build/project-summary-card";
import { EmptyState } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireSignedIn } from "@/lib/session";

// The page title names the page (WCAG 2.4.2); the layout adds "| Plan2Build".
export const metadata: Metadata = { title: getTranslator("Projects")("title") };

export default async function ProjectsPage() {
  await requireSignedIn("/projects");
  const t = getTranslator("Projects");
  const { data: projects } = await (await serverApi()).GET("/api/v1/projects");
  if (!projects) throw new Error("projects could not be loaded");
  const startNew = (
    <Button asChild variant={projects.length === 0 ? "default" : "outline"}>
      <Link href="/start">
        <PlusIcon aria-hidden="true" data-icon="inline-start" />
        {t("startNew")}
      </Link>
    </Button>
  );
  return (
    <PageContainer>
      <PageHeader title={t("title")} actions={projects.length > 0 ? startNew : undefined} />
      {projects.length === 0 ? (
        <EmptyState icon={FolderOpenIcon} title={t("empty")} action={startNew} />
      ) : (
        <ul className="flex flex-col gap-4">
          {projects.map((project) => (
            <li key={project.project_id}>
              <ProjectSummaryCard project={project} />
            </li>
          ))}
        </ul>
      )}
    </PageContainer>
  );
}
