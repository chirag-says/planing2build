import type { Metadata } from "next";
import Link from "next/link";

import { JsonForm } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("nav.assurance") };

// The assurance queue (Slice 3.7B, functional): gate stages to inspect, open inspections (an
// exception after the configured days, EX-12), submissions to approve, corrections to re-inspect
// and findings past due (EX-23). Nothing here sends anything to anyone.
export default async function OpsAssurancePage() {
  await requireVerifiedStaff("/assurance");
  const { data } = await (await serverApi()).GET("/api/v1/ops/assurance");
  const t = getTranslator("Assurance");
  const project = (id: string, code: string) => (
    <Link href={`/assurance/${id}`} className="underline underline-offset-4">{t("project", { code })}</Link>
  );
  return (
    <PageContainer width="wide">
      <PageHeader title={t("opsTitle")} description={t("opsIntro", { days: data?.inspection_open_days ?? 0 })} />
      <Link href="/assurance/config" className="text-sm font-medium underline underline-offset-4">{t("config")}</Link>
      <section aria-labelledby="to-schedule" className="flex flex-col gap-2">
        <SectionHeader id="to-schedule" title={t("toSchedule")} />
        {(data?.to_schedule ?? []).map((s) => (
          <div key={s.stage_instance_id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm" data-testid="to-schedule">
            <span>{project(s.project_id, s.project_code)} · {t("inspection", { gate: s.gate, stage: s.stage_name })}</span>
            <JsonForm id={`schedule-${s.stage_instance_id}`} label={t("schedule")} method="POST"
              url={`/api/v1/ops/stages/${s.stage_instance_id}/inspections`} submitLabel={t("send")} once
              initial={JSON.stringify({ appointment_id: "", visit_note: "" }, null, 2)} />
          </div>
        ))}
      </section>
      {([["open-inspections", t("openInspections"), data?.open_inspections], ["to-approve", t("toApprove"), data?.to_approve]] as const).map(([id, title, items]) => (
        <section key={id} aria-labelledby={id} className="flex flex-col gap-2">
          <SectionHeader id={id} title={title} />
          <ul className="flex flex-col gap-1 text-sm">
            {(items ?? []).map((i) => (
              <li key={i.inspection_id} data-testid={id}>
                {project(i.project_id, i.project_code)} · {t("inspection", { gate: i.gate, stage: i.stage_name })} · {t(`states.${i.state}`)} · {formatDate(i.scheduled_at)}
                {i.exception && <span className="ml-2 text-destructive">{t("exception")}</span>}
              </li>
            ))}
          </ul>
        </section>
      ))}
      {([["rectified", t("rectifiedList"), data?.rectified], ["overdue", t("overdueList"), data?.overdue]] as const).map(([id, title, items]) => (
        <section key={id} aria-labelledby={id} className="flex flex-col gap-2">
          <SectionHeader id={id} title={title} />
          <ul className="flex flex-col gap-1 text-sm">
            {(items ?? []).map((f) => (
              <li key={f.nc_id} data-testid={id}>
                {project(f.project_id, f.project_code)} · {t("inspection", { gate: f.gate, stage: f.stage_name })} · {t(`ncStates.${f.state}`)} · {t("due", { date: formatDate(f.due_date) })}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </PageContainer>
  );
}
