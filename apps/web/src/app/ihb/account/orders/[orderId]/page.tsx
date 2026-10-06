import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { BackLink, OrderView } from "@/components/plan2build/billing";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireSignedIn } from "@/lib/session";

export const metadata: Metadata = { title: getTranslator("Billing")("account.title") };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// An AI credit order (orders without a project): payment, invoice, refund requests.
export default async function AccountOrderPage({
  params,
  searchParams,
}: {
  params: Promise<{ orderId: string }>;
  searchParams: Promise<{ project?: string | string[] }>;
}) {
  const { orderId } = await params;
  const { project } = await searchParams;
  await requireSignedIn(`/account/orders/${orderId}`);
  if (!UUID.test(orderId)) notFound();
  const response = await (await serverApi()).GET("/api/v1/orders/{order_id}", {
    params: { path: { order_id: orderId } },
  });
  if (response.response.status === 404) notFound();
  const order = response.data;
  if (!order) throw new Error("the order could not be loaded");
  const t = getTranslator("Billing");
  const projectId = typeof project === "string" && UUID.test(project) ? project : null;
  return (
    <PageContainer>
      <BackLink
        href={projectId ? `/projects/${projectId}/designs` : "/account/billing"}
        label={projectId ? t("credits.backToDesigns") : t("account.title")}
      />
      <PageHeader title={t("order.title", { code: order.code })} />
      <OrderView order={order} />
    </PageContainer>
  );
}
