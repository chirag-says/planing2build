import type { Metadata } from "next";

import { HangingCard } from "@/components/plan2build/hanging-card";
import { SignInForm } from "@/components/plan2build/sign-in-form";
import { SignedInNotice } from "@/components/plan2build/signed-in-notice";
import { getTranslator } from "@/lib/i18n";
import { safeNextPath } from "@/lib/navigation";
import { currentUser } from "@/lib/session";
import { homeownerSignInUrl } from "@/marketing/lib/hosts";

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
  // A session in this browser is shown, never silently used: the email is always asked for.
  const user = await currentUser();
  return (
    <HangingCard
      eyebrow={t("signIn.card.eyebrow")}
      title={t("signIn.title")}
      description={t("signIn.intro")}
      label={t("signIn.card.label")}
      note={t("signIn.card.note")}
    >
      {user && (
        <div className="mb-6">
          <SignedInNotice name={user.display_name} continueHref={safeNextPath(target, "/")} />
        </div>
      )}
      <SignInForm framed next={target} />
      {/* A family who landed here signs in on the homeowner site. */}
      <p className="mt-6 text-sm text-muted-foreground">
        {t("signIn.homeowner")}{" "}
        <a href={homeownerSignInUrl()} className="font-medium text-foreground underline underline-offset-4">
          {t("signIn.homeownerLink")}
        </a>
      </p>
    </HangingCard>
  );
}
