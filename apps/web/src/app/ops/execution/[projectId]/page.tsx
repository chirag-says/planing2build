import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { JsonForm } from "@/components/plan2build/build-plan";
import { OpsEvidenceUpload, OpsStageUpdates } from "@/components/plan2build/execution";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { TextAction } from "@/components/plan2build/rfq";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("nav.execution") };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// One project's execution for operations (Slice 3.7A, functional): stages, confirm or return a
// completion request with a reason (EX-03); for an outside contractor, photos and updates entered
// with how they were received (EX-02) and its "received" marks. JSON editors are acceptable here
// (H-06).
export default async function OpsProjectExecutionPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  if (!UUID.test(projectId)) notFound();
  await requireVerifiedStaff(`/execution/${projectId}`);
  const api = await serverApi();
  const path = { params: { path: { project_id: projectId } } };
  const [execution, marks] = await Promise.all([
    api.GET("/api/v1/ops/projects/{project_id}/execution", path),
    api.GET("/api/v1/ops/projects/{project_id}/payment-marks", path),
  ]);
  if (!execution.data) notFound();
  const t = getTranslator("Execution");
  const data = execution.data;
  const outside = data.contractor?.party === "OUTSIDE";
  return (
    <PageContainer width="wide">
      <PageHeader title={t("opsProject", { code: data.project_code })}
        description={data.contractor ? t("contractor", { name: `${data.contractor.name ?? ""} · ${data.contractor.party}` }) : t("noContractor")} />
      <span className="flex flex-wrap gap-4 text-sm">
        <Link href={`/assurance/${projectId}`} className="underline underline-offset-4">{getTranslator("Ops")("nav.assurance")}</Link>
        <Link href={`/handover/${projectId}`} className="underline underline-offset-4">{getTranslator("Records")("openHandover")}</Link>
        <Link href={`/rfqs/project/${projectId}`} className="underline underline-offset-4">{getTranslator("Rfq")("opsProjectLink")}</Link>
      </span>
      <ol className="flex flex-col gap-2">
        {data.stages.map((s) => (
          <li key={s.id} className="flex flex-col gap-2 rounded-md border border-border p-3 text-sm" data-testid={`ops-stage-${s.stage_number}-${s.floor ?? "x"}`}>
            <span className="font-medium">
              {s.stage_number}. {s.name} {s.floor ?? ""} · <span data-testid="stage-state">{t(`states.${s.state}`)}</span>
              {s.is_gate && s.gate_status && ` · ${t("gate", { status: t(`gates.${s.gate_status}`) })}`}
              {` · ${t("updateCount", { count: s.update_count })}`}
            </span>
            <span className="font-mono text-xs text-muted-foreground">{s.id}</span>
            <OpsStageUpdates stageId={s.id} />
            {outside && s.state !== "COMPLETED" && (
              <details>
                <summary className="cursor-pointer">{t("onBehalf")}</summary>
                <JsonForm id={`ops-update-${s.id}`} label={t("onBehalf")} method="POST"
                  url={`/api/v1/ops/stages/${s.id}/updates`} submitLabel={t("send")} once
                  initial={JSON.stringify({ kind: "PROGRESS", note: "", file_ids: [], reason: "" }, null, 2)} />
              </details>
            )}
            {s.state === "COMPLETION_REQUESTED" && (
              <div className="grid gap-3 sm:grid-cols-2">
                <TextAction id={`confirm-${s.id}`} label={t("opsConfirm")} field="reason"
                  url={`/api/v1/ops/stages/${s.id}/confirm`} extra={{ version: s.version }} />
                <TextAction id={`return-${s.id}`} label={t("opsReturn")} field="reason"
                  url={`/api/v1/ops/stages/${s.id}/return`} extra={{ version: s.version }} />
              </div>
            )}
          </li>
        ))}
      </ol>
      {outside && (
        <section aria-labelledby="on-behalf" className="flex flex-col gap-3">
          <SectionHeader id="on-behalf" title={t("onBehalf")} />
          <OpsEvidenceUpload projectId={projectId} />
          <ul className="flex flex-col gap-2 text-sm">
            {(marks.data?.milestones ?? []).map((m) => (
              <li key={m.stage_instance_id}>
                <JsonForm id={`received-${m.stage_instance_id}`} label={`${t("receivedMark")} · ${m.stage_number}`}
                  method="POST" url={`/api/v1/ops/stages/${m.stage_instance_id}/payment-mark`} submitLabel={t("send")} once
                  initial={JSON.stringify({ value: "YES", reason: "" }, null, 2)} />
              </li>
            ))}
          </ul>
        </section>
      )}
    </PageContainer>
  );
}
