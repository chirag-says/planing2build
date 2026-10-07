import type { Metadata } from "next";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { PortfolioManager } from "@/components/plan2build/pro-forms";
import { getTranslator } from "@/lib/i18n";
import { OnboardingRail } from "@/components/plan2build/onboarding-rail";
import { loadOwnProfile } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Pro")("portfolio.title") };

export default async function ProPortfolioPage() {
  const data = await loadOwnProfile("/portfolio");
  const t = getTranslator("Pro");
  return (
    <PageContainer>
      <PageHeader title={t("portfolio.title")} description={t("portfolio.intro")} />
      {/* Guided onboarding until a category is listed. */}
      {!data.categories.some((c) => c.listing_state === "LISTED") && <OnboardingRail data={data} />}
      <PortfolioManager data={data} />
    </PageContainer>
  );
}
