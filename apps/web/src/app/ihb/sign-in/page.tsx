import type { Metadata } from "next";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { SignInForm } from "@/components/plan2build/sign-in-form";
import { Card, CardContent } from "@/components/ui/card";
import { getTranslator } from "@/lib/i18n";

// The page title names the page (WCAG 2.4.2); the layout adds "| Plan2Build".
export const metadata: Metadata = { title: getTranslator("SignIn")("title") };

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const t = getTranslator("SignIn");
  const { next } = await searchParams;
  return (
    <PageContainer width="narrow">
      <PageHeader title={t("title")} description={t("intro")} />
      <Card>
        <CardContent>
          <SignInForm next={typeof next === "string" ? next : undefined} />
        </CardContent>
      </Card>
    </PageContainer>
  );
}
