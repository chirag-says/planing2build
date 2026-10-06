import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ActionButton, JsonForm, ReasonAction } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { DownloadLink, OpsUpload } from "@/components/plan2build/rfq";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("nav.rfqs") };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// One RFQ for operations (Slice 3.6, functional): recipients, deadline and issue; quote versions
// with review and adjustments; staff capture; clarifications; comparison publication; history.
export default async function OpsRfqPage({ params }: { params: Promise<{ rfqId: string }> }) {
  const { rfqId } = await params;
  if (!UUID.test(rfqId)) notFound();
  await requireVerifiedStaff(`/rfqs/${rfqId}`);
  const { data } = await (await serverApi()).GET("/api/v1/ops/rfqs/{rfq_id}", { params: { path: { rfq_id: rfqId } } });
  if (!data) notFound();
  const t = getTranslator("Rfq");
  const ops = `/api/v1/ops/rfqs/${rfqId}`;
  const open = data.state === "DRAFT" || data.state === "ISSUED";
  const capture = JSON.stringify({
    lines: [{ line_no: 1, rate: "0.00" }], valid_from: "", valid_to: "", tax_treatment: "EXCLUSIVE",
    duration_days: 1, evidence_file_id: "",
  }, null, 2);
  return (
    <PageContainer width="wide">
      <PageHeader title={t("project", { code: data.project_code })} description={`${data.state} · ${data.package_state} · ${data.manifest_sha256 ?? ""}`} />
      <p className="text-sm">{t("deadline", { when: data.quotes_due_at ?? t("notSet") })}</p>
      {data.state === "DRAFT" && (
        <div className="flex flex-col gap-3">
          <JsonForm id="deadline" label={t("setDeadline")} method="PUT" url={`${ops}/deadline`} submitLabel={t("send")}
            initial={JSON.stringify({ quotes_due_at: "" }, null, 2)} />
          <ActionButton label={t("issue")} url={`${ops}/issue`} />
        </div>
      )}
      {data.state === "ISSUED" && (
        <JsonForm id="extend" label={t("extend")} method="POST" url={`${ops}/deadline/extend`} once submitLabel={t("send")}
          initial={JSON.stringify({ quotes_due_at: "", reason: "" }, null, 2)} />
      )}
      {open && <ReasonAction label={t("cancel")} url={`${ops}/cancel`} />}

      <section aria-labelledby="invitations" className="flex flex-col gap-2 text-sm">
        <SectionHeader id="invitations" title={t("contractors")} />
        {data.invitations.map((i) => (
          <div key={i.id} className="flex flex-col gap-1 rounded-md border border-border p-2" data-invitation={i.id}>
            <span>{i.contractor_name ?? i.firm_name} · {i.party} · {i.source} · {i.state}{i.decline_reason ? ` · ${i.decline_reason}` : ""}</span>
            {(i.state === "PROPOSED" || i.state === "SENT" || i.state === "ACCEPTED") && (
              <ReasonAction label={t("withdrawInvitation")} url={`/api/v1/ops/rfq-invitations/${i.id}/withdraw`} />
            )}
            {i.state === "ACCEPTED" && data.state === "ISSUED" && (
              <JsonForm id={`capture-${i.id}`} label={t("capture")} method="POST" url={`/api/v1/ops/rfq-invitations/${i.id}/capture`}
                once submitLabel={t("send")} initial={capture} />
            )}
          </div>
        ))}
        {open && (
          <JsonForm id="introduce" label={t("introduce")} method="POST" url={`${ops}/invitations`} once submitLabel={t("send")}
            initial={JSON.stringify({ profile_id: "", reason: "" }, null, 2)} />
        )}
        {open && <OpsUpload projectId={data.project_id} />}
      </section>

      <section aria-labelledby="versions" className="flex flex-col gap-2 text-sm">
        <SectionHeader id="versions" title={t("review")} />
        {data.quote_versions.map((v) => (
          <div key={v.quote.id} className="flex flex-col gap-1 rounded-md border border-border p-2" data-quote={v.quote.id} data-review={v.review_state}>
            <span>v{v.quote.version_no} · {v.quote.kind} · {v.state} · {v.review_state} · {v.quote.comparable_total}{v.quote.captured_by_staff ? " · captured" : ""}</span>
            <ul>{v.quote.lines.map((l) => <li key={l.line_no}>{l.line_no}. {l.excluded ? t("excluded", { reason: l.exclusion_reason ?? "" }) : `${l.rate} = ${l.amount}`}</li>)}</ul>
            {v.quote.attachments.map((f) => <DownloadLink key={f.file_id} label={f.file_name} url={`/api/v1/ops/rfq-files/${f.file_id}/url`} />)}
            {v.state === "SUBMITTED" && (v.review_state === "PENDING" || v.review_state === "NEEDS_CLARIFICATION") && (
              <>
                <JsonForm id={`adj-${v.quote.id}`} label={t("setAdjustments")} method="PUT" wrap="adjustments"
                  url={`/api/v1/ops/quote-versions/${v.quote.id}/adjustments`} submitLabel={t("setAdjustments")}
                  initial={JSON.stringify(v.adjustments.length ? v.adjustments : [], null, 2)} />
                <ActionButton label={t("reviewed")} url={`/api/v1/ops/quote-versions/${v.quote.id}/reviewed`} />
              </>
            )}
          </div>
        ))}
        {data.state === "ISSUED" && <ActionButton label={t("publish")} url={`${ops}/comparisons`} />}
      </section>

      <section aria-labelledby="clarifications" className="flex flex-col gap-2 text-sm">
        <SectionHeader id="clarifications" title={t("questions")} />
        {data.clarifications.map((c) => (
          <div key={c.id} className="flex flex-col gap-1 rounded-md border border-border p-2">
            <span>{c.direction} · {c.state} · {c.question}</span>
            {c.answer && <span className="text-muted-foreground">{c.answer}</span>}
            {c.state === "OPEN" && c.direction === "CONTRACTOR_ASKS" && (
              <JsonForm id={`ans-${c.id}`} label={t("answerQuestion")} method="POST" url={`/api/v1/ops/rfq-clarifications/${c.id}/answer`}
                once submitLabel={t("send")} initial={JSON.stringify({ answer: "", shared_with_all: false }, null, 2)} />
            )}
            {c.state === "OPEN" && <ReasonAction label={t("close")} url={`/api/v1/ops/rfq-clarifications/${c.id}/close`} />}
          </div>
        ))}
        {data.state === "ISSUED" && (
          <JsonForm id="ask" label={t("askContractor")} method="POST" url={`${ops}/clarifications`} once submitLabel={t("send")}
            initial={JSON.stringify({ invitation_id: "", quote_version_id: null, question: "" }, null, 2)} />
        )}
      </section>

      <section aria-labelledby="comparisons" className="flex flex-col gap-2 text-sm">
        <SectionHeader id="comparisons" title={t("comparison", { version: data.comparisons.length })} />
        {data.comparisons.map((c) => (
          <div key={c.id} className="flex items-center gap-2" data-comparison={c.state}>
            v{c.version_no} · {c.state} · {c.counts.included}
            <DownloadLink label={t("download")} url={`/api/v1/ops/rfq-files/${c.document_file_id}/url`} />
          </div>
        ))}
        {data.selection && <p>{t("selected", { name: data.selection.contractor_name ?? "", when: data.selection.selected_at })}</p>}
      </section>

      <details className="text-xs">
        <summary>{t("history")}</summary>
        <ul>{data.history.map((h, n) => <li key={n}>{h.at} {h.subject} {h.from_state ?? "-"} → {h.to_state} ({h.actor_role}) {h.reason ?? ""}</li>)}</ul>
      </details>
    </PageContainer>
  );
}
