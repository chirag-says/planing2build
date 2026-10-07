import { ArrowRightIcon, InboxIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { EmptyState } from "@/components/plan2build/states";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatDate, formatDateTime } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireOnboarded } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Pro")("connections.title") };

// Requests families sent (Slice 3.4). Before acceptance each shows the brief only (N-08).
export default async function ProConnectionsPage() {
  await requireOnboarded();
  const { data, response } = await (await serverApi()).GET("/api/v1/pro/connections");
  if (response.status === 401) redirect("/sign-in?next=%2Fconnections");
  if (response.status === 404) redirect("/profile");
  if (!data) throw new Error("the requests could not be loaded");
  const t = getTranslator("Pro");
  return (
    <PageContainer>
      <PageHeader title={t("connections.title")} description={t("connections.intro")} />
      {data.items.length === 0 ? (
        <EmptyState icon={InboxIcon} title={t("connections.empty")} description={t("connections.emptyBody")} />
      ) : (
        <ul className="flex flex-col gap-3">
          {data.items.map((item) => (
            <li key={item.id}>
              <Card size="sm">
                <CardHeader>
                  <CardTitle className="text-base">
                    <h2>
                      {item.category_name}
                      {item.brief.locality ? ` · ${item.brief.locality}` : ""}
                    </h2>
                  </CardTitle>
                  <CardAction>
                    <StatusBadge kind="connection" status={item.state} />
                  </CardAction>
                </CardHeader>
                <CardContent className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm text-muted-foreground">
                    {item.state === "SENT"
                      ? t("connections.respondBy", { date: formatDateTime(item.respond_by) })
                      : t("connections.received", { date: formatDate(item.sent_at) })}
                  </p>
                  <Button asChild variant="outline" size="sm">
                    <Link href={`/connections/${item.id}`} aria-label={`${t("connections.view")}: ${item.category_name}`}>
                      {t("connections.view")}
                      <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </PageContainer>
  );
}
