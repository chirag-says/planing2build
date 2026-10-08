import { cn } from "cn";
import { MessageSquareTextIcon, PhoneIcon } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { MessageComposer } from "@/components/plan2build/message-composer";
import { contactHref, whenText } from "@/components/plan2build/overview";
import { SectionHeader } from "@/components/plan2build/page-header";
import { EmptyState, Notice } from "@/components/plan2build/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getTranslator } from "@/lib/i18n";
import { getInbox } from "@/lib/inbox-server";
import { loadProject, projectTitle } from "@/lib/project";
import { initialsOf } from "@/lib/session";

export async function generateMetadata({ params }: { params: Promise<{ projectId: string }> }): Promise<Metadata> {
  return {
    title: await projectTitle((await params).projectId, getTranslator("Inbox")("messages.title")),
  };
}

// The overview's "Message" (lib/inbox.ts). PREVIEW: the API has no messaging yet (OQ-025), so the
// threads are samples and nothing is sent; every screen says so, and the call is one tap away.
export default async function MessagesPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ to?: string | string[] }>;
}) {
  const [{ projectId }, { to }] = await Promise.all([params, searchParams]);
  const [detail, inbox] = await Promise.all([loadProject(projectId), getInbox(projectId)]);
  const t = getTranslator("Inbox");
  const base = `/projects/${projectId}`;
  const threads = inbox.threads;
  const active = threads.find((thread) => thread.id === to) ?? threads[0] ?? null;
  const phone = active ? contactHref(active.phone) : null;

  return (
    <section aria-labelledby="messages-title" className="flex flex-col gap-6">
      <SectionHeader
        id="messages-title"
        title={t("messages.title")}
        description={t("messages.intro", { code: detail.project.code })}
        action={<Badge variant="outline">{t("preview")}</Badge>}
      />
      <Notice tone="info">
        <p>{t("previewNote")}</p>
      </Notice>
      {!active ? (
        <EmptyState icon={MessageSquareTextIcon} title={t("messages.empty")} />
      ) : (
        <div className="grid overflow-hidden rounded-lg bg-card ring-1 ring-foreground/15 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
          <nav aria-label={t("messages.choose")} className="border-b border-foreground/12 lg:border-r lg:border-b-0">
            <ul className="flex flex-col">
              {threads.map((thread) => {
                const current = thread.id === active.id;
                const last = thread.messages[thread.messages.length - 1];
                return (
                  <li key={thread.id} className="border-b border-foreground/12 last:border-b-0">
                    <Link
                      href={`${base}/messages?to=${thread.id}`}
                      aria-current={current ? "page" : undefined}
                      className={cn(
                        "grid grid-cols-[2.5rem_minmax(0,1fr)] items-center gap-3 px-4 py-3 outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                        current ? "bg-foreground text-background" : "hover:bg-foreground/5",
                      )}
                    >
                      <span
                        aria-hidden="true"
                        className={cn(
                          "inline-flex size-10 items-center justify-center rounded-md font-mono text-xs font-semibold ring-1",
                          current ? "bg-brand text-brand-foreground ring-background" : "bg-muted ring-foreground/20",
                        )}
                      >
                        {thread.id === "plan2build" ? "P2B" : (initialsOf(thread.name) ?? "·")}
                      </span>
                      <span className="flex min-w-0 flex-col">
                        <span className="flex items-center justify-between gap-2">
                          <span className="truncate font-semibold">{thread.name}</span>
                          {thread.unread > 0 && !current && (
                            <span aria-hidden="true" className="size-2 shrink-0 bg-brand ring-1 ring-foreground" />
                          )}
                        </span>
                        <span
                          className={cn("truncate text-sm", current ? "text-background/80" : "text-muted-foreground")}
                        >
                          {thread.role}
                          {last && ` · ${last.text}`}
                        </span>
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="flex min-w-0 flex-col">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-foreground/12 px-5 py-4">
              <div className="flex min-w-0 flex-col">
                <h3 className="text-lg font-semibold">{active.name}</h3>
                <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase">{active.role}</p>
              </div>
              {phone && (
                <Button asChild variant="outline" size="sm">
                  <a href={phone.href}>
                    <PhoneIcon aria-hidden="true" data-icon="inline-start" />
                    {getTranslator("Overview")("team.call")}
                  </a>
                </Button>
              )}
            </div>
            <ol className="flex flex-col gap-3 px-5 py-5">
              {active.messages.map((message) => (
                <li
                  key={message.id}
                  className={cn(
                    "flex max-w-[34rem] flex-col gap-1 rounded-lg px-4 py-3",
                    message.from === "me"
                      ? "self-end bg-foreground text-background"
                      : "self-start bg-background ring-1 ring-foreground/15",
                  )}
                >
                  <p className="text-base text-pretty">{message.text}</p>
                  <p className="font-mono text-[0.6875rem] tracking-widest text-muted-foreground uppercase">
                    <time dateTime={message.at}>{whenText(message.at, inbox.now)}</time>
                  </p>
                </li>
              ))}
            </ol>
            <div className="mt-auto border-t border-foreground/12 px-5 py-4">
              <MessageComposer name={active.name} phoneHref={phone?.kind === "phone" ? phone.href : null} />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
