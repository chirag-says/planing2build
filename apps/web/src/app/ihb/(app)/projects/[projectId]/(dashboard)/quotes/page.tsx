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
        // A request for quotes as the website's site board: an ink bar with its state and deadline,
        // then the invited contractors on ruled rows.
        <article key={rfq.id} className="flex flex-col gap-4 overflow-hidden rounded-lg bg-card pb-4 ring-1 ring-foreground/15" data-rfq-state={rfq.state}>
          <div className="flex flex-wrap items-center justify-between gap-2 bg-foreground px-4 py-3 text-background">
            <h3 className="flex items-center gap-2.5 font-mono text-xs tracking-widest uppercase">
              <span aria-hidden="true" className="size-2 bg-brand" />
              {t("state", { state: rfq.state })}
            </h3>
            <p className="font-mono text-xs tracking-wider uppercase opacity-80">{t("deadline", { when: rfq.quotes_due_at ?? t("notSet") })}</p>
          </div>
          <h4 className="px-4 font-heading text-lg leading-none">{t("contractors")}</h4>
          <ul className="flex flex-col px-4 text-sm">
            {rfq.invitations.map((i) => (
              <li key={i.id} className="border-b border-foreground/10 py-2 last:border-b-0">
                {i.contractor_name ?? i.firm_name} · {i.state} ·{" "}
                {i.latest_quote
                  ? t("quoteStatus", { version: i.latest_quote.version_no, state: i.latest_quote.state, when: i.latest_quote.submitted_at })
                  : t("noQuote")}
              </li>
            ))}
          </ul>
          {!rfq.comparison && <p className="px-4 text-sm text-muted-foreground">{t("pricesLater")}</p>}
          {rfq.can_cancel && (
            <div className="px-4">
              <ActionButton label={t("cancel")} variant="outline" url={`/api/v1/projects/${projectId}/rfqs/${rfq.id}/cancel`} body={{}} />
            </div>
          )}
          {rfq.selection && (
            <div className="px-4">
              <Notice tone="success">{t("selected", { name: rfq.selection.contractor_name ?? "", when: rfq.selection.selected_at })}</Notice>
            </div>
          )}
          {rfq.comparison && (
            <section aria-labelledby={`cmp-${rfq.id}`} className="flex flex-col gap-3 px-4" data-testid="comparison">
              <h4 id={`cmp-${rfq.id}`} className="font-heading text-xl leading-none">{t("comparison", { version: rfq.comparison.version_no })}</h4>
              <p className="text-sm">
                {t("counts", { invited: rfq.comparison.counts.invited, received: rfq.comparison.counts.quotes_received, included: rfq.comparison.counts.included })}
              </p>
              {rfq.comparison.notes.map((n) => <p key={n} className="text-xs text-muted-foreground">{n}</p>)}
              <DownloadLink label={t("download")}
                url={`/api/v1/projects/${projectId}/rfqs/${rfq.id}/comparisons/${rfq.comparison.id}/document`} />
              <div className="grid gap-4 lg:grid-cols-2">
              {rfq.comparison.quotes.map((q) => (
                // A quote sheet (the website's quote audit): gaps priced in brass, the equal-scope
                // total on the brass plate.
                <div key={q.quote_version_id} className="flex flex-col gap-2 overflow-hidden rounded-lg bg-background p-4 ring-1 ring-foreground/20" data-quote={q.quote_version_id}>
                  <h5 className="font-heading text-xl leading-none">{q.contractor_name ?? q.firm_name} · v{q.quote.version_no}</h5>
                  <p className="font-mono text-xs tracking-widest uppercase">{t("adjustments")}</p>
                  {q.adjustments.length === 0 ? (
                    <p className="text-sm text-muted-foreground">{t("noAdjustments")}</p>
                  ) : (
                    <ul className="flex flex-col gap-1 text-sm">
                      {q.adjustments.map((a, n) => <li key={n} className="border-l-4 border-brand pl-2">{a.deviation_type}: {a.description} ({money(a.rupee_impact)})</li>)}
                    </ul>
                  )}
                  <p className="text-sm">{t("submitted", { amount: money(q.quote.comparable_total) })}</p>
                  <p className="text-sm">{t("adjustmentsTotal", { amount: money(q.adjustments_total) })}</p>
                  <p className="self-start bg-brand px-2 py-1 font-heading text-2xl leading-none text-brand-foreground tabular-nums">{t("normalised", { amount: money(q.normalised_total) })}</p>
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
              </div>
            </section>
          )}
        </article>
      ))}
    </section>
  );
}
