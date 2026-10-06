import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import {
  CancelPackageForm,
  StaffInvoiceLink,
  StaffRefundForm,
} from "@/components/plan2build/ops-billing";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { ProjectBreadcrumb } from "@/components/plan2build/project-breadcrumb";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatDate, formatRupees } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("billing.title") };

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="text-base"><h2>{title}</h2></CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-sm">{children}</CardContent>
    </Card>
  );
}

// One order as operations see it: payments (applied or not), refunds, invoices, package history,
// refund requests; raise a refund request; ADMIN may cancel the package.
export default async function OpsOrderPage({ params }: { params: Promise<{ orderId: string }> }) {
  const { orderId } = await params;
  const staff = await requireVerifiedStaff(`/billing/orders/${orderId}`);
  if (!staff.roles.includes("OPS") && !staff.roles.includes("ADMIN")) notFound();
  const response = await (await serverApi()).GET("/api/v1/ops/billing/orders/{order_id}", {
    params: { path: { order_id: orderId } },
  });
  if (response.response.status === 404 || response.response.status === 422) notFound();
  const order = response.data;
  if (!order) throw new Error("the order could not be loaded");
  const t = getTranslator("Ops");
  const b = getTranslator("Billing");
  const money = (amount: string) => b("money", { amount: formatRupees(amount) });
  const title = t("billing.order", { code: order.code });
  return (
    <PageContainer width="wide">
      <div className="flex flex-col gap-4">
        <ProjectBreadcrumb root={{ label: t("billing.title"), href: "/billing" }} trail={[{ label: title }]} />
        <PageHeader title={title} actions={<StatusBadge kind="order" status={order.state} withLabel />} />
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-6">
          <Section title={order.offering_name}>
            {order.is_test && <Badge variant="warning" className="self-start">{t("billing.testOrder")}</Badge>}
            <p>{b("package.total")}: {money(order.total)} ({b("package.taxable")} {money(order.taxable_total)})</p>
            <ul className="flex flex-col gap-1">
              {order.dues.map((due) => (
                <li key={due.due_id} className="flex flex-wrap items-center gap-2">
                  {b("order.due", { sequence: due.sequence })}: {money(due.amount)}
                  <StatusBadge kind="due" status={due.state} />
                </li>
              ))}
            </ul>
          </Section>
          <Section title={t("billing.payments")}>
            {order.payments.length === 0 ? <p className="text-muted-foreground">-</p> : (
              <ul className="flex flex-col gap-1">
                {order.payments.map((payment) => (
                  <li key={payment.payment_id} className="flex flex-col">
                    <span>{money(payment.amount)} · {payment.provider_payment_id} · {formatDate(payment.captured_at)}</span>
                    <span className="text-muted-foreground">
                      {payment.applied ? t("billing.applied") : t("billing.notApplied")} · {payment.source}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <Section title={t("billing.refundsMade")}>
            {order.refunds.length === 0 ? <p className="text-muted-foreground">-</p> : (
              <ul className="flex flex-col gap-1">
                {order.refunds.map((refund) => (
                  <li key={refund.refund_id}>
                    {money(refund.amount)} · {refund.state} · {formatDate(refund.created_at)}
                    {refund.failure && ` · ${refund.failure}`}
                  </li>
                ))}
              </ul>
            )}
            {order.staff_refund_requests.map((request) => (
              <Link key={request.request_id} href={`/billing/refunds/${request.request_id}`}
                className="flex flex-wrap items-center gap-2 underline underline-offset-4">
                {t("billing.refund")} · {formatDate(request.created_at)}
                <StatusBadge kind="refund" status={request.state} />
              </Link>
            ))}
          </Section>
          <Section title={t("billing.invoices")}>
            {order.invoices.length === 0 ? <p className="text-muted-foreground">-</p> : (
              <ul className="flex flex-col gap-2">
                {order.invoices.map((invoice) => (
                  <li key={invoice.invoice_id} className="flex flex-wrap items-center justify-between gap-2">
                    <span>{b(`order.invoiceKinds.${invoice.kind}`)} {invoice.code} · {money(invoice.total)}</span>
                    {invoice.document_ready && <StaffInvoiceLink invoiceId={invoice.invoice_id} code={invoice.code} />}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>
        <aside className="order-first flex flex-col gap-6 lg:order-none">
          <Section title={t("billing.buyer")}>
            <p className="break-all">{order.buyer_email ?? "-"}</p>
            <p>{order.buyer.name}</p>
            <p className="whitespace-pre-line text-muted-foreground">{order.buyer.address}</p>
          </Section>
          {order.package_history.length > 0 && (
            <Section title={t("billing.history")}>
              <ol className="flex flex-col gap-2">
                {order.package_history.map((entry, index) => (
                  <li key={`${entry.at}-${index}`} className="flex flex-col">
                    <span className="flex items-center gap-2">
                      <StatusBadge kind="package" status={entry.to_state} />
                      <span className="text-muted-foreground">{entry.actor_role} · {formatDate(entry.at)}</span>
                    </span>
                    {entry.reason && <span>{entry.reason}</span>}
                  </li>
                ))}
              </ol>
            </Section>
          )}
          {Number(order.refundable) > 0 && (
            <Section title={t("billing.staffRefund")}>
              <p>{t("billing.refundable", { amount: formatRupees(order.refundable) })}</p>
              <StaffRefundForm orderId={order.order_id} />
            </Section>
          )}
          {staff.roles.includes("ADMIN") && order.project_id &&
            order.package_history.at(-1)?.to_state === "ACTIVE" && (
              <Section title={t("billing.cancelPackage")}>
                <CancelPackageForm projectId={order.project_id} />
              </Section>
            )}
        </aside>
      </div>
    </PageContainer>
  );
}
