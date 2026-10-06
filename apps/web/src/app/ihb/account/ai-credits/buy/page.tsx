import type { Metadata } from "next";

import { BackLink, CreditPurchase } from "@/components/plan2build/billing";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireSignedIn } from "@/lib/session";

export const metadata: Metadata = { title: getTranslator("Billing")("credits.title") };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Buy one AI credit (L-04: single credits only, separate from the package).
export default async function BuyCreditPage({
  searchParams,
}: {
  searchParams: Promise<{ project?: string | string[] }>;
}) {
  const { project } = await searchParams;
  const projectId = typeof project === "string" && UUID.test(project) ? project : null;
  await requireSignedIn(`/account/ai-credits/buy${projectId ? `?project=${projectId}` : ""}`);
  const { data } = await (await serverApi()).GET("/api/v1/me/ai-credits");
  if (!data) throw new Error("AI credits could not be loaded");
  const t = getTranslator("Billing");
  return (
    <PageContainer>
      {projectId && (
        <BackLink href={`/projects/${projectId}/designs`} label={t("credits.backToDesigns")} />
      )}
      <PageHeader title={t("credits.title")} description={t("credits.intro")} />
      <p className="text-sm font-medium">{t("account.balance", { count: data.balance })}</p>
      {data.offer ? (
        <CreditPurchase offer={data.offer} states={data.states} projectId={projectId} />
      ) : (
        <Notice tone="info">{t("package.notConfigured")}</Notice>
      )}
    </PageContainer>
  );
}
