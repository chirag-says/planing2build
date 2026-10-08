// The notifications for one request (lib/inbox.ts, derived from the API's own records): one clock
// reading, shared by the shell's bell and the pages that list them.
import "server-only";

import { cache } from "react";

import { buildNotifications, unreadCount, type InboxNotification } from "@/lib/inbox";
import { getProjectOverview } from "@/lib/project-overview";

export interface Inbox {
  now: string;
  notifications: InboxNotification[];
  /** For the bell: the next actions that need the family. */
  unread: number;
}

export const getInbox = cache(async (projectId: string): Promise<Inbox> => {
  const overview = await getProjectOverview(projectId);
  const now = new Date().toISOString();
  const notifications = buildNotifications(overview, now);
  return { now, notifications, unread: unreadCount(notifications) };
});
