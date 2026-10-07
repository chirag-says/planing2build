import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { AssuranceSection } from "@/components/plan2build/assurance-view";
import { ActionButton } from "@/components/plan2build/build-plan";
import { UpdateForm } from "@/components/plan2build/execution";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { DownloadLink } from "@/components/plan2build/rfq";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireOnboarded } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Execution")("proTitle") };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// The engaged contractor's execution page (Slice 3.7A, functional): the accepted Build Plan's
// drawings, the stages with its own update counts, the update form (EX-02) and the "received"
// marks on payment milestones (EX-05). Only while the contractor engagement is active.
export default async function ProExecutionPage({ params }: { params: Promise<{ engagementId: string }> }) {
  await requireOnboarded();
  const { engagementId } = await params;
  if (!UUID.test(engagementId)) notFound();
  const api = await serverApi();
  const path = { params: { path: { engagement_id: engagementId } } };
  const [execution, marks, assurance] = await Promise.all([
    api.GET("/api/v1/pro/engagements/{engagement_id}/execution", path),
    api.GET("/api/v1/pro/engagements/{engagement_id}/payment-marks", path),
    api.GET("/api/v1/pro/engagements/{engagement_id}/assurance", path),
  ]);
  if (execution.response.status === 401) redirect("/sign-in");
  if (!execution.data || !marks.data || !assurance.data) notFound();
  const t = getTranslator("Execution");
  const data = execution.data;
  const base = `/api/v1/pro/engagements/${engagementId}`;
  const label = (s: { stage_number: number; name: string; floor?: number | null }) =>
    `${s.stage_number}. ${s.name}${s.floor === null || s.floor === undefined ? "" : ` (${s.floor})`}`;
  const labels = new Map(data.stages.map((s) => [s.id, label(s)]));
  const open = data.stages.filter((s) => s.state !== "COMPLETED");
  return (
    <PageContainer>
      <PageHeader title={t("proTitle")} description={data.project_code} />
      <section aria-labelledby="drawings" className="flex flex-col gap-2 text-sm">
        <SectionHeader id="drawings" title={data.build_plan_version_no
          ? t("drawings", { version: data.build_plan_version_no }) : t("noDrawings")} />
        <span className="flex flex-wrap gap-2">
          {data.drawings.map((d) => (
            <DownloadLink key={d.file_id} label={`${d.sheet_no ?? ""} ${d.title ?? d.drawing_class ?? ""}`.trim()}
              url={`${base}/execution/files/${d.file_id}/url`} />
          ))}
        </span>
      </section>
      <section aria-labelledby="post" className="flex flex-col gap-3">
        <SectionHeader id="post" title={t("postTitle")} />
        <UpdateForm engagementId={engagementId} stages={open.map((s) => ({ id: s.id, label: label(s) }))} />
      </section>
      <section aria-labelledby="stage-list" className="flex flex-col gap-2">
        <SectionHeader id="stage-list" title={t("stage")} />
        <ol className="flex flex-col gap-2">
          {data.stages.map((s) => (
            <li key={s.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm"
              data-testid={`pro-stage-${s.stage_number}-${s.floor ?? "x"}`}>
              <span className="font-medium">{label(s)}</span>
              <span className="flex flex-wrap gap-x-3 text-muted-foreground">
                <span data-testid="stage-state">{t(`states.${s.state}`)}</span>
                {s.actual_start && <span>{t("started", { date: formatDate(s.actual_start) })}</span>}
                {s.actual_end && <span>{t("finished", { date: formatDate(s.actual_end) })}</span>}
                {s.is_gate && s.gate_status && <span>{t("gate", { status: t(`gates.${s.gate_status}`) })}</span>}
                <span>{t("updateCount", { count: s.update_count })}</span>
              </span>
            </li>
          ))}
        </ol>
      </section>
      <AssuranceSection data={assurance.data} engagementId={engagementId} />
      <section aria-labelledby="marks" className="flex flex-col gap-2">
        <SectionHeader id="marks" title={t("marks")} description={t("marksIntro")} />
        <ul className="flex flex-col gap-2">
          {marks.data.milestones.map((m) => (
            <li key={m.stage_instance_id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm">
              <span className="font-medium">{labels.get(m.stage_instance_id)} · {m.due ? t("due") : t("notDue")}</span>
              <span>{t("paid", { value: m.paid ? (m.paid.value === "YES" ? t("yes") : t("no")) : t("notMarked") })}</span>
              <span>{t("received", { value: m.received ? (m.received.value === "YES" ? t("yes") : t("no")) : t("notMarked") })}</span>
              <ActionButton variant="outline" label={m.received?.value === "YES" ? t("markNotReceived") : t("markReceived")}
                url={`${base}/stages/${m.stage_instance_id}/payment-mark`}
                body={{ value: m.received?.value === "YES" ? "NO" : "YES" }} />
            </li>
          ))}
        </ul>
      </section>
    </PageContainer>
  );
}
