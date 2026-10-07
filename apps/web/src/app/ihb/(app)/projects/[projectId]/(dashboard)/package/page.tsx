import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { PackagePurchase } from "@/components/plan2build/billing";
import { SectionHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import { serverApi } from "@/lib/api/server";
import { formatDate, formatRupees } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  const area = getTranslator("Dashboard")("areas.package");
  return { title: await projectTitle((await params).projectId, area) };
}

// The one Plan2Build package (Slice 3.3): what it gives, its state, and when it can be bought,
// the server's price and the way to pay. Buying it changes nothing else about the project.
export default async function ProjectPackagePage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const { project } = await loadProject(projectId);
  if (!dashboardOpen(project.status)) redirect(`/projects/${projectId}`);
  const { data: view } = await (await serverApi()).GET("/api/v1/projects/{project_id}/package", {
    params: { path: { project_id: projectId } },
  });
  if (!view) throw new Error("the package could not be loaded");
  const t = getTranslator("Billing");
  const missing = view.unavailable?.missing.join(", ") ?? "";
  return (
    <section aria-labelledby="package" className="flex flex-col gap-6">
      <SectionHeader
        id="package"
        title={t("package.title")}
        description={t("package.intro")}
        action={<StatusBadge kind="package" status={view.state} withLabel />}
      />
      {view.state === "ACTIVE" && <Notice tone="success">{t("package.active")}</Notice>}
      {(view.state === "CANCELLED" || view.state === "REFUNDED") && (
        <Notice tone="info">{t("package.ended")}</Notice>
      )}
      {view.availability !== "ELIGIBLE" && <Notice tone="info">{t("package.notEligible")}</Notice>}
      {view.open_order_id ? (
        <Notice tone="info" title={t("package.openOrder")}>
          <Button asChild className="mt-2">
            <Link href={`/projects/${projectId}/package/orders/${view.open_order_id}`}>
              {t("package.continueOrder")}
            </Link>
          </Button>
        </Notice>
      ) : (
        view.offer && (
          <PackagePurchase projectId={projectId} offer={view.offer} states={view.states} />
        )
      )}
      {view.unavailable &&
        (view.unavailable.code === "PRICE_UNAVAILABLE" ? (
          <Notice tone="warning">{t("package.priceUnavailable", { missing })}</Notice>
        ) : (
          <Notice tone="info">{t("package.notConfigured")}</Notice>
        ))}
      {view.orders.length > 0 && (
        <section aria-labelledby="orders" className="flex flex-col gap-3">
          <h3 id="orders" className="font-heading text-base font-medium">
            {t("package.orders")}
          </h3>
          <ul className="flex flex-col gap-2 text-sm">
            {view.orders.map((order) => (
              <li key={order.order_id} className="flex flex-wrap items-center gap-2">
                <Link
                  href={`/projects/${projectId}/package/orders/${order.order_id}`}
                  className="font-medium underline underline-offset-4"
                >
                  {order.code}
                </Link>
                <StatusBadge kind="order" status={order.state} />
                <span className="text-muted-foreground">
                  {t("money", { amount: formatRupees(order.total) })} ·{" "}
                  {formatDate(order.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  );
}
