import type { Metadata } from "next";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { PortfolioManager } from "@/components/plan2build/pro-forms";
import { getTranslator } from "@/lib/i18n";
import { loadOwnProfile } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Pro")("portfolio.title") };

export default async function ProPortfolioPage() {
  const data = await loadOwnProfile("/portfolio");
  const t = getTranslator("Pro");
  return (
    <PageContainer>
      <PageHeader title={t("portfolio.title")} description={t("portfolio.intro")} />
      <PortfolioManager data={data} />
    </PageContainer>
  );
}
