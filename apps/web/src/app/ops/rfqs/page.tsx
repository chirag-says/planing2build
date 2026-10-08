import type { Metadata } from "next";
import Link from "next/link";

import { ActionButton, JsonForm } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("nav.rfqs") };

// Requests for quotation (Slice 3.6, functional): open ones first by deadline; the selection
// statement versions (ADMIN activates; wording pending final client and legal confirmation).
export default async function OpsRfqsPage() {
  const staff = await requireVerifiedStaff("/rfqs");
  const admin = staff.roles.includes("ADMIN");
  const api = await serverApi();
  const [rfqs, statements] = await Promise.all([
    api.GET("/api/v1/ops/rfqs"),
    api.GET("/api/v1/ops/selection-statements"),
  ]);
  const t = getTranslator("Rfq");
  return (
    <PageContainer width="wide">
      <PageHeader title={t("opsTitle")} />
      <ul className="flex flex-col gap-2">
        {(rfqs.data?.items ?? []).map((r) => (
          <li key={r.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm">
            <span>{t("project", { code: r.project_code })} · {r.state} · {r.invitations} / {r.quotes} / {r.pending_reviews}</span>
            <span>{t("deadline", { when: r.quotes_due_at ?? t("notSet") })}</span>
            <span className="flex flex-wrap gap-4">
              <Link href={`/rfqs/${r.id}`} className="font-medium underline underline-offset-4">{t("open")}</Link>
              <Link href={`/rfqs/project/${r.project_id}`} className="underline underline-offset-4">{t("opsProjectLink")}</Link>
            </span>
          </li>
        ))}
      </ul>
      <section aria-labelledby="statements" className="flex flex-col gap-3">
        <SectionHeader id="statements" title={t("statements")} />
        <ul className="flex flex-col gap-2 text-sm">
          {(statements.data ?? []).map((s) => (
            <li key={s.id} className="flex flex-col gap-1">
              <span className="font-medium">v{s.version} · {s.status}</span>
              <p>{s.text}</p>
              <p className="text-muted-foreground">{s.note}</p>
              {admin && s.status === "DRAFT" && (
                <ActionButton label={t("activate")} url={`/api/v1/admin/selection-statements/${s.id}/activate`} once={false} />
              )}
            </li>
          ))}
        </ul>
        {admin && (
          <JsonForm id="new-selection-statement" label={t("newStatement")} method="POST" url="/api/v1/admin/selection-statements"
            initial={JSON.stringify({ text: "", note: "" }, null, 2)} submitLabel={t("send")} once />
        )}
      </section>
    </PageContainer>
  );
}
