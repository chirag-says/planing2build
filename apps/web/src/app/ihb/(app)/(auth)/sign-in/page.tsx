import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { HangingCard } from "@/components/plan2build/hanging-card";
import { SignInForm } from "@/components/plan2build/sign-in-form";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { safeNextPath } from "@/lib/navigation";

// The page title names the page (WCAG 2.4.2); the layout adds "| Plan2Build".
export const metadata: Metadata = { title: getTranslator("SignIn")("title") };

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const t = getTranslator("SignIn");
  const { next } = await searchParams;
  const target = typeof next === "string" ? next : undefined;
  // Already signed in (the website's header always offers Sign in): straight on to the projects.
  let signedIn = false;
  try {
    signedIn = Boolean((await (await serverApi()).GET("/api/v1/me")).data);
  } catch {
    // The API being unreachable must not take the page down; the form handles its own errors.
  }
  if (signedIn) redirect(safeNextPath(target, "/projects"));
  return (
    <HangingCard
      eyebrow={t("card.eyebrow")}
      title={t("title")}
      description={t("intro")}
      label={t("card.label")}
      note={t("card.note")}
    >
      <SignInForm framed home="/welcome" next={target} />
    </HangingCard>
  );
}
