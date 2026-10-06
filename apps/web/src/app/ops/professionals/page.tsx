import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { CreateProfessionalForm } from "@/components/plan2build/ops-professional-review";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("professionals.title") };

type Entry = { category_id: string; display_name?: string | null; firm_name?: string | null;
  category_code: string; listing_state: "DRAFT" | "PENDING_REVIEW" | "CHANGES_REQUESTED" | "LISTED" | "REJECTED" | "SUSPENDED";
  submitted_at?: string | null; claimed?: boolean; claimed_by_me?: boolean };

function EntryList({ entries, empty }: { entries: Entry[]; empty: string }) {
  const t = getTranslator("Ops");
  if (entries.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <ul className="flex flex-col gap-2">
      {entries.map((e) => (
        <li key={e.category_id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border px-3 py-2">
          <span className="flex flex-col">
            <Link href={`/professionals/${e.category_id}`} className="font-medium underline-offset-4 hover:underline">
              {e.display_name ?? e.firm_name ?? e.category_id} · {e.category_code}
            </Link>
            {e.submitted_at && (
              <span className="text-xs text-muted-foreground">
                {t("professionals.submitted", { date: formatDate(e.submitted_at) })}
              </span>
            )}
          </span>
          <StatusBadge kind="listing" status={e.listing_state} />
        </li>
      ))}
    </ul>
  );
}

// Professional reviews: the queue (oldest first), listed and suspended categories, and creating
// an invited professional's account (D-04).
export default async function OpsProfessionalsPage() {
  const staff = await requireVerifiedStaff("/professionals");
  const isOps = staff.roles.includes("OPS");
  if (!isOps && !staff.roles.includes("ADMIN")) notFound();
  const api = await serverApi();
  const [queue, listed, suspended] = await Promise.all([
    isOps ? api.GET("/api/v1/ops/queues/professional-review") : Promise.resolve({ data: undefined }),
    api.GET("/api/v1/ops/professionals", { params: { query: { state: "LISTED" } } }),
    api.GET("/api/v1/ops/professionals", { params: { query: { state: "SUSPENDED" } } }),
  ]);
  const t = getTranslator("Ops");
  return (
    <PageContainer width="wide">
      <PageHeader title={t("professionals.title")} />
      {isOps && (
        <section aria-labelledby="waiting" className="flex flex-col gap-3">
          <SectionHeader id="waiting" title={t("professionals.waiting")} />
          <EntryList entries={queue.data?.entries ?? []} empty={t("professionals.none")} />
        </section>
      )}
      <section aria-labelledby="listed" className="flex flex-col gap-3">
        <SectionHeader id="listed" title={t("professionals.listed")} />
        <EntryList entries={listed.data ?? []} empty={t("professionals.noneInState")} />
      </section>
      <section aria-labelledby="suspended" className="flex flex-col gap-3">
        <SectionHeader id="suspended" title={t("professionals.suspended")} />
        <EntryList entries={suspended.data ?? []} empty={t("professionals.noneInState")} />
      </section>
      {isOps && (
        <Card size="sm">
          <CardHeader>
            <CardTitle className="text-base"><h2>{t("professionals.create")}</h2></CardTitle>
            <CardDescription>{t("professionals.createIntro")}</CardDescription>
          </CardHeader>
          <CardContent><CreateProfessionalForm /></CardContent>
        </Card>
      )}
    </PageContainer>
  );
}
