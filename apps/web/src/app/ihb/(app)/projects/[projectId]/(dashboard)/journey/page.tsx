import type { Metadata } from "next";

import { JourneyPhases } from "@/components/plan2build/overview";
import { SectionHeader } from "@/components/plan2build/page-header";
import { getTranslator } from "@/lib/i18n";
import type { Phase } from "@/lib/journey";
import { dashboardOpen, hasStagesAndLines, loadProject, projectTitle } from "@/lib/project";
import { getProjectOverview } from "@/lib/project-overview";
import imgBuild from "@/marketing/assets/stages/build.webp";
import imgCompare from "@/marketing/assets/stages/compare.webp";
import imgPlan from "@/marketing/assets/stages/plan.webp";
import imgRecord from "@/marketing/assets/stages/record.webp";
import imgSelect from "@/marketing/assets/stages/select.webp";
import imgVerify from "@/marketing/assets/stages/verify.webp";

/** The website's stage photographs (Built section); handover has none of its own. */
const IMAGES = {
  plan: imgPlan,
  compare: imgCompare,
  select: imgSelect,
  build: imgBuild,
  verify: imgVerify,
  record: imgRecord,
};

export async function generateMetadata({ params }: { params: Promise<{ projectId: string }> }): Promise<Metadata> {
  return {
    title: await projectTitle((await params).projectId, getTranslator("Dashboard")("areas.journey")),
  };
}

// The whole journey (IHB_FLOW section 34), the overview's "View journey": seven phases from the
// first answer to the build record, what happens in each, where the project is, and the pages
// where each phase is done. No phase is compulsory (PD-17); the order is the build's own.
export default async function JourneyPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const [detail, overview] = await Promise.all([loadProject(projectId), getProjectOverview(projectId)]);
  const t = getTranslator("Dashboard");
  const o = getTranslator("Overview");
  const base = `/projects/${projectId}`;
  const open = dashboardOpen(detail.project.status);
  const built = hasStagesAndLines(detail.project.status);
  const go = (path: string, label: string) => ({
    href: `${base}${path}`,
    label: o("journeyPage.open", { page: label }),
  });
  const links: Partial<Record<Phase, Array<{ href: string; label: string }>>> = open
    ? {
        plan: [
          go("/answers", t("areas.requirement")),
          go("/estimate", t("areas.estimate")),
          go("/designs", t("areas.designs")),
          go("/package", t("areas.package")),
          go("/build-plan", t("areas.buildPlan")),
        ],
        compare: [go("/services", t("areas.professionals")), go("/quotes", t("areas.quotes"))],
        select: [go("/quotes", t("areas.quotes"))],
        ...(built
          ? {
              build: [go("/construction", t("areas.construction")), go("/specification", t("areas.specification"))],
              verify: [go("/construction#inspections", o("nav.inspections"))],
            }
          : {}),
        record: [go("/documents", t("areas.documents"))],
      }
    : { plan: [go("/requirement", t("areas.requirement"))] };
  return (
    <section aria-labelledby="journey-title" className="flex max-w-4xl flex-col gap-8">
      <SectionHeader
        id="journey-title"
        title={o("journeyPage.title")}
        description={
          overview.phase ? o("journeyPage.intro", { phase: o(`phases.${overview.phase}`) }) : o("journeyPage.introNone")
        }
      />
      <JourneyPhases overview={overview} links={links} images={IMAGES} />
    </section>
  );
}
