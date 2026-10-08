import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AcceptPanel, DownloadButton } from "@/components/plan2build/build-plan";
import { SnapshotView } from "@/components/plan2build/build-plan-view";
import { PackageLock } from "@/components/plan2build/package-lock";
import { Notice } from "@/components/plan2build/states";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { loadProject, projectTitle } from "@/lib/project";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function generateMetadata({ params }: { params: Promise<{ projectId: string }> }): Promise<Metadata> {
  return { title: await projectTitle((await params).projectId, getTranslator("BuildPlan")("title")) };
}

// One issued version for the family: its content, its PDFs, acceptance by one-time code (BP-05).
export default async function BuildPlanVersionPage({
  params,
}: {
  params: Promise<{ projectId: string; versionId: string }>;
}) {
  const { projectId, versionId } = await params;
  if (!UUID.test(versionId)) notFound();
  await loadProject(projectId);
  const api = await serverApi();
  const [snapshot, plan] = await Promise.all([
    api.GET("/api/v1/projects/{project_id}/build-plan/versions/{version_id}", {
      params: { path: { project_id: projectId, version_id: versionId } },
    }),
    api.GET("/api/v1/projects/{project_id}/build-plan", { params: { path: { project_id: projectId } } }),
  ]);
  if (snapshot.response.status === 404 || !snapshot.data || !plan.data) notFound();
  const t = getTranslator("BuildPlan");
  const summary = plan.data.versions.find((v) => v.id === versionId);
  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-wrap gap-2">
        {summary?.issued_document_id && (
          <DownloadButton audience="family" projectId={projectId} fileId={summary.issued_document_id} label={t("downloadIssued")} />
        )}
        {summary?.accepted_document_id && (
          <DownloadButton audience="family" projectId={projectId} fileId={summary.accepted_document_id} label={t("downloadAccepted")} />
        )}
      </div>
      {snapshot.data.version.state === "ACCEPTED" && <Notice tone="success">{t("acceptedNotice")}</Notice>}
      {snapshot.data.version.state === "ISSUED" && plan.data.can_act && plan.data.package_state === "ACTIVE" && (
        <AcceptPanel projectId={projectId} versionId={versionId} />
      )}
      {snapshot.data.version.state === "ISSUED" && plan.data.can_act && plan.data.package_state !== "ACTIVE" && (
        <PackageLock projectId={projectId} reason={t("acceptLocked")} />
      )}
      <SnapshotView view={snapshot.data} />
    </section>
  );
}
