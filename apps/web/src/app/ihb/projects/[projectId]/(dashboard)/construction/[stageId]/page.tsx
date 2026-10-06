import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { SectionHeader } from "@/components/plan2build/page-header";
import { DownloadLink } from "@/components/plan2build/rfq";
import { serverApi } from "@/lib/api/server";
import { formatDate } from "@/lib/format";
import { getTranslator } from "@/lib/i18n";
import { projectTitle } from "@/lib/project";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<Metadata> {
  const area = getTranslator("Dashboard")("areas.construction");
  return { title: await projectTitle((await params).projectId, area) };
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// One stage's updates, newest first, with the contractor who posted each one (EX-19) and the
// photos behind logged links. A photo's capture time is the device's claim (EX-22).
export default async function StageUpdatesPage({
  params,
}: {
  params: Promise<{ projectId: string; stageId: string }>;
}) {
  const { projectId, stageId } = await params;
  if (!UUID.test(stageId)) notFound();
  const { data } = await (await serverApi()).GET("/api/v1/projects/{project_id}/stages/{stage_id}/updates", {
    params: { path: { project_id: projectId, stage_id: stageId } },
  });
  if (!data) notFound();
  const t = getTranslator("Execution");
  return (
    <section aria-labelledby="updates" className="flex flex-col gap-4">
      <SectionHeader id="updates" title={t("updatesTitle", { stage: `${data.stage.stage_number}. ${data.stage.name}` })}
        description={t(`states.${data.stage.state}`)} />
      <Link href={`/projects/${projectId}/construction`} className="text-sm underline underline-offset-4">{t("back")}</Link>
      {data.updates.length === 0 && <p className="text-sm">{t("noUpdates")}</p>}
      <ol className="flex flex-col gap-3">
        {data.updates.map((u) => (
          <li key={u.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-sm" data-testid="update">
            <span className="font-medium">
              {t(`kinds.${u.kind}`)} · {formatDate(u.posted_at)} · {u.contractor_name ?? ""}
              {u.entered_by_operations && ` · ${t("enteredByOps")}`}
            </span>
            {u.corrects_update_id && <span className="text-muted-foreground">{t("corrects")}</span>}
            <p className="whitespace-pre-wrap">{u.note}</p>
            {u.materials && <p>{t("materials", { text: u.materials })}</p>}
            {u.open_problems && <p>{t("openProblems", { text: u.open_problems })}</p>}
            <span className="flex flex-wrap gap-2">
              {u.photos.map((p, n) => (
                <span key={p.file_id} className="flex flex-col gap-1">
                  <DownloadLink label={t("photo", { n: n + 1 })}
                    url={`/api/v1/projects/${projectId}/stages/${stageId}/files/${p.file_id}/url`} />
                  {p.captured_at && <span className="text-xs text-muted-foreground">{t("captured", { at: p.captured_at })}</span>}
                </span>
              ))}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
