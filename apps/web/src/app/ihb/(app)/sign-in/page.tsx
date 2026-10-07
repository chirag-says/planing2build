import type { Metadata } from "next";

import { HangingCard } from "@/components/plan2build/hanging-card";
import { SignInForm } from "@/components/plan2build/sign-in-form";
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
    <HangingCard
      eyebrow={t("card.eyebrow")}
      title={t("title")}
      description={t("intro")}
      label={t("card.label")}
      note={t("card.note")}
    >
      <SignInForm framed next={typeof next === "string" ? next : undefined} />
    </HangingCard>
  );
}
