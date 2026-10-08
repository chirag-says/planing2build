import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { MfaVerifyForm } from "@/components/plan2build/mfa-forms";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { Card, CardContent } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { mfaSummary } from "@/lib/ops-admin";
import { staffSession } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("mfa.verifyTitle") };

export default async function MfaVerifyPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const staff = await staffSession();
  if (!staff) redirect("/sign-in?next=%2Fmfa");
  if (!staff.mfa_enrolled) redirect("/mfa/setup");
  const t = getTranslator("Ops");
  const { next } = await searchParams;
  // The second factor's state (GET /auth/mfa): whether this session is verified and how many
  // recovery codes are left. The form works without it, so a failed read only shows a notice.
  const { data: status } = await (await serverApi()).GET("/api/v1/auth/mfa");
  const summary = status ? mfaSummary(status) : null;
  return (
    <PageContainer width="narrow">
      <PageHeader title={t("mfa.verifyTitle")} description={t("mfa.verifyIntro")} />
      {status && summary && (
        <Notice tone={summary === "noRecoveryCodes" ? "warning" : summary === "verified" ? "success" : "info"}
          title={t(`mfa.status.${summary}`)}>
          <span data-testid="mfa-recovery-left">{t("mfa.status.recoveryLeft", { count: status.recovery_codes_left })}</span>
        </Notice>
      )}
      {!status && <Notice tone="warning">{t("mfa.status.unavailable")}</Notice>}
      <Card>
        <CardContent>
          <MfaVerifyForm next={typeof next === "string" ? next : undefined} />
        </CardContent>
      </Card>
    </PageContainer>
  );
}
