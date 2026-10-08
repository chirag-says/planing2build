import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { ReasonAction } from "@/components/plan2build/build-plan";
import { PageContainer, PageHeader, SectionHeader } from "@/components/plan2build/page-header";
import { DownloadLink } from "@/components/plan2build/rfq";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";

export const metadata: Metadata = { title: getTranslator("Rfq")("engagement") };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// An engagement the professional holds, whatever its origin (ADR-024): the family's contact, and
// the plot pin and shared files while it is active (N-08).
export default async function ProEngagementPage({ params }: { params: Promise<{ engagementId: string }> }) {
  const { engagementId } = await params;
  if (!UUID.test(engagementId)) notFound();
  const { data, response } = await (await serverApi()).GET("/api/v1/pro/engagements/{engagement_id}", {
    params: { path: { engagement_id: engagementId } },
  });
  if (response.status === 401) redirect("/sign-in");
  if (!data) notFound();
  const t = getTranslator("Rfq");
  return (
    <PageContainer>
      <PageHeader title={t("engagement")} description={`${data.project_code} · ${data.category_name} · ${data.state}`} />
      <section aria-labelledby="contact" className="flex flex-col gap-1 text-sm" data-testid="family-contact">
        <SectionHeader id="contact" title={t("familyContact")} />
        {data.family_contact && (
          <p>{data.family_contact.name} · {data.family_contact.phone} · {data.family_contact.email ?? ""}</p>
        )}
        {data.location && <p>{t("location")}: {data.location.lat}, {data.location.lng}</p>}
      </section>
      {data.shared_files.length > 0 && (
        <section aria-labelledby="files" className="flex flex-col gap-1 text-sm">
          <SectionHeader id="files" title={t("sharedFiles")} />
          {data.shared_files.map((f) => (
            <DownloadLink key={f.file_id} label={f.file_name} url={`/api/v1/pro/engagements/${engagementId}/files/${f.file_id}/url`} />
          ))}
        </section>
      )}
      {data.state === "ACTIVE" && data.category === "CONTRACTOR" && (
        <Link href={`/engagements/${engagementId}/execution`} className="text-sm font-medium underline underline-offset-4">
          {getTranslator("Execution")("openExecution")}
        </Link>
      )}
      {data.state === "ACTIVE" && <ReasonAction label={t("end")} url={`/api/v1/pro/engagements/${engagementId}/end`} />}
    </PageContainer>
  );
}
