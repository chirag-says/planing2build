import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { HangingCard } from "@/components/plan2build/hanging-card";
import { SignInForm } from "@/components/plan2build/sign-in-form";
import { getTranslator } from "@/lib/i18n";
import { safeNextPath } from "@/lib/navigation";
import { currentUser } from "@/lib/session";

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
  const target = typeof next === "string" ? next : undefined;
  // Already signed in: straight on to the dashboard (or where they were going).
  if (await currentUser()) redirect(safeNextPath(target, "/"));
  return (
    <HangingCard
      eyebrow={t("signIn.card.eyebrow")}
      title={t("signIn.title")}
      description={t("signIn.intro")}
      label={t("signIn.card.label")}
      note={t("signIn.card.note")}
    >
      <SignInForm framed next={target} />
    </HangingCard>
  );
}
