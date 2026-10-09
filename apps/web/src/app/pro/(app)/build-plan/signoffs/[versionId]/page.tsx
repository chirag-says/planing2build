import { ArrowLeftIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { DownloadButton, RevokeSignoff, SignPanel } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { serverApi } from "@/lib/api/server";
import { formatDateTime } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { revokeEffect } from "@/lib/signoff";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const metadata: Metadata = { title: getTranslator("BuildPlan")("signTitle") };

// Structural sign-off of one version (BP-04): the lines as entered, the drawings, the statement,
// signing with a one-time code, and your sign-offs on this version with revoking where the API
// allows it (BP-20).
export default async function SignoffPage({ params }: { params: Promise<{ versionId: string }> }) {
  const { versionId } = await params;
  if (!UUID.test(versionId)) notFound();
  const { data, response } = await (await serverApi()).GET("/api/v1/pro/build-plan/signoffs/{version_id}", {
    params: { path: { version_id: versionId } },
  });
  if (response.status === 401) redirect(`/sign-in?next=${encodeURIComponent(`/build-plan/signoffs/${versionId}`)}`);
  if (!data) notFound();
  const t = getTranslator("BuildPlan");
  const unsigned = data.lines.filter((l) => !l.signed).map((l) => l.code);
  return (
    <PageContainer>
      <Button asChild variant="ghost" className="self-start">
        <Link href="/build-plan">
          <ArrowLeftIcon aria-hidden="true" />
          {t("backToList")}
        </Link>
      </Button>
      <PageHeader title={t("signTitle")} description={`${data.project_code}: ${t("version", { number: data.version_no })}`} />
      <p className="text-sm text-muted-foreground">{t("signIntro")}</p>
      <p className="break-all font-mono text-xs">{t("contentHash")}: {data.content_hash}</p>
      {data.statement_text && (
        <Notice tone="info" title={t("statement", { number: data.statement_version ?? 0 })}>{data.statement_text}</Notice>
      )}
      <ul className="flex flex-col gap-2 text-sm">
        {data.lines.map((line) => (
          <li key={line.code} className="flex flex-col">
            <span className="font-medium">{line.code} {line.item}{line.signed ? ` (${t("signed")})` : ""}</span>
            <span className="text-muted-foreground">{t("criteria")}: {line.criteria}</span>
            <span>
              {t("projectValue")}:{" "}
              {line.applicability === "APPLICABLE" ? line.value : t("notApplicable", { reason: line.not_applicable_reason ?? "" })}
            </span>
          </li>
        ))}
      </ul>
      <ul className="flex flex-col gap-1 text-sm">
        {data.drawings.map((d) => (
          <li key={d.id} className="flex flex-wrap items-center gap-2">
            {t(`classes.${d.drawing_class}`)}: {d.title}
            <DownloadButton audience="pro" projectId="" fileId={d.file_id} label={t("download")} />
          </li>
        ))}
      </ul>
      {!data.verified && <Notice tone="warning">{t("notVerified")}</Notice>}
      {data.verified && data.state === "IN_REVIEW" && unsigned.length > 0 && (
        <SignPanel versionId={versionId} codes={unsigned} />
      )}
      <section aria-labelledby="my-signoffs" className="flex flex-col gap-3">
        <SectionHeader id="my-signoffs" title={t("revoke.mine")} description={t("revoke.intro")} />
        {data.my_signoffs.length === 0 && <p className="text-sm text-muted-foreground">{t("revoke.none")}</p>}
        <ul className="flex flex-col gap-2">
          {data.my_signoffs.map((s) => {
            const effect = revokeEffect(s, data.state);
            return (
              <li key={s.id} className="flex flex-col gap-2 rounded-md border border-border p-3 text-sm" data-testid="my-signoff">
                <span className="font-medium">
                  {s.line_code} · {s.state === "SIGNED" ? t("revoke.stateSigned") : t("revoke.stateVoid")}
                </span>
                <span className="text-muted-foreground">
                  {s.engineer_name}{s.engineer_firm ? `, ${s.engineer_firm}` : ""}
                  {s.signed_at ? ` · ${t("revoke.signedAt", { when: formatDateTime(s.signed_at) })}` : ""}
                </span>
                {s.void_reason && <span>{t("revoke.voidReason", { reason: s.void_reason })}</span>}
                {effect && <RevokeSignoff signoffId={s.id} lineCode={s.line_code} afterIssue={effect === "afterIssue"} />}
              </li>
            );
          })}
        </ul>
      </section>
    </PageContainer>
  );
}
