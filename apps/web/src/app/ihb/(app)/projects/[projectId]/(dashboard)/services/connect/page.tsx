import { ArrowLeftIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { ConnectionRequestForm } from "@/components/plan2build/engagements";
import { SectionHeader } from "@/components/plan2build/page-header";
import { Notice } from "@/components/plan2build/states";
import { Button } from "@/components/ui/button";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, loadProject, projectTitle } from "@/lib/project";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const CODE = /^[A-Z_]{1,40}$/;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  const area = getTranslator("Services")("connect.title");
  return { title: await projectTitle((await params).projectId, area) };
}

// The request screen (Slice 3.4): what the professional will see and when, the family's contact
// (shared only on acceptance, N-08), and the reason when a request cannot be sent now.
export default async function ConnectPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ category?: string; profile?: string }>;
}) {
  const { projectId } = await params;
  const { category, profile } = await searchParams;
  if (!category || !profile || !CODE.test(category) || !UUID.test(profile)) notFound();
  const { project } = await loadProject(projectId);
  if (!dashboardOpen(project.status)) redirect(`/projects/${projectId}`);
  const { data: target, response } = await (await serverApi()).GET(
    "/api/v1/projects/{project_id}/connection-target",
    { params: { path: { project_id: projectId }, query: { category, profile_id: profile } } },
  );
  if (response.status === 404) notFound();
  if (!target) throw new Error("the request screen could not be loaded");
  const t = getTranslator("Services");
  const name = target.professional_name ?? target.firm_name ?? "";
  const blocked = target.blocked;
  const back = `/professionals/${profile}?project=${projectId}&category=${category}`;

  return (
    <section aria-labelledby="connect" className="flex flex-col gap-6">
      <Button asChild variant="ghost" className="self-start">
        <Link href={back}>
          <ArrowLeftIcon aria-hidden="true" />
          {t("connect.back")}
        </Link>
      </Button>
      <SectionHeader
        id="connect"
        title={t("connect.title")}
        description={`${name} · ${target.category_name}`}
      />
      <p className="text-muted-foreground">{t("connect.intro", { name })}</p>
      {blocked ? (
        <Notice tone="info" title={t("connect.blocked")}>
          <p>{t(`errors.${blocked as "ENGAGED"}`)}</p>
          {blocked === "PACKAGE_REQUIRED" ? (
            <Link href={`/projects/${projectId}/package`} className="font-medium underline underline-offset-4">
              {t("packageLink")}
            </Link>
          ) : (
            <Link href={`/projects/${projectId}/services#${category}`} className="font-medium underline underline-offset-4">
              {t("connect.viewServices")}
            </Link>
          )}
        </Notice>
      ) : (
        <ConnectionRequestForm
          projectId={projectId}
          category={category}
          profileId={profile}
          defaultName={target.contact_name}
          hours={target.response_hours}
        />
      )}
    </section>
  );
}
