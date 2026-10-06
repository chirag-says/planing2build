// Operations view of a project's needs, requests, engagements and quote reviews (Slice 3.4):
// decline reasons and notes, withdrawal reasons, the family's request contact, and history.
// Withdrawing a request or ending an engagement takes a reason (the API records who and why).
import type { components } from "@p2b/contracts";
import Link from "next/link";

import { DownloadButton } from "@/components/plan2build/download-button";
import { OpsEnd, OpsWithdraw } from "@/components/plan2build/engagements";
import { SectionHeader } from "@/components/plan2build/page-header";
import { StatusBadge } from "@/components/plan2build/status-badge";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

type View = components["schemas"]["OpsEngagementsOut"];

export function OpsEngagements({ view, names }: { view: View; names: Record<string, string> }) {
  const t = getTranslator("Ops");
  const pro = getTranslator("Pro");
  const services = getTranslator("Services");
  const name = (code: string) => names[code] ?? code;
  return (
    <section aria-labelledby="engagements" className="flex flex-col gap-5">
      <SectionHeader
        id="engagements"
        title={t("engagements.title")}
        action={
          <Link href={`/projects/${view.project_id}/build-plan`} className="text-sm underline underline-offset-4">
            {getTranslator("BuildPlan")("title")}
          </Link>
        }
      />

      <section aria-labelledby="ops-needs" className="flex flex-col gap-2">
        <h3 id="ops-needs" className="text-sm font-medium">{t("engagements.needs")}</h3>
        {view.needs.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("engagements.noNeeds")}</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {view.needs.map((need) => (
              <li key={need.category} className="flex items-center gap-1 text-sm">
                {name(need.category)}
                {need.subtypes.length > 0 && ` (${need.subtypes.join(", ")})`}
                <StatusBadge kind="need" status={need.state} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="ops-engaged" className="flex flex-col gap-2">
        <h3 id="ops-engaged" className="text-sm font-medium">{t("engagements.engagements")}</h3>
        {view.engagements.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("engagements.noEngagements")}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {view.engagements.map((e) => (
              <li key={e.id} className="flex flex-col gap-2 py-2 text-sm">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{name(e.category)}: {e.name}</span>
                  <Badge variant="neutral">{e.party === "LISTED" ? t("engagements.listed") : t("engagements.outside")}</Badge>
                  <StatusBadge kind="engagement" status={e.state} />
                </span>
                {e.contact && <span className="break-all text-muted-foreground">{e.contact}</span>}
                {e.ended_at && (
                  <span className="text-muted-foreground">
                    {t("engagements.ended", { date: formatDate(e.ended_at), role: e.ended_by_role ?? "", reason: e.end_reason ?? "" })}
                  </span>
                )}
                {e.state === "ACTIVE" && <OpsEnd engagementId={e.id} />}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="ops-connections" className="flex flex-col gap-2">
        <h3 id="ops-connections" className="text-sm font-medium">{t("engagements.connections")}</h3>
        {view.connections.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("engagements.noConnections")}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {view.connections.map((c) => (
              <li key={c.id} className="flex flex-col gap-1 py-2 text-sm">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{name(c.category)}: {c.professional_name}</span>
                  <StatusBadge kind="connection" status={c.state} />
                </span>
                <span className="text-muted-foreground">
                  {t("engagements.sent", { date: formatDate(c.sent_at), due: formatDate(c.respond_by) })}
                </span>
                <span className="break-all text-muted-foreground">
                  {t("engagements.familyContact", {
                    name: String(c.family_contact.name ?? ""),
                    phone: String(c.family_contact.phone ?? ""),
                  })}
                </span>
                {c.decline_reason && (
                  <span>
                    {t("engagements.declineReason", { reason: pro(`connections.reasons.${c.decline_reason}`) })}
                    {c.decline_note ? `: ${c.decline_note}` : ""}
                  </span>
                )}
                {c.withdraw_reason && (
                  <span>
                    {t("engagements.withdrawReason", {
                      reason: services(`withdrawReasons.${c.withdraw_reason}`),
                      role: c.withdrawn_by_role ?? "",
                    })}
                    {c.withdraw_note ? ` ${c.withdraw_note}` : ""}
                  </span>
                )}
                {c.state === "SENT" && <OpsWithdraw connectionId={c.id} />}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="ops-quotes" className="flex flex-col gap-2">
        <h3 id="ops-quotes" className="text-sm font-medium">{t("engagements.quotes")}</h3>
        {view.quote_reviews.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("engagements.noQuotes")}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {view.quote_reviews.map((q) => (
              <li key={q.id} className="flex flex-col gap-2 py-2 text-sm">
                <span className="font-medium">
                  {name(q.category)} · {t("engagements.quotedBy", { name: q.quoted_by })} · {formatDate(q.submitted_at)}
                </span>
                {q.note && <span className="whitespace-pre-line">{q.note}</span>}
                <span className="flex flex-wrap gap-2">
                  {q.file_ids.map((fileId, index) => (
                    <DownloadButton key={fileId} fileId={fileId} name={t("engagements.file", { index: index + 1 })} staff />
                  ))}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {view.history.length > 0 && (
        <section aria-labelledby="ops-history" className="flex flex-col gap-2">
          <h3 id="ops-history" className="text-sm font-medium">{t("engagements.history")}</h3>
          <ol className="flex flex-col gap-1 text-sm">
            {view.history.map((h, index) => (
              <li key={`${h.subject_id}-${h.to_state}-${index}`} className="text-muted-foreground">
                {formatDate(h.at)} · {name(h.category)} · {h.subject} {h.from_state ?? "NEW"} → {h.to_state} ·{" "}
                {t("engagements.by", { role: h.actor_role })}
                {h.reason ? ` · ${h.reason}` : ""}
              </li>
            ))}
          </ol>
        </section>
      )}
    </section>
  );
}
