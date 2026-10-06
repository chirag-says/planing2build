import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { OpsFileUpload } from "@/components/plan2build/assurance";
import { ActionButton, JsonForm } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { DownloadLink, TextAction } from "@/components/plan2build/rfq";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("nav.assurance") };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// One project's inspections and findings for operations (Slice 3.7B, functional; JSON editors
// acceptable, H-06): approve, return, cancel, capture a signed report, correct a report as a new
// version; findings: send a correction back, change the due date, re-inspect.
export default async function OpsProjectAssurancePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  if (!UUID.test(projectId)) notFound();
  await requireVerifiedStaff(`/assurance/${projectId}`);
  const { data } = await (await serverApi()).GET("/api/v1/ops/projects/{project_id}/assurance", {
    params: { path: { project_id: projectId } },
  });
  if (!data) notFound();
  const t = getTranslator("Assurance");
  return (
    <PageContainer width="wide">
      <PageHeader title={t("project", { code: data.project_code })} />
      <OpsFileUpload id="inspection-evidence" url={`/api/v1/ops/projects/${projectId}/inspection-evidence`} />
      <section aria-labelledby="inspections" className="flex flex-col gap-3">
        <SectionHeader id="inspections" title={t("title")} />
        {data.inspections.map((i) => {
          const url = `/api/v1/ops/inspections/${i.id}`;
          return (
            <div key={i.id} className="flex flex-col gap-2 rounded-md border border-border p-3 text-sm" data-testid="ops-inspection">
              <span className="font-medium">
                {t(`kinds.${i.kind}`)} · {t("inspection", { gate: i.gate, stage: i.stage_name })} {i.floor ?? ""} ·{" "}
                <span data-testid="inspection-state">{t(`states.${i.state}`)}</span>
              </span>
              <span>{i.auditor_code} ({i.auditor_name}) · {formatDate(i.scheduled_at)} · v{i.checklist_version}</span>
              <span className="font-mono text-xs">{i.id}</span>
              {i.outcome && <span>{i.outcome}</span>}
              {i.content_sha256 && <span className="font-mono text-xs">sha256 {i.content_sha256}</span>}
              <ul className="flex flex-col gap-1">
                {i.checkpoints.map((c) => {
                  const r = i.results.find((x) => x.checkpoint_id === c.id);
                  return (
                    <li key={c.id}>
                      <span className="font-mono text-xs">{c.id}</span> {c.code} {c.text}: {r ? t(`results.${r.result}`) : "-"}
                      {r?.severity && ` · ${r.severity}: ${r.description}`}
                    </li>
                  );
                })}
              </ul>
              {i.reports.map((r) => (
                <DownloadLink key={r.version} label={t("report", { version: r.version })} url={`${url}/reports/${r.version}/url`} />
              ))}
              {i.state === "SUBMITTED" && (
                <div className="grid gap-3 sm:grid-cols-2">
                  <ActionButton label={t("approve")} url={`${url}/approve`} />
                  <TextAction id={`return-${i.id}`} label={t("returnLabel")} field="reason" url={`${url}/return`} />
                </div>
              )}
              {(i.state === "SCHEDULED" || i.state === "IN_PROGRESS") && (
                <div className="grid gap-3 sm:grid-cols-2">
                  <TextAction id={`cancel-${i.id}`} label={t("cancelLabel")} field="reason" url={`${url}/cancel`} />
                  <JsonForm id={`capture-${i.id}`} label={t("capture")} method="POST" url={`${url}/capture`} submitLabel={t("send")} once
                    initial={JSON.stringify({ evidence_file_id: "", summary: "", results: i.checkpoints.map((c) => ({ checkpoint_id: c.id, result: "PASS" })) }, null, 2)} />
                </div>
              )}
              {i.state === "APPROVED" && (
                <TextAction id={`correct-${i.id}`} label={t("correctReport")} field="reason" url={`${url}/report-corrections`} />
              )}
            </div>
          );
        })}
      </section>
      <section aria-labelledby="findings" className="flex flex-col gap-3">
        <SectionHeader id="findings" title={t("findings")} />
        {data.findings.map((f) => {
          const url = `/api/v1/ops/non-conformances/${f.id}`;
          return (
            <div key={f.id} className="flex flex-col gap-2 rounded-md border border-border p-3 text-sm" data-testid="ops-finding">
              <span className="font-medium">{t("inspection", { gate: f.gate, stage: f.stage_name })} · {t(`ncStates.${f.state}`)} · {f.severity}</span>
              <span className="font-mono text-xs">{f.id}</span>
              <p>{f.description}</p>
              <span>{t("due", { date: formatDate(f.due_date) })}{f.overdue && ` · ${t("overdue")}`}</span>
              {f.state === "RECTIFICATION_SUBMITTED" && (
                <div className="grid gap-3 sm:grid-cols-2">
                  <TextAction id={`reopen-${f.id}`} label={t("reopen")} field="reason" url={`${url}/reopen`} />
                  <JsonForm id={`reinspect-${f.id}`} label={t("reinspect")} method="POST" url="/api/v1/ops/reinspections" submitLabel={t("send")} once
                    initial={JSON.stringify({ nc_ids: [f.id], appointment_id: "" }, null, 2)} />
                </div>
              )}
              {f.state === "OPEN" && (
                <JsonForm id={`ops-rectify-${f.id}`} label={t("opsRectify")} method="POST" url={`${url}/rectification`} submitLabel={t("send")} once
                  initial={JSON.stringify({ note: "", file_ids: [], reason: "" }, null, 2)} />
              )}
              {f.state !== "CLOSED" && (
                <JsonForm id={`due-${f.id}`} label={t("dueDateJson")} method="POST" url={`${url}/due-date`} submitLabel={t("send")} once
                  initial={JSON.stringify({ due_date: f.due_date, reason: "" }, null, 2)} />
              )}
            </div>
          );
        })}
      </section>
    </PageContainer>
  );
}
