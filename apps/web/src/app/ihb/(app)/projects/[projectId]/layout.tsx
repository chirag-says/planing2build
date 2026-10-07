import type { ReactNode } from "react";

import { HomeownerShell } from "@/components/plan2build/homeowner-shell";
import { loadProject } from "@/lib/project";

// Every page of one project (the dashboard and the requirement): the shell with the project
// switcher and the project's sections in the sidebar. The layout stays mounted between them.
export default async function ProjectLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const detail = await loadProject(projectId);
  return <HomeownerShell project={detail}>{children}</HomeownerShell>;
}
