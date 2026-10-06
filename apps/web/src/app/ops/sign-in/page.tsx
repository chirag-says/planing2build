import type { Metadata } from "next";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { SignInForm } from "@/components/plan2build/sign-in-form";
import { Card, CardContent } from "@/components/ui/card";
import { getTranslator } from "@/lib/i18n";

export const metadata: Metadata = { title: getTranslator("Ops")("signIn.title") };

// Staff accounts are created by operations (no self-registration on this host); the same emailed
// code signs them in, and the entry route then asks for the second factor.
export default async function StaffSignInPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const t = getTranslator("Ops");
  const { next } = await searchParams;
  return (
    <PageContainer width="narrow">
      <PageHeader title={t("signIn.title")} description={t("signIn.intro")} />
      <Card>
        <CardContent>
          <SignInForm next={typeof next === "string" ? next : undefined} />
        </CardContent>
      </Card>
    </PageContainer>
  );
}
