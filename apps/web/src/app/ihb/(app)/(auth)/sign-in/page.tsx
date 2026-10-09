import type { Metadata } from "next";

import { HangingCard } from "@/components/plan2build/hanging-card";
import { SignInForm } from "@/components/plan2build/sign-in-form";
import { SignedInNotice } from "@/components/plan2build/signed-in-notice";
import { getTranslator } from "@/lib/i18n";
import { safeNextPath } from "@/lib/navigation";
import { currentUser } from "@/lib/session";
import { professionalsSignInUrl } from "@/marketing/lib/hosts";

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
  // A session in this browser is shown, never silently used: the email is always asked for.
  const user = await currentUser();
  return (
    <HangingCard
      eyebrow={t("card.eyebrow")}
      title={t("title")}
      description={t("intro")}
      label={t("card.label")}
      note={t("card.note")}
    >
      {user && (
        <div className="mb-6">
          <SignedInNotice name={user.display_name} continueHref={safeNextPath(target, "/continue")} />
        </div>
      )}
      <SignInForm framed home="/continue" next={target} />
      {/* A professional who landed here signs in on their own site. */}
      <p className="mt-6 text-sm text-muted-foreground">
        {t("professional")}{" "}
        <a href={professionalsSignInUrl()} className="font-medium text-foreground underline underline-offset-4">
          {t("professionalLink")}
        </a>
      </p>
    </HangingCard>
  );
}
