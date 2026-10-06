import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Badge } from "@/components/ui/badge";
import { serverApi } from "@/lib/api/server";
import { formatDate, formatRupees } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("billing.title") };

// Billing for operations (Slice 3.3): refund requests to decide, payment exceptions to resolve,
// recent orders. OPS or ADMIN with a verified second factor.
export default async function OpsBillingPage() {
  const staff = await requireVerifiedStaff("/billing");
  if (!staff.roles.includes("OPS") && !staff.roles.includes("ADMIN")) notFound();
  const api = await serverApi();
  const [requested, failed, exceptions, orders] = await Promise.all([
    api.GET("/api/v1/ops/billing/refund-requests", { params: { query: { state: "REQUESTED" } } }),
    api.GET("/api/v1/ops/billing/refund-requests", { params: { query: { state: "FAILED" } } }),
    api.GET("/api/v1/ops/billing/exceptions"),
    api.GET("/api/v1/ops/billing/orders"),
  ]);
  const t = getTranslator("Ops");
  const money = getTranslator("Billing");
  const waiting = [...(requested.data ?? []), ...(failed.data ?? [])];
  const open = (exceptions.data ?? []).filter((e) => e.state === "OPEN");
  return (
    <PageContainer width="wide">
      <PageHeader title={t("billing.title")} />
      <section aria-labelledby="refunds" className="flex flex-col gap-3">
        <SectionHeader id="refunds" title={t("billing.refunds")} />
        {waiting.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("billing.noRefunds")}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {waiting.map((request) => (
              <li key={request.request_id} className="flex flex-wrap items-center gap-2 rounded-md border border-border p-3 text-sm">
                <Link href={`/billing/refunds/${request.request_id}`} className="font-medium underline underline-offset-4">
                  {t("billing.refund")} · {request.order_code}
                </Link>
                <StatusBadge kind="refund" status={request.state} />
                <span className="text-muted-foreground">
                  {t("billing.refundable", { amount: formatRupees(request.refundable) })} · {formatDate(request.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-labelledby="exceptions" className="flex flex-col gap-3">
        <SectionHeader
          id="exceptions"
          title={t("billing.exceptions")}
          action={<Link href="/billing/exceptions" className="text-sm underline underline-offset-4">{t("billing.allExceptions")}</Link>}
        />
        {open.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("billing.noExceptions")}</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {open.map((exception) => (
              <li key={exception.exception_id} className="flex flex-wrap items-center gap-2">
                <Badge variant="warning">{t(`billing.kinds.${exception.kind}`)}</Badge>
                {exception.order_code && exception.order_id && (
                  <Link href={`/billing/orders/${exception.order_id}`} className="underline underline-offset-4">
                    {exception.order_code}
                  </Link>
                )}
                <span className="text-muted-foreground">{formatDate(exception.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-labelledby="orders" className="flex flex-col gap-3">
        <SectionHeader id="orders" title={t("billing.orders")} />
        {(orders.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("billing.noOrders")}</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {(orders.data ?? []).map((order) => (
              <li key={order.order_id} className="flex flex-wrap items-center gap-2">
                <Link href={`/billing/orders/${order.order_id}`} className="font-medium underline underline-offset-4">
                  {order.code}
                </Link>
                <Badge variant="neutral">{money(`account.kinds.${order.kind}`)}</Badge>
                {order.is_test && <Badge variant="warning">{t("billing.testOrder")}</Badge>}
                <StatusBadge kind="order" status={order.state} />
                <span className="text-muted-foreground">
                  {money("money", { amount: formatRupees(order.total) })} · {formatDate(order.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </PageContainer>
  );
}
