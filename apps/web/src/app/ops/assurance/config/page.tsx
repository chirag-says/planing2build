import type { Metadata } from "next";

import { ActionButton, JsonForm } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { TextAction } from "@/components/plan2build/rfq";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Assurance")("config") };

// Auditor appointments (ADMIN appoints and ends, EX-09) and checklist versions (operations draft,
// ADMIN publishes, EX-08). JSON editors are acceptable here (H-06).
export default async function OpsAssuranceConfigPage() {
  const staff = await requireVerifiedStaff("/assurance/config");
  const admin = staff.roles.includes("ADMIN");
  const api = await serverApi();
  const [appointments, checklists] = await Promise.all([
    api.GET("/api/v1/ops/auditor-appointments"),
    api.GET("/api/v1/ops/checklists"),
  ]);
  const t = getTranslator("Assurance");
  return (
    <PageContainer width="wide">
      <PageHeader title={t("config")} />
      <section aria-labelledby="appointments" className="flex flex-col gap-3">
        <SectionHeader id="appointments" title={t("appointments")} />
        <ul className="flex flex-col gap-2 text-sm">
          {(appointments.data ?? []).map((a) => (
            <li key={a.id} className="flex flex-col gap-1 rounded-md border border-border p-3" data-testid="appointment">
              <span className="font-medium">{a.auditor_code} · {a.name} · {a.status}</span>
              <span>{a.qualification}{a.registration_reference ? ` · ${a.registration_reference}` : ""}</span>
              <span className="font-mono text-xs">{a.id}</span>
              {admin && a.status === "ACTIVE" && (
                <TextAction id={`end-${a.id}`} label={t("endAppointment")} field="reason"
                  url={`/api/v1/admin/auditor-appointments/${a.id}/end`} />
              )}
            </li>
          ))}
        </ul>
        {admin && (
          <JsonForm id="appoint" label={t("appoint")} method="POST" url="/api/v1/admin/auditor-appointments" submitLabel={t("send")} once
            initial={JSON.stringify({ name: "", qualification: "", registration_reference: "", account_email: "" }, null, 2)} />
        )}
      </section>
      <section aria-labelledby="checklists" className="flex flex-col gap-3">
        <SectionHeader id="checklists" title={t("checklists")} />
        {(checklists.data ?? []).map((v) => (
          <div key={v.id} className="flex flex-col gap-2 rounded-md border border-border p-3 text-sm" data-testid="checklist">
            <span className="font-medium">v{v.version} · {v.status} · {v.checkpoints.length}</span>
            <span className="font-mono text-xs">{v.id}</span>
            <p className="text-muted-foreground">{v.note}</p>
            {v.status === "DRAFT" && (
              <>
                <JsonForm id={`checkpoints-${v.id}`} label={t("checkpoints")} method="PUT" url={`/api/v1/ops/checklists/${v.id}/checkpoints`}
                  submitLabel={t("send")}
                  initial={JSON.stringify({ checkpoints: v.checkpoints.map(({ gate, sequence, code, text, expected_evidence, is_critical, spec_line_code }) => ({ gate, sequence, code, text, expected_evidence, is_critical, spec_line_code })) }, null, 2)} />
                {admin && <ActionButton label={t("publish")} url={`/api/v1/admin/checklists/${v.id}/publish`} />}
              </>
            )}
          </div>
        ))}
        <JsonForm id="draft" label={t("draft")} method="POST" url="/api/v1/ops/checklists" submitLabel={t("send")} once
          initial={JSON.stringify({ from_version_id: checklists.data?.find((v) => v.status === "PUBLISHED")?.id ?? null, note: "" }, null, 2)} />
      </section>
    </PageContainer>
  );
}
