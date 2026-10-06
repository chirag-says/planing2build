import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { BackLink, OrderView } from "@/components/plan2build/billing";
import { SectionHeader } from "@/components/plan2build/page-header";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  const area = getTranslator("Dashboard")("areas.package");
  return { title: await projectTitle((await params).projectId, area) };
}

// A package order: payments, invoices, refunds. The order belongs to this project's owner.
export default async function PackageOrderPage({
  params,
}: {
  params: Promise<{ projectId: string; orderId: string }>;
}) {
  const { projectId, orderId } = await params;
  await loadProject(projectId);
  const response = await (await serverApi()).GET("/api/v1/orders/{order_id}", {
    params: { path: { order_id: orderId } },
  });
  if (response.response.status === 404 || response.response.status === 422) notFound();
  const order = response.data;
  if (!order || order.project_id !== projectId) notFound();
  const t = getTranslator("Billing");
  return (
    <section aria-labelledby="order" className="flex flex-col gap-6">
      <BackLink href={`/projects/${projectId}/package`} label={t("package.title")} />
      <SectionHeader id="order" title={t("order.title", { code: order.code })} />
      <OrderView order={order} />
    </section>
  );
}
