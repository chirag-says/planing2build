import { ArrowRightIcon, InboxIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { EmptyState, Notice } from "@/components/plan2build/states";
import { ReviewFlagBadge } from "@/components/plan2build/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("queue.title") };

// The requirement review queue (API 18): submissions waiting for Plan2Build review, oldest first,
// with their review flags and who is reviewing each one.
export default async function ReviewQueuePage({
  searchParams,
}: {
  searchParams: Promise<{ cursor?: string | string[] }>;
}) {
  const staff = await requireVerifiedStaff("/queue");
  const t = getTranslator("Ops");
  if (!staff.roles.includes("OPS")) {
    return (
      <PageContainer>
        <PageHeader title={t("noAccess.title")} />
        <Notice tone="warning">{t("noAccess.body")}</Notice>
      </PageContainer>
    );
  }
  const { cursor } = await searchParams;
  const { data } = await (
    await serverApi()
  ).GET("/api/v1/ops/queues/requirement-review", {
    params: { query: { cursor: typeof cursor === "string" ? cursor : undefined } },
  });
  if (!data) throw new Error("the review queue could not be loaded");

  return (
    <PageContainer width="wide">
      <PageHeader title={t("queue.title")} description={t("queue.intro")} />
      {data.entries.length === 0 ? (
        <EmptyState icon={InboxIcon} title={t("queue.empty")} />
      ) : (
        <Card size="sm">
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead scope="col">{t("queue.project")}</TableHead>
                  <TableHead scope="col">{t("queue.submitted")}</TableHead>
                  <TableHead scope="col" className="hidden md:table-cell">
                    {t("queue.locality")}
                  </TableHead>
                  <TableHead scope="col">{t("queue.flags")}</TableHead>
                  <TableHead scope="col" className="hidden md:table-cell">
                    {t("queue.reviewer")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.entries.map(({ item, project }) => (
                  <TableRow key={item.item_id}>
                    <TableCell className="font-medium tabular-nums">
                      {/* The code is the way in, so it stays reachable on a phone. */}
                      <Link
                        href={`/projects/${project.project_id}`}
                        className="inline-flex min-h-11 items-center text-foreground underline underline-offset-4 hover:text-muted-foreground sm:min-h-9"
                      >
                        {project.code}
                      </Link>
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {project.submitted_at ? formatDate(project.submitted_at) : ""}
                    </TableCell>
                    <TableCell className="hidden whitespace-normal md:table-cell">
                      {project.locality}
                    </TableCell>
                    <TableCell className="whitespace-normal">
                      {project.review_flags.length === 0 ? (
                        <span className="text-muted-foreground">{t("queue.none")}</span>
                      ) : (
                        <span className="flex flex-wrap gap-1">
                          {project.review_flags.map((flag) => (
                            <ReviewFlagBadge key={flag} flag={flag} />
                          ))}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      {item.claimed_by_me
                        ? t("queue.you")
                        : (item.claimed_by_email ?? (
                            <span className="text-muted-foreground">{t("queue.unclaimed")}</span>
                          ))}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      {data.next_cursor && (
        <Button asChild variant="outline" className="self-start">
          <Link href={`/queue?cursor=${encodeURIComponent(data.next_cursor)}`}>
            {t("queue.next")}
            <ArrowRightIcon aria-hidden="true" data-icon="inline-end" />
          </Link>
        </Button>
      )}
    </PageContainer>
  );
}
