import { ScrollTextIcon } from "lucide-react";
import type { Metadata } from "next";

import { ConfirmAction } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { AcknowledgementStatementForm } from "@/components/plan2build/records";
import { EmptyState, Notice } from "@/components/plan2build/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Records")("ops.statementsTitle") };

const STATUS_TONE: Record<string, "success" | "info" | "neutral"> = { ACTIVE: "success", DRAFT: "info" };
const KNOWN = ["DRAFT", "ACTIVE", "RETIRED"] as const;

// The statement the owner reads when acknowledging a handover (Slice 3.7C). Staff read every
// version; ADMIN drafts a new version and activates it, which retires the active one.
export default async function AcknowledgementStatementsPage() {
  const staff = await requireVerifiedStaff("/admin/acknowledgement-statements");
  const admin = staff.roles.includes("ADMIN");
  const t = getTranslator("Records");
  const { data, error } = await (await serverApi()).GET("/api/v1/ops/acknowledgement-statements");
  const statements = [...(data ?? [])].reverse();
  const label = (status: string) =>
    (KNOWN as readonly string[]).includes(status) ? t(`ops.statementStates.${status as (typeof KNOWN)[number]}`) : status;
  return (
    <PageContainer width="wide">
      <PageHeader title={t("ops.statementsTitle")} description={t("ops.statementsIntro")} />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section aria-labelledby="versions" className="flex flex-col gap-3">
          <SectionHeader id="versions" title={t("ops.statementVersions")} />
          {!data ? (
            <Notice tone="error" title={t("ops.loadError")}>{error?.error?.message}</Notice>
          ) : statements.length === 0 ? (
            <EmptyState icon={ScrollTextIcon} title={t("ops.noStatements")} />
          ) : (
            <ul className="flex flex-col gap-3">
              {statements.map((s) => (
                <li key={s.id} data-testid="acknowledgement-statement">
                  <Card size="sm">
                    <CardHeader>
                      <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                        <h3>{t("ops.statementVersion", { version: s.version })}</h3>
                        <Badge variant={STATUS_TONE[s.status] ?? "neutral"}>{label(s.status)}</Badge>
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-2 text-sm">
                      <blockquote className="border-l-2 border-border pl-3 whitespace-pre-line">{s.text}</blockquote>
                      <p className="text-muted-foreground">{s.note}</p>
                      {admin && s.status === "DRAFT" && (
                        <ConfirmAction id={`activate-${s.id}`} label={t("ops.activate")}
                          url={`/api/v1/admin/acknowledgement-statements/${s.id}/activate`}
                          title={t("ops.activateTitle", { version: s.version })} description={t("ops.activateBody")}
                          variant="default" />
                      )}
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </section>
        {admin ? (
          <Card size="sm">
            <CardHeader><CardTitle className="text-sm"><h2>{t("ops.newStatement")}</h2></CardTitle></CardHeader>
            <CardContent>
              <AcknowledgementStatementForm />
            </CardContent>
          </Card>
        ) : (
          <Notice tone="info">{t("ops.adminOnly")}</Notice>
        )}
      </div>
    </PageContainer>
  );
}
