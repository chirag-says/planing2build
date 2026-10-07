import type { components } from "@p2b/contracts";
import { SearchIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import {
  FamilyEndEngagement,
  NeedControl,
  OutsideProfessionalDialog,
  QuoteFileButton,
  QuoteReviewForm,
  ShareFiles,
  WithdrawButton,
} from "@/components/plan2build/engagements";
import { SectionHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatDate, formatDateTime } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, loadProject, projectTitle } from "@/lib/project";

type Category = components["schemas"]["CategoryServiceOut"];
type Engagement = components["schemas"]["FamilyEngagementOut"];
type Connection = components["schemas"]["FamilyConnectionOut"];

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  const area = getTranslator("Dashboard")("areas.professionals");
  return { title: await projectTitle((await params).projectId, area) };
}

const t = getTranslator("Services");

function Contact({ engagement }: { engagement: Engagement }) {
  const contact = engagement.professional_contact;
  if (engagement.party === "OUTSIDE") {
    return engagement.contact ? (
      <p className="text-sm break-all">{t("contact")}: {engagement.contact}</p>
    ) : null;
  }
  if (!contact) return null;
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
      <dt className="text-muted-foreground">{t("phone")}</dt>
      <dd className="break-all">
        {contact.phone ? <a href={`tel:${contact.phone}`} className="underline underline-offset-4">{contact.phone}</a> : t("notGiven")}
      </dd>
      <dt className="text-muted-foreground">{t("email")}</dt>
      <dd className="break-all">
        {contact.email ? <a href={`mailto:${contact.email}`} className="underline underline-offset-4">{contact.email}</a> : t("notGiven")}
      </dd>
    </dl>
  );
}

function ConnectionNote({ connection }: { connection: Connection }) {
  if (connection.state === "DECLINED") return <p className="text-sm text-muted-foreground">{t("declinedNeutral")}</p>;
  if (connection.state === "EXPIRED") return <p className="text-sm text-muted-foreground">{t("expiredNote")}</p>;
  if (connection.state === "WITHDRAWN" && connection.withdraw_reason) {
    return <p className="text-sm text-muted-foreground">{t(`withdrawReasons.${connection.withdraw_reason}`)}</p>;
  }
  if (connection.state === "SENT") {
    return (
      <p className="text-sm text-muted-foreground">
        {t("sentOn", { date: formatDate(connection.sent_at) })} · {t("respondBy", { date: formatDateTime(connection.respond_by) })}
      </p>
    );
  }
  return null;
}

