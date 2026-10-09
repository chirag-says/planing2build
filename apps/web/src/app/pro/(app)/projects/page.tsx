import type { Metadata } from "next";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import Link from "next/link";

import { ActiveWork } from "@/components/plan2build/pro-console";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { loadConsole, loadEngagements } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Console")("projectsPage.title") };

// The professional's projects: won through a request to quote (with the build's stages) and the
// services families engaged them for. Each sheet opens the project's own screen.
export default async function ProProjectsPage() {
  const [c, engagements] = await Promise.all([loadConsole("/projects"), loadEngagements()]);
  const t = getTranslator("Console");
  const e = getTranslator("Engagement");
  // Only what the API records as ended: never a history rebuilt from the browser.
  const past = engagements.filter((item) => item.ended);
  return (
    <PageContainer width="wide" className="max-w-6xl">
      <PageHeader size="compact" title={t("projectsPage.title")} description={t("projectsPage.intro")} />
      <ActiveWork console={c} heading={false} />
      <section aria-labelledby="past-title" className="flex flex-col gap-3 border-t-2 border-foreground pt-4">
        <h2 id="past-title" className="font-heading text-2xl leading-none">
          {t("projectsPage.past")}
        </h2>
        <p className="text-sm text-muted-foreground">{t("projectsPage.pastIntro")}</p>
        {past.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("projectsPage.pastNone")}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {past.map((item) => (
              <li key={item.engagementId} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
                <span>
                  <Link href={`/engagements/${item.engagementId}`} className="font-medium underline underline-offset-4">
                    {item.projectCode}
                  </Link>
                  <span className="text-muted-foreground">{` · ${item.category}`}</span>
                </span>
                <span className="text-muted-foreground">{e("since", { date: formatDate(item.startedAt) })}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </PageContainer>
  );
}
