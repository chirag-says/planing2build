// The inbox for one request (lib/inbox.ts, a preview until the API has notifications and
// messages): one clock reading, shared by the shell's bell and the pages that list it.
import "server-only";

import { cache } from "react";

import { buildNotifications, buildThreads, type InboxNotification, type Thread } from "@/lib/inbox";
import { getProjectOverview } from "@/lib/project-overview";
import { site } from "@/marketing/content/site";

export interface Inbox {
  now: string;
  threads: Thread[];
  notifications: InboxNotification[];
  /** For the bell: what needs the family plus unread messages. */
  unread: number;
}

export const getInbox = cache(async (projectId: string): Promise<Inbox> => {
  const overview = await getProjectOverview(projectId);
  const now = new Date().toISOString();
  const threads = buildThreads(overview, { phone: site.phone, email: site.email }, now);
  const notifications = buildNotifications(overview, threads, now);
  return { now, threads, notifications, unread: notifications.filter((item) => item.unread).length };
});
