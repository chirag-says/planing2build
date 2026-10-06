import { ArrowRightIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { AnswerSummary } from "@/components/plan2build/answer-summary";
import { SectionHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  const area = getTranslator("Dashboard")("areas.requirement");
  return { title: await projectTitle((await params).projectId, area) };
}

// The submitted requirement, read only. While Plan2Build asks for more information the family
// edits it in the requirement form (ruling 2.7).
export default async function ProjectAnswersPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const { project, requirement } = await loadProject(projectId);
  if (!dashboardOpen(project.status)) redirect(`/projects/${projectId}`);
  const questions = (await (await serverApi()).GET("/api/v1/public/requirement-questions")).data;
  if (!questions) throw new Error("the question set could not be loaded");

  const t = getTranslator("Dashboard");
  const projects = getTranslator("Projects");
  const common = getTranslator("Common");
  const sameSet = questions.version === requirement.question_set_version;
  return (
    <section aria-labelledby="requirement" className="flex flex-col gap-4">
      <SectionHeader
        id="requirement"
        title={t("requirementTitle")}
        action={
          project.status === "NEEDS_INFO" && (
            <Button asChild>
              <Link href={`/projects/${projectId}/requirement`}>
                {projects("update")}
                <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
              </Link>
            </Button>
          )
        }
      />
      {sameSet ? (
        <AnswerSummary
          set={questions}
          answers={requirement.answers}
          labels={{ yes: common("yes"), no: common("no"), notSure: common("notSure") }}
          notAnswered={getTranslator("Requirement")("notAnswered")}
          hideUnanswered
        />
      ) : (
        <Notice tone="info">
          {getTranslator("Ops")("detail.versionMismatch", {
            version: requirement.question_set_version,
          })}
        </Notice>
      )}
    </section>
  );
}
