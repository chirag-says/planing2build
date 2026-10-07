import { AppShell } from "@/components/plan2build/app-shell";
import { HeaderNav } from "@/components/plan2build/header-nav";
import { getTranslator } from "@/lib/i18n";
import { isOnboarding, loadProCounts, ownProfileOrNull } from "@/lib/professional";
import { currentUser, initialsOf } from "@/lib/session";

// Professionals host shell (every page but sign-in). Before sign-in, and while the profile is
// still being set up, only the website-style header: there is no work to navigate to yet, and
// onboarding stays one focused screen. Once the profile is complete, the app shell with the
// professional's work and listing (counts of what waits for them beside the links).
export default async function ProLayout({ children }: { children: React.ReactNode }) {
  const t = getTranslator("Pro");
  const shell = getTranslator("Shell");
  const user = await currentUser();
  const own = user ? await ownProfileOrNull() : null;
  if (!user || isOnboarding(own)) {
    return (
      <>
        <HeaderNav brand={t("title")} tag={t("tag")} signedIn={Boolean(user)} links={[]} />
        {/* The website's blueprint ground under every professional screen. */}
        <div className="p2b-ground flex flex-1 flex-col">{children}</div>
      </>
    );
  }
  const counts = await loadProCounts();
  // The name they gave during onboarding (their profile), before the account's own.
  const name = own?.profile.display_name ?? user.display_name;
  return (
    <AppShell
      brand={t("title")}
      tag={t("tag")}
      userName={name}
      initials={initialsOf(name)}
      accountKind={shell("professional")}
      context={
        <p className="flex min-w-0 items-center gap-2.5 font-mono text-sm tracking-widest text-muted-foreground uppercase">
          <span aria-hidden="true" className="size-2 shrink-0 bg-brand ring-1 ring-foreground" />
          <span className="truncate">
            {name ? shell("greeting", { name }) : shell("greetingNoName")}
          </span>
        </p>
      }
      primaryAction={{ href: "/#add", label: t("dashboard.add") }}
      sections={[
        {
          navLabel: getTranslator("Nav")("main"),
          groups: [
            {
              label: shell("groups.work"),
              items: [
                { href: "/", label: t("nav.dashboard"), icon: "overview", exact: true },
                { href: "/connections", label: t("nav.connections"), icon: "requests", count: counts.requests },
                { href: "/quotes", label: t("nav.quotes"), icon: "quoteRequests", count: counts.quotes },
                { href: "/build-plan", label: t("nav.buildPlan"), icon: "buildPlan" },
                { href: "/inspections", label: t("nav.inspections"), icon: "inspections", count: counts.inspections },
              ],
            },
            {
              label: shell("groups.listing"),
              items: [
                { href: "/profile", label: t("nav.profile"), icon: "profile" },
                { href: "/portfolio", label: t("nav.portfolio"), icon: "portfolio" },
              ],
            },
          ],
        },
      ]}
      accountLinks={[
        { href: "/profile", label: t("nav.profile"), icon: "profile" },
        { href: "/portfolio", label: t("nav.portfolio"), icon: "portfolio" },
      ]}
    >
      {children}
    </AppShell>
  );
}
