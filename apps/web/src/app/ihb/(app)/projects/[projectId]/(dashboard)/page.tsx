import type { components } from "@p2b/contracts";
import { ArrowRightIcon, PackageIcon, SparklesIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { DesignThumbnail } from "@/components/plan2build/design-gallery";
import { SectionHeader } from "@/components/plan2build/page-header";
import { nextStepText } from "@/components/plan2build/project-summary-card";
import { Notice } from "@/components/plan2build/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatInr } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, loadProject, projectTitle, type ProjectDetail } from "@/lib/project";

type Estimate = components["schemas"]["ProjectEstimateOut"];
type DesignList = components["schemas"]["DesignListOut"];

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  return { title: await projectTitle((await params).projectId) };
}

/** Where the review stands (PD-21). It runs in the background and never blocks the dashboard. */
function ReviewNotice({ detail }: { detail: ProjectDetail }) {
  const t = getTranslator("Dashboard");
  const projects = getTranslator("Projects");
  const { project, review_message: message } = detail;
  if (project.status === "DRAFT") {
    return (
      <Notice tone="info" title={t("draftTitle")}>
        <p>{t("draftBody")}</p>
      </Notice>
    );
  }
  if (message?.status === "NEEDS_INFO") {
    return (
      <Notice tone="warning" title={projects("needsInfoTitle")}>
        <p className="whitespace-pre-line">{message.message}</p>
        <p className="mt-2">{nextStepText(project)}</p>
      </Notice>
    );
  }
  if (message?.status === "CANCELLED") {
    return (
      <Notice tone="info" title={projects("cancelledTitle")}>
        <p className="whitespace-pre-line">{projects("reason", { reason: message.message })}</p>
      </Notice>
    );
  }
  if (project.status === "SUBMITTED") {
    return (
      <Notice tone="info" title={t("reviewTitle")}>
        <p>{t("reviewBody")}</p>
      </Notice>
    );
  }
  if (detail.package.availability === "ELIGIBLE") {
    return (
      <Notice tone="success" title={t("acceptedTitle")}>
        <p>{t("acceptedBody")}</p>
      </Notice>
    );
  }
  return (
    <Notice tone="info" title={projects("nextStep")}>
      <p>{nextStepText(project)}</p>
    </Notice>
  );
}

function EstimateSummary({ estimate, href }: { estimate: Estimate; href: string }) {
  const t = getTranslator("Dashboard");
  const estimateT = getTranslator("Estimate");
  const figures = estimate.figures;
  return (
    <Card size="sm">
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-base">
            <h3>{t("estimateTitle")}</h3>
          </CardTitle>
          {figures?.rate_card.is_demo && <Badge variant="warning">{estimateT("demoBadge")}</Badge>}
        </div>
        <CardDescription>{t("estimateNotQuote")}</CardDescription>
      </CardHeader>
      <CardContent>
        {figures ? (
          <p className="text-xl font-semibold tabular-nums">
            {formatInr(figures.total_low)} to {formatInr(figures.total_high)}
          </p>
        ) : (
          <p className="text-sm">
            {t(`unavailable.${estimate.unavailable_reason ?? "NO_RATE_CARD"}`, {
              city: estimate.inputs.city,
            })}
          </p>
        )}
      </CardContent>
      <CardFooter>
        <Button asChild variant="outline">
          <Link href={href}>
            {t("estimateLink")}
            <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
          </Link>
        </Button>
      </CardFooter>
    </Card>
  );
}

