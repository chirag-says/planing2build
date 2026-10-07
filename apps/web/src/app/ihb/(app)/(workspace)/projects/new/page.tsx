import type { Metadata } from "next";

import { CreateProjectButton } from "@/components/plan2build/create-project-button";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { getTranslator } from "@/lib/i18n";
import { requireSignedIn } from "@/lib/session";

// The page title names the page (WCAG 2.4.2); the layout adds "| Plan2Build".
export const metadata: Metadata = { title: getTranslator("Projects")("newTitle") };

export default async function NewProjectPage() {
  await requireSignedIn("/projects/new");
  const t = getTranslator("Projects");
  return (
    <PageContainer>
      <PageHeader title={t("newTitle")} />
      <Card>
        <CardContent className="flex flex-col gap-6">
          <p className="text-base">{t("newIntro")}</p>
          <CreateProjectButton />
        </CardContent>
      </Card>
    </PageContainer>
  );
}
