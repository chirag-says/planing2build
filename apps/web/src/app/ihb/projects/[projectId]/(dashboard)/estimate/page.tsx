import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { EstimateFigures } from "@/components/plan2build/estimate-figures";
import { SectionHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  const area = getTranslator("Dashboard")("areas.estimate");
  return { title: await projectTitle((await params).projectId, area) };
}

// The indicative estimate stored with the latest submission (PD-04): never a quote and never the
// package fee. Demonstration figures are marked as such by EstimateFigures.
export default async function ProjectEstimatePage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const { project } = await loadProject(projectId);
  if (!dashboardOpen(project.status)) redirect(`/projects/${projectId}`);
  const { data: estimate } = await (await serverApi()).GET("/api/v1/projects/{project_id}/estimate", {
    params: { path: { project_id: projectId } },
  });
  if (!estimate) throw new Error("the estimate could not be loaded");

  const t = getTranslator("Dashboard");
  const estimateT = getTranslator("Estimate");
  const { inputs } = estimate;
  const basis =
    inputs.built_up_area_sqft && inputs.floors && inputs.finish_level
      ? t("estimateBasis", {
          area: inputs.built_up_area_sqft.toLocaleString("en-IN"),
          floors: estimateT(`floorOptions.${String(inputs.floors) as "1" | "2" | "3" | "4"}`),
          tier: estimateT(`tiers.${inputs.finish_level}`),
          city: inputs.city,
        })
      : null;
  const made = t("estimateMade", { date: formatDate(estimate.created_at) });

  return (
    <section aria-labelledby="estimate" className="flex flex-col gap-4">
      <SectionHeader id="estimate" title={t("estimateTitle")} description={t("estimateNotQuote")} />
      {estimate.figures ? (
        <EstimateFigures
          figures={estimate.figures}
          title={estimateT("range")}
          level={3}
          description={
            <>
              {basis && <p>{basis}</p>}
              <p>{made}</p>
            </>
          }
        />
      ) : (
        <Notice tone="info">
          {t(`unavailable.${estimate.unavailable_reason ?? "NO_RATE_CARD"}`, { city: inputs.city })}
        </Notice>
      )}
    </section>
  );
}
