import { FileIcon } from "lucide-react";
import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { DownloadButton } from "@/components/plan2build/download-button";
import { FileRow } from "@/components/plan2build/file-row";
import { SectionHeader } from "@/components/plan2build/page-header";
import { EmptyState } from "@/components/plan2build/states";
import { Card, CardContent } from "@/components/ui/card";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { dashboardOpen, loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  const area = getTranslator("Dashboard")("areas.documents");
  return { title: await projectTitle((await params).projectId, area) };
}

// The files attached to the project (requirement uploads for now); downloads are logged.
export default async function ProjectDocumentsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const { project } = await loadProject(projectId);
  if (!dashboardOpen(project.status)) redirect(`/projects/${projectId}`);
  const { data: files } = await (await serverApi()).GET("/api/v1/projects/{project_id}/files", {
    params: { path: { project_id: projectId } },
  });
  if (!files) throw new Error("the files could not be loaded");
  const t = getTranslator("Dashboard");
  const projects = getTranslator("Projects");
  return (
    <section aria-labelledby="documents" className="flex flex-col gap-4">
      <SectionHeader
        id="documents"
        title={t("documentsTitle")}
        description={projects("fileCount", { count: files.length })}
      />
      {files.length === 0 ? (
        <EmptyState icon={FileIcon} title={projects("noFiles")} />
      ) : (
        <Card size="sm">
          <CardContent>
            <ul className="divide-y divide-border">
              {files.map((file) => (
                <li key={file.file_id}>
                  <FileRow
                    name={file.file_name}
                    mime={file.content_type}
                    size={file.size_bytes}
                    state={file.state}
                    actions={
                      file.state === "AVAILABLE" && (
                        <DownloadButton fileId={file.file_id} name={file.file_name} />
                      )
                    }
                  />
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </section>
  );
}
