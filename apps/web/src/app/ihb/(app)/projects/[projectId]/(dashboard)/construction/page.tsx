import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { BuildProgress } from "@/components/plan2build/build-progress";
import { AssuranceSection } from "@/components/plan2build/assurance-view";
import { ActionButton } from "@/components/plan2build/build-plan";
import { BuildRecordSection, HandoverSection } from "@/components/plan2build/records-view";
import { SectionHeader } from "@/components/plan2build/page-header";
import { TextAction } from "@/components/plan2build/rfq";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { hasStagesAndLines, loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  const area = getTranslator("Dashboard")("areas.construction");
  return { title: await projectTitle((await params).projectId, area) };
}

const FLOORS = { "-1": "basement", "0": "ground", "1": "first", "2": "second", "3": "third" } as const;

// Construction progress (Slice 3.7A, functional): each stage's state, actual dates and updates;
// the owner confirms or returns a completion request (EX-03) and marks milestone payments for
// their own records (EX-05). No planned dates or percentages (EX-04). Household members read.
export default async function ProjectConstructionPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const { project } = await loadProject(projectId);
  if (!hasStagesAndLines(project.status)) redirect(`/projects/${projectId}`);
  const api = await serverApi();
  const path = { params: { path: { project_id: projectId } } };
  const [execution, marks, assurance, handover, records] = await Promise.all([
    api.GET("/api/v1/projects/{project_id}/execution", path),
    api.GET("/api/v1/projects/{project_id}/payment-marks", path),
    api.GET("/api/v1/projects/{project_id}/assurance", path),
    api.GET("/api/v1/projects/{project_id}/handover", path),
    api.GET("/api/v1/projects/{project_id}/build-record", path),
  ]);
  if (!execution.data || !marks.data || !assurance.data || !handover.data || !records.data) {
    throw new Error("the stages could not be loaded");
  }
  const t = getTranslator("Execution");
  const w = getTranslator("Workspace");
  const data = execution.data;
  const floor = (f: number | null | undefined) => {
    const key = f === null || f === undefined ? undefined : FLOORS[String(f) as keyof typeof FLOORS];
    return key ? ` · ${w(`floors.${key}`)}` : "";
  };
  const labels = new Map(data.stages.map((s) => [s.id, `${s.stage_number}. ${s.name}${floor(s.floor)}`]));
  const yesNo = (m: { value: string; by_operations: boolean } | null | undefined) =>
    m ? `${m.value === "YES" ? t("yes") : t("no")}${m.by_operations ? ` (${t("byOps")})` : ""}` : t("notMarked");
  const base = `/api/v1/projects/${projectId}`;
  const contractor = data.contractor
    ? t("contractor", {
        name: `${data.contractor.name ?? ""}${data.contractor.party === "OUTSIDE" ? ` (${t("outsideContractor")})` : ""}`,
      })
    : t("noContractor");
  return (
    <section aria-labelledby="stages" className="flex flex-col gap-4">
      <SectionHeader id="stages" title={t("title")} description={t("intro")} />
      <p className="text-sm" data-testid="contractor">{contractor}</p>
      <BuildProgress stages={data.stages} label={(s) => labels.get(s.id) ?? s.name} />
      <ol className="flex flex-col gap-2">
        {data.stages.map((s) => (
          <li key={s.id} className="flex flex-col gap-2 rounded-md border border-border p-3 text-sm"
            data-testid={`stage-${s.stage_number}-${s.floor ?? "x"}`}>
            <span className="font-medium">{labels.get(s.id)}</span>
            <span className="flex flex-wrap gap-x-3 gap-y-1 text-muted-foreground">
              <span data-testid="stage-state">{t(`states.${s.state}`)}</span>
              {s.actual_start && <span>{t("started", { date: formatDate(s.actual_start) })}</span>}
              {s.actual_end && <span>{t("finished", { date: formatDate(s.actual_end) })}</span>}
              {s.is_gate && s.gate_status && <span>{t("gate", { status: t(`gates.${s.gate_status}`) })}</span>}
              {s.is_payment_milestone && <span>{t("milestone")}</span>}
              {s.update_count > 0 && (
                <Link className="underline underline-offset-4" href={`/projects/${projectId}/construction/${s.id}`}>
                  {t("viewUpdates")} ({s.update_count})
                </Link>
              )}
            </span>
            {data.is_owner && s.state === "COMPLETION_REQUESTED" && (
              <div className="flex flex-col gap-2">
                <ActionButton label={t("confirm")} url={`${base}/stages/${s.id}/confirm`} body={{ version: s.version }} />
                <TextAction id={`return-${s.id}`} label={t("returnLabel")} field="reason"
                  url={`${base}/stages/${s.id}/return`} extra={{ version: s.version }} />
              </div>
            )}
          </li>
        ))}
      </ol>
      <AssuranceSection data={assurance.data} reportBase={`/api/v1/projects/${projectId}/inspections`} />
      <HandoverSection projectId={projectId} view={handover.data} />
      <BuildRecordSection projectId={projectId} records={records.data} />
      <section aria-labelledby="marks" className="flex flex-col gap-3">
        <SectionHeader id="marks" title={t("marks")} description={t("marksIntro")} />
        <ul className="flex flex-col gap-2">
          {marks.data.milestones.map((m) => (
            <li key={m.stage_instance_id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm"
              data-testid="milestone">
              <span className="font-medium">{labels.get(m.stage_instance_id)} · {m.due ? t("due") : t("notDue")}</span>
              <span>{t("paid", { value: yesNo(m.paid) })}</span>
              <span>{t("received", { value: yesNo(m.received) })}</span>
              {data.is_owner && (
                <ActionButton variant="outline" label={m.paid?.value === "YES" ? t("markNotPaid") : t("markPaid")}
                  url={`${base}/stages/${m.stage_instance_id}/payment-mark`}
                  body={{ value: m.paid?.value === "YES" ? "NO" : "YES" }} />
              )}
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
