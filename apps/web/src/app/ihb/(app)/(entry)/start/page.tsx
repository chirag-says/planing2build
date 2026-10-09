import type { Metadata } from "next";

import { EntryQuestions } from "@/components/plan2build/entry-questions";
import { HangingCard } from "@/components/plan2build/hanging-card";
import { getTranslator } from "@/lib/i18n";
import { currentUser } from "@/lib/session";

// The page title names the page (WCAG 2.4.2); the layout adds "| Plan2Build".
export const metadata: Metadata = { title: getTranslator("Start")("title") };

// Where every public "build plan" button lands, and where "New project" starts: the two entry
// questions, then the project is created. `ready=1` is how sign-in returns here with both answers
// already given.
export default async function StartPage({ searchParams }: { searchParams: Promise<{ ready?: string }> }) {
  const [{ ready }, user] = await Promise.all([searchParams, currentUser()]);
  const t = getTranslator("Start");
  return (
    <HangingCard
      eyebrow={t("card.eyebrow")}
      title={t("title")}
      description={t("card.intro")}
      label={t("card.label")}
      note={t("card.note")}
    >
      <EntryQuestions framed signedIn={Boolean(user)} ready={ready === "1"} />
    </HangingCard>
  );
}
