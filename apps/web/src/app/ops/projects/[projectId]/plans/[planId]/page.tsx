import { ArrowLeftIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { PlanViewer } from "@/components/plan2build/plan/plan-viewer";
import { ProjectBreadcrumb } from "@/components/plan2build/project-breadcrumb";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { drawablePlan } from "@/lib/ops-flow";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Plan")("title") };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// One concept floor plan for operations, read only: its state, the ruleset it was laid out with,
// why it failed or does not fit, and the drawing with the validator's checks when it is VALID.
// The API answers 404 while the feature is off.
export default async function OpsFloorPlanPage({
  params,
}: {
  params: Promise<{ projectId: string; planId: string }>;
}) {
  const { projectId, planId } = await params;
  if (!UUID.test(projectId) || !UUID.test(planId)) notFound();
  await requireVerifiedStaff(`/projects/${projectId}/plans/${planId}`);
  const response = await (await serverApi()).GET("/api/v1/ops/house-plans/{plan_id}", {
    params: { path: { plan_id: planId } },
  });
  if (response.response.status === 404 || response.response.status === 422) notFound();
  const t = getTranslator("Plan");
  const plan = response.data;
  const back = `/projects/${projectId}`;
  const header = (
    <PageHeader
      title={plan ? t("planNumber", { number: plan.sequence }) : t("title")}
      description={plan ? t("joined", { a: t(`list.state.${plan.state}`), b: formatDate(plan.created_at) }) : undefined}
      actions={
        <Button asChild variant="outline">
          <Link href={back}>
            <ArrowLeftIcon aria-hidden="true" data-icon="inline-start" />
            {t("ops.back")}
          </Link>
        </Button>
      }
    />
  );
  if (!plan) {
    const message = (response.error as { error?: { message?: string } } | undefined)?.error?.message;
    return (
      <PageContainer width="wide">
        {header}
        <Notice tone="error">{message ? t("ops.errorReason", { reason: message }) : t("ops.error")}</Notice>
      </PageContainer>
    );
  }

  return (
    <PageContainer width="full">
      <div className="flex flex-col gap-4">
        <ProjectBreadcrumb
          root={{ label: getTranslator("Ops")("queue.title"), href: "/queue" }}
          trail={[{ label: t("ops.title"), href: `${back}#floor-plans` }, { label: t("planNumber", { number: plan.sequence }) }]}
        />
        {header}
      </div>
      <Notice tone="info">{t("ops.viewOnly")}</Notice>
      <Notice tone="warning" title={t("disclaimer")}>
        {t("disclaimerDetail")}
      </Notice>
      <p className="text-sm text-muted-foreground">
        {t("ops.ruleset", { version: plan.ruleset_version, status: t(`ops.rulesetStatus.${plan.ruleset_status}`) })}
        {plan.ruleset_is_synthetic && ` · ${t("ops.synthetic")}`}
        {plan.validity && ` · ${t(`ops.validity.${plan.validity}`)}`}
        {plan.completed_at && ` · ${t("ops.completed", { date: formatDate(plan.completed_at) })}`}
      </p>
      {(plan.ruleset_is_synthetic || plan.ruleset_status !== "PUBLISHED") && (
        <Notice tone="info" title={t("rulesUnverified")}>
          {t("rulesUnverifiedBody")}
        </Notice>
      )}
      {plan.state === "FAILED" && (
        <Notice tone="error" title={t("list.state.FAILED")}>
          {t(`ops.failure.${plan.failure_reason ?? "UNKNOWN"}`)}
          {plan.failure_detail && (
            <span className="mt-1 block font-mono text-xs break-all">{plan.failure_detail}</span>
          )}
        </Notice>
      )}
      {plan.state === "INFEASIBLE" && (
        <Notice tone="warning" title={t("list.state.INFEASIBLE")}>
          {[plan.infeasibility?.message, plan.infeasibility?.explanation].filter(Boolean).join(" ")}
          {plan.infeasibility && plan.infeasibility.reasons.length > 0 && (
            <span className="mt-1 block font-mono text-xs">
              {plan.infeasibility.reasons.map((r) => r.code).join(", ")}
            </span>
          )}
        </Notice>
      )}
      {drawablePlan(plan) ? (
        <PlanViewer document={plan.document} geometry={plan.geometry} validation={plan.validation} />
      ) : (
        plan.state !== "FAILED" &&
        plan.state !== "INFEASIBLE" && <Notice tone="info">{t("ops.notDrawable")}</Notice>
      )}
    </PageContainer>
  );
}
