import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { OpsRequestQuotes } from "@/components/plan2build/rfq";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { openRfq } from "@/lib/ops-flow";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("nav.rfqs") };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// One project's requests for quotation for operations, newest first, and a new DRAFT request at
// the owner's direction (QD-03) while none is open. The API decides whether a request can be made
// and answers with its reason; this page only shows a locked state while one is already open.
export default async function OpsProjectRfqsPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ q?: string }>;
}) {
  const { projectId } = await params;
  if (!UUID.test(projectId)) notFound();
  const q = ((await searchParams).q ?? "").slice(0, 80) || undefined;
  const staff = await requireVerifiedStaff(`/rfqs/project/${projectId}`);
  const api = await serverApi();
  const path = { params: { path: { project_id: projectId } } };
  const [rfqs, detail, directory] = await Promise.all([
    api.GET("/api/v1/ops/projects/{project_id}/rfqs", path),
    // the project code when no request exists yet (operations role only; optional)
    staff.roles.includes("OPS") ? api.GET("/api/v1/ops/projects/{project_id}", path) : null,
    api.GET("/api/v1/public/professionals", { params: { query: { category: "CONTRACTOR", q } } }),
  ]);
  if (rfqs.response.status === 404 || rfqs.response.status === 422) notFound();
  const t = getTranslator("Rfq");
  const items = rfqs.data?.items ?? [];
  const code = items[0]?.project_code ?? detail?.data?.project.code;
  const title = code ? t("opsProjectTitle", { code }) : t("opsProjectTitleNoCode");
  if (!rfqs.data) {
    const message = (rfqs.error as { error?: { message?: string } } | undefined)?.error?.message;
    return (
      <PageContainer width="wide">
        <PageHeader title={title} />
        <Notice tone="error">{t("errorReason", { reason: message ?? t("error") })}</Notice>
      </PageContainer>
    );
  }
  const open = openRfq(items);
  const candidates = (directory.data?.items ?? []).map((c) => ({
    id: c.profile_id,
    name: [c.display_name, c.firm_name].filter(Boolean).join(", ") || c.profile_id,
  }));
  return (
    <PageContainer width="wide">
      <PageHeader title={title} description={t("opsProjectIntro")} />
      <span className="flex flex-wrap gap-4 text-sm">
        <Link href="/rfqs" className="underline underline-offset-4">{t("opsTitle")}</Link>
        <Link href={`/execution/${projectId}`} className="underline underline-offset-4">{getTranslator("Ops")("nav.execution")}</Link>
      </span>
      <section aria-labelledby="project-rfqs" className="flex flex-col gap-3">
        <SectionHeader id="project-rfqs" title={t("opsProjectList")} />
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("opsProjectEmpty")}</p>
        ) : (
          <ul className="flex flex-col gap-2" data-testid="ops-project-rfqs">
            {items.map((r) => (
              <li key={r.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm" data-rfq-state={r.state}>
                <span className="font-medium">{t(`states.${r.state}`)} · {t("created", { when: formatDate(r.created_at) })}</span>
                <span>{t("deadline", { when: r.quotes_due_at ? formatDate(r.quotes_due_at) : t("notSet") })}</span>
                <Link href={`/rfqs/${r.id}`} className="font-medium underline underline-offset-4">{t("open")}</Link>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section aria-labelledby="new-rfq" className="flex flex-col gap-3">
        <SectionHeader id="new-rfq" title={t("opsNew")} />
        {open ? (
          <Notice tone="info" title={t("opsOpenExists")}>
            <Link href={`/rfqs/${open.id}`} className="underline underline-offset-4">{t("open")}</Link>
          </Notice>
        ) : (
          <>
            <form method="get" className="flex flex-col gap-2 sm:flex-row sm:items-end">
              <label className="flex flex-col gap-1 text-sm">
                {t("searchLabel")}
                <Input name="q" defaultValue={q ?? ""} />
              </label>
              <Button type="submit" variant="outline">{t("search")}</Button>
            </form>
            <OpsRequestQuotes projectId={projectId} candidates={candidates} />
          </>
        )}
      </section>
    </PageContainer>
  );
}
