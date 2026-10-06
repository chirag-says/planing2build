// One project read per request, shared by the dashboard layout and its pages (React `cache`
// deduplicates within a render). The API decides access: another family's project is a 404.
import type { components } from "@p2b/contracts";
import { notFound } from "next/navigation";
import { cache } from "react";

import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import { requireSignedIn } from "@/lib/session";

export type ProjectDetail = components["schemas"]["ProjectDetail"];
export type ProjectStatus = ProjectDetail["project"]["status"];

export const loadProject = cache(async (projectId: string): Promise<ProjectDetail> => {
  await requireSignedIn(`/projects/${projectId}`);
  const { data, response } = await (await serverApi()).GET("/api/v1/projects/{project_id}", {
    params: { path: { project_id: projectId } },
  });
  if (response.status === 404 || response.status === 422) notFound();
  if (!data) throw new Error("the project could not be loaded");
  return data;
});

/** The dashboard opens on submission (PD-21); only a draft has no dashboard yet. */
export function dashboardOpen(status: ProjectStatus): boolean {
  return status !== "DRAFT";
}

/** Stages and lines exist once the project passed the initial review (created on ACCEPTED). */
export function hasStagesAndLines(status: ProjectStatus): boolean {
  return !["DRAFT", "SUBMITTED", "NEEDS_INFO", "CANCELLED"].includes(status);
}

/** Page title: the area (if any) and the project code (WCAG 2.4.2). Never redirects. */
export async function projectTitle(projectId: string, area?: string): Promise<string> {
  const projects = getTranslator("Projects");
  try {
    const { data } = await (await serverApi()).GET("/api/v1/projects/{project_id}", {
      params: { path: { project_id: projectId } },
    });
    if (!data) return area ?? projects("title");
    const code = projects("code", { code: data.project.code });
    return area ? `${area} · ${code}` : code;
  } catch {
    return area ?? projects("title");
  }
}