/** Generate My Design from the overview: free designs left, the latest concepts, the gallery. */
function DesignsSummary({ designs, base }: { designs: DesignList; base: string }) {
  const t = getTranslator("Designs");
  const latest = designs.items.filter((item) => item.state === "SUCCEEDED").slice(0, 3);
  return (
    <Card size="sm" className="md:col-span-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <SparklesIcon aria-hidden="true" className="size-4 text-muted-foreground" />
          <h3>{t("overviewTitle")}</h3>
        </CardTitle>
        <CardDescription>{t("intro")}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {designs.quota.block && designs.quota.block !== "FREE_QUOTA_USED" && (
          <p className="text-sm">{t(`blocks.${designs.quota.block}`)}</p>
        )}
        <p className="text-sm font-medium">
          {t("remaining", {
            remaining: designs.quota.free_remaining,
            total: designs.quota.free_total,
          })}
        </p>
        {latest.length > 0 && (
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {latest.map((design) => (
              <li key={design.design_id}>
                <DesignThumbnail design={design} href={`${base}/designs/${design.design_id}`} index={design.sequence - 1} />
              </li>
            ))}
          </ul>
        )}
      </CardContent>
      <CardFooter className="flex flex-wrap gap-2">
        {designs.quota.can_generate && (
          <Button asChild>
            <Link href={`${base}/designs`}>
              <SparklesIcon aria-hidden="true" data-icon="inline-start" />
              {t("generate")}
            </Link>
          </Button>
        )}
        {designs.items.length > 0 && (
          <Button asChild variant="outline">
            <Link href={`${base}/designs`}>{t("seeAll")}</Link>
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}

/** The one Plan2Build package: what it is, its state, and the way to it (Slice 3.3). */
function PackageCard({ detail }: { detail: ProjectDetail }) {
  const t = getTranslator("Dashboard");
  const { state, availability, purchasable } = detail.package;
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <PackageIcon aria-hidden="true" className="size-4 text-muted-foreground" />
          <h3>{t("packageTitle")}</h3>
        </CardTitle>
        <CardDescription>{t("packageBody")}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <p>{t("packageModular")}</p>
        <p className="font-medium">
          {state === "ACTIVE"
            ? t("packageActive")
            : state !== "NOT_ACTIVE"
              ? t("packageEnded")
              : t(`packageState.${availability}`)}
        </p>
      </CardContent>
      {(purchasable || state !== "NOT_ACTIVE") && (
        <CardFooter>
          <Button asChild variant={purchasable ? "default" : "outline"}>
            <Link href={`/projects/${detail.project.project_id}/package`}>
              {t("packageView")}
              <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
            </Link>
          </Button>
        </CardFooter>
      )}
    </Card>
  );
}

export default async function ProjectOverviewPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const detail = await loadProject(projectId);
  const { project } = detail;
  const projects = getTranslator("Projects");
  const t = getTranslator("Dashboard");
  const base = `/projects/${project.project_id}`;
  const editable = project.status === "DRAFT" || project.status === "NEEDS_INFO";
  const open = dashboardOpen(project.status);
  const api = open ? await serverApi() : undefined;
  const path = { params: { path: { project_id: projectId } } };
  const [estimate, designs] = api
    ? await Promise.all([
        api.GET("/api/v1/projects/{project_id}/estimate", path).then((r) => r.data),
        api.GET("/api/v1/projects/{project_id}/designs", path).then((r) => r.data),
      ])
    : [undefined, undefined];

  return (
    <>
      <div className="flex flex-col gap-4">
        <ReviewNotice detail={detail} />
        {editable && (
          <Button asChild size="lg" className="sm:self-start">
            <Link href={`${base}/requirement`}>
              {project.status === "NEEDS_INFO" ? projects("update") : projects("continue")}
              <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
            </Link>
          </Button>
        )}
      </div>
      {open && (
        <section aria-labelledby="at-a-glance" className="flex flex-col gap-4">
          <SectionHeader id="at-a-glance" title={t("areas.overview")} />
          <div className="grid gap-4 md:grid-cols-2">
            {designs && <DesignsSummary designs={designs} base={base} />}
            {estimate && <EstimateSummary estimate={estimate} href={`${base}/estimate`} />}
            <PackageCard detail={detail} />
          </div>
        </section>
      )}
    </>
  );
}
