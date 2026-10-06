import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { RefundDecision } from "@/components/plan2build/ops-billing";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { ProjectBreadcrumb } from "@/components/plan2build/project-breadcrumb";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Card, CardContent } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatDate, formatRupees } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("billing.refund") };

// One refund request: what was asked, what remains refundable, which package services were
// delivered (the "substantial work" record, O-04), and the decision with a reason (L-03).
export default async function OpsRefundPage({ params }: { params: Promise<{ requestId: string }> }) {
  const { requestId } = await params;
  const staff = await requireVerifiedStaff(`/billing/refunds/${requestId}`);
  if (!staff.roles.includes("OPS") && !staff.roles.includes("ADMIN")) notFound();
  const response = await (await serverApi()).GET("/api/v1/ops/billing/refund-requests/{request_id}", {
    params: { path: { request_id: requestId } },
  });
  if (response.response.status === 404 || response.response.status === 422) notFound();
  const request = response.data;
  if (!request) throw new Error("the refund request could not be loaded");
  const t = getTranslator("Ops");
  const title = `${t("billing.refund")} · ${request.order_code}`;
  return (
    <PageContainer>
      <div className="flex flex-col gap-4">
        <ProjectBreadcrumb root={{ label: t("billing.title"), href: "/billing" }} trail={[{ label: title }]} />
        <PageHeader title={title} actions={<StatusBadge kind="refund" status={request.state} withLabel />} />
      </div>
      <Card size="sm">
        <CardContent className="flex flex-col gap-2 text-sm">
          <Link href={`/billing/orders/${request.order_id}`} className="font-medium underline underline-offset-4">
            {t("billing.order", { code: request.order_code })}
          </Link>
          <p className="break-all">{request.buyer_email}</p>
          <p>{t("billing.requestedBy", { role: request.requested_role })} · {formatDate(request.created_at)}</p>
          <p className="whitespace-pre-line">{request.reason}</p>
          <p className="font-medium">{t("billing.refundable", { amount: formatRupees(request.refundable) })}</p>
          {request.kind === "PACKAGE" && (
            <p className="text-muted-foreground">
              {request.package_services_used.length
                ? t("billing.servicesUsed", { services: request.package_services_used.join(", ") })
                : t("billing.noServicesUsed")}
            </p>
          )}
          {request.decision && (
            <p>{request.decision.decision}: {request.decision.reason}</p>
          )}
        </CardContent>
      </Card>
      <RefundDecision request={request} />
    </PageContainer>
  );
}
