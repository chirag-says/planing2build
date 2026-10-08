import { FileTextIcon, KeyRoundIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { ActionButton, ConfirmAction } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { ProjectBreadcrumb } from "@/components/plan2build/project-breadcrumb";
import {
  AssembleBuildRecord,
  BuildRecordSnapshot,
  OpsHandoverDocumentForm,
  OpsWarrantyForm,
} from "@/components/plan2build/records";
import { TextAction } from "@/components/plan2build/rfq";
import { EmptyState, Notice } from "@/components/plan2build/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatDate, formatDateTime } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import {
  BUILD_RECORD_TONE,
  HANDOVER_TONE,
  assembleMode,
  documentHasWarranty,
  handoverControls,
} from "@/lib/ops-admin";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Records")("openHandover") };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="text-base"><h2 id={id}>{title}</h2></CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">{children}</CardContent>
    </Card>
  );
}

// One project's handover and Build Record for operations (Slice 3.7C): open the handover, record
// documents received outside the portal and warranties, confirm ready, reopen, or issue without
// the owner's acknowledgement with a reason (EX-15); assemble, read and issue Build Record
// versions (EX-17; issuing needs the package, EX-18). The API decides every rule.
export default async function OpsHandoverPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  if (!UUID.test(projectId)) notFound();
  await requireVerifiedStaff(`/handover/${projectId}`);
  const { data, error, response } = await (await serverApi()).GET("/api/v1/ops/projects/{project_id}/handover", {
    params: { path: { project_id: projectId } },
  });
  if (response.status === 404) notFound();
  const t = getTranslator("Records");
  const o = getTranslator("Ops");
  if (!data) {
    return (
      <PageContainer width="wide">
        <PageHeader title={t("openHandover")} />
        <Notice tone="error" title={t("ops.loadError")}>{error?.error?.message}</Notice>
      </PageContainer>
    );
  }
  const base = `/api/v1/ops/projects/${projectId}/handover`;
  const h = data.handover;
  const controls = handoverControls(h?.state ?? null);
  const versions = data.build_records.versions;
  const title = t("opsTitle", { code: data.project_code });
  return (
    <PageContainer width="wide">
      <div className="flex flex-col gap-4">
        <ProjectBreadcrumb root={{ label: o("nav.execution"), href: "/execution" }}
          trail={[{ label: data.project_code, href: `/execution/${projectId}` }, { label: t("openHandover") }]} />
        <PageHeader title={title} description={t("ops.intro")}
          actions={h && (
            <Badge variant={HANDOVER_TONE[h.state]} data-testid="handover-state">{t(`states.${h.state}`)}</Badge>
          )} />
      </div>

      {!h && (
        <EmptyState icon={KeyRoundIcon} title={t("noHandover")} description={t("ops.openIntro")}
          action={controls.open && <ActionButton label={t("open")} url={base} />} />
      )}

      {h && (
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-6">
            <Section id="documents" title={t("documents")}>
              {h.documents.length === 0 ? (
                <p className="text-muted-foreground">{t("noDocuments")}</p>
              ) : (
                <ul className="flex flex-col divide-y divide-border">
                  {h.documents.map((d) => {
                    const linked = documentHasWarranty(d.id, h.warranties);
                    return (
                      <li key={d.id} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0" data-testid="ops-handover-document">
                        <span className="flex flex-wrap items-center gap-2">
                          <Badge variant="neutral">{t(`kinds.${d.kind}`)}</Badge>
                          <span className="font-medium">{d.title}</span>
                        </span>
                        <span className="text-muted-foreground">{t("ops.added", { when: formatDate(d.added_at), role: d.added_role })}</span>
                        {controls.editDocuments && !linked && (
                          <ConfirmAction id={`remove-${d.id}`} label={t("ops.remove")} url={`${base}/documents/${d.id}/remove`}
                            title={t("ops.removeTitle", { title: d.title })} description={t("ops.removeBody")} />
                        )}
                        {controls.editDocuments && linked && <p className="text-muted-foreground">{t("ops.linkedToWarranty")}</p>}
                      </li>
                    );
                  })}
                </ul>
              )}
              {controls.editDocuments && (
                <div className="flex flex-col gap-2 border-t border-border pt-3">
                  <h3 className="font-medium">{t("addDocument")}</h3>
                  <p className="text-muted-foreground">{t("upload")}</p>
                  <OpsHandoverDocumentForm projectId={projectId} />
                </div>
              )}
            </Section>

            <Section id="warranties" title={t("warranties")}>
              {h.warranties.length === 0 ? (
                <p className="text-muted-foreground">{t("ops.noWarranties")}</p>
              ) : (
                <ul className="flex flex-col gap-1">
                  {h.warranties.map((w) => (
                    <li key={w.id}>{t("warranty", { item: w.item, term: w.term, expiry: formatDate(w.expiry_date), installer: w.installer })}</li>
                  ))}
                </ul>
              )}
              {controls.editDocuments && (
                <div className="flex flex-col gap-2 border-t border-border pt-3">
                  <h3 className="font-medium">{t("addWarranty")}</h3>
                  <OpsWarrantyForm projectId={projectId} documents={h.documents} />
                </div>
              )}
            </Section>

            {h.statement_text && (
              <Section id="statement" title={t("ops.statement")}>
                <blockquote className="border-l-2 border-border pl-3">{h.statement_text}</blockquote>
              </Section>
            )}
          </div>

          <aside className="order-first flex flex-col gap-6 lg:order-none">
            <Section id="next" title={t("ops.nextStep")}>
              {controls.confirmReady && (
                <>
                  <p className="text-muted-foreground">{t("ops.readyIntro")}</p>
                  <ActionButton label={t("ready")} url={`${base}/ready`} />
                </>
              )}
              {controls.reopenOrIssue && (
                <>
                  <p className="text-muted-foreground">{t("ops.waitingForOwner")}</p>
                  <TextAction id="reopen" label={t("reopen")} field="reason" url={`${base}/reopen`} />
                  <ConfirmAction id="issue-without" reason variant="destructive" label={t("ops.issueWithout")}
                    url={`${base}/issue-without-acknowledgement`} title={t("ops.issueWithoutTitle")}
                    description={t("ops.issueWithoutBody")} />
                </>
              )}
              {controls.assemble && <p className="text-muted-foreground">{t("ops.closed")}</p>}
            </Section>
            <Section id="timeline" title={t("ops.timeline")}>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                <dt className="text-muted-foreground">{t("ops.openedAt")}</dt>
                <dd>{formatDateTime(h.opened_at)}</dd>
                {h.ready_at && (
                  <>
                    <dt className="text-muted-foreground">{t("ops.readyAt")}</dt>
                    <dd>{formatDateTime(h.ready_at)}</dd>
                  </>
                )}
                {h.acknowledged_at && (
                  <>
                    <dt className="text-muted-foreground">{t("ops.acknowledgedAt")}</dt>
                    <dd>{formatDateTime(h.acknowledged_at)}</dd>
                  </>
                )}
                {h.issued_at && (
                  <>
                    <dt className="text-muted-foreground">{t("ops.issuedAt")}</dt>
                    <dd>{formatDateTime(h.issued_at)}</dd>
                  </>
                )}
              </dl>
              {h.issued_without_acknowledgement && h.issue_reason && (
                <p>{t("ops.issueReason", { reason: h.issue_reason })}</p>
              )}
              <Link href="/admin/acknowledgement-statements" className="underline underline-offset-4">
                {t("ops.statementsLink")}
              </Link>
            </Section>
          </aside>
        </div>
      )}

      <Section id="build-record" title={t("buildRecord")}>
        {versions.length === 0 ? (
          <EmptyState icon={FileTextIcon} title={t("noBuildRecord")} description={t("ops.assembleWhen")} />
        ) : (
          <ul className="flex flex-col gap-3">
            {versions.map((v) => (
              <li key={v.id} className="flex flex-col gap-2 rounded-md border border-border p-3" data-testid="ops-build-record">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{t("version", { version: v.version_no, state: t(`versionStates.${v.state}`) })}</span>
                  <Badge variant={BUILD_RECORD_TONE[v.state]}>{t(`ops.basis.${v.basis}`)}</Badge>
                </span>
                {v.issued_at && <span className="text-muted-foreground">{t("ops.issuedOn", { when: formatDateTime(v.issued_at) })}</span>}
                {v.correction_reason && <span>{t("correction", { reason: v.correction_reason })}</span>}
                {v.snapshot_sha256 && <span className="font-mono text-xs break-all">sha256 {v.snapshot_sha256}</span>}
                {v.state === "DRAFT" && <ActionButton label={t("issue", { version: v.version_no })} url={`/api/v1/ops/build-records/${v.id}/issue`} />}
                <BuildRecordSnapshot recordId={v.id} />
              </li>
            ))}
          </ul>
        )}
        {controls.assemble && <AssembleBuildRecord projectId={projectId} mode={assembleMode(versions)} />}
      </Section>
    </PageContainer>
  );
}
