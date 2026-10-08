import { ArrowRightIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { HangingCard } from "@/components/plan2build/hanging-card";
import { Button } from "@/components/ui/button";
import { getTranslator } from "@/lib/i18n";
import { ownProjects, requireSignedIn } from "@/lib/session";

// The page title names the page (WCAG 2.4.2); the layout adds "| Plan2Build".
export const metadata: Metadata = { title: getTranslator("Welcome")("title") };

// Where a plain sign-in lands (no page it was heading for). A family with a project goes on to
// its projects; a new one is asked once whether to describe the home now. Either answer is fine:
// the dashboard asks for the requirement again, so signing up never waits on a long form.
export default async function WelcomePage() {
  await requireSignedIn("/welcome");
  if ((await ownProjects())?.length) redirect("/projects");
  const t = getTranslator("Welcome");
  return (
    <HangingCard
      eyebrow={t("card.eyebrow")}
      title={t("title")}
      description={t("intro")}
      label={t("card.label")}
      note={t("card.note")}
    >
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <Button asChild size="lg">
            <Link href="/start">
              {t("now")}
              <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
            </Link>
          </Button>
          <p className="text-base text-muted-foreground">{t("nowHint")}</p>
        </div>
        <div className="flex flex-col gap-2">
          <Button asChild size="lg" variant="outline">
            <Link href="/projects">{t("skip")}</Link>
          </Button>
          <p className="text-base text-muted-foreground">{t("skipHint")}</p>
        </div>
      </div>
    </HangingCard>
  );
}
