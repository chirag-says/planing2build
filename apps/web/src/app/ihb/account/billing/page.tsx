import type { Metadata } from "next";
import Link from "next/link";

import { OrderBadge } from "@/components/plan2build/billing";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import { serverApi } from "@/lib/api/server";
import { formatDate, formatRupees } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireSignedIn } from "@/lib/session";

export const metadata: Metadata = { title: getTranslator("Billing")("account.title") };

// The account's orders, invoices and AI credits (Slice 3.3).
export default async function BillingPage() {
  await requireSignedIn("/account/billing");
  const { data } = await (await serverApi()).GET("/api/v1/me/billing");
  if (!data) throw new Error("billing could not be loaded");
  const t = getTranslator("Billing");
  return (
    <PageContainer>
      <PageHeader title={t("account.title")} description={t("account.intro")} />
      <section aria-labelledby="credits" className="flex flex-col gap-3">
        <SectionHeader id="credits" title={t("account.credits")} />
        <p className="text-sm font-medium">
          {t("account.balance", { count: data.credit_balance })}
        </p>
        <Button asChild variant="outline" className="sm:self-start">
          <Link href="/account/ai-credits/buy">{t("account.buyCredit")}</Link>
        </Button>
      </section>
      <section aria-labelledby="orders" className="flex flex-col gap-3">
        <SectionHeader id="orders" title={t("account.orders")} />
        {data.orders.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("account.none")}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {data.orders.map((order) => (
              <li
                key={order.order_id}
                className="flex flex-wrap items-center gap-2 rounded-md border border-border p-3 text-sm"
              >
                <Link
                  className="font-medium underline underline-offset-4"
                  href={
                    order.project_id
                      ? `/projects/${order.project_id}/package/orders/${order.order_id}`
                      : `/account/orders/${order.order_id}`
                  }
                >
                  {order.code}
                </Link>
                <OrderBadge kind={order.kind} />
                <StatusBadge kind="order" status={order.state} />
                <span className="text-muted-foreground">
                  {t("money", { amount: formatRupees(order.total) })} ·{" "}
                  {formatDate(order.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </PageContainer>
  );
}
