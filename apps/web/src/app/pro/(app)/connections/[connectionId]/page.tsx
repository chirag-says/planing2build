import { ArrowLeftIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { ProEndEngagement, ProRespond, SharedFileButton } from "@/components/plan2build/engagements";
import { FileRow } from "@/components/plan2build/file-row";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatDate, formatDateTime } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const metadata: Metadata = { title: getTranslator("Pro")("connections.view") };

// One request (Slice 3.4): the brief; after acceptance the family's contact, the site pin and
// the files they chose to share (N-08); accept, decline with a reason (N-06), or end.
export default async function ProConnectionPage({ params }: { params: Promise<{ connectionId: string }> }) {
  const { connectionId } = await params;
  if (!UUID.test(connectionId)) notFound();
  const api = await serverApi();
  const [{ data: c, response }, questions] = await Promise.all([
    api.GET("/api/v1/pro/connections/{connection_id}", { params: { path: { connection_id: connectionId } } }),
    api.GET("/api/v1/public/requirement-questions"),
  ]);
  if (response.status === 401) redirect(`/sign-in?next=${encodeURIComponent(`/connections/${connectionId}`)}`);
  if (response.status === 404) notFound();
  if (!c) throw new Error("the request could not be loaded");
  // Accepted: the engagement's workspace is the one page for this job (decided 2026-10-08).
  if (c.engagement_id) redirect(`/engagements/${c.engagement_id}`);
  const t = getTranslator("Pro");
  const b = c.brief;
  const none = t("connections.notGiven");
  const yesNo = (value: boolean | null) =>
    value === null ? none : value ? t("connections.yes") : t("connections.no");
  // The family's own option labels for coded answers (the requirement's question set).
  const label = (key: string, value: string | null) =>
    value === null
      ? none
      : (questions.data?.questions.find((q) => q.key === key)?.options?.find((o) => o.value === value)?.label ?? value);
  const rows: [string, string][] = [
    [t("connections.locality"), b.locality ?? none],
    [t("connections.plotArea"), b.plot_area_sqft ? t("connections.sqft", { value: b.plot_area_sqft }) : none],
    [t("connections.builtUp"), b.built_up_area_sqft ? t("connections.sqft", { value: String(b.built_up_area_sqft) }) : none],
    [t("connections.floors"), b.floors !== null ? String(b.floors) : none],
    [t("connections.basement"), yesNo(b.basement)],
    [t("connections.budget"), label("budget_band", b.budget_band)],
    [t("connections.start"), label("start_timeline", b.start_window)],
    ...(b.subtypes.length > 0 ? ([[t("connections.types"), b.subtypes.join(", ")]] as [string, string][]) : []),
  ];
  const active = c.engagement_state === "ACTIVE";

  return (
    <PageContainer>
      <Button asChild variant="ghost" className="self-start">
        <Link href="/connections">
          <ArrowLeftIcon aria-hidden="true" />
          {t("connections.back")}
        </Link>
      </Button>
      <PageHeader
        title={c.category_name}
        description={
          c.state === "SENT"
            ? t("connections.respondBy", { date: formatDateTime(c.respond_by) })
            : t("connections.received", { date: formatDate(c.sent_at) })
        }
        actions={<StatusBadge kind="connection" status={c.state} withLabel />}
      />
      {c.state === "WITHDRAWN" && <Notice tone="info">{t("connections.withdrawn")}</Notice>}
      {c.state === "EXPIRED" && <Notice tone="info">{t("connections.expired")}</Notice>}
      {c.state === "DECLINED" && <Notice tone="info">{t("connections.declined")}</Notice>}
      {c.engagement_state === "ENDED" && <Notice tone="info">{t("connections.ended")}</Notice>}

      <section aria-labelledby="brief" className="flex flex-col gap-3">
        <SectionHeader id="brief" title={t("connections.brief")} />
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
          {rows.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-muted-foreground">{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      {c.state === "SENT" && <ProRespond connectionId={c.id} />}

      {c.family_contact && (
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-base">
              <h2>{t("connections.family")}</h2>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
              <dt className="text-muted-foreground">{t("connections.name")}</dt>
              <dd>{c.family_contact.name}</dd>
              <dt className="text-muted-foreground">{t("connections.phoneLabel")}</dt>
              <dd>
                <a href={`tel:${c.family_contact.phone}`} className="underline underline-offset-4">{c.family_contact.phone}</a>
              </dd>
              <dt className="text-muted-foreground">{t("connections.email")}</dt>
              <dd className="break-all">
                {c.family_contact.email ? (
                  <a href={`mailto:${c.family_contact.email}`} className="underline underline-offset-4">{c.family_contact.email}</a>
                ) : (
                  none
                )}
              </dd>
              {c.family_contact.site_address && (
                <>
                  <dt className="text-muted-foreground">{t("connections.siteAddress")}</dt>
                  <dd className="whitespace-pre-line">{c.family_contact.site_address}</dd>
                </>
              )}
              {c.location && (
                <>
                  <dt className="text-muted-foreground">{t("connections.location")}</dt>
                  <dd>
                    <a
                      href={`https://www.openstreetmap.org/?mlat=${c.location.lat}&mlon=${c.location.lng}#map=17/${c.location.lat}/${c.location.lng}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline underline-offset-4"
                    >
                      {t("connections.openMap")}
                    </a>
                  </dd>
                </>
              )}
            </dl>
            {active && (
              <section aria-labelledby="shared" className="flex flex-col gap-2">
                <h3 id="shared" className="text-sm font-medium">{t("connections.files")}</h3>
                {c.shared_files.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{t("connections.noFiles")}</p>
                ) : (
                  <ul className="divide-y divide-border">
                    {c.shared_files.map((file) => (
                      <li key={file.file_id}>
                        <FileRow
                          name={file.file_name}
                          mime={file.content_type}
                          size={file.size_bytes}
                          state={file.state}
                          actions={<SharedFileButton connectionId={c.id} fileId={file.file_id} name={file.file_name} />}
                        />
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}
            {active && <ProEndEngagement connectionId={c.id} />}
          </CardContent>
        </Card>
      )}
    </PageContainer>
  );
}
