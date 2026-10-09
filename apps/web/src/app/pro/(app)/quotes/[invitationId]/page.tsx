import { ArrowLeftIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { JsonForm, ReasonAction } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { DownloadLink, QuoteAttachmentList, QuoteForm, RespondToInvitation, TextAction } from "@/components/plan2build/rfq";
import { Button } from "@/components/ui/button";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";

export const metadata: Metadata = { title: getTranslator("Rfq")("proTitle") };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// One request to quote (Slice 3.6, functional): the brief before accepting; then the frozen pack,
// the quote form, your versions and the questions you may see. Never another contractor's
// information, Plan2Build's rates or its review of your quote (QD-08, QD-09).
export default async function ProQuotePage({ params }: { params: Promise<{ invitationId: string }> }) {
  const { invitationId } = await params;
  if (!UUID.test(invitationId)) notFound();
  const { data, response } = await (await serverApi()).GET("/api/v1/pro/rfq-invitations/{invitation_id}", {
    params: { path: { invitation_id: invitationId } },
  });
  if (response.status === 401) redirect(`/sign-in?next=%2Fquotes%2F${invitationId}`);
  if (!data) notFound();
  const t = getTranslator("Rfq");
  const base = `/api/v1/pro/rfq-invitations/${invitationId}`;
  const b = data.brief;
  return (
    <PageContainer>
      <Button asChild variant="ghost" className="self-start">
        <Link href="/quotes">
          <ArrowLeftIcon aria-hidden="true" />
          {t("backToQuotes")}
        </Link>
      </Button>
      <PageHeader title={t("proTitle")} description={`${data.state}${data.outcome ? ` · ${data.outcome}` : ""}`} />
      <section aria-labelledby="brief" className="flex flex-col gap-1 text-sm">
        <SectionHeader id="brief" title={t("brief")} />
        <p>{t("locality", { value: b.locality ?? "" })}</p>
        <p>{b.plot_area_sqft} sq ft plot · {b.built_up_area_sqft ?? "-"} sq ft built-up · {b.floors ?? "-"} floors · {b.budget_band ?? ""}</p>
        <p>{t("deadline", { when: data.quotes_due_at ?? t("notSet") })}</p>
        {data.state === "SENT" && data.respond_by && <p>{t("respondBy", { when: data.respond_by })}</p>}
      </section>
      {data.state === "SENT" && <RespondToInvitation invitationId={invitationId} />}
      {data.engagement_id && (
        <Link href={`/engagements/${data.engagement_id}`} className="font-medium underline underline-offset-4">{t("engagement")}</Link>
      )}
      {data.pack && (
        <section aria-labelledby="pack" className="flex flex-col gap-2 text-sm" data-testid="pack">
          <SectionHeader id="pack" title={t("pack")} description={`v${data.pack.build_plan_version_no} · ${data.pack.manifest_sha256}`} />
          <h3 className="font-medium">{t("drawings")}</h3>
          <ul className="flex flex-col gap-1">
            {data.pack.drawings.map((d) => (
              <li key={d.file_id} className="flex items-center gap-2">
                {d.drawing_class} {d.title}
                <DownloadLink label={t("open")} url={`${base}/drawings/${d.file_id}/url`} />
              </li>
            ))}
          </ul>
          <h3 className="font-medium">{t("scope")}</h3>
          <ul>{data.pack.scope.inclusions.concat(data.pack.scope.exclusions, data.pack.scope.assumptions).map((s, n) => <li key={n}>{s}</li>)}</ul>
          <details>
            <summary>{t("specifications")}</summary>
            <ul>{data.pack.specifications.map((s) => <li key={s.code}>{s.code} {s.item}: {s.value ?? s.not_applicable_reason}</li>)}</ul>
          </details>
          <details>
            <summary>{t("schedule")}</summary>
            <ul>{data.pack.schedule.map((s) => <li key={s.entry_key}>{s.stage_name}{s.floor != null ? ` (floor ${s.floor})` : ""}: {s.duration_days ?? "-"}</li>)}</ul>
          </details>
        </section>
      )}
      {data.can_submit && data.pack && (
        <QuoteForm invitationId={invitationId} lines={data.pack.quantities} draft={data.draft} attachmentsMax={data.attachments_max} />
      )}
      {data.versions.length > 0 && (
        <section aria-labelledby="versions" className="flex flex-col gap-2 text-sm">
          <SectionHeader id="versions" title={t("yourVersions")} />
          <ul className="flex flex-col gap-1">
            {data.versions.map((v) => (
              <li key={v.quote.id} className="flex flex-col gap-2">
                <span>v{v.quote.version_no} · {v.quote.kind} · {v.state} · {v.quote.comparable_total} · {v.quote.valid_to}</span>
                <QuoteAttachmentList invitationId={invitationId} files={v.quote.attachments} />
              </li>
            ))}
          </ul>
          {data.can_withdraw && <ReasonAction label={t("withdraw")} url={`${base}/quote/withdraw`} />}
          {data.can_renew && (
            <JsonForm id="renew" label={t("renew")} method="POST" url={`${base}/quote/renew`} once submitLabel={t("renew")}
              initial={JSON.stringify({ valid_from: new Date().toISOString().slice(0, 10), valid_to: "" }, null, 2)} />
          )}
        </section>
      )}
      {data.state === "ACCEPTED" && (
        <section aria-labelledby="questions" className="flex flex-col gap-2 text-sm">
          <SectionHeader id="questions" title={t("questions")} />
          <ul className="flex flex-col gap-2">
            {data.clarifications.map((c) => (
              <li key={c.id} className="flex flex-col gap-1">
                <span>{c.question}{c.yours ? "" : ` (${t("shared")})`}</span>
                {c.answer && <span className="text-muted-foreground">{c.answer}</span>}
                {c.direction === "PLAN2BUILD_ASKS" && c.state === "OPEN" && (
                  <TextAction id={`answer-${c.id}`} label={t("answer")} field="answer" url={`${base}/clarifications/${c.id}/answer`} />
                )}
              </li>
            ))}
          </ul>
          {data.rfq_open && <TextAction id="ask" label={t("ask")} field="question" url={`${base}/clarifications`} />}
        </section>
      )}
    </PageContainer>
  );
}
