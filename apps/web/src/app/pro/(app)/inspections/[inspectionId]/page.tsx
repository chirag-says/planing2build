import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { AuditorResults, SubmitInspection } from "@/components/plan2build/assurance";
import { ActionButton } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { DownloadLink } from "@/components/plan2build/rfq";
import { Notice } from "@/components/plan2build/states";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireOnboarded } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Assurance")("proTitle") };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// One assigned inspection (Slice 3.7B, functional): the stage, the checklist with each line's
// criteria, the accepted drawings; readiness, results with findings, submission with a code.
// Online only (EX-10). No supplier, brand, product, price or homeowner contact.
export default async function AuditorInspectionPage({ params }: { params: Promise<{ inspectionId: string }> }) {
  await requireOnboarded();
  const { inspectionId } = await params;
  if (!UUID.test(inspectionId)) notFound();
  const { data, response } = await (await serverApi()).GET("/api/v1/pro/inspections/{inspection_id}", {
    params: { path: { inspection_id: inspectionId } },
  });
  if (response.status === 401) redirect("/sign-in");
  if (!data) notFound();
  const t = getTranslator("Assurance");
  const base = `/api/v1/pro/inspections/${inspectionId}`;
  return (
    <PageContainer>
      <PageHeader
        title={`${data.project_code} · ${t("inspection", { gate: data.gate, stage: data.stage_name })}`}
        description={`${t(`kinds.${data.kind}`)} · ${t(`states.${data.state}`)} · ${t("checklist", { version: data.checklist_version })}`}
      />
      {data.locality && <p className="text-sm">{data.locality}</p>}
      {data.visit_note && <p className="text-sm">{data.visit_note}</p>}
      {data.return_reason && <Notice tone="info">{t("returnReason", { reason: data.return_reason })}</Notice>}
      <section aria-labelledby="drawings" className="flex flex-col gap-2 text-sm">
        <SectionHeader id="drawings" title={t("drawings")} />
        <span className="flex flex-wrap gap-2">
          {data.drawings.map((d) => (
            <DownloadLink key={d.file_id} label={`${d.sheet_no ?? ""} ${d.title ?? d.drawing_class ?? ""}`.trim()}
              url={`${base}/files/${d.file_id}/url`} />
          ))}
        </span>
      </section>
      {data.state === "SCHEDULED" && <ActionButton label={t("ready")} url={`${base}/readiness`} />}
      {data.state === "IN_PROGRESS" && (
        <>
          <AuditorResults inspectionId={inspectionId} kind={data.kind} checkpoints={data.checkpoints} results={data.results} />
          <SubmitInspection inspectionId={inspectionId} />
        </>
      )}
      {data.state !== "SCHEDULED" && data.state !== "IN_PROGRESS" && (
        <ul className="flex flex-col gap-1 text-sm">
          {data.checkpoints.map((c) => {
            const r = data.results.find((x) => x.checkpoint_id === c.id);
            return <li key={c.id}>{c.code} {c.text}: {r ? t(`results.${r.result}`) : "-"}</li>;
          })}
        </ul>
      )}
    </PageContainer>
  );
}
