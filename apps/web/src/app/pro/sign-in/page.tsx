import type { Metadata } from "next";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { SignInForm } from "@/components/plan2build/sign-in-form";
import { Card, CardContent } from "@/components/ui/card";
import { getTranslator } from "@/lib/i18n";

export const metadata: Metadata = { title: getTranslator("Pro")("signIn.title") };

// One emailed code signs a professional in, or registers them (D-04). Registering makes nothing
// public: only an approved category is listed.
export default async function ProSignInPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const t = getTranslator("Pro");
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
