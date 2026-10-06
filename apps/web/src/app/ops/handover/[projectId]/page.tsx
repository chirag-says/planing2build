import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { OpsFileUpload } from "@/components/plan2build/assurance";
import { ActionButton, JsonForm } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { TextAction } from "@/components/plan2build/rfq";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Records")("openHandover") };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// One project's handover and Build Record for operations (Slice 3.7C, functional; JSON editors
// acceptable, H-06): open, record documents and warranties, confirm ready, reopen, issue without
// the owner's acknowledgement with a reason (EX-15); assemble and issue Build Record versions.
export default async function OpsHandoverPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  if (!UUID.test(projectId)) notFound();
  await requireVerifiedStaff(`/handover/${projectId}`);
  const { data } = await (await serverApi()).GET("/api/v1/ops/projects/{project_id}/handover", {
    params: { path: { project_id: projectId } },
  });
  if (!data) notFound();
  const t = getTranslator("Records");
  const base = `/api/v1/ops/projects/${projectId}/handover`;
  const h = data.handover;
  return (
    <PageContainer width="wide">
      <PageHeader title={t("opsTitle", { code: data.project_code })} />
      <section aria-labelledby="handover" className="flex flex-col gap-3 text-sm">
        <SectionHeader id="handover" title={t("handover")} />
        {!h && <ActionButton label={t("open")} url={base} />}
        {h && (
          <>
            <p data-testid="handover-state">{t(`states.${h.state}`)}</p>
            <ul className="flex flex-col gap-1">
              {h.documents.map((d) => (
                <li key={d.id}>{t(`kinds.${d.kind}`)}: {d.title} <span className="font-mono text-xs">{d.id}</span></li>
              ))}
              {h.warranties.map((w) => (
                <li key={w.id}>{t("warranty", { item: w.item, term: w.term, expiry: formatDate(w.expiry_date), installer: w.installer })}</li>
              ))}
            </ul>
            {h.state === "OPEN" && (
              <div className="grid gap-3 sm:grid-cols-2">
                <OpsFileUpload id="handover-file" url={`/api/v1/ops/projects/${projectId}/handover-files`} />
                <JsonForm id="handover-document" label={t("documentJson")} method="POST" url={`${base}/documents`}
                  submitLabel={t("send")} once initial={JSON.stringify({ kind: "MANUAL", title: "", file_id: "" }, null, 2)} />
                <JsonForm id="handover-warranty" label={t("warrantyJson")} method="POST" url={`${base}/warranties`}
                  submitLabel={t("send")} once
                  initial={JSON.stringify({ item: "", term: "", expiry_date: "", installer: "", spec_line_code: null, document_id: null }, null, 2)} />
                <ActionButton label={t("ready")} url={`${base}/ready`} />
              </div>
            )}
            {h.state === "READY" && (
              <div className="grid gap-3 sm:grid-cols-2">
                <TextAction id="reopen" label={t("reopen")} field="reason" url={`${base}/reopen`} />
                <TextAction id="issue-without" label={t("issueWithout")} field="reason" url={`${base}/issue-without-acknowledgement`} />
              </div>
            )}
          </>
        )}
      </section>
      <section aria-labelledby="build-record" className="flex flex-col gap-3 text-sm">
        <SectionHeader id="build-record" title={t("buildRecord")} />
        <ul className="flex flex-col gap-2">
          {data.build_records.versions.map((v) => (
            <li key={v.id} className="flex flex-col gap-1 rounded-md border border-border p-3" data-testid="ops-build-record">
              <span className="font-medium">{t("version", { version: v.version_no, state: t(`versionStates.${v.state}`) })} · {v.basis}</span>
              {v.correction_reason && <span>{t("correction", { reason: v.correction_reason })}</span>}
              {v.snapshot_sha256 && <span className="font-mono text-xs break-all">sha256 {v.snapshot_sha256}</span>}
              {v.state === "DRAFT" && <ActionButton label={t("issue", { version: v.version_no })} url={`/api/v1/ops/build-records/${v.id}/issue`} />}
            </li>
          ))}
        </ul>
        {h && (h.state === "ACKNOWLEDGED" || h.state === "ISSUED_BY_OPERATIONS") && (
          <JsonForm id="assemble" label={t("assemble")} method="POST" url={`/api/v1/ops/projects/${projectId}/build-record/assemble`}
            submitLabel={t("send")} once initial={JSON.stringify({ reason: null }, null, 2)} />
        )}
      </section>
    </PageContainer>
  );
}
