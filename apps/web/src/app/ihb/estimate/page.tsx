import type { Metadata } from "next";

import { Estimator } from "@/components/plan2build/estimator";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { getTranslator } from "@/lib/i18n";

// The page title names the page (WCAG 2.4.2); the layout adds "| Plan2Build".
export const metadata: Metadata = { title: getTranslator("Estimate")("title") };

export default function EstimatePage() {
  const t = getTranslator("Estimate");
  return (
    <PageContainer width="wide">
      <PageHeader title={t("title")} description={t("intro")} />
      <Estimator />
    </PageContainer>
  );
}
