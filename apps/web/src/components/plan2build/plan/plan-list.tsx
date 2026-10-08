// "Your floor plans" on the designs page: the project's concept floor plans with their state, a
// link to each ready one, and the owner's way to ask for a new one. The API answers 404 while the
// feature is off; then nothing shows. Who may generate is the API's answer: `is_owner` from the
// project's execution view, or `editing.can_edit` on a ready plan (owner only, AD-12). Whether
// the AI assistant is on is only exposed on a ready plan (`editing.assistant`); without one the
// panel shows and hides itself when the API answers 404.
import { FloorPlans } from "@/components/plan2build/plan/floor-plans";
import { SectionHeader } from "@/components/plan2build/page-header";
import { serverApi } from "@/lib/api/server";
import { getTranslator } from "@/lib/i18n";
import type { ProjectStatus } from "@/lib/project";

export async function PlanList({ projectId, status }: { projectId: string; status: ProjectStatus }) {
  const api = await serverApi();
  const response = await api.GET("/api/v1/projects/{project_id}/house-plans", {
    params: { path: { project_id: projectId } },
  });
  if (response.response.status === 404 || !response.data) return null;
  const plans = response.data.items;

  const execution = await api
    .GET("/api/v1/projects/{project_id}/execution", { params: { path: { project_id: projectId } } })
    .catch(() => null);
  let isOwner: boolean | null = execution?.data?.is_owner ?? null;
  let assistant: boolean | null = null;
  const ready = plans.find((p) => p.state === "VALID");
  if (ready && isOwner !== false) {
    const detail = await api
      .GET("/api/v1/projects/{project_id}/house-plans/{plan_id}", {
        params: { path: { project_id: projectId, plan_id: ready.plan_id } },
      })
      .catch(() => null);
    const editing = detail?.data?.editing;
    if (editing) {
      isOwner ??= editing.can_edit;
      // for the owner, `assistant` is exactly whether the assistant is on
      if (editing.can_edit) assistant = editing.assistant;
    }
  }

  const t = getTranslator("Plan");
  return (
    <section aria-labelledby="floor-plans" className="flex flex-col gap-4">
      <SectionHeader id="floor-plans" title={t("list.title")} description={t("list.intro")} />
      <FloorPlans
        projectId={projectId}
        status={status}
        initial={plans}
        isOwner={isOwner}
        assistant={assistant}
      />
    </section>
  );
}
