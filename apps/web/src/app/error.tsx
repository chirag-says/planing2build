"use client";

import { RotateCcwIcon } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { Button } from "@/components/ui/button";
import { getTranslator } from "@/lib/i18n";

const t = getTranslator("Common");

// Shown when a page cannot load its data (for example the API is down). Details stay in the logs.
export default function ErrorPage({ retry }: { error: Error; retry: () => void }) {
  return (
    <PageContainer width="narrow">
      <PageHeader title={t("errorTitle")} description={t("errorBody")} />
      <Button type="button" size="lg" onClick={() => retry()} className="self-start">
        <RotateCcwIcon aria-hidden="true" />
        {t("retry")}
      </Button>
    </PageContainer>
  );
}
