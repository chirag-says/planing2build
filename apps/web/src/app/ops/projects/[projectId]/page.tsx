import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AnswerSummary } from "@/components/plan2build/answer-summary";
import { ClaimControl } from "@/components/plan2build/claim-control";
import { DecisionPanel } from "@/components/plan2build/decision-panel";
import { DownloadButton } from "@/components/plan2build/download-button";
import { FileRow } from "@/components/plan2build/file-row";
import { OpsEngagements } from "@/components/plan2build/ops-engagements";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { OpsPlanList } from "@/components/plan2build/plan/ops-plan-list";
import { ProjectBreadcrumb } from "@/components/plan2build/project-breadcrumb";
import { Notice } from "@/components/plan2build/states";
import { ReviewFlagBadge, StatusBadge } from "@/components/plan2build/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("detail.review") };

// One submission as operations review it (API 18): read-only answers with the family's labels,
// review flags, contact, files, who is reviewing, the decisions and the history of each change.
export default async function OpsProjectPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const staff = await requireVerifiedStaff(`/projects/${projectId}`);
  if (!staff.roles.includes("OPS")) notFound();
  const api = await serverApi();
  const [detail, questions, engagements, categories] = await Promise.all([
    api.GET("/api/v1/ops/projects/{project_id}", { params: { path: { project_id: projectId } } }),
    api.GET("/api/v1/public/requirement-questions"),
    api.GET("/api/v1/ops/projects/{project_id}/engagements", { params: { path: { project_id: projectId } } }),
    api.GET("/api/v1/public/professional-categories"),
  ]);
  if (detail.response.status === 404 || detail.response.status === 422) notFound();
  if (!detail.data || !questions.data) throw new Error("the submission could not be loaded");

  const t = getTranslator("Ops");
  const projects = getTranslator("Projects");
  const common = getTranslator("Common");
  const { project, requirement, files, queue_item: item } = detail.data;
  const code = projects("code", { code: project.code });
  const sameSet = questions.data.version === requirement.question_set_version;

  return (
    <PageContainer width="wide">
      <div className="flex flex-col gap-4">
        <ProjectBreadcrumb
          root={{ label: t("queue.title"), href: "/queue" }}
          trail={[{ label: code }]}
        />
        <PageHeader
          title={code}
          description={[
            project.locality,
            project.submitted_at
              ? t("detail.submittedOn", { date: formatDate(project.submitted_at) })
              : null,
          ]
            .filter(Boolean)
            .join(" · ")}
          actions={<StatusBadge kind="project" status={project.status} withLabel />}
        />
        {/* Project-level operations areas (ops-flow): one block, kept together for easy merges. */}
        <nav aria-label={t("detail.areas")} className="flex flex-wrap gap-4 text-sm">
          <Link href={`/projects/${projectId}/build-plan`} className="underline underline-offset-4">{t("nav.buildPlan")}</Link>
          <Link href={`/rfqs/project/${projectId}`} className="underline underline-offset-4">{t("nav.rfqs")}</Link>
          <Link href={`/execution/${projectId}`} className="underline underline-offset-4">{t("nav.execution")}</Link>
          <Link href={`/assurance/${projectId}`} className="underline underline-offset-4">{t("nav.assurance")}</Link>
          <Link href={`/handover/${projectId}`} className="underline underline-offset-4">{getTranslator("Records")("openHandover")}</Link>
        </nav>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-6">
          {project.review_flags.length > 0 && (
            <Notice tone="warning" title={t("detail.flagsTitle")}>
              <ul className="mt-1 flex flex-col gap-2">
                {project.review_flags.map((flag) => (
                  <li key={flag} className="flex flex-wrap items-center gap-2">
                    <ReviewFlagBadge flag={flag} />
                    <span>{t(`flagNotes.${flag}`)}</span>
                  </li>
                ))}
              </ul>
            </Notice>
          )}
          <section aria-labelledby="requirement" className="flex flex-col gap-4">
            <SectionHeader id="requirement" title={t("detail.requirement")} />
            {sameSet ? (
              <AnswerSummary
                set={questions.data}
                answers={requirement.answers}
                labels={{ yes: common("yes"), no: common("no"), notSure: common("notSure") }}
                notAnswered={getTranslator("Requirement")("notAnswered")}
              />
            ) : (
              <Notice tone="info">
                {t("detail.versionMismatch", { version: requirement.question_set_version })}
              </Notice>
            )}
          </section>
          {engagements.data && (
            <OpsEngagements
              view={engagements.data}
              names={Object.fromEntries((categories.data ?? []).map((c) => [c.code, c.name]))}
            />
          )}
          <OpsPlanList projectId={projectId} />
        </div>

        {/* Phones: the review and decision first, the long requirement after. */}
        <aside className="order-first flex flex-col gap-6 lg:order-none">
          <Card size="sm">
            <CardHeader>
              <CardTitle className="text-base">
                <h2>{t("detail.review")}</h2>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {item ? (
                <ClaimControl item={item} />
              ) : (
                project.status === "SUBMITTED" && <p>{t("detail.notQueued")}</p>
              )}
              <DecisionPanel
                projectId={project.project_id}
                status={project.status}
                claimedByMe={Boolean(item?.claimed_by_me)}
                eligibility={detail.data.eligibility}
              />
            </CardContent>
          </Card>
          {(detail.data.eligibility.assessment || project.status === "ACCEPTED") && (
            <Card size="sm">
              <CardHeader>
                <CardTitle className="text-base">
                  <h2>{t("eligibility.title")}</h2>
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2 text-sm">
                {detail.data.eligibility.assessment ? (
                  <>
                    <ul className="flex flex-col gap-2">
                      {detail.data.eligibility.assessment.map((result) => (
                        <li key={result.item_id} className="flex flex-col">
                          <span className="font-medium">
                            {detail.data.eligibility.items.find((i) => i.id === result.item_id)?.label ??
                              result.item_id}
                            {": "}
                            {result.outcome === "PASSED" ? t("eligibility.passed") : t("eligibility.failed")}
                          </span>
                          {result.note && <span className="text-muted-foreground">{result.note}</span>}
                        </li>
                      ))}
                    </ul>
                    {detail.data.eligibility.assessed_at && (
                      <p className="break-all text-xs text-muted-foreground">
                        {t("eligibility.recorded", {
                          email: detail.data.eligibility.assessed_by_email ?? "",
                          date: formatDate(detail.data.eligibility.assessed_at),
                        })}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-muted-foreground">{t("eligibility.legacy")}</p>
                )}
              </CardContent>
            </Card>
          )}
          <Card size="sm">
            <CardHeader>
              <CardTitle className="text-base">
                <h2>{t("decision.historyTitle")}</h2>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="flex flex-col gap-3">
                {detail.data.history.map((entry, index) => (
                  <li key={`${entry.at}-${index}`} className="flex flex-col gap-1 text-sm">
                    <span className="flex flex-wrap items-center gap-2">
                      <StatusBadge kind="project" status={entry.to_status} />
                      <span className="text-muted-foreground">{formatDate(entry.at)}</span>
                    </span>
                    {entry.actor_email && (
                      <span className="break-all text-muted-foreground">
                        {t("decision.by", { email: entry.actor_email })}
                      </span>
                    )}
                    {entry.reason && <span className="whitespace-pre-line">{entry.reason}</span>}
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
          <Card size="sm">
            <CardHeader>
              <CardTitle className="text-base">
                <h2>{t("detail.contact")}</h2>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm break-all">
                {detail.data.owner_email ?? (
                  <span className="text-muted-foreground">{t("detail.noEmail")}</span>
                )}
              </p>
            </CardContent>
          </Card>
          <Card size="sm">
            <CardHeader>
              <CardTitle className="text-base">
                <h2>{t("detail.files")}</h2>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {files.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("detail.noFiles")}</p>
              ) : (
                <ul className="divide-y divide-border">
                  {files.map((file) => (
                    <li key={file.file_id}>
                      <FileRow
                        name={file.file_name}
                        mime={file.content_type}
                        size={file.size_bytes}
                        state={file.state}
                        actions={
                          file.state === "AVAILABLE" && (
                            <DownloadButton fileId={file.file_id} name={file.file_name} staff />
                          )
                        }
                      />
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </PageContainer>
  );
}
