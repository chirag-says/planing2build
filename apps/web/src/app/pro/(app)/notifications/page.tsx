import { CheckIcon } from "lucide-react";
import type { Metadata } from "next";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { QueueRow } from "@/components/plan2build/pro-console";
import { getTranslator } from "@/lib/i18n";
import { loadOwnProfile, loadProWork } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Console")("notifications.title") };

// Everything waiting on the professional, most urgent first. The API has no notification store;
// what waits on them is the real work queue (requests, requests to quote, inspections), so this
// page is that queue in full, and the bell's count is its length.
export default async function ProNotificationsPage() {
  await loadOwnProfile("/notifications");
  const { queue } = await loadProWork();
  const t = getTranslator("Console");
  return (
    <PageContainer width="wide">
      <PageHeader size="compact" title={t("notifications.title")} description={t("notifications.intro")} />
      {queue.length > 0 ? (
        <ul className="flex flex-col border-t-2 border-foreground">
          {queue.map((item) => (
            <QueueRow key={`${item.kind}-${item.id}`} item={item} />
          ))}
        </ul>
      ) : (
        <div className="flex items-center gap-4 border-y border-foreground/15 py-6">
          <span aria-hidden="true" className="grid size-10 shrink-0 place-items-center bg-brand text-brand-foreground ring-1 ring-foreground">
            <CheckIcon className="size-5" strokeWidth={2.5} />
          </span>
          <div className="flex flex-col gap-0.5">
            <p className="font-heading text-2xl leading-none">{t("notifications.empty")}</p>
            <p className="text-base text-muted-foreground">{t("notifications.emptyBody")}</p>
          </div>
        </div>
      )}
    </PageContainer>
  );
}
