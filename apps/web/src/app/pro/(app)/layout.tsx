import { BellIcon } from "lucide-react";
import Link from "next/link";

import { AppShell } from "@/components/plan2build/app-shell";
import { HeaderNav } from "@/components/plan2build/header-nav";
import { getTranslator } from "@/lib/i18n";
import { loadProCounts, ownProfileOrNull } from "@/lib/professional";
import { currentUser, initialsOf } from "@/lib/session";

// Professionals host shell (every page but sign-in). Before sign-in (or when the profile cannot be
// loaded), only the website-style header. Signed in, the app shell in two groups: the work (what
// brings and delivers projects, with brass counts of what waits) above their presence (profile,
// services, portfolio), which reads quieter. The bell counts everything waiting on them.
export default async function ProLayout({ children }: { children: React.ReactNode }) {
  const t = getTranslator("Pro");
  const c = getTranslator("Console");
  const shell = getTranslator("Shell");
  const user = await currentUser();
  const own = user ? await ownProfileOrNull() : null;
  if (!user || !own) {
    return (
      <>
        <HeaderNav brand={t("title")} tag={t("tag")} signedIn={Boolean(user)} links={[]} />
        {/* The website's blueprint ground under every professional screen. */}
        <div className="p2b-ground flex flex-1 flex-col">{children}</div>
      </>
    );
  }
  const counts = await loadProCounts();
  const waiting = counts.requests + counts.quotes + counts.inspections + counts.findings;
  // The name they gave during onboarding (their profile), before the account's own.
  const name = own?.profile.display_name ?? user.display_name;
  const firm = own?.profile.firm_name;
  // Under their name in the header: the firm, else the trade they are building a listing for.
  const subtitle = firm ?? own?.categories[0]?.name ?? null;
  const bell = (
    <Link
      href="/notifications"
      aria-label={c("notifications.count", { count: waiting })}
      className="relative inline-flex size-11 items-center justify-center rounded-md border-2 border-foreground/15 bg-card outline-none transition-colors hover:border-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <BellIcon aria-hidden="true" className="size-5" strokeWidth={2} />
      {waiting > 0 && (
        <span
          aria-hidden="true"
          className="absolute -top-1.5 -right-1.5 grid min-w-5 place-items-center bg-brand px-1 py-0.5 font-mono text-[0.6875rem] leading-none font-semibold text-brand-foreground tabular-nums ring-1 ring-foreground"
        >
          {waiting > 99 ? "99+" : waiting}
        </span>
      )}
    </Link>
  );
  return (
    <AppShell
      brand={t("title")}
      tag={t("tag")}
      userName={name}
      initials={initialsOf(name)}
      accountSubtitle={subtitle}
      accountKind={shell("professional")}
      context={
        <p className="flex min-w-0 items-center gap-2.5 font-mono text-sm tracking-widest text-muted-foreground uppercase">
          <span aria-hidden="true" className="size-2 shrink-0 bg-brand ring-1 ring-foreground" />
          <span className="truncate">{firm ?? (name ? shell("greeting", { name }) : shell("greetingNoName"))}</span>
        </p>
      }
      headerActions={bell}
      sections={[
        {
          navLabel: getTranslator("Nav")("main"),
          groups: [
            {
              label: c("nav.work"),
              items: [
                { href: "/", label: c("nav.today"), icon: "overview", exact: true },
                { href: "/connections", label: c("nav.requests"), icon: "requests", count: counts.requests },
                { href: "/quotes", label: c("nav.rfqs"), icon: "quoteRequests", count: counts.quotes },
                { href: "/projects", label: c("nav.projects"), icon: "construction" },
                ...(counts.auditor
                  ? [{ href: "/inspections", label: c("nav.inspections"), icon: "inspections" as const, count: counts.inspections }]
                  : []),
                { href: "/build-plan", label: c("nav.drawings"), icon: "buildPlan" },
              ],
            },
            {
              label: c("nav.presence"),
              quiet: true,
              items: [
                { href: "/profile", label: c("nav.profile"), icon: "profile" },
                { href: "/services", label: c("nav.services"), icon: "specification" },
                { href: "/portfolio", label: c("nav.portfolio"), icon: "portfolio" },
              ],
            },
          ],
        },
      ]}
      accountLinks={[
        { href: "/profile", label: t("nav.profile"), icon: "profile" },
        { href: "/services", label: c("nav.services"), icon: "specification" },
        { href: "/portfolio", label: t("nav.portfolio"), icon: "portfolio" },
      ]}
    >
      {children}
    </AppShell>
  );
}
