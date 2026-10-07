// "Your floor plans" on the designs page: the project's concept floor plans with their state, and
// a link to each ready one. The API answers 404 while the feature is off; then nothing shows.
import { MapIcon } from "lucide-react";
import Link from "next/link";

import { SectionHeader } from "@/components/plan2build/page-header";
import { Button } from "@/components/ui/button";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

export async function PlanList({ projectId }: { projectId: string }) {
  const response = await (await serverApi()).GET("/api/v1/projects/{project_id}/house-plans", {
    params: { path: { project_id: projectId } },
  });
  if (response.response.status === 404 || !response.data) return null;
  const t = getTranslator("Plan");
  const plans = response.data.items;
  return (
    <section aria-labelledby="floor-plans" className="flex flex-col gap-4">
      <SectionHeader id="floor-plans" title={t("list.title")} description={t("list.intro")} />
      {plans.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("list.empty")}</p>
      ) : (
        <ul className="flex flex-col divide-y rounded-lg border">
          {plans.map((plan) => (
            <li key={plan.plan_id} className="flex flex-wrap items-center justify-between gap-3 p-3">
              <div className="flex flex-col">
                <span className="font-medium">{t("planNumber", { number: plan.sequence })}</span>
                <span className="text-sm text-muted-foreground">
                  {t("joined", { a: t(`list.state.${plan.state}`), b: formatDate(plan.created_at) })}
                </span>
              </div>
              {plan.state === "VALID" && (
                <Button asChild variant="outline">
                  <Link href={`/projects/${projectId}/designs/plans/${plan.plan_id}`}>
                    <MapIcon aria-hidden="true" data-icon="inline-start" />
                    {t("list.open")}
                  </Link>
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
