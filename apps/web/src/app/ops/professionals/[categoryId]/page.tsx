import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ClaimControl } from "@/components/plan2build/claim-control";
import { DownloadButton } from "@/components/plan2build/download-button";
import {
  DecisionControls,
  PortfolioReview,
  RecordCheckForm,
  SuspensionControl,
} from "@/components/plan2build/ops-professional-review";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { ProjectBreadcrumb } from "@/components/plan2build/project-breadcrumb";
import { Notice } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("professionals.detailTitle") };

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="text-base"><h2>{title}</h2></CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">{children}</CardContent>
    </Card>
  );
}

// One category's verification: profile and contact (operations only), the requirements with
// what is still unmet, documents through logged links, references, portfolio review, recorded
// checks, the decision (with the reviewer's claim), suspension and the history.
export default async function OpsProfessionalCategoryPage({
  params,
}: {
  params: Promise<{ categoryId: string }>;
}) {
  const { categoryId } = await params;
  const staff = await requireVerifiedStaff(`/professionals/${categoryId}`);
  const isOps = staff.roles.includes("OPS");
  if (!isOps && !staff.roles.includes("ADMIN")) notFound();
  const response = await (await serverApi()).GET("/api/v1/ops/professional-categories/{category_id}", {
    params: { path: { category_id: categoryId } },
  });
  if (response.response.status === 404 || response.response.status === 422) notFound();
  const detail = response.data;
  if (!detail) throw new Error("the review could not be loaded");
  const t = getTranslator("Ops");
  const checks = getTranslator("Checks");
  const pro = getTranslator("Pro");
  const profile = detail.profile;
  const claimedByMe = Boolean(detail.queue_item?.claimed_by_me);
  const title = `${profile.display_name ?? profile.firm_name ?? "?"} · ${detail.category_name}`;

  return (
    <PageContainer width="wide">
      <div className="flex flex-col gap-4">
        <ProjectBreadcrumb root={{ label: t("professionals.title"), href: "/professionals" }} trail={[{ label: title }]} />
        <PageHeader title={title} actions={<StatusBadge kind="listing" status={detail.listing_state} withLabel />} />
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-6">
          <Section title={t("professionals.requirements")}>
            <ul className="flex flex-col gap-2">
              {detail.requirements.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-2">
                  <span>{r.label}{r.level === "WHERE_APPLICABLE" && ` (${checks("level.WHERE_APPLICABLE")})`}</span>
                  <Badge variant={detail.unmet.includes(r.id) ? "warning" : "success"}>
                    {detail.unmet.includes(r.id) ? t("professionals.unmet") : t("professionals.met")}
                  </Badge>
                </li>
              ))}
            </ul>
          </Section>
          <Section title={t("professionals.documents")}>
            {detail.documents.length === 0 ? <p className="text-muted-foreground">{t("professionals.noneInState")}</p> : (
              <ul className="flex flex-col gap-2">
                {detail.documents.map((d) => (
                  <li key={d.document_id} className="flex flex-wrap items-center justify-between gap-2">
                    <span>
                      {pro(`category.kinds.${d.kind}`)}
                      {Object.entries(d.details).map(([k, v]) => ` · ${k}: ${v}`).join("")}
                    </span>
                    {d.file?.state === "AVAILABLE" && <DownloadButton fileId={d.file.file_id} name={d.file.file_name} staff />}
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <Section title={t("professionals.references")}>
            {detail.references.length === 0 ? <p className="text-muted-foreground">{t("professionals.noneInState")}</p> : (
              <ul className="flex flex-col gap-1">
                {detail.references.map((r) => (
                  <li key={r.reference_id}>{r.name} · {r.phone} · {r.project_note}</li>
                ))}
              </ul>
            )}
          </Section>
          <Section title={t("professionals.portfolio")}>
            {detail.portfolio.length === 0 ? <p className="text-muted-foreground">{t("professionals.noneInState")}</p> : (
              <ul className="flex flex-col gap-2">
                {detail.portfolio.map((p) => (
                  <li key={p.item_id} className="flex flex-wrap items-center justify-between gap-2">
                    <span>{p.caption} · {pro(`portfolio.review.${p.review_state}`)}</span>
                    <span className="flex gap-2">
                      {p.file?.state === "AVAILABLE" && <DownloadButton fileId={p.file.file_id} name={p.file.file_name} staff />}
                      {isOps && p.review_state === "PENDING" && <PortfolioReview itemId={p.item_id} />}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <Section title={t("professionals.checks")}>
            {detail.checks.length === 0 ? <p className="text-muted-foreground">{t("professionals.noChecks")}</p> : (
              <ul className="flex flex-col gap-2">
                {detail.checks.map((c, i) => (
                  <li key={`${c.recorded_at}-${i}`} className="flex flex-col">
                    <span className="font-medium">{checks(`kind.${c.kind}`)}: {c.subject} · {checks(`outcome.${c.outcome}`)}</span>
                    <span className="text-xs text-muted-foreground">
                      {formatDate(c.recorded_at)}{c.recorded_by_email && ` · ${c.recorded_by_email}`}
                      {c.internal_note && ` · ${c.internal_note}`}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>

        <aside className="order-first flex flex-col gap-6 lg:order-none">
          {detail.queue_item && isOps && (
            <Section title={t("detail.review")}>
              <ClaimControl item={detail.queue_item} />
            </Section>
          )}
          {detail.case_open && isOps && (
            claimedByMe ? (
              <>
                <Section title={t("professionals.recordCheck")}><RecordCheckForm detail={detail} /></Section>
                <Section title={t("professionals.decisions")}><DecisionControls detail={detail} /></Section>
              </>
            ) : (
              <Notice tone="info">{t("professionals.claimFirst")}</Notice>
            )
          )}
          {(detail.listing_state === "LISTED" || detail.listing_state === "SUSPENDED") && (
            <Section title={t("professionals.suspension")}><SuspensionControl detail={detail} /></Section>
          )}
          <Section title={t("professionals.contact")}>
            <p className="break-all">{detail.email ?? t("professionals.noneInState")}</p>
            <p>{profile.firm_name}</p>
            <p>{t("professionals.location")}: {profile.base_locality ?? t("professionals.noneInState")}
              {profile.base_point && ` (${profile.base_point.lat}, ${profile.base_point.lng}), ${profile.service_radius_km} km`}</p>
            {profile.bio && <p className="whitespace-pre-line text-muted-foreground">{profile.bio}</p>}
          </Section>
          <Section title={t("professionals.history")}>
            <ol className="flex flex-col gap-2">
              {detail.history.map((h, i) => (
                <li key={`${h.at}-${i}`} className="flex flex-col">
                  <span className="flex flex-wrap items-center gap-2">
                    <StatusBadge kind="listing" status={h.to_state} />
                    <span className="text-muted-foreground">{h.event} · {formatDate(h.at)}</span>
                  </span>
                  <span className="text-xs text-muted-foreground">{h.actor_role}{h.actor_email && ` · ${h.actor_email}`}</span>
                  {h.reason && <span className="whitespace-pre-line">{h.reason}</span>}
                </li>
              ))}
            </ol>
          </Section>
        </aside>
      </div>
    </PageContainer>
  );
}
