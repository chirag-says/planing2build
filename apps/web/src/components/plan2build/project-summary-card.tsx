// A project in a list, and the next-step text shared by the list and the project page.
// Slice 1 ends at SUBMITTED (B-01); later states fall back to one neutral sentence.
import type { ProjectSummary } from "@p2b/contracts";
import { ArrowRightIcon } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

export function nextStepText(project: ProjectSummary): string {
  const t = getTranslator("Projects");
  if (project.status === "DRAFT") return t("next.DRAFT");
  if (project.status === "NEEDS_INFO") return t("next.NEEDS_INFO");
  if (project.status === "ACCEPTED") return t("next.ACCEPTED");
  if (project.status === "CANCELLED") return t("next.CANCELLED");
  if (project.status === "SUBMITTED") {
    return t("next.SUBMITTED", {
      date: project.submitted_at ? formatDate(project.submitted_at) : "",
    });
  }
  return t("next.other");
}

export function ProjectSummaryCard({ project }: { project: ProjectSummary }) {
  const t = getTranslator("Projects");
  // The requirement is the way in while it can still change (drafting, or after a request).
  const draft = project.status === "DRAFT" || project.status === "NEEDS_INFO";
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          <h2>{t("code", { code: project.code })}</h2>
        </CardTitle>
        <CardDescription>{project.locality ?? project.city_code}</CardDescription>
        <CardAction>
          <StatusBadge kind="project" status={project.status} withLabel />
        </CardAction>
      </CardHeader>
      <CardContent>
        <p className="text-sm">{nextStepText(project)}</p>
      </CardContent>
      <CardFooter>
        <Button asChild variant={draft ? "default" : "outline"}>
          <Link
            href={
              draft
                ? `/projects/${project.project_id}/requirement`
                : `/projects/${project.project_id}`
            }
          >
            {project.status === "NEEDS_INFO"
              ? t("update")
              : draft
                ? t("continue")
                : t("view")}
            <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
          </Link>
        </Button>
      </CardFooter>
    </Card>
  );
}
