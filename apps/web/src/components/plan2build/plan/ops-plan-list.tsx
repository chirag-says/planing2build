// Floor plans on the operations project page: every concept plan of the project with its state,
// read only. The API answers 404 while the feature is off; then the section does not show.
import { MapIcon } from "lucide-react";
import Link from "next/link";

import { SectionHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

export async function OpsPlanList({ projectId }: { projectId: string }) {
  const response = await (await serverApi()).GET("/api/v1/ops/projects/{project_id}/house-plans", {
    params: { path: { project_id: projectId } },
  });
  if (response.response.status === 404) return null;
  const t = getTranslator("Plan");
  const header = <SectionHeader id="floor-plans" title={t("ops.title")} description={t("ops.intro")} />;
  if (!response.data) {
    const message = (response.error as { error?: { message?: string } } | undefined)?.error?.message;
    return (
      <section aria-labelledby="floor-plans" className="flex flex-col gap-4">
        {header}
        <Notice tone="error">{message ? t("ops.errorReason", { reason: message }) : t("ops.error")}</Notice>
      </section>
    );
  }
  const plans = response.data.items;
  return (
    <section aria-labelledby="floor-plans" className="flex flex-col gap-4" data-testid="ops-floor-plans">
      {header}
      {plans.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("ops.empty")}</p>
      ) : (
        <ul className="flex flex-col divide-y rounded-lg border">
          {plans.map((plan) => (
            <li key={plan.plan_id} className="flex flex-wrap items-center justify-between gap-3 p-3">
              <div className="flex flex-col">
                <span className="font-medium">{t("planNumber", { number: plan.sequence })}</span>
                <span className="text-sm text-muted-foreground">
                  {t("joined", { a: t(`list.state.${plan.state}`), b: formatDate(plan.created_at) })}
                  {plan.validity && ` · ${t(`ops.validity.${plan.validity}`)}`}
                </span>
                <span className="text-xs text-muted-foreground">
                  {t("ops.ruleset", {
                    version: plan.ruleset_version,
                    status: t(`ops.rulesetStatus.${plan.ruleset_status}`),
                  })}
                  {plan.ruleset_is_synthetic && ` · ${t("ops.synthetic")}`}
                </span>
              </div>
              <Button asChild variant="outline">
                <Link href={`/projects/${projectId}/plans/${plan.plan_id}`}>
                  <MapIcon aria-hidden="true" data-icon="inline-start" />
                  {t("ops.open")}
                </Link>
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
