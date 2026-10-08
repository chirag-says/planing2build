import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";

export const metadata: Metadata = { title: getTranslator("Rfq")("proTitle") };

// Requests to quote sent to the contractor (Slice 3.6, functional): the brief only until accepted.
export default async function ProQuotesPage() {
  const { data, response } = await (await serverApi()).GET("/api/v1/pro/rfq-invitations");
  if (response.status === 401) redirect("/sign-in?next=%2Fquotes");
  if (response.status === 404) redirect("/profile");
  const t = getTranslator("Rfq");
  const items = data?.items ?? [];
  return (
    <PageContainer>
      <PageHeader title={t("proTitle")} />
      {items.length === 0 && <p className="text-sm text-muted-foreground">{t("nothing")}</p>}
      <ul className="flex flex-col gap-2">
        {items.map((i) => (
          <li key={i.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm">
            <span>{t("locality", { value: i.locality ?? "" })} · {i.state}{i.outcome ? ` · ${i.outcome}` : ""}</span>
            <span>{t("deadline", { when: i.quotes_due_at ?? t("notSet") })}</span>
            <Link href={`/quotes/${i.id}`} className="font-medium underline underline-offset-4">{t("open")}</Link>
          </li>
        ))}
      </ul>
    </PageContainer>
  );
}
