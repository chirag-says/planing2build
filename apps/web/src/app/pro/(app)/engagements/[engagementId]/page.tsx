import { ArrowLeftIcon, ArrowRightIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ProEndEngagementById } from "@/components/plan2build/engagements";
import { FileRow } from "@/components/plan2build/file-row";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { DownloadLink } from "@/components/plan2build/rfq";
import { Notice } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { rolesOf } from "@/lib/pro-console";
import { loadEngagements, loadOwnProfile, loadProRaw } from "@/lib/professional";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const metadata: Metadata = { title: getTranslator("Engagement")("title") };

// The professional's one page for a job once an engagement exists, whatever brought it (an
// accepted request or a selected quote; ADR-024): the family's contact, the plot pin and the
// files they share while it is active (N-08), and the work that belongs to this trade here: a
// contractor's construction, an architect's drawing requests, a structural engineer's sign-offs.
// Requests and quote invitations keep their own pages until then.
export default async function ProEngagementPage({ params }: { params: Promise<{ engagementId: string }> }) {
  const { engagementId } = await params;
  if (!UUID.test(engagementId)) notFound();
  const dashboard = await loadOwnProfile();
  const api = await serverApi();
  const [{ data, response }, raw, engagements] = await Promise.all([
    api.GET("/api/v1/pro/engagements/{engagement_id}", { params: { path: { engagement_id: engagementId } } }),
    loadProRaw(),
    loadEngagements(),
  ]);
  if (response.status === 404) notFound();
  if (!data) throw new Error("the engagement could not be loaded");
  const t = getTranslator("Engagement");
  const roles = rolesOf(dashboard);
  const active = data.state === "ACTIVE";
  const mine = engagements.find((e) => e.engagementId === engagementId);
  const stages = mine?.stages ?? [];
  const done = stages.filter((s) => s.state === "COMPLETED").length;
  const drawings = raw.drawings.filter((d) => d.project_code === data.project_code);
  const signoffs = raw.signoffs.filter((s) => s.project_code === data.project_code && s.state === "IN_REVIEW");
  const contact = data.family_contact;
  const none = t("notGiven");
  const base = `/api/v1/pro/engagements/${engagementId}`;

  return (
    <PageContainer>
      <Button asChild variant="ghost" className="self-start">
        <Link href="/projects">
          <ArrowLeftIcon aria-hidden="true" />
          {t("back")}
        </Link>
      </Button>
      <PageHeader
        title={data.project_code}
        description={`${data.category_name} · ${t(`origin.${data.origin === "RFQ_SELECTION" ? "rfq" : "connection"}`)} · ${
          data.ended_at ? t("endedAt", { date: formatDate(data.ended_at) }) : t("since", { date: formatDate(data.started_at) })
        }`}
        actions={<StatusBadge kind="engagement" status={data.state} withLabel />}
      />
      {!active && <Notice tone="info">{t("ended")}</Notice>}

      {contact && (
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-base">
              <h2>{t("family")}</h2>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]" data-testid="family-contact">
              <dt className="text-muted-foreground">{t("name")}</dt>
              <dd>{contact.name}</dd>
              <dt className="text-muted-foreground">{t("phone")}</dt>
              <dd>
                <a href={`tel:${contact.phone}`} className="underline underline-offset-4">{contact.phone}</a>
              </dd>
              <dt className="text-muted-foreground">{t("email")}</dt>
              <dd className="break-all">
                {contact.email ? (
                  <a href={`mailto:${contact.email}`} className="underline underline-offset-4">{contact.email}</a>
                ) : (
                  none
                )}
              </dd>
              {contact.site_address && (
                <>
                  <dt className="text-muted-foreground">{t("siteAddress")}</dt>
                  <dd className="whitespace-pre-line">{contact.site_address}</dd>
                </>
              )}
              {data.location && (
                <>
                  <dt className="text-muted-foreground">{t("location")}</dt>
                  <dd>
                    <a
                      href={`https://www.openstreetmap.org/?mlat=${data.location.lat}&mlon=${data.location.lng}#map=17/${data.location.lat}/${data.location.lng}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline underline-offset-4"
                    >
                      {t("openMap")}
                    </a>
                  </dd>
                </>
              )}
            </dl>
            {active && (
              <section aria-labelledby="shared" className="flex flex-col gap-2">
                <h3 id="shared" className="text-sm font-medium">{t("files")}</h3>
                {data.shared_files.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{t("noFiles")}</p>
                ) : (
                  <ul className="divide-y divide-border">
                    {data.shared_files.map((file) => (
                      <li key={file.file_id}>
                        <FileRow
                          name={file.file_name}
                          mime={file.content_type}
                          size={file.size_bytes}
                          state={file.state}
                          actions={<DownloadLink label={t("download")} url={`${base}/files/${file.file_id}/url`} />}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}
          </CardContent>
        </Card>
      )}

      {/* A contractor's build: the stages and everything recorded on them live on the execution page. */}
      {data.category === "CONTRACTOR" && (
        <section aria-labelledby="execution" className="flex flex-col gap-3">
          <SectionHeader id="execution" title={t("execution")} description={t("executionIntro")} />
          <p className="text-sm" data-testid="stage-summary">
            {stages.length ? t("stages", { done, total: stages.length }) : t("noStages")}
          </p>
          {mine?.handover && <p className="text-sm">{t(`handover.${mine.handover}`)}</p>}
          {active && (
            <Button asChild className="self-start">
              <Link href={`/engagements/${engagementId}/execution`}>
                {t("openExecution")}
                <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
              </Link>
            </Button>
          )}
        </section>
      )}

      {(roles.architect || drawings.length > 0) && (
        <section aria-labelledby="drawings" className="flex flex-col gap-3">
          <SectionHeader id="drawings" title={t("drawings")} description={t("drawingsIntro")} />
          <ul className="flex flex-col gap-1 text-sm">
            {drawings.map((d) => (
              <li key={d.request.id}>
                {d.request.scope_note} · {d.request.sets.length ? d.request.sets[d.request.sets.length - 1].state : "—"}
              </li>
            ))}
          </ul>
          <Button asChild variant="outline" className="self-start">
            <Link href="/build-plan">
              {t("openDrawings")}
              <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
            </Link>
          </Button>
        </section>
      )}

      {(roles.engineer || signoffs.length > 0) && (
        <section aria-labelledby="signoffs" className="flex flex-col gap-3">
          <SectionHeader id="signoffs" title={t("signoffs")} description={t("signoffsIntro")} />
          <ul className="flex flex-col gap-2">
            {signoffs.map((s) => (
              <li key={s.version_id}>
                <Link href={`/build-plan/signoffs/${s.version_id}`} className="font-medium underline underline-offset-4">
                  {t("signVersion", { number: s.version_no })}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {active && <ProEndEngagementById engagementId={engagementId} />}
    </PageContainer>
  );
}
