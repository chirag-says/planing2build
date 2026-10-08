// The bell in the top bar: what needs the family and unread messages, counted; it opens the
// project's notifications page (lib/inbox.ts, a preview until the API has notifications).
import { BellIcon } from "lucide-react";
import Link from "next/link";

import { getTranslator } from "@/lib/i18n";

export function NotificationsBell({ href, count }: { href: string; count: number }) {
  const t = getTranslator("Inbox");
  return (
    <Link
      href={href}
      aria-label={t("bellCount", { count })}
      className="relative inline-flex size-11 items-center justify-center rounded-md text-foreground transition-colors outline-none hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <BellIcon aria-hidden="true" className="size-5" />
      {count > 0 && (
        <span
          aria-hidden="true"
          className="absolute top-1 right-1 inline-flex min-w-5 items-center justify-center rounded-sm bg-brand px-1 font-mono text-[0.6875rem] leading-5 font-semibold text-brand-foreground tabular-nums ring-1 ring-foreground"
        >
          {count > 9 ? "9+" : count}
        </span>
      )}
    </Link>
  );
}
