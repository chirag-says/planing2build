import { cn } from "cn";
import {
  ArrowRightIcon,
  BellRingIcon,
  ClipboardCheckIcon,
  MessageSquareTextIcon,
  RefreshCwIcon,
  ReceiptIcon,
  ScaleIcon,
  type LucideIcon,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { actionCopy, activityText, whenText } from "@/components/plan2build/overview";
import { SectionHeader } from "@/components/plan2build/page-header";
import { EmptyState } from "@/components/plan2build/states";
import { Badge } from "@/components/ui/badge";
import { getTranslator } from "@/lib/i18n";
import { dayGroup, type InboxNotification, type NotificationKind } from "@/lib/inbox";
import { getInbox } from "@/lib/inbox-server";
import { loadProject, projectTitle } from "@/lib/project";

export async function generateMetadata({ params }: { params: Promise<{ projectId: string }> }): Promise<Metadata> {
  return {
    title: await projectTitle((await params).projectId, getTranslator("Inbox")("notifications.title")),
  };
}

const KIND_ICON: Record<NotificationKind, LucideIcon> = {
  action: BellRingIcon,
  update: RefreshCwIcon,
  quote: ScaleIcon,
  inspection: ClipboardCheckIcon,
  payment: ReceiptIcon,
  message: MessageSquareTextIcon,
};

function text(item: InboxNotification): string {
  if (item.source.type === "action") return actionCopy(item.source.action).title;
  if (item.source.type === "activity") return activityText(item.source.item);
  return `${item.source.from}: ${item.source.text}`;
}

// The bell's page (lib/inbox.ts, a preview until the API has notifications): what needs the family
// and what changed, by day. Action notifications come from the next actions and updates from the
// dates the API records; only message notifications are samples, and they say so.
export default async function NotificationsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const [detail, inbox] = await Promise.all([loadProject(projectId), getInbox(projectId)]);
  const t = getTranslator("Inbox");
  const base = `/projects/${projectId}`;
  const groups = (["today", "yesterday", "earlier"] as const)
    .map((group) => ({
      group,
      items: inbox.notifications.filter((item) => dayGroup(item.at, inbox.now) === group),
    }))
    .filter((entry) => entry.items.length > 0);

  return (
    <section aria-labelledby="notifications-title" className="flex max-w-3xl flex-col gap-8">
      <SectionHeader
        id="notifications-title"
        title={t("notifications.title")}
        description={t("notifications.intro", { code: detail.project.code })}
      />
      {groups.length === 0 ? (
        <EmptyState icon={BellRingIcon} title={t("notifications.empty")} />
      ) : (
        groups.map(({ group, items }) => (
          <section key={group} aria-labelledby={`day-${group}`} className="flex flex-col gap-2">
            <h3
              id={`day-${group}`}
              className="border-b-2 border-foreground pb-2 font-mono text-xs tracking-widest text-muted-foreground uppercase"
            >
              {t(`notifications.groups.${group}`)}
            </h3>
            <ul className="flex flex-col">
              {items.map((item) => {
                const Icon = KIND_ICON[item.kind];
                return (
                  <li key={item.id} className="border-b border-foreground/12 last:border-b-0">
                    <Link
                      href={`${base}${item.path}`}
                      className="group grid grid-cols-[2.5rem_minmax(0,1fr)_auto] items-center gap-4 rounded-md py-3.5 outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
                    >
                      <span
                        aria-hidden="true"
                        className={cn(
                          "inline-flex size-10 items-center justify-center rounded-md ring-1",
                          item.kind === "action"
                            ? "bg-brand text-brand-foreground ring-foreground"
                            : "bg-card ring-foreground/20",
                        )}
                      >
                        <Icon className="size-4" />
                      </span>
                      <span className="flex min-w-0 flex-col gap-1">
                        <span className="flex flex-wrap items-center gap-2 font-mono text-xs tracking-widest text-muted-foreground uppercase">
                          {t(`notifications.kinds.${item.kind}`)}
                          {item.unread && (
                            <span className="rounded-sm bg-foreground px-1.5 py-0.5 text-background">
                              {t("notifications.new")}
                            </span>
                          )}
                          {item.preview && <Badge variant="outline">{t("preview")}</Badge>}
                        </span>
                        <span className="text-base font-medium text-pretty">{text(item)}</span>
                        <span className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
                          <time dateTime={item.at}>{whenText(item.at, inbox.now)}</time>
                        </span>
                      </span>
                      <ArrowRightIcon
                        aria-hidden="true"
                        className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-foreground"
                      />
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        ))
      )}
    </section>
  );
}
