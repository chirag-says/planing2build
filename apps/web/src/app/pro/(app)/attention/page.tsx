import { CheckIcon } from "lucide-react";
import type { Metadata } from "next";

import { PageContainer, PageHeader } from "@/components/plan2build/page-header";
import { QueueRow } from "@/components/plan2build/pro-console";
import { getTranslator } from "@/lib/i18n";
import { QUEUE_GROUPS } from "@/lib/pro-console";
import { loadOwnProfile, loadProWork } from "@/lib/professional";

export const metadata: Metadata = { title: getTranslator("Console")("notifications.title") };

// Everything waiting on the professional, in the order Today uses: urgent, respond, review,
// complete. The API has no notification store; what waits on them is the real work across every
// domain (requests, requests to quote, drawings, sign-offs, inspections, findings, handover), so
// this page is that queue in full, and the bell's count is its length. Email carries the actual
// notifications.
export default async function ProAttentionPage() {
  await loadOwnProfile("/attention");
  const { queue } = await loadProWork();
  const t = getTranslator("Console");
  const groups = QUEUE_GROUPS.map((group) => ({ group, items: queue.filter((item) => item.group === group) })).filter(
    (entry) => entry.items.length > 0,
  );
  return (
    <PageContainer width="wide">
      <PageHeader size="compact" title={t("notifications.title")} description={t("notifications.intro")} />
      {groups.length > 0 ? (
        groups.map(({ group, items }) => (
          <section key={group} aria-labelledby={`group-${group}`} className="flex flex-col gap-2">
            <h2
              id={`group-${group}`}
              className="border-b-2 border-foreground pb-2 font-mono text-xs tracking-widest text-muted-foreground uppercase"
            >
              {t(`groups.${group}`)}
            </h2>
            <ul className="flex flex-col">
              {items.map((item) => (
                <QueueRow key={`${item.kind}-${item.id}`} item={item} />
              ))}
            </ul>
          </section>
        ))
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
