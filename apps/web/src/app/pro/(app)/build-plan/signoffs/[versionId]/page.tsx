import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { DownloadButton, SignPanel } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireOnboarded } from "@/lib/professional";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const metadata: Metadata = { title: getTranslator("BuildPlan")("signTitle") };

// Structural sign-off of one version (BP-04): the lines as entered, the drawings, the statement,
// and signing with a one-time code.
export default async function SignoffPage({ params }: { params: Promise<{ versionId: string }> }) {
  await requireOnboarded();
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
    </PageContainer>
  );
}
