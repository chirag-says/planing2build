import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { MfaSetupForm } from "@/components/plan2build/mfa-forms";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { getTranslator } from "@/lib/i18n";
import { staffSession } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("mfa.setupTitle") };

export default async function MfaSetupPage() {
  const staff = await staffSession();
  if (!staff) redirect("/sign-in?next=%2Fmfa%2Fsetup");
  if (staff.mfa_enrolled) redirect("/mfa");
  const t = getTranslator("Ops");
  return (
    <PageContainer>
      <PageHeader title={t("mfa.setupTitle")} description={t("mfa.setupIntro")} />
      <Card>
        <CardContent>
          <MfaSetupForm />
        </CardContent>
      </Card>
    </PageContainer>
  );
}