function CategoryCard({
  projectId,
  category,
  canAct,
  canConnect,
  files,
}: {
  projectId: string;
  category: Category;
  canAct: boolean;
  canConnect: boolean;
  files: components["schemas"]["FileOut"][];
}) {
  const engagement = category.engagement;
  const full = category.open_requests >= category.open_limit;
  const directory = `/professionals?project=${projectId}&category=${category.code}`;
  return (
    <Card size="sm" id={category.code} className="scroll-mt-24">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <h3>{category.name}</h3>
          <StatusBadge kind="need" status={category.need} />
          {category.need_source === "REQUIREMENT" && category.need === "NEEDED" && (
            <Badge variant="neutral">{t("fromRequirement")}</Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        {engagement ? (
          <section aria-label={t("engaged")} className="flex flex-col gap-3 rounded-md border border-border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{t("engaged")}: {engagement.name}</span>
              <Badge variant={engagement.party === "LISTED" ? "success" : "neutral"}>
                {engagement.party === "LISTED" ? t("listed") : t("outside")}
              </Badge>
            </div>
            {engagement.firm && engagement.firm !== engagement.name && (
              <p className="text-sm text-muted-foreground">{engagement.firm}</p>
            )}
            <p className="text-sm text-muted-foreground">{t("since", { date: formatDate(engagement.started_at) })}</p>
            <Contact engagement={engagement} />
            {engagement.party === "LISTED" && canAct && (
              <ShareFiles projectId={projectId} engagementId={engagement.id} files={files} shared={engagement.shared_file_ids} />
            )}
            {canAct && <FamilyEndEngagement projectId={projectId} engagementId={engagement.id} />}
          </section>
        ) : (
          canAct && (
            <>
              <NeedControl
                projectId={projectId}
                code={category.code}
                name={category.name}
                need={category.need}
                subtypes={category.subtypes}
                chosen={category.chosen_subtypes}
              />
              {category.need !== "NOT_NEEDED" && (
                <div className="flex flex-col gap-2">
                  <p className="text-sm text-muted-foreground">
                    {t("openCount", { count: category.open_requests, limit: category.open_limit })}
                  </p>
                  {full && <Notice tone="info">{t("limitReached")}</Notice>}
                  <div className="flex flex-wrap gap-2">
                    {canConnect && !full && (
                      <Button asChild>
                        <Link href={directory} aria-label={`${t("find")}: ${category.name}`}>
                          <SearchIcon aria-hidden="true" />
                          {t("find")}
                        </Link>
                      </Button>
                    )}
                    <OutsideProfessionalDialog projectId={projectId} code={category.code} name={category.name} />
                  </div>
                </div>
              )}
            </>
          )
        )}
        {category.connections.length > 0 && (
          <section aria-label={`${t("requests")}: ${category.name}`} className="flex flex-col gap-2">
            <h4 className="text-sm font-medium">{t("requests")}</h4>
            <ul className="flex flex-col divide-y divide-border">
              {category.connections.map((connection) => {
                const name = connection.professional_name ?? connection.firm_name ?? "";
                return (
                  <li key={connection.id} className="flex flex-wrap items-start justify-between gap-3 py-2"
                    data-connection={connection.state}>
                    <div className="flex flex-col gap-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{name}</span>
                        <StatusBadge kind="connection" status={connection.state} />
                      </span>
                      <ConnectionNote connection={connection} />
                    </div>
                    {connection.state === "SENT" && canAct && (
                      <WithdrawButton projectId={projectId} connectionId={connection.id} name={name} />
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        )}
        {category.past_engagements.length > 0 && (
          <section aria-label={`${t("past")}: ${category.name}`} className="flex flex-col gap-1">
            <h4 className="text-sm font-medium">{t("past")}</h4>
            <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
              {category.past_engagements.map((past) => (
                <li key={past.id} className="flex flex-wrap items-center gap-2">
                  <span>{past.name}</span>
                  <StatusBadge kind="engagement" status={past.state} />
                </li>
              ))}
            </ul>
          </section>
        )}
      </CardContent>
    </Card>
  );
}

// Professionals for the project (Slice 3.4): one card per category, each on its own (modularity).
// The family decides what is needed, finds a listed professional through the directory (with the
// package), records their own, follows requests, and shares files with an active engagement.
export default async function ProjectServicesPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ sent?: string }>;
}) {
  const { projectId } = await params;
  const { sent } = await searchParams;
  const { project } = await loadProject(projectId);
  if (!dashboardOpen(project.status)) redirect(`/projects/${projectId}`);
  const { data: view } = await (await serverApi()).GET("/api/v1/projects/{project_id}/services", {
    params: { path: { project_id: projectId } },
  });
  if (!view) throw new Error("the services could not be loaded");
  const packageActive = view.package_state === "ACTIVE";
  const packageEnded = view.package_state === "CANCELLED" || view.package_state === "REFUNDED";
  const sentTo = view.categories.find((c) => c.code === sent);

  return (
    <section aria-labelledby="services" className="flex flex-col gap-6">
      <SectionHeader
        id="services"
        title={t("title")}
        description={t("intro")}
        action={
          <Button asChild variant="outline">
            <Link href={`/professionals?project=${projectId}`}>
              <SearchIcon aria-hidden="true" />
              {t("browse")}
            </Link>
          </Button>
        }
      />
      {sentTo && <Notice tone="success" live="polite">{t("connect.sent")}</Notice>}
      {view.availability !== "ELIGIBLE" && <Notice tone="info">{t("notEligible")}</Notice>}
      {view.availability === "ELIGIBLE" && !view.can_act && <Notice tone="info">{t("readOnly")}</Notice>}
      {view.can_act && packageEnded && <Notice tone="info">{t("packageEnded")}</Notice>}
      {view.can_act && !packageActive && (
        <Notice tone="info">
          {t("packageNeeded")}{" "}
          <Link href={`/projects/${projectId}/package`} className="font-medium underline underline-offset-4">
            {t("packageLink")}
          </Link>
        </Notice>
      )}
      {view.has_contractor && view.can_act && !view.categories.find((c) => c.code === "CONTRACTOR")?.engagement && (
        <Notice tone="info">{t("hasContractor")}</Notice>
      )}
      <div className="flex flex-col gap-4">
        {view.categories.map((category) => (
          <CategoryCard
            key={category.code}
            projectId={projectId}
            category={category}
            canAct={view.can_act}
            canConnect={packageActive}
            files={view.requirement_files}
          />
        ))}
      </div>
      {view.availability === "ELIGIBLE" && (
        <section aria-labelledby="quote" className="flex flex-col gap-4">
          <SectionHeader id="quote" title={t("quote.title")} description={t("quote.intro")} />
          {view.quote_reviews.length > 0 && (
            <section aria-labelledby="quote-list" className="flex flex-col gap-2">
              <h3 id="quote-list" className="text-sm font-medium">{t("quote.list")}</h3>
              <ul className="flex flex-col gap-2 text-sm">
                {view.quote_reviews.map((review) => (
                  <li key={review.id} className="flex flex-col gap-1 rounded-md border border-border p-3">
                    <span className="font-medium">
                      {view.categories.find((c) => c.code === review.category)?.name ?? review.category} · {review.quoted_by}
                    </span>
                    <span className="text-muted-foreground">{t("quote.received", { date: formatDate(review.submitted_at) })}</span>
                    <span className="flex flex-wrap gap-1">
                      {review.files.map((file) => (
                        <QuoteFileButton key={file.file_id} projectId={projectId} fileId={file.file_id} name={file.file_name} />
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {view.can_act &&
            (packageActive ? (
              <QuoteReviewForm
                projectId={projectId}
                categories={view.categories.map((c) => ({ code: c.code, name: c.name }))}
              />
            ) : (
              <p className="text-sm text-muted-foreground">{t("errors.PACKAGE_REQUIRED")}</p>
            ))}
        </section>
      )}
    </section>
  );
}
