import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { MfaVerifyForm } from "@/components/plan2build/mfa-forms";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { getTranslator } from "@/lib/i18n";
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
  return (
    <PageContainer width="narrow">
      <PageHeader title={t("mfa.verifyTitle")} description={t("mfa.verifyIntro")} />
      <Card>
        <CardContent>
          <MfaVerifyForm next={typeof next === "string" ? next : undefined} />
        </CardContent>
      </Card>
    </PageContainer>
  );
}
