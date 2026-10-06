// Inspections and findings as the homeowner and the contractor see them (Slice 3.7B): an
// inspection's content only once Plan2Build approves it; reports behind logged links; findings
// in plain language. The contractor also gets the correction form for an open finding.
import type { components } from "@p2b/contracts";

import { RectifyForm } from "@/components/plan2build/assurance";
import { SectionHeader } from "@/components/plan2build/page-header";
import { DownloadLink } from "@/components/plan2build/rfq";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";

type Assurance = components["schemas"]["AssuranceOut"];

export function AssuranceSection({ data, reportBase, engagementId }: {
  data: Assurance; reportBase?: string; engagementId?: string;
}) {
  const t = getTranslator("Assurance");
  return (
    <section aria-labelledby="inspections" className="flex flex-col gap-3">
      <SectionHeader id="inspections" title={t("title")} description={t("intro")} />
      {data.inspections.length === 0 && <p className="text-sm">{t("none")}</p>}
      <ul className="flex flex-col gap-2">
        {data.inspections.map((i) => (
          <li key={i.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm" data-testid="inspection">
            <span className="font-medium">
              {t(`kinds.${i.kind}`)} · {t("inspection", { gate: i.gate, stage: i.stage_name })}
              {i.floor !== null && i.floor !== undefined ? ` (${i.floor})` : ""}
            </span>
            <span data-testid="inspection-state">{t(`states.${i.state}`)}</span>
            {i.auditor_code && <span>{t("auditor", { code: i.auditor_code })} · {formatDate(i.approved_at ?? i.scheduled_at)}</span>}
            {i.outcome && <span data-testid="inspection-outcome">{i.outcome}</span>}
            {reportBase && i.reports.map((r) => (
              <DownloadLink key={r.version} label={t("report", { version: r.version })}
                url={`${reportBase}/${i.id}/reports/${r.version}/url`} />
            ))}
          </li>
        ))}
      </ul>
      <h3 className="text-base font-medium">{t("findings")}</h3>
      {data.findings.length === 0 && <p className="text-sm">{t("noFindings")}</p>}
      <ul className="flex flex-col gap-2">
        {data.findings.map((f) => (
          <li key={f.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm" data-testid="finding">
            <span className="font-medium">{t("inspection", { gate: f.gate, stage: f.stage_name })} · {t(`ncStates.${f.state}`)}</span>
            <span>{t("severity", { value: f.severity })} · {t("due", { date: formatDate(f.due_date) })}
              {f.overdue && ` · ${t("overdue")}`}</span>
            <p>{f.description}</p>
            <p>{t("correction", { text: f.corrective_action })}</p>
            {engagementId && f.state === "OPEN" && <RectifyForm engagementId={engagementId} ncId={f.id} />}
          </li>
        ))}
      </ul>
    </section>
  );
}
