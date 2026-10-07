import { ArrowLeftIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { DesignThumbnail } from "@/components/plan2build/design-gallery";
import { DesignReferenceButton } from "@/components/plan2build/design-reference-button";
import { SectionHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string; designId: string }>;
}): Promise<Metadata> {
  const area = getTranslator("Dashboard")("areas.designs");
  return { title: await projectTitle((await params).projectId, area) };
}

// One concept: the image with its "Illustrative" marks, what the family may know about it, and
// "Use as design reference". No provider, prompt or cost is shown (nor sent by the API).
export default async function DesignDetailPage({
  params,
}: {
  params: Promise<{ projectId: string; designId: string }>;
}) {
  const { projectId, designId } = await params;
  const { project } = await loadProject(projectId);
  if (!dashboardOpen(project.status)) redirect(`/projects/${projectId}`);
  const response = await (await serverApi()).GET(
    "/api/v1/projects/{project_id}/designs/{design_id}",
    { params: { path: { project_id: projectId, design_id: designId } } },
  );
  if (response.response.status === 404 || response.response.status === 422) notFound();
  const design = response.data;
  if (!design) throw new Error("the design could not be loaded");

  const t = getTranslator("Designs");
  const status = getTranslator("Status");
  const base = `/projects/${projectId}/designs`;
  const title = `${t("designNumber", { number: design.sequence })} · ${t(`viewShort.${design.view}`)}`;
  return (
    <section aria-labelledby="design" className="flex flex-col gap-4">
      <SectionHeader
        id="design"
        title={title}
        action={
          <Button asChild variant="outline">
            <Link href={base}>
              <ArrowLeftIcon aria-hidden="true" data-icon="inline-start" />
              {t("back")}
            </Link>
          </Button>
        }
      />
      <Notice tone="warning" title={t("illustrativeTitle")}>
        {t("illustrativeBody")}
      </Notice>
      <DesignThumbnail design={design} />
      <Card size="sm">
        <CardHeader>
          <CardTitle className="text-base">
            <h3>{t("detailsTitle")}</h3>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
            <dt className="text-muted-foreground">{t("number")}</dt>
            <dd>{design.sequence}</dd>
            <dt className="text-muted-foreground">{t("shows")}</dt>
            <dd>{t(`views.${design.view}`)}</dd>
            <dt className="text-muted-foreground">{t("requestedOn")}</dt>
            <dd>{formatDate(design.created_at)}</dd>
            <dt className="text-muted-foreground">{t("funding")}</dt>
            <dd>{design.funding === "FREE" ? t("free") : t("paid")}</dd>
            <dt className="text-muted-foreground">{status("label")}</dt>
            <dd>
              <StatusBadge kind="design" status={design.state} />
            </dd>
          </dl>
        </CardContent>
      </Card>
      {design.state === "SUCCEEDED" && design.reference && (
        <Notice tone="info" title={t("referenceBadge")}>
          <p>{t("referenceMarked", { date: formatDate(design.reference.marked_at) })}</p>
          <p className="mt-1">{t("referenceHelp")}</p>
        </Notice>
      )}
      {design.state === "SUCCEEDED" && project.status !== "CANCELLED" && (
        <DesignReferenceButton
          projectId={projectId}
          designId={design.design_id}
          marked={Boolean(design.reference)}
        />
      )}
    </section>
  );
}
