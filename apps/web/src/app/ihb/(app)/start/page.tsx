import type { Metadata } from "next";

import { EntryQuestions } from "@/components/plan2build/entry-questions";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { getTranslator } from "@/lib/i18n";

// The page title names the page (WCAG 2.4.2); the layout adds "| Plan2Build".
export const metadata: Metadata = { title: getTranslator("Start")("title") };

export default function StartPage() {
  const t = getTranslator("Start");
  return (
    <PageContainer>
      <PageHeader title={t("title")} />
      <Card>
        <CardContent>
          <EntryQuestions />
        </CardContent>
      </Card>
    </PageContainer>
  );
}
