import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ResolveException } from "@/components/plan2build/ops-billing";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { ProjectBreadcrumb } from "@/components/plan2build/project-breadcrumb";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("billing.exceptions") };

// Payments billing would not apply automatically: what was expected, what the provider reported,
// and a resolution with a reason. Resolving never applies money; refunds go through a request.
export default async function OpsExceptionsPage() {
  const staff = await requireVerifiedStaff("/billing/exceptions");
  if (!staff.roles.includes("OPS") && !staff.roles.includes("ADMIN")) notFound();
  const { data } = await (await serverApi()).GET("/api/v1/ops/billing/exceptions");
  const t = getTranslator("Ops");
  const title = t("billing.exceptions");
  return (
    <PageContainer width="wide">
      <div className="flex flex-col gap-4">
        <ProjectBreadcrumb root={{ label: t("billing.title"), href: "/billing" }} trail={[{ label: title }]} />
        <PageHeader title={title} />
      </div>
      {(data ?? []).length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("billing.noExceptions")}</p>
      ) : (
        <ul className="flex flex-col gap-4">
          {(data ?? []).map((exception) => (
            <li key={exception.exception_id}>
              <Card size="sm">
                <CardHeader>
                  <CardTitle className="flex flex-wrap items-center gap-2 text-base">
                    <h2>{t(`billing.kinds.${exception.kind}`)}</h2>
                    <Badge variant={exception.state === "OPEN" ? "warning" : "neutral"}>{exception.state}</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-2 text-sm">
                  <p className="text-muted-foreground">{exception.provider_ref} · {formatDate(exception.created_at)}</p>
                  {exception.order_id && exception.order_code && (
                    <Link href={`/billing/orders/${exception.order_id}`} className="underline underline-offset-4">
                      {t("billing.order", { code: exception.order_code })}
                    </Link>
                  )}
                  <p className="break-all font-mono text-xs">
                    {t("billing.expected")}: {JSON.stringify(exception.expected)}
                  </p>
                  <p className="break-all font-mono text-xs">
                    {t("billing.observed")}: {JSON.stringify(exception.observed)}
                  </p>
                  {exception.state === "OPEN" ? (
                    <ResolveException exceptionId={exception.exception_id} />
                  ) : (
                    <p>{t("billing.resolved", { resolution: exception.resolution ?? "" })}</p>
                  )}
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </PageContainer>
  );
}
