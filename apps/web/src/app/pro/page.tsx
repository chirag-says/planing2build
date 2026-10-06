import { ArrowRightIcon, LayersIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { AddCategoryForm } from "@/components/plan2build/pro-forms";
import { EmptyState, Notice } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { loadOwnProfile } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Pro")("dashboard.title") };

// The professional's dashboard: profile completeness and each category's listing state (listing
// is per category, D-06). Approval alone lists a category; nothing here is paid (D-03).
export default async function ProDashboardPage() {
  const data = await loadOwnProfile("/");
  const t = getTranslator("Pro");
  const tops = data.available_categories.filter((c) => !c.parent_code);
  const added = new Set(data.categories.map((c) => c.code));
  return (
    <PageContainer>
      <PageHeader title={t("dashboard.title")} description={t("dashboard.intro")} />
      {data.profile.missing.length > 0 && (
        <Notice tone="info" title={t("dashboard.profileIncomplete")}>
          <Link href="/profile" className="font-medium underline underline-offset-4">
            {t("dashboard.completeProfile")}
          </Link>
        </Notice>
      )}
      <section aria-labelledby="categories" className="flex flex-col gap-4">
        <SectionHeader id="categories" title={t("dashboard.categories")} />
        {data.categories.length === 0 ? (
          <EmptyState icon={LayersIcon} title={t("dashboard.none")} description={t("dashboard.noneBody")} />
        ) : (
          <ul className="flex flex-col gap-3">
            {data.categories.map((category) => (
              <li key={category.code}>
                <Card size="sm">
                  <CardHeader>
                    <CardTitle className="text-base">
                      <h3>{category.name}</h3>
                    </CardTitle>
                    <CardDescription>
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
                  <CardContent className="flex flex-col gap-3">
                    {category.message && (
                      <Notice tone={category.listing_state === "LISTED" ? "info" : "warning"} title={t("category.message")}>
                        <p className="whitespace-pre-line">{category.message}</p>
                      </Notice>
                    )}
                    <Button asChild variant="outline" className="sm:self-start">
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
      <section aria-labelledby="add" className="flex flex-col gap-4">
        <SectionHeader id="add" title={t("dashboard.add")} />
        {tops.every((c) => added.has(c.code)) ? (
          <p className="text-sm text-muted-foreground">{t("dashboard.allAdded")}</p>
        ) : (
          <AddCategoryForm options={tops.filter((c) => !added.has(c.code))} />
        )}
      </section>
    </PageContainer>
  );
}
