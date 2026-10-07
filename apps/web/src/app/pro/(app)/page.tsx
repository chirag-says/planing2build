import { ArrowRightIcon, CircleCheckIcon, LayersIcon, UserRoundPenIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { OnboardingRail } from "@/components/plan2build/onboarding-rail";
import { AddCategoryForm } from "@/components/plan2build/pro-forms";
import { EmptyState, Notice } from "@/components/plan2build/states";
import { StatGrid } from "@/components/plan2build/stat-tile";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { loadOwnProfile, loadProCounts, type ProDashboard } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Pro")("dashboard.title") };

// The professional's dashboard: profile completeness and each category's listing state (listing
// is per category, D-06). Approval alone lists a category; nothing here is paid (D-03).
/** Profile completeness and the portfolio, beside the categories. */
function ProfileCard({ data }: { data: ProDashboard }) {
  const t = getTranslator("Pro");
  const missing = data.profile.missing.length;
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl group-data-[size=sm]/card:text-xl">
          <UserRoundPenIcon aria-hidden="true" className="size-5 text-muted-foreground" />
          <h2>{t("profileCard.title")}</h2>
        </CardTitle>
        <CardDescription className="text-base">{data.profile.firm_name ?? data.profile.display_name ?? undefined}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-base">
        <p className="flex items-center gap-2 font-medium">
          {missing === 0 && <CircleCheckIcon aria-hidden="true" className="size-4 text-success" />}
          {missing === 0 ? t("profileCard.complete") : t("profileCard.missing", { count: missing })}
        </p>
        <p className="text-muted-foreground">{t("profileCard.portfolio", { count: data.portfolio.length })}</p>
      </CardContent>
      <CardFooter>
        <Button asChild variant="outline">
          <Link href="/profile">
            {t("profileCard.edit")}
            <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
          </Link>
        </Button>
      </CardFooter>
    </Card>
  );
}

export default async function ProDashboardPage() {
  const data = await loadOwnProfile("/");
  const counts = await loadProCounts();
  const t = getTranslator("Pro");
  const tops = data.available_categories.filter((c) => !c.parent_code);
  const added = new Set(data.categories.map((c) => c.code));
  const listed = data.categories.filter((c) => c.listing_state === "LISTED").length;
  return (
    <PageContainer width="wide">
      <PageHeader size="compact" title={t("dashboard.title")} description={t("dashboard.intro")} />
      <StatGrid
        id="at-a-glance"
        title={t("kpi.title")}
        stats={[
          {
            label: t("kpi.listed"),
            value: listed,
            caption: t("kpi.listedCaption", { total: data.categories.length }),
            tone: "lead",
          },
          {
            label: t("kpi.requests"),
            value: counts.requests,
            caption: t("kpi.requestsCaption"),
            href: "/connections",
            tone: counts.requests > 0 ? "attention" : "default",
          },
          {
            label: t("kpi.quotes"),
            value: counts.quotes,
            caption: t("kpi.quotesCaption"),
            href: "/quotes",
            tone: counts.quotes > 0 ? "attention" : "default",
          },
          {
            label: t("kpi.inspections"),
            value: counts.inspections,
            caption: t("kpi.inspectionsCaption"),
            href: "/inspections",
          },
        ]}
      />
      <Card size="sm">
        <CardContent>
          <OnboardingRail data={data} />
        </CardContent>
      </Card>
      {data.profile.missing.length > 0 && (
        <Notice tone="info" title={t("dashboard.profileIncomplete")}>
          <Link href="/profile" className="font-medium underline underline-offset-4">
            {t("dashboard.completeProfile")}
          </Link>
        </Notice>
      )}
      <div className="grid items-start gap-8 lg:grid-cols-3 lg:gap-6">
        <div className="flex min-w-0 flex-col gap-8 lg:col-span-2">
          <section aria-labelledby="categories" className="flex flex-col gap-4">
            <SectionHeader id="categories" title={t("dashboard.categories")} />
            {data.categories.length === 0 ? (
              <EmptyState icon={LayersIcon} title={t("dashboard.none")} description={t("dashboard.noneBody")} />
            ) : (
              <ul className="grid gap-3 xl:grid-cols-2">
                {data.categories.map((category) => (
                  <li key={category.code} className="min-w-0">
                    <Card size="sm" className="h-full">
                      <CardHeader>
                        <CardTitle className="text-xl group-data-[size=sm]/card:text-xl">
                          <h3>{category.name}</h3>
                        </CardTitle>
                        <CardDescription className="text-base">
                          {category.public
                            ? t("dashboard.public")
                            : category.hidden
                              ? t("dashboard.hidden")
                              : t("dashboard.notPublic")}
                          {category.review_due_at &&
                            ` · ${t("dashboard.reviewDue", { date: formatDate(category.review_due_at) })}`}
                        </CardDescription>
                        <CardAction>
                          <StatusBadge kind="listing" status={category.listing_state} withLabel />
                        </CardAction>
                      </CardHeader>
                      <CardContent className="flex flex-1 flex-col gap-3">
                        {category.message && (
                          <Notice
                            tone={category.listing_state === "LISTED" ? "info" : "warning"}
                            title={t("category.message")}
                          >
                            <p className="whitespace-pre-line">{category.message}</p>
                          </Notice>
                        )}
                        <Button asChild variant="outline" className="mt-auto sm:self-start">
                          <Link href={`/categories/${category.code}`}>
                            {t("dashboard.open")}
                            <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
                          </Link>
                        </Button>
                      </CardContent>
                    </Card>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section id="add" aria-labelledby="add-title" className="flex scroll-mt-24 flex-col gap-4">
            <SectionHeader id="add-title" title={t("dashboard.add")} />
            {tops.every((c) => added.has(c.code)) ? (
              <p className="text-sm text-muted-foreground">{t("dashboard.allAdded")}</p>
            ) : (
              <AddCategoryForm options={tops.filter((c) => !added.has(c.code))} />
            )}
          </section>
        </div>
        <ProfileCard data={data} />
      </div>
    </PageContainer>
  );
}
