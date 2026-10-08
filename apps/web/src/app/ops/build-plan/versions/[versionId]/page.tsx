import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import {
  ActionButton,
  ConfirmAction,
  DownloadButton,
  JsonForm,
  ReasonAction,
  ScopeForm,
  SignDocumentForm,
} from "@/components/plan2build/build-plan";
import { SnapshotView } from "@/components/plan2build/build-plan-view";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { canRefreshCriteria, canRevokeSignoff } from "@/lib/ops-admin";
import { requireVerifiedStaff } from "@/lib/staff";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const metadata: Metadata = { title: getTranslator("BuildPlan")("title") };

// Drafting, review, sign-off and issue of one version (Slice 3.5, functional; JSON editors for
// the bulk content). The API refuses every edit outside DRAFT.
export default async function OpsVersionPage({ params }: { params: Promise<{ versionId: string }> }) {
  const { versionId } = await params;
  if (!UUID.test(versionId)) notFound();
  await requireVerifiedStaff(`/build-plan/versions/${versionId}`);
  const api = await serverApi();
  const { data, response } = await api.GET("/api/v1/ops/build-plan-versions/{version_id}", {
    params: { path: { version_id: versionId } },
  });
  if (response.status === 404 || !data) notFound();
  const snap = data.snapshot;
  const projectId = snap.project.id;
  const [plan, cards] = await Promise.all([
    api.GET("/api/v1/ops/projects/{project_id}/build-plan", { params: { path: { project_id: projectId } } }),
    api.GET("/api/v1/ops/item-rate-cards"),
  ]);
  const t = getTranslator("BuildPlan");
  const state = snap.version.state;
  const base = `/api/v1/ops/build-plan-versions/${versionId}`;
  const approvedSets = (plan.data?.design_requests ?? []).flatMap((r) => r.sets.filter((s) => s.state === "APPROVED"));
  const published = (cards.data ?? []).filter((c) => c.status === "PUBLISHED");
  const values = snap.values.map((v) => ({
    code: v.code,
    applicability: v.applicability,
    value_text: v.value,
    basis: v.basis,
    not_applicable_reason: v.not_applicable_reason,
  }));
  const boq = {
    rate_card_id: snap.rate_card?.id ?? published[0]?.id ?? "",
    lines: snap.boq.length
      ? snap.boq.map((b) => ({
          item_code: b.item_code,
          quantity: b.quantity,
          quantity_basis: b.quantity_basis,
          drawing_file_id: b.drawing_file_id,
          basis_note: b.basis_note,
          stage_number: b.stage_number,
          spec_line_codes: b.spec_line_codes,
        }))
      : [],
  };
  const schedule = snap.schedule.map((e) => ({
    entry_key: e.entry_key,
    duration_days: e.duration_days,
    predecessors: e.predecessors,
  }));
  const structural = snap.values.filter((v) => v.is_structural).map((v) => v.code);
  return (
    <PageContainer width="wide">
      <PageHeader title={`${snap.project.code}: ${t("version", { number: snap.version.version_no })}`} />
      <Link href={`/projects/${projectId}/build-plan`} className="text-sm underline underline-offset-4">
        {t("ops.projectTitle", { code: snap.project.code })}
      </Link>
      <div className="flex flex-wrap gap-2">
        {data.issued_document_id && (
          <DownloadButton audience="ops" projectId={projectId} fileId={data.issued_document_id} label={t("downloadIssued")} />
        )}
        {data.accepted_document_id && (
          <DownloadButton audience="ops" projectId={projectId} fileId={data.accepted_document_id} label={t("downloadAccepted")} />
        )}
      </div>
      {state === "DRAFT" && (
        <section aria-labelledby="draft" className="flex flex-col gap-4">
          <SectionHeader id="draft" title={t("version", { number: snap.version.version_no })} />
          {data.missing.length > 0 && <Notice tone="info">{t("ops.missing", { items: data.missing.join(", ") })}</Notice>}
          <ul className="flex flex-col gap-1 text-sm">
            {approvedSets.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-2">
                {t("set", { number: s.set_no })} ({s.files.length})
                <ActionButton label={t("ops.useSet")} method="PUT" url={`${base}/drawing-set`} body={{ set_id: s.id }} once={false}
                  variant="outline" />
              </li>
            ))}
          </ul>
          <JsonForm id="values-json" label={t("ops.valuesJson")} method="PUT" url={`${base}/values`} wrap="values"
            initial={JSON.stringify(values, null, 1)} submitLabel={t("ops.save")} />
          <JsonForm id="boq-json" label={t("ops.boqJson")} method="PUT" url={`${base}/boq`}
            initial={JSON.stringify(boq, null, 1)} submitLabel={t("ops.save")} />
          <JsonForm id="schedule-json" label={t("ops.scheduleJson")} method="PUT" url={`${base}/schedule`} wrap="entries"
            initial={JSON.stringify(schedule, null, 1)} submitLabel={t("ops.save")} />
          <ScopeForm versionId={versionId} scope={snap.scope} />
          {canRefreshCriteria(state) && snap.values.length > 0 && (
            <details className="text-sm">
              <summary className="cursor-pointer font-medium">{t("ops.refreshTitle")}</summary>
              <p className="my-2 text-muted-foreground">{t("ops.refreshIntro")}</p>
              <ul className="flex flex-col gap-2">
                {snap.values.map((v) => (
                  <li key={v.code} className="flex flex-col gap-1 rounded-md border border-border p-2" data-testid={`refresh-${v.code}`}>
                    <span className="font-medium">{v.code} · {v.item}</span>
                    <span className="text-muted-foreground">{v.criteria}</span>
                    <ActionButton label={t("ops.refresh")} url={`${base}/values/${encodeURIComponent(v.code)}/refresh`} once={false}
                      variant="outline" />
                  </li>
                ))}
              </ul>
            </details>
          )}
          <ActionButton label={t("ops.submit")} url={`${base}/submit`} />
          <ReasonAction label={t("ops.withdraw")} url={`${base}/withdraw`} />
        </section>
      )}
      {state === "IN_REVIEW" && (
        <section aria-labelledby="review" className="flex flex-col gap-4">
          <SectionHeader id="review" title={t("signoffs")} />
          {snap.unsigned_structural_lines.length > 0 && (
            <Notice tone="info">{t("ops.missing", { items: snap.unsigned_structural_lines.join(", ") })}</Notice>
          )}
          <SignDocumentForm projectId={projectId} versionId={versionId}
            codes={snap.unsigned_structural_lines.length ? snap.unsigned_structural_lines : structural} />
          <ActionButton label={t("ops.issue")} url={`${base}/issue`} />
          <ReasonAction label={t("ops.return")} url={`${base}/return`} />
          <ReasonAction label={t("ops.withdraw")} url={`${base}/withdraw`} />
        </section>
      )}
      {state === "ISSUED" && <ReasonAction label={t("ops.withdraw")} url={`${base}/withdraw`} />}
      {snap.signoffs.some((s) => canRevokeSignoff(state, s.state)) && (
        <section aria-labelledby="revoke" className="flex flex-col gap-3">
          <SectionHeader id="revoke" title={t("ops.revokeSection")}
            description={state === "IN_REVIEW" ? t("ops.revokeBeforeIssue") : t("ops.revokeAfterIssue")} />
          <ul className="flex flex-col gap-3 text-sm">
            {snap.signoffs.filter((s) => canRevokeSignoff(state, s.state)).map((s) => (
              <li key={s.id} className="flex flex-col gap-2 rounded-md border border-border p-3" data-testid={`signoff-${s.id}`}>
                {/* The full sign-off (registration, document) is in the snapshot below; this names the line. */}
                <span className="font-medium">{s.line_code} · {s.engineer_name}</span>
                <ConfirmAction id={`revoke-${s.id}`} reason label={t("ops.revoke")} url={`/api/v1/ops/signoffs/${s.id}/revoke`}
                  title={t("ops.revokeTitle", { line: s.line_code })}
                  description={state === "IN_REVIEW" ? t("ops.revokeBeforeIssue") : t("ops.revokeAfterIssue")}
                  done={t("ops.revoked")} />
              </li>
            ))}
          </ul>
        </section>
      )}
      <SnapshotView view={snap} />
    </PageContainer>
  );
}
