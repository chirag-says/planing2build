import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { getTranslator } from "@/lib/i18n";

export default async function NotFound() {
  const t = getTranslator("NotFound");
  return (
    <PageContainer width="narrow">
      <PageHeader title={t("title")} />
    </PageContainer>
  );
}
