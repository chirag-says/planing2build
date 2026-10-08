import type { Metadata } from "next";

import { EntryQuestions } from "@/components/plan2build/entry-questions";
import { HangingCard } from "@/components/plan2build/hanging-card";
import { getTranslator } from "@/lib/i18n";

// The page title names the page (WCAG 2.4.2); the layout adds "| Plan2Build".
export const metadata: Metadata = { title: getTranslator("Start")("title") };

export default function StartPage() {
  const t = getTranslator("Start");
  return (
    <HangingCard
      eyebrow={t("card.eyebrow")}
      title={t("title")}
      description={t("card.intro")}
      label={t("card.label")}
      note={t("card.note")}
    >
      <EntryQuestions framed />
    </HangingCard>
  );
}
