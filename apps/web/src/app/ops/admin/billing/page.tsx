import type { Metadata } from "next";
import { notFound } from "next/navigation";

import {
  ConfigDraftForm,
  PricePreview,
  PublishButton,
  ReconcileButton,
} from "@/components/plan2build/ops-billing";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { requireVerifiedStaff } from "@/lib/staff";

export const metadata: Metadata = { title: getTranslator("Ops")("configuration.title") };

const KINDS = ["pricing-rules", "instalment-plans", "tax-configurations", "offerings"] as const;

// Templates show the shape each kind expects; every value in them is a placeholder to replace.
const TEMPLATES: Record<(typeof KINDS)[number] | "eligibility", string> = {
  "pricing-rules": JSON.stringify({ offering_code: "P2B_PACKAGE", rule: { base: "0", adjustments: [] } }, null, 2),
  "instalment-plans": JSON.stringify({ instalments: [
    { share_bp: 5000, due: "ON_ORDER" }, { share_bp: 5000, due: "DAYS_AFTER_ACTIVATION", days: 30 }] }, null, 2),
  "tax-configurations": JSON.stringify({
    legal_name: "", address: "", gstin: "", state_code: "", invoice_series: "",
    prices_include_tax: false,
    lines: { PACKAGE: { sac: "", components: [] }, AI_CREDIT: { sac: "", components: [] } } }, null, 2),
  offerings: JSON.stringify({ offering_code: "P2B_PACKAGE", pricing_rule_version_id: "",
    payment_modes: ["FULL"], instalment_plan_version_id: null, terms_version: "" }, null, 2),
  eligibility: JSON.stringify({ items: [{ id: "item_id", label: "", help: "" }] }, null, 2),
};

// Billing configuration for ADMIN (MFA): versions of each kind, new drafts, publishing, price
// previews, the eligibility checklist and a manual reconciliation. Never an edit in place.
export default async function AdminBillingPage() {
  const staff = await requireVerifiedStaff("/admin/billing");
  if (!staff.roles.includes("ADMIN")) notFound();
  const api = await serverApi();
  const [lists, checklists] = await Promise.all([
    Promise.all(KINDS.map((kind) => api.GET("/api/v1/admin/billing/{kind}", { params: { path: { kind } } }))),
    api.GET("/api/v1/admin/eligibility-checklists"),
  ]);
  const t = getTranslator("Ops");
  return (
    <PageContainer width="wide">
      <PageHeader title={t("configuration.title")} description={t("configuration.intro")} />
      <ReconcileButton />
      {KINDS.map((kind, index) => (
        <section key={kind} aria-labelledby={kind} className="flex flex-col gap-3">
          <SectionHeader id={kind} title={t(`configuration.kinds.${kind}`)} />
          <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <ul className="flex flex-col gap-3">
              {(lists[index].data ?? []).length === 0 && (
                <li className="text-sm text-muted-foreground">{t("configuration.none")}</li>
              )}
              {(lists[index].data ?? []).map((version) => (
                <li key={version.version_id}>
                  <Card size="sm">
                    <CardHeader>
                      <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                        <h3>{t("configuration.version", { version: version.version })}</h3>
                        <Badge variant={version.status === "ACTIVE" ? "success" : "neutral"}>{version.status}</Badge>
                        {version.is_test && <Badge variant="warning">{t("configuration.test")}</Badge>}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-2 text-xs">
                      <p className="break-all font-mono">{version.version_id}</p>
                      <pre
                        tabIndex={0}
                        aria-label={t("configuration.version", { version: version.version })}
                        className="max-h-40 overflow-auto rounded bg-muted p-2"
                      >
                        {JSON.stringify(version.content, null, 2)}
                      </pre>
                      {version.note && <p className="text-muted-foreground">{version.note}</p>}
                      <p className="text-muted-foreground">
                        {formatDate(version.created_at)}
                        {version.published_at && ` · ${formatDate(version.published_at)}`}
                      </p>
                      {version.status === "DRAFT" && <PublishButton kind={kind} versionId={version.version_id} />}
                      {kind === "pricing-rules" && <PricePreview versionId={version.version_id} />}
                    </CardContent>
                  </Card>
                </li>
              ))}
            </ul>
            <Card size="sm">
              <CardHeader><CardTitle className="text-sm"><h3>{t("configuration.create")}</h3></CardTitle></CardHeader>
              <CardContent>
                <ConfigDraftForm kind={kind} template={TEMPLATES[kind]} label={t(`configuration.kinds.${kind}`)} />
              </CardContent>
            </Card>
          </div>
        </section>
      ))}
      <section aria-labelledby="eligibility" className="flex flex-col gap-3">
        <SectionHeader id="eligibility" title={t("configuration.kinds.eligibility")} />
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <ul className="flex flex-col gap-3">
            {(checklists.data ?? []).map((checklist) => (
              <li key={checklist.version_id}>
                <Card size="sm">
                  <CardHeader>
                    <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                      <h3>{t("configuration.version", { version: checklist.version })}</h3>
                      <Badge variant={checklist.status === "ACTIVE" ? "success" : "neutral"}>{checklist.status}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2 text-sm">
                    <ul className="list-disc pl-5">
                      {checklist.items.map((item) => <li key={item.id}>{item.label}</li>)}
                    </ul>
                    {checklist.status === "DRAFT" && <PublishButton kind="eligibility" versionId={checklist.version_id} />}
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
          <Card size="sm">
            <CardHeader><CardTitle className="text-sm"><h3>{t("configuration.create")}</h3></CardTitle></CardHeader>
            <CardContent>
              <ConfigDraftForm kind="eligibility" template={TEMPLATES.eligibility} label={t("configuration.items")} />
            </CardContent>
          </Card>
        </div>
      </section>
    </PageContainer>
  );
}
