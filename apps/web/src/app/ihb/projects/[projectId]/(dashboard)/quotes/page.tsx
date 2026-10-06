import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ActionButton } from "@/components/plan2build/build-plan";
import { SectionHeader } from "@/components/plan2build/page-header";
import { DownloadLink, RequestQuotes, SelectQuote } from "@/components/plan2build/rfq";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({ params }: { params: Promise<{ projectId: string }> }): Promise<Metadata> {
  return { title: await projectTitle((await params).projectId, getTranslator("Rfq")("title")) };
}

const money = (value: string) => `INR ${Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;

// Contractor quotes for the family (Slice 3.6, functional): the request, its status without
// prices until Plan2Build publishes the comparison (QD-07), the neutral comparison with the
// adjustment list first (QD-11), and the selection with a one-time code (QD-12).
export default async function QuotesPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ q?: string }>;
}) {
  const { projectId } = await params;
  const q = ((await searchParams).q ?? "").slice(0, 80) || undefined;
  const { project } = await loadProject(projectId);
  if (!dashboardOpen(project.status)) redirect(`/projects/${projectId}`);
  const api = await serverApi();
  const [view, directory] = await Promise.all([
    api.GET("/api/v1/projects/{project_id}/rfqs", { params: { path: { project_id: projectId } } }),
    api.GET("/api/v1/public/professionals", { params: { query: { category: "CONTRACTOR", q } } }),
  ]);
  if (!view.data) throw new Error("the quotes could not be loaded");
  const t = getTranslator("Rfq");
  const data = view.data;
  const candidates = (directory.data?.items ?? []).map((c) => ({
    id: c.profile_id,
    name: [c.display_name, c.firm_name].filter(Boolean).join(", ") || c.profile_id,
  }));
  return (
    <section aria-labelledby="quotes" className="flex flex-col gap-6">
      <SectionHeader id="quotes" title={t("title")} description={t("intro")} />
      {data.accepted_build_plan_version_no == null ? (
        <Notice tone="info">{t("noBaseline")}</Notice>
      ) : (
        <p className="text-sm">{t("baseline", { version: data.accepted_build_plan_version_no })}</p>
      )}
      {data.engaged_contractor && <Notice tone="info">{t("engaged", { name: data.engaged_contractor })}</Notice>}
      {data.can_request && !data.engaged_contractor && (
        <form method="get" className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <label className="flex flex-col gap-1 text-sm">
            {t("searchLabel")}
            <Input name="q" defaultValue={q ?? ""} />
          </label>
          <Button type="submit" variant="outline">{t("search")}</Button>
        </form>
      )}
      {data.can_request && (
        <RequestQuotes projectId={projectId} candidates={candidates} max={data.max_recipients}
          engaged={Boolean(data.engaged_contractor)} />
      )}
      {data.rfqs.map((rfq) => (
        <article key={rfq.id} className="flex flex-col gap-3 rounded-md border border-border p-3" data-rfq-state={rfq.state}>
          <h3 className="font-medium">{t("state", { state: rfq.state })}</h3>
          <p className="text-sm">{t("deadline", { when: rfq.quotes_due_at ?? t("notSet") })}</p>
          <h4 className="text-sm font-medium">{t("contractors")}</h4>
          <ul className="flex flex-col gap-1 text-sm">
            {rfq.invitations.map((i) => (
              <li key={i.id}>
                {i.contractor_name ?? i.firm_name} · {i.state} ·{" "}
                {i.latest_quote
                  ? t("quoteStatus", { version: i.latest_quote.version_no, state: i.latest_quote.state, when: i.latest_quote.submitted_at })
                  : t("noQuote")}
              </li>
            ))}
          </ul>
          {!rfq.comparison && <p className="text-sm text-muted-foreground">{t("pricesLater")}</p>}
          {rfq.can_cancel && (
            <ActionButton label={t("cancel")} variant="outline" url={`/api/v1/projects/${projectId}/rfqs/${rfq.id}/cancel`} body={{}} />
          )}
          {rfq.selection && (
            <Notice tone="success">{t("selected", { name: rfq.selection.contractor_name ?? "", when: rfq.selection.selected_at })}</Notice>
          )}
          {rfq.comparison && (
            <section aria-labelledby={`cmp-${rfq.id}`} className="flex flex-col gap-3" data-testid="comparison">
              <h4 id={`cmp-${rfq.id}`} className="font-medium">{t("comparison", { version: rfq.comparison.version_no })}</h4>
              <p className="text-sm">
                {t("counts", { invited: rfq.comparison.counts.invited, received: rfq.comparison.counts.quotes_received, included: rfq.comparison.counts.included })}
              </p>
              {rfq.comparison.notes.map((n) => <p key={n} className="text-xs text-muted-foreground">{n}</p>)}
              <DownloadLink label={t("download")}
                url={`/api/v1/projects/${projectId}/rfqs/${rfq.id}/comparisons/${rfq.comparison.id}/document`} />
              {rfq.comparison.quotes.map((q) => (
                <div key={q.quote_version_id} className="flex flex-col gap-2 rounded-md border border-border p-3" data-quote={q.quote_version_id}>
                  <h5 className="font-medium">{q.contractor_name ?? q.firm_name} · v{q.quote.version_no}</h5>
                  <p className="text-sm font-medium">{t("adjustments")}</p>
                  {q.adjustments.length === 0 ? (
                    <p className="text-sm text-muted-foreground">{t("noAdjustments")}</p>
                  ) : (
                    <ul className="text-sm">
                      {q.adjustments.map((a, n) => <li key={n}>{a.deviation_type}: {a.description} ({money(a.rupee_impact)})</li>)}
                    </ul>
                  )}
                  <p className="text-sm">{t("submitted", { amount: money(q.quote.comparable_total) })}</p>
                  <p className="text-sm">{t("adjustmentsTotal", { amount: money(q.adjustments_total) })}</p>
                  <p className="text-sm font-medium">{t("normalised", { amount: money(q.normalised_total) })}</p>
                  {Number(q.quote.additional_total) > 0 && <p className="text-sm">{t("additional", { amount: money(q.quote.additional_total) })}</p>}
                  <p className="text-sm">
                    {t("validity", { from: q.quote.valid_from, to: q.quote.valid_to })} · {t("tax", { treatment: q.quote.tax_treatment })} · {t("duration", { days: q.quote.duration_days })}
                  </p>
                  <details>
                    <summary className="text-sm">{t("lines")}</summary>
                    <ul className="text-sm">
                      {q.quote.lines.map((l) => (
                        <li key={l.line_no}>
                          {l.line_no}. {l.description}: {l.excluded ? t("excluded", { reason: l.exclusion_reason ?? "" }) : money(l.amount ?? "0")}
                        </li>
                      ))}
                    </ul>
                  </details>
                  {q.quote.payment_terms && <p className="text-sm">{t("paymentTerms")}: {q.quote.payment_terms}</p>}
                  {rfq.can_select && <SelectQuote projectId={projectId} rfqId={rfq.id} quoteVersionId={q.quote_version_id} />}
                </div>
              ))}
            </section>
          )}
        </article>
      ))}
    </section>
  );
}
